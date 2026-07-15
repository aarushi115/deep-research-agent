"""End-to-end graph test exercising the full plan -> approve -> research ->
critique -> synthesize flow, including the human-in-the-loop interrupt/resume
cycle. All LLM and search calls are mocked so this runs offline.
"""

import uuid
from unittest.mock import patch

from langgraph.types import Command

from src.graph import build_graph, initial_state
from src.state import (
    CritiqueResult,
    ResearchReport,
    ReportSection,
    SourceSnippet,
    SubQuestion,
    SubQuestionList,
)


def _run_config():
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


@patch("src.nodes.call_text")
@patch("src.nodes.search_web")
@patch("src.nodes.call_structured")
def test_full_run_with_hitl_approval(mock_structured, mock_search, mock_text):
    # Planner call, then critique call, then synthesis call, in sequence.
    mock_structured.side_effect = [
        SubQuestionList(
            sub_questions=[
                SubQuestion(question="Q1?", rationale="r1"),
                SubQuestion(question="Q2?", rationale="r2"),
            ]
        ),
        CritiqueResult(sufficient=True, gaps=[]),
        ResearchReport(
            title="Final Report",
            executive_summary="Summary.",
            sections=[ReportSection(heading="Section 1", body="Body.")],
            citations=[],
            open_questions=[],
        ),
    ]
    mock_search.return_value = [SourceSnippet(url="https://x.com", title="X", snippet="content")]
    mock_text.return_value = "A summary of the sub-question findings."

    graph = build_graph()
    config = _run_config()

    result = graph.invoke(initial_state("Test query", hitl_enabled=True), config=config)

    # Graph should be paused awaiting human approval.
    snapshot = graph.get_state(config)
    assert snapshot.next  # not finished
    assert any(task.interrupts for task in snapshot.tasks)

    # Approve and resume.
    result = graph.invoke(Command(resume={"approved": True, "feedback": ""}), config=config)

    assert result["final_report"] is not None
    assert result["final_report"].title == "Final Report"
    assert len(result["research_results"]) == 2


@patch("src.nodes.call_text")
@patch("src.nodes.search_web")
@patch("src.nodes.call_structured")
def test_hitl_disabled_runs_without_pausing(mock_structured, mock_search, mock_text):
    mock_structured.side_effect = [
        SubQuestionList(sub_questions=[SubQuestion(question="Q1?", rationale="r1")]),
        CritiqueResult(sufficient=True, gaps=[]),
        ResearchReport(
            title="Auto Report",
            executive_summary="Summary.",
            sections=[ReportSection(heading="S", body="B")],
            citations=[],
            open_questions=[],
        ),
    ]
    mock_search.return_value = [SourceSnippet(url="https://x.com", title="X", snippet="c")]
    mock_text.return_value = "Summary text."

    graph = build_graph()
    config = _run_config()
    result = graph.invoke(initial_state("Test query", hitl_enabled=False), config=config)

    assert result["final_report"].title == "Auto Report"


@patch("src.nodes.call_text")
@patch("src.nodes.search_web")
@patch("src.nodes.call_structured")
def test_critique_loop_retries_then_synthesizes(mock_structured, mock_search, mock_text):
    # First plan -> insufficient critique -> second (refined) plan -> sufficient critique -> synthesis
    mock_structured.side_effect = [
        SubQuestionList(sub_questions=[SubQuestion(question="Q1?", rationale="r1")]),
        CritiqueResult(sufficient=False, gaps=["missing detail"]),
        SubQuestionList(sub_questions=[SubQuestion(question="Q1 refined?", rationale="r1b")]),
        CritiqueResult(sufficient=True, gaps=[]),
        ResearchReport(
            title="Refined Report",
            executive_summary="Summary.",
            sections=[ReportSection(heading="S", body="B")],
            citations=[],
            open_questions=[],
        ),
    ]
    mock_search.return_value = [SourceSnippet(url="https://x.com", title="X", snippet="c")]
    mock_text.return_value = "Summary text."

    graph = build_graph()
    config = _run_config()
    result = graph.invoke(initial_state("Test query", hitl_enabled=False), config=config)

    assert result["final_report"].title == "Refined Report"
    assert result["retry_count"] == 1
