"""Assembles the Deep Research Agent as a compiled LangGraph StateGraph.

Flow:
    START -> plan_research -> human_approval
          -> [rejected]  -> plan_research (replan)
          -> [approved]  -> Send() fan-out -> researcher (parallel, N branches)
          -> aggregate_findings (fan-in) -> critique_node
          -> [insufficient, retries left] -> increment_retry -> plan_research
          -> [sufficient or retries exhausted] -> synthesize_report -> END
"""

from functools import lru_cache

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from src.logging_config import get_logger
from src.nodes import (
    critique_node,
    human_approval,
    plan_research,
    researcher_node,
    route_after_critique,
    synthesize_report,
)
from src.state import ResearchState

logger = get_logger(__name__)


def route_after_approval(state: ResearchState):
    """After human_approval: fan out to parallel researchers, or replan.

    Returning a list of `Send` objects triggers LangGraph's dynamic
    parallel fan-out — one branch per sub-question, sized at runtime.
    """
    if not state.get("human_approved", True):
        return "plan_research"

    return [
        Send(
            "researcher",
            {
                "question": sq.question,
                "rationale": sq.rationale,
                "original_query": state["original_query"],
            },
        )
        for sq in state["sub_questions"]
    ]


def build_graph():
    """Construct and compile the research graph with in-memory checkpointing."""
    graph = StateGraph(ResearchState)

    graph.add_node("plan_research", plan_research)
    graph.add_node("human_approval", human_approval)
    graph.add_node("researcher", researcher_node)
    graph.add_node("critique_node", critique_node)
    graph.add_node("synthesize_report", synthesize_report)

    graph.add_edge(START, "plan_research")
    graph.add_edge("plan_research", "human_approval")

    graph.add_conditional_edges(
        "human_approval",
        route_after_approval,
        ["researcher", "plan_research"],
    )

    graph.add_edge("researcher", "critique_node")

    graph.add_conditional_edges(
        "critique_node",
        route_after_critique,
        {"plan_research": "plan_research", "synthesize_report": "synthesize_report"},
    )

    graph.add_edge("synthesize_report", END)

    checkpointer = MemorySaver()
    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("Research graph compiled.")
    return compiled


@lru_cache
def get_graph():
    """Return a process-wide singleton compiled graph instance."""
    return build_graph()


def initial_state(query: str, hitl_enabled: bool = True) -> ResearchState:
    """Build the initial state dict for a new research run."""
    return {
        "original_query": query,
        "hitl_enabled": hitl_enabled,
        "sub_questions": [],
        "research_results": [],
        "critique": None,
        "retry_count": 0,
        "human_approved": False,
        "final_report": None,
        "status_message": "Starting research...",
    }
