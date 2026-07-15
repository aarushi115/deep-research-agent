"""Unit tests for individual node functions.

LLM and search calls are mocked so tests run offline, fast, and without
requiring API keys.
"""

from unittest.mock import patch

from src.nodes import (
    critique_node,
    plan_research,
    researcher_node,
    route_after_critique,
    synthesize_report,
)
from src.state import (
    CritiqueResult,
    ResearchReport,
    ReportSection,
    SourceSnippet,
    SubQuestion,
    SubQuestionList,
    SubResearchResult,
)


def make_state(**overrides):
    base = {
        "original_query": "How does LangGraph handle parallel execution?",
        "hitl_enabled": True,
        "sub_questions": [],
        "research_results": [],
        "critique": None,
        "retry_count": 0,
        "human_approved": False,
        "final_report": None,
        "status_message": "",
    }
    base.update(overrides)
    return base


class TestPlanResearch:
    @patch("src.nodes.call_structured")
    def test_initial_plan(self, mock_call):
        mock_call.return_value = SubQuestionList(
            sub_questions=[
                SubQuestion(question="What is the Send API?", rationale="Core to fan-out."),
                SubQuestion(question="How does checkpointing work?", rationale="Enables resumability."),
            ]
        )
        state = make_state()
        result = plan_research(state)

        assert len(result["sub_questions"]) == 2
        assert "Planned 2" in result["status_message"]
        mock_call.assert_called_once()

    @patch("src.nodes.call_structured")
    def test_replan_incorporates_gaps(self, mock_call):
        mock_call.return_value = SubQuestionList(
            sub_questions=[SubQuestion(question="Refined question?", rationale="Closes gap.")]
        )
        state = make_state(critique=CritiqueResult(sufficient=False, gaps=["Missing pricing info"]))
        plan_research(state)

        prompt_arg = mock_call.call_args[0][0]
        assert "Missing pricing info" in prompt_arg


class TestResearcherNode:
    @patch("src.nodes.call_text")
    @patch("src.nodes.search_web")
    def test_success(self, mock_search, mock_text):
        mock_search.return_value = [
            SourceSnippet(url="https://example.com", title="Example", snippet="Some content")
        ]
        mock_text.return_value = "A concise summary of findings."

        payload = {
            "question": "What is X?",
            "rationale": "Because Y.",
            "original_query": "Overall query",
        }
        result = researcher_node(payload)

        results = result["research_results"]
        assert len(results) == 1
        assert results[0].error is None
        assert results[0].summary == "A concise summary of findings."

    @patch("src.nodes.search_web")
    def test_no_results_handled_gracefully(self, mock_search):
        mock_search.return_value = []
        payload = {"question": "Obscure question", "rationale": "r", "original_query": "q"}
        result = researcher_node(payload)

        assert result["research_results"][0].error == "no_results"

    @patch("src.nodes.search_web")
    def test_search_exception_is_caught(self, mock_search):
        mock_search.side_effect = RuntimeError("network down")
        payload = {"question": "Q", "rationale": "r", "original_query": "q"}
        result = researcher_node(payload)

        assert result["research_results"][0].error is not None
        assert "network down" in result["research_results"][0].summary




class TestCritiqueNode:
    @patch("src.nodes.call_structured")
    def test_sufficient(self, mock_call):
        mock_call.return_value = CritiqueResult(sufficient=True, gaps=[])
        state = make_state(
            research_results=[SubResearchResult(question="q", summary="s", sources=[])]
        )
        result = critique_node(state)
        assert result["critique"].sufficient is True
        assert "retry_count" not in result

    @patch("src.nodes.call_structured")
    def test_insufficient_increments_retry(self, mock_call):
        mock_call.return_value = CritiqueResult(sufficient=False, gaps=["gap"])
        state = make_state(
            retry_count=1,
            research_results=[SubResearchResult(question="q", summary="s", sources=[])]
        )
        result = critique_node(state)
        assert result["critique"].sufficient is False
        assert result["retry_count"] == 2


class TestRouteAfterCritique:
    def test_sufficient_goes_to_synthesis(self):
        state = make_state(critique=CritiqueResult(sufficient=True, gaps=[]), retry_count=0)
        assert route_after_critique(state) == "synthesize_report"

    def test_insufficient_with_retries_left_replans(self):
        state = make_state(critique=CritiqueResult(sufficient=False, gaps=["gap"]), retry_count=0)
        assert route_after_critique(state) == "plan_research"

    def test_insufficient_but_retries_exhausted_still_synthesizes(self):
        state = make_state(critique=CritiqueResult(sufficient=False, gaps=["gap"]), retry_count=2)
        assert route_after_critique(state) == "synthesize_report"




class TestSynthesizeReport:
    @patch("src.nodes.call_structured")
    def test_produces_report(self, mock_call):
        mock_call.return_value = ResearchReport(
            title="Findings on LangGraph",
            executive_summary="Summary.",
            sections=[ReportSection(heading="Overview", body="Body text.")],
            citations=[],
            open_questions=[],
        )
        state = make_state(
            research_results=[SubResearchResult(question="q", summary="s", sources=[])],
            critique=CritiqueResult(sufficient=True, gaps=[]),
        )
        result = synthesize_report(state)
        assert result["final_report"].title == "Findings on LangGraph"
        assert result["status_message"] == "Report complete."
