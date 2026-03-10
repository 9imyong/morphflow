from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    # Future expansion: INFERENCE_DONE, DOWNSTREAM_PROCESSING, PARTIAL_SUCCESS


@dataclass(slots=True)
class Job:
    id: str
    status: JobStatus
    request_payload: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    retry_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class JobEvent:
    event_id: str
    job_id: str
    event_type: str
    source: str
    payload: dict[str, Any]
    trace_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
