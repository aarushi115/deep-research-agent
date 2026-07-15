"""State and schema definitions for the Deep Research Agent graph.

`ResearchState` is the top-level graph state. The Pydantic models below are
used both as structured-output targets for the LLM and as the shape of data
carried in the state, so every field the LLM produces is validated on the
way in.
"""

import operator
from typing import Annotated, Optional, TypedDict

from pydantic import BaseModel, Field


class SubQuestion(BaseModel):
    """A single research sub-question produced by the planner."""

    question: str = Field(description="A focused, answerable research question.")
    rationale: str = Field(description="Why this sub-question matters to the overall query.")


class SubQuestionList(BaseModel):
    """Wrapper so the planner can return a structured list in one call."""

    sub_questions: list[SubQuestion] = Field(
        description="3 to 5 sub-questions that together cover the original query."
    )


class SourceSnippet(BaseModel):
    """A single search result used as evidence."""

    url: str
    title: str
    snippet: str


class SubResearchResult(BaseModel):
    """The output of researching a single sub-question."""

    question: str
    summary: str
    sources: list[SourceSnippet] = Field(default_factory=list)
    error: Optional[str] = Field(
        default=None, description="Set if this branch failed; summary will note the gap."
    )


class CritiqueResult(BaseModel):
    """Reflection output judging whether findings are sufficient."""

    sufficient: bool = Field(description="True if findings adequately answer the original query.")
    gaps: list[str] = Field(
        default_factory=list, description="Specific missing angles or unanswered aspects, if any."
    )


class Citation(BaseModel):
    """A claim-to-source mapping used in the final report."""

    claim: str
    source_url: str


class ReportSection(BaseModel):
    """A single section of the final synthesized report."""

    heading: str
    body: str


class ResearchReport(BaseModel):
    """The final structured research report."""

    title: str
    executive_summary: str
    sections: list[ReportSection]
    citations: list[Citation]
    open_questions: list[str] = Field(default_factory=list)


class ResearchState(TypedDict):
    """Top-level graph state, threaded through every node.

    `research_results` uses `operator.add` as its reducer so that parallel
    researcher branches (fanned out via the `Send` API) can each append
    their own result without clobbering the others.
    """

    original_query: str
    hitl_enabled: bool
    sub_questions: list[SubQuestion]
    research_results: Annotated[list[SubResearchResult], operator.add]
    critique: Optional[CritiqueResult]
    retry_count: int
    human_approved: bool
    final_report: Optional[ResearchReport]
    status_message: str


class ResearcherInput(TypedDict):
    """Payload sent to each parallel researcher branch via `Send`.

    Deliberately a separate, smaller shape than `ResearchState`: each
    branch only needs its own question plus the original query for context.
    """

    question: str
    rationale: str
    original_query: str
