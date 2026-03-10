from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


class EventType(StrEnum):
    REQUESTED = "REQUESTED"
    PROCESSING_STARTED = "PROCESSING_STARTED"
    PROCESSING_COMPLETED = "PROCESSING_COMPLETED"
    INFERENCE_COMPLETED = "INFERENCE_COMPLETED"
    DOWNSTREAM_COMPLETED = "DOWNSTREAM_COMPLETED"
    FAILED = "FAILED"
    # Future expansion: INFERENCE_COMPLETED, DOWNSTREAM_REQUESTED, DOWNSTREAM_COMPLETED


def build_event(
    *,
    job_id: str,
    event_type: EventType,
    source: str,
    trace_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "job_id": job_id,
        "event_type": event_type.value,
        "trace_id": trace_id,
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
