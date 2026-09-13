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


# 어떤 상태에서 어떤 상태로 갈 수 있는지. 상태 갱신은 이 표를 조건으로 건
# 조건부 UPDATE 로만 수행한다. 조건 없이 덮어쓰면, 재시도나 lease 만료로
# 같은 job 을 두 워커가 잡았을 때 늦게 끝난 쪽이 SUCCESS 를 FAILED 로
# 되돌릴 수 있다.
ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.PROCESSING: frozenset({JobStatus.PENDING, JobStatus.FAILED, JobStatus.PROCESSING}),
    JobStatus.SUCCESS: frozenset({JobStatus.PROCESSING}),
    JobStatus.FAILED: frozenset({JobStatus.PENDING, JobStatus.PROCESSING}),
}

# SUCCESS 는 종착 상태다. 여기서 나가는 전이는 없다.
TERMINAL_STATUSES: frozenset[JobStatus] = frozenset({JobStatus.SUCCESS})


def allowed_source_statuses(target: JobStatus) -> frozenset[JobStatus]:
    """target 으로 전이할 수 있는 출발 상태 집합."""
    return ALLOWED_TRANSITIONS.get(target, frozenset())


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
