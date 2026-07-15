"""Request and response models for the research API."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class StartResearchRequest(BaseModel):
    """Payload to kick off a new research job."""

    query: str = Field(min_length=3, max_length=500)
    hitl_enabled: bool = True


class StartResearchResponse(BaseModel):
    thread_id: str
    status: str


class ApprovalRequest(BaseModel):
    """Payload sent when a human approves or rejects the research plan."""

    approved: bool
    feedback: str = ""


class StatusResponse(BaseModel):
    """Polled by the frontend to track job progress."""

    thread_id: str
    status: str  # "running" | "waiting_approval" | "completed" | "error"
    status_message: Optional[str] = None
    sub_questions: Optional[list[dict[str, Any]]] = None
    research_results: Optional[list[dict[str, Any]]] = None
    retry_count: Optional[int] = None
    report: Optional[dict[str, Any]] = None
    error: Optional[str] = None
