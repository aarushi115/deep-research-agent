"""FastAPI backend for the Deep Research Agent.

Exposes endpoints to start a research job, poll its status, and approve
or reject the research plan when human-in-the-loop is enabled. Long-running
graph execution happens in background asyncio tasks; the frontend polls
`/api/research/{thread_id}` for progress.
"""

import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command

from backend.job_store import job_store
from backend.schemas import (
    ApprovalRequest,
    StartResearchRequest,
    StartResearchResponse,
    StatusResponse,
)
from src.config import get_settings
from src.graph import get_graph, initial_state
from src.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

app = FastAPI(title="Deep Research Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _config_for(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


async def _sync_status_from_graph(thread_id: str) -> None:
    """Inspect the graph's checkpointed state and update the job store.

    Determines whether the graph is paused on an interrupt, finished, or
    still running, and mirrors the relevant state into `JobStore` so the
    HTTP layer never has to touch LangGraph internals directly.
    """
    graph = get_graph()
    config = _config_for(thread_id)
    snapshot = graph.get_state(config)

    sub_questions = [sq.model_dump() for sq in snapshot.values.get("sub_questions", [])]
    research_results = [r.model_dump() for r in snapshot.values.get("research_results", [])]
    retry_count = snapshot.values.get("retry_count", 0)
    status_message = snapshot.values.get("status_message", "")

    if snapshot.next:
        # Graph is paused. Check whether it's paused on our interrupt.
        interrupted = False
        for task in snapshot.tasks:
            if task.interrupts:
                interrupted = True
                break
        status = "waiting_approval" if interrupted else "running"
        await job_store.update(
            thread_id,
            status=status,
            status_message=status_message,
            sub_questions=sub_questions,
            research_results=research_results,
            retry_count=retry_count,
        )
        return

    final_report = snapshot.values.get("final_report")
    if final_report is not None:
        await job_store.update(
            thread_id,
            status="completed",
            status_message="Report complete.",
            sub_questions=sub_questions,
            research_results=research_results,
            retry_count=retry_count,
            report=final_report.model_dump(),
        )
    else:
        await job_store.update(
            thread_id,
            status="error",
            status_message=status_message,
            error="Graph finished without producing a report.",
        )


async def _run_graph(thread_id: str, query: str, hitl_enabled: bool) -> None:
    """Background task: run the graph from the start until it pauses or finishes."""
    graph = get_graph()
    config = _config_for(thread_id)
    try:
        await graph.ainvoke(initial_state(query, hitl_enabled), config=config)
        await _sync_status_from_graph(thread_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Research job %s failed", thread_id)
        await job_store.update(thread_id, status="error", error=str(exc))


async def _resume_graph(thread_id: str, approved: bool, feedback: str) -> None:
    """Background task: resume a paused graph after a human decision."""
    graph = get_graph()
    config = _config_for(thread_id)
    try:
        await graph.ainvoke(
            Command(resume={"approved": approved, "feedback": feedback}),
            config=config,
        )
        await _sync_status_from_graph(thread_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Resuming research job %s failed", thread_id)
        await job_store.update(thread_id, status="error", error=str(exc))


@app.post("/api/research", response_model=StartResearchResponse)
async def start_research(payload: StartResearchRequest) -> StartResearchResponse:
    """Kick off a new research job and return its thread_id immediately."""
    thread_id = str(uuid.uuid4())
    await job_store.create(thread_id)

    import asyncio

    asyncio.create_task(_run_graph(thread_id, payload.query, payload.hitl_enabled))
    logger.info("Started research job %s for query: %s", thread_id, payload.query)
    return StartResearchResponse(thread_id=thread_id, status="running")


@app.get("/api/research/{thread_id}", response_model=StatusResponse)
async def get_status(thread_id: str) -> StatusResponse:
    """Poll the current status of a research job."""
    record = await job_store.get(thread_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown thread_id")
    return StatusResponse(
        thread_id=record.thread_id,
        status=record.status,
        status_message=record.status_message,
        sub_questions=record.sub_questions,
        research_results=record.research_results,
        retry_count=record.retry_count,
        report=record.report,
        error=record.error,
    )


@app.post("/api/research/{thread_id}/approve", response_model=StatusResponse)
async def approve_research(thread_id: str, payload: ApprovalRequest) -> StatusResponse:
    """Approve or reject the pending research plan, resuming the graph."""
    record = await job_store.get(thread_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown thread_id")
    if record.status != "waiting_approval":
        raise HTTPException(status_code=409, detail="Job is not waiting for approval")

    await job_store.update(thread_id, status="running", status_message="Resuming after review...")

    import asyncio

    asyncio.create_task(_resume_graph(thread_id, payload.approved, payload.feedback))
    return StatusResponse(thread_id=thread_id, status="running", status_message="Resuming after review...")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


# Serve the static frontend last so /api routes take precedence.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
