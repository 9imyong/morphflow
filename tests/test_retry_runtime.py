from __future__ import annotations

from collections import Counter

import pytest

from app.adapters.db.repositories import SqlAlchemyJobEventRepository
from app.application.job_service import JobService
from app.application.worker_service import WorkerService
from app.domain.models import JobStatus
from app.workers.runner import _compute_retry_backoff_seconds, _decode_headers, _parse_retry_count


class FlakyProcessor:
    def __init__(self) -> None:
        self.calls = 0

    async def process(self, payload: dict) -> dict:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient failure")
        return {"ok": True, "payload": payload}


def test_retry_header_decode_and_count_parse() -> None:
    headers = [("retry-count", b"2"), ("original-topic", b"request-topic"), ("error-reason", b"boom")]
    decoded = _decode_headers(headers)
    assert decoded["retry-count"] == "2"
    assert decoded["original-topic"] == "request-topic"
    assert _parse_retry_count(decoded) == 2
    assert _parse_retry_count({"retry-count": "invalid"}) == 0


def test_retry_backoff_exponential_with_cap() -> None:
    assert _compute_retry_backoff_seconds(1, base=1.0, multiplier=2.0, max_seconds=30.0) == 1.0
    assert _compute_retry_backoff_seconds(2, base=1.0, multiplier=2.0, max_seconds=30.0) == 2.0
    assert _compute_retry_backoff_seconds(10, base=1.0, multiplier=2.0, max_seconds=30.0) == 30.0


@pytest.mark.asyncio
async def test_worker_can_retry_after_failed_attempt(session_factory, idempotency_store, publisher) -> None:
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        publisher=publisher,
        topic="request-topic",
    )
    worker_service = WorkerService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        processor=FlakyProcessor(),
    )

    created = await job_service.create_job(
        payload={"input": {"type": "text", "content": "retry-me"}, "options": {}},
        idempotency_key="retry-me-key",
    )
    event = publisher.published[-1][1]

    success_first, error_first = await worker_service.handle_event(event)
    assert success_first is False
    assert error_first is not None

    success_second, error_second = await worker_service.handle_event(event)
    assert success_second is True
    assert error_second is None

    updated = await job_service.get_job(created.id)
    assert updated is not None
    assert updated.status == JobStatus.SUCCESS

    async with session_factory() as session:
        events = await SqlAlchemyJobEventRepository(session).list_for_job(created.id)
    event_counts = Counter(item.event_type for item in events)
    assert event_counts["PROCESSING_STARTED"] == 2
    assert event_counts["FAILED"] == 1
    assert event_counts["PROCESSING_COMPLETED"] == 1
