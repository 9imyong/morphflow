from __future__ import annotations

from collections import Counter

import pytest

from app.adapters.db.repositories import SqlAlchemyJobEventRepository
from app.application.job_service import JobService
from app.application.pipeline_services import InferencePipelineService
from app.application.worker_service import WorkerService
from app.domain.models import JobStatus
from app.ports.idempotency import IdempotencyPort, IdempotencyRecord


class SequenceIdempotencyStore(IdempotencyPort):
    def __init__(self, *, reserve_outcomes: list[bool]) -> None:
        self._request_records: dict[str, IdempotencyRecord] = {}
        self._job_records: dict[str, IdempotencyRecord] = {}
        self._reserve_outcomes = list(reserve_outcomes)

    async def get_request_record(self, key: str) -> IdempotencyRecord | None:
        return self._request_records.get(key)

    async def reserve_request(self, key: str, job_id: str) -> bool:
        if key in self._request_records:
            return False
        self._request_records[key] = IdempotencyRecord(key=key, job_id=job_id, status="PROCESSING")
        return True

    async def complete_request(self, key: str, job_id: str) -> None:
        self._request_records[key] = IdempotencyRecord(key=key, job_id=job_id, status="COMPLETED")

    async def reserve_job_processing(self, job_id: str) -> bool:
        if self._reserve_outcomes:
            outcome = self._reserve_outcomes.pop(0)
            if not outcome:
                return False

        self._job_records[job_id] = IdempotencyRecord(key=job_id, job_id=job_id, status="PROCESSING")
        return True

    async def complete_job_processing(self, job_id: str, success: bool) -> None:
        if success:
            self._job_records[job_id] = IdempotencyRecord(key=job_id, job_id=job_id, status="COMPLETED")
            return
        self._job_records.pop(job_id, None)


class SuccessProcessor:
    async def process(self, payload: dict) -> dict:
        return {"echo": payload}


class InferenceSuccessProcessor:
    async def process(self, payload: dict) -> dict:
        return {"mode": "simulated-gpu", "echo": payload.get("input", {}).get("content", "")}


@pytest.mark.asyncio
async def test_worker_lock_contention_retries_then_recovers(session_factory, publisher) -> None:
    idempotency_store = SequenceIdempotencyStore(reserve_outcomes=[False, True])
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        publisher=publisher,
        topic="request-topic",
    )
    worker_service = WorkerService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        processor=SuccessProcessor(),
    )

    created = await job_service.create_job(
        payload={"input": {"type": "text", "content": "lock-recovery"}, "options": {}},
        idempotency_key="lock-recovery-worker-key",
    )
    event = publisher.published[-1][1]

    first_ok, first_error = await worker_service.handle_event(event)
    assert first_ok is False
    assert first_error == "IN_PROGRESS_LOCK"

    pending = await job_service.get_job(created.id)
    assert pending is not None
    assert pending.status == JobStatus.PENDING

    second_ok, second_error = await worker_service.handle_event(event)
    assert second_ok is True
    assert second_error is None

    updated = await job_service.get_job(created.id)
    assert updated is not None
    assert updated.status == JobStatus.SUCCESS


@pytest.mark.asyncio
async def test_inference_lock_contention_retries_then_recovers(session_factory, publisher) -> None:
    idempotency_store = SequenceIdempotencyStore(reserve_outcomes=[False, True])
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        publisher=publisher,
        topic="request-topic",
    )
    inference_service = InferencePipelineService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        processor=InferenceSuccessProcessor(),
        publisher=publisher,
        downstream_topic="downstream-topic",
    )

    created = await job_service.create_job(
        payload={"input": {"type": "text", "content": "lock-recovery-inference"}, "options": {}},
        idempotency_key="lock-recovery-inference-key",
    )
    inference_event = publisher.published[-1][1]

    first_ok, first_error = await inference_service.handle_event(inference_event)
    assert first_ok is False
    assert first_error == "IN_PROGRESS_LOCK"

    second_ok, second_error = await inference_service.handle_event(inference_event)
    assert second_ok is True
    assert second_error is None
    assert publisher.published[-1][0] == "downstream-topic"

    mid_state = await job_service.get_job(created.id)
    assert mid_state is not None
    assert mid_state.status == JobStatus.PROCESSING

    async with session_factory() as session:
        events = await SqlAlchemyJobEventRepository(session).list_for_job(created.id)
    counts = Counter(item.event_type for item in events)
    assert counts["PROCESSING_STARTED"] == 1
    assert counts["INFERENCE_COMPLETED"] == 1
