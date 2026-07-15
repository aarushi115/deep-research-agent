"""Node implementations for the Deep Research Agent graph.

Each function takes (a slice of) the graph state and returns a partial
state update dict, per LangGraph convention.
"""

from langgraph.types import interrupt

from src.config import get_settings
from src.llm import call_structured, call_text
from src.logging_config import get_logger
from src.state import (
    CritiqueResult,
    ResearcherInput,
    ResearchReport,
    ResearchState,
    SubQuestionList,
    SubResearchResult,
)
from src.tools import search_web

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = (
    "You are a meticulous research planner. Given a user's research query, "
    "break it into 3 to 5 focused, non-overlapping sub-questions that together "
    "give a complete picture. Each sub-question must be independently "
    "researchable via web search."
)

CRITIQUE_SYSTEM_PROMPT = (
    "You are a skeptical research editor. Review the collected findings against "
    "the original query and decide if they are sufficient to write a complete, "
    "well-supported report. Flag specific missing angles, unanswered questions, "
    "or contradictions as gaps. Be strict: only mark sufficient if a reader's "
    "obvious follow-up questions are already answered."
)

SYNTHESIS_SYSTEM_PROMPT = (
    "You are a senior research analyst writing a highly detailed, long-form final report. "
    "Write comprehensively, exploring all angles of the topic. Each section should span "
    "multiple detailed paragraphs. Cite specific claims to their source URLs, and be honest "
    "about open questions that remain unanswered."
)


def plan_research(state: ResearchState) -> dict:
    """Produce (or refine) the list of research sub-questions.

    On the first pass this decomposes the original query. On a replan
    (triggered by the critique loop) it also incorporates the critique's
    gaps so the next round targets what was missing.
    """
    critique = state.get("critique")
    is_replan = critique is not None and not critique.sufficient

    if is_replan:
        gaps_text = "\n".join(f"- {gap}" for gap in critique.gaps) or "- (no specific gaps listed)"
        prompt = (
            f"Original query: {state['original_query']}\n\n"
            f"A previous research pass had these gaps:\n{gaps_text}\n\n"
            "Produce a refined list of 3 to 5 sub-questions that specifically "
            "close these gaps. You may reuse a prior sub-question if it is still relevant."
        )
        logger.info("Replanning research to address %d gap(s)", len(critique.gaps))
    else:
        prompt = f"Research query: {state['original_query']}"
        logger.info("Planning initial research for query: %s", state["original_query"])

    result = call_structured(prompt, SubQuestionList, system=PLANNER_SYSTEM_PROMPT)
    return {
        "sub_questions": result.sub_questions,
        "status_message": f"Planned {len(result.sub_questions)} sub-question(s).",
    }


def human_approval(state: ResearchState) -> dict:
    """Pause for human approval of the research plan, if HITL is enabled.

    Uses LangGraph's `interrupt()` to suspend execution. The graph resumes
    when the caller sends a `Command(resume=...)` with the human's decision.
    """
    if not state.get("hitl_enabled", True):
        return {"human_approved": True, "status_message": "HITL disabled; auto-approved plan."}

    decision = interrupt(
        {
            "type": "approval_request",
            "sub_questions": [sq.model_dump() for sq in state["sub_questions"]],
        }
    )
    approved = bool(decision.get("approved", True))
    feedback = (decision.get("feedback") or "").strip()

    update: dict = {"human_approved": approved}
    if not approved:
        gaps = [feedback] if feedback else ["Reviewer rejected the plan; broaden or adjust the sub-questions."]
        update["critique"] = CritiqueResult(sufficient=False, gaps=gaps)
        update["status_message"] = "Plan rejected by reviewer; replanning."
    else:
        update["status_message"] = "Plan approved by reviewer."
    return update


def researcher_node(state: ResearcherInput) -> dict:
    """Research a single sub-question: search the web, then summarize.

    Runs as one of N parallel branches fanned out via the `Send` API.
    Failures are caught and returned as a `SubResearchResult` with an
    `error` field so one bad branch doesn't crash the whole run.
    """
    question = state["question"]
    try:
        sources = search_web(question)
        if not sources:
            summary = "No search results were found for this sub-question."
            return {
                "research_results": [
                    SubResearchResult(question=question, summary=summary, sources=[], error="no_results")
                ]
            }

        sources_text = "\n\n".join(
            f"Source: {s.title} ({s.url})\n{s.snippet}" for s in sources
        )
        prompt = (
            f"Original research query: {state['original_query']}\n"
            f"Sub-question: {question}\n"
            f"Why it matters: {state['rationale']}\n\n"
            f"Search results:\n{sources_text}\n\n"
            "Write a detailed, comprehensive summary (at least 3-4 paragraphs) answering the "
            "sub-question using only the search results above. Include all relevant facts, "
            "statistics, and nuances. Do not invent information not present in the sources."
        )
        summary = call_text(prompt)
        logger.info("Researched sub-question: %s", question)
        return {
            "research_results": [
                SubResearchResult(question=question, summary=summary, sources=sources)
            ]
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Researcher branch failed for %r: %s", question, exc)
        return {
            "research_results": [
                SubResearchResult(
                    question=question,
                    summary=f"Research failed for this sub-question: {exc}",
                    sources=[],
                    error=str(exc),
                )
            ]
        }





def critique_node(state: ResearchState) -> dict:
    """Reflect on aggregated findings and judge whether they're sufficient."""
    findings_text = "\n\n".join(
        f"Q: {r.question}\nA: {r.summary}" for r in state["research_results"]
    )
    prompt = (
        f"Original query: {state['original_query']}\n\n"
        f"Collected findings:\n{findings_text}\n\n"
        "Judge whether these findings are sufficient to write a complete report."
    )
    result = call_structured(prompt, CritiqueResult, system=CRITIQUE_SYSTEM_PROMPT)
    logger.info("Critique: sufficient=%s, gaps=%s", result.sufficient, result.gaps)
    
    update = {
        "critique": result,
        "status_message": "Findings sufficient." if result.sufficient else f"Found {len(result.gaps)} gap(s).",
    }
    if not result.sufficient:
        update["retry_count"] = state["retry_count"] + 1
        
    return update


def route_after_critique(state: ResearchState) -> str:
    """Decide whether to loop back to planning or move to synthesis."""
    settings = get_settings()
    critique = state["critique"]
    if critique.sufficient:
        return "synthesize_report"
    if state["retry_count"] >= settings.max_research_retries:
        logger.info("Max research retries reached; synthesizing with current findings.")
        return "synthesize_report"
    return "plan_research"




def synthesize_report(state: ResearchState) -> dict:
    """Produce the final structured, cited research report."""
    findings_text = "\n\n".join(
        f"Sub-question: {r.question}\n"
        f"Summary: {r.summary}\n"
        f"Sources: {', '.join(s.url for s in r.sources) or 'none'}"
        for r in state["research_results"]
    )
    open_gaps = state["critique"].gaps if state.get("critique") else []
    prompt = (
        f"Original query: {state['original_query']}\n\n"
        f"Research findings:\n{findings_text}\n\n"
        f"Known open gaps: {', '.join(open_gaps) or 'none'}\n\n"
        "Write the final research report in extreme detail. Each section must be long-form "
        "and comprehensive (at least 3-5 paragraphs per section), thoroughly covering all findings. "
        "Every claim in the sections must cite one of the source URLs above via the citations list. "
        "List any remaining open questions honestly."
    )
    report = call_structured(prompt, ResearchReport, system=SYNTHESIS_SYSTEM_PROMPT)
    logger.info("Synthesized final report: %s", report.title)
    return {"final_report": report, "status_message": "Report complete."}
