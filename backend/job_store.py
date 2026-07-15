"""In-memory store for research job status.

A production deployment would back this with Redis or a database; for a
portfolio/demo project a process-local dict is sufficient and keeps the
free-tier deployment story simple (no extra infra to provision).
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class JobRecord:
    thread_id: str
    status: str = "running"  # running | waiting_approval | completed | error
    status_message: str = "Starting research..."
    sub_questions: Optional[list[dict[str, Any]]] = None
    research_results: Optional[list[dict[str, Any]]] = None
    retry_count: int = 0
    report: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class JobStore:
    """Thread-safe (within one asyncio event loop) job registry."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, thread_id: str) -> JobRecord:
        async with self._lock:
            record = JobRecord(thread_id=thread_id)
            self._jobs[thread_id] = record
            return record

    async def get(self, thread_id: str) -> Optional[JobRecord]:
        async with self._lock:
            return self._jobs.get(thread_id)

    async def update(self, thread_id: str, **fields: Any) -> None:
        async with self._lock:
            record = self._jobs.get(thread_id)
            if record is None:
                return
            for key, value in fields.items():
                setattr(record, key, value)


job_store = JobStore()
