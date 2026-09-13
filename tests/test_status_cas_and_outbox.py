"""조건부 상태 전이(CAS)와 트랜잭셔널 아웃박스 검증.

두 가지를 고정한다.
1. 늦게 끝난 워커가 이미 확정된 결과를 덮어쓰지 못한다.
2. Kafka 발행이 실패해도 메시지가 사라지지 않고, 다음 릴레이에서 나간다.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.adapters.db.models import OutboxMessageModel
from app.adapters.db.repositories import SqlAlchemyJobRepository, SqlAlchemyOutboxRepository
from app.application.job_service import JobService
from app.application.worker_service import WorkerService
from app.domain.models import Job, JobStatus
from app.ports.publisher import EventPublisherPort

from conftest import FailingProcessor, SuccessProcessor


async def _seed_job(session_factory, job_id: str, status: JobStatus) -> None:
    async with session_factory() as session:
        await SqlAlchemyJobRepository(session).add(
            Job(id=job_id, status=status, request_payload={"input": "x"})
        )
        await session.commit()


async def _status_of(session_factory, job_id: str) -> JobStatus:
    async with session_factory() as session:
        job = await SqlAlchemyJobRepository(session).get(job_id)
    assert job is not None
    return job.status


# --------------------------------------------------------------------------
# CAS
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_cannot_overwrite_success(session_factory) -> None:
    """뒤늦게 끝난 워커가 SUCCESS 를 FAILED 로 되돌리지 못한다.

    lease 만료나 재시도로 같은 job 을 두 워커가 잡았을 때 실제로 일어나던
    상황이다. 조건 없는 UPDATE 였다면 마지막 쓰기가 이겨서 성공한 작업이
    실패로 기록됐다.
    """
    await _seed_job(session_factory, "job-1", JobStatus.PROCESSING)

    async with session_factory() as session:
        repository = SqlAlchemyJobRepository(session)
        winner = await repository.update_status("job-1", JobStatus.SUCCESS.value, result={"ok": True})
        await session.commit()
    assert winner is not None

    async with session_factory() as session:
        repository = SqlAlchemyJobRepository(session)
        loser = await repository.update_status("job-1", JobStatus.FAILED.value, error="too late")
        await session.commit()

    assert loser is None, "종료된 job 의 상태가 바뀌었다"
    assert await _status_of(session_factory, "job-1") == JobStatus.SUCCESS


@pytest.mark.asyncio
async def test_success_requires_processing(session_factory) -> None:
    """PENDING 에서 곧바로 SUCCESS 로 건너뛸 수 없다."""
    await _seed_job(session_factory, "job-2", JobStatus.PENDING)

    async with session_factory() as session:
        repository = SqlAlchemyJobRepository(session)
        result = await repository.update_status("job-2", JobStatus.SUCCESS.value, result={"ok": True})
        await session.commit()

    assert result is None
    assert await _status_of(session_factory, "job-2") == JobStatus.PENDING


@pytest.mark.asyncio
async def test_only_one_worker_claims_the_job(session_factory) -> None:
    """PROCESSING 선점은 한 번만 성공하는 게 아니라, 종료 상태에서는 실패해야 한다."""
    await _seed_job(session_factory, "job-3", JobStatus.PENDING)

    async with session_factory() as session:
        repository = SqlAlchemyJobRepository(session)
        assert await repository.update_status("job-3", JobStatus.PROCESSING.value) is not None
        assert await repository.update_status("job-3", JobStatus.SUCCESS.value, result={}) is not None
        await session.commit()

    async with session_factory() as session:
        repository = SqlAlchemyJobRepository(session)
        # 뒤늦게 도착한 재시도 메시지가 다시 처리를 시작하려는 상황
        assert await repository.update_status("job-3", JobStatus.PROCESSING.value) is None
        await session.commit()

    assert await _status_of(session_factory, "job-3") == JobStatus.SUCCESS


@pytest.mark.asyncio
async def test_duplicate_delivery_does_not_reprocess(
    session_factory, idempotency_store, publisher, outbox_relay
) -> None:
    """중복 전달된 메시지가 이미 끝난 job 을 다시 처리하지 않는다."""
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        topic="request-topic",
    )
    worker = WorkerService(
        session_factory=session_factory,
        processor=SuccessProcessor(),
    )

    created = await job_service.create_job(payload={"input": "dup"}, idempotency_key="dup-key")
    await outbox_relay.drain_once()
    event = publisher.published[-1][1]

    assert await worker.handle_event(event) == (True, None)
    assert await _status_of(session_factory, created.id) == JobStatus.SUCCESS

    # 같은 메시지가 한 번 더 도착해도 상태가 흔들리지 않는다.
    ok, error = await worker.handle_event(event)
    assert ok is True and error is None
    assert await _status_of(session_factory, created.id) == JobStatus.SUCCESS


@pytest.mark.asyncio
async def test_failure_path_still_records_failed(
    session_factory, idempotency_store, publisher, outbox_relay
) -> None:
    """CAS 를 걸어도 정상적인 실패 기록은 막히지 않는다."""
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        topic="request-topic",
    )
    worker = WorkerService(
        session_factory=session_factory,
        processor=FailingProcessor(),
    )

    created = await job_service.create_job(payload={"input": "fail"}, idempotency_key="fail-key")
    await outbox_relay.drain_once()
    event = publisher.published[-1][1]

    ok, error = await worker.handle_event(event)
    assert ok is False and error is not None
    assert await _status_of(session_factory, created.id) == JobStatus.FAILED


# --------------------------------------------------------------------------
# Outbox
# --------------------------------------------------------------------------


class BrokenPublisher(EventPublisherPort):
    """발행이 항상 실패하는 퍼블리셔."""

    def __init__(self) -> None:
        self.attempts = 0

    async def publish(self, topic: str, event: dict, headers: dict[str, str] | None = None) -> None:
        self.attempts += 1
        raise RuntimeError("kafka down")


async def _pending_rows(session_factory) -> list[OutboxMessageModel]:
    async with session_factory() as session:
        rows = await session.execute(
            select(OutboxMessageModel).where(OutboxMessageModel.status == "PENDING")
        )
        return list(rows.scalars())


@pytest.mark.asyncio
async def test_job_creation_writes_outbox_not_kafka(
    session_factory, idempotency_store, publisher
) -> None:
    """생성 시점에는 DB 에만 쓰고 Kafka 로 나가지 않는다."""
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        topic="request-topic",
    )

    await job_service.create_job(payload={"input": "x"}, idempotency_key="outbox-key")

    assert publisher.published == [], "커밋 시점에 바로 발행됐다"
    pending = await _pending_rows(session_factory)
    assert len(pending) == 1
    assert pending[0].topic == "request-topic"


@pytest.mark.asyncio
async def test_publish_failure_keeps_message_for_retry(
    session_factory, idempotency_store
) -> None:
    """발행이 실패하면 메시지는 PENDING 으로 남고 재시도 횟수만 올라간다."""
    from app.adapters.messaging.outbox_relay import OutboxRelay

    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        topic="request-topic",
    )
    await job_service.create_job(payload={"input": "x"}, idempotency_key="broken-key")

    broken = BrokenPublisher()
    relay = OutboxRelay(
        session_factory=session_factory, publisher=broken, batch_size=10, poll_interval_seconds=0.01
    )

    assert await relay.drain_once() == 0
    assert broken.attempts == 1

    pending = await _pending_rows(session_factory)
    assert len(pending) == 1, "발행 실패한 메시지가 사라졌다"
    assert pending[0].attempts == 1

    # Kafka 가 살아나면 다음 주기에 그대로 나간다.
    from conftest import CapturingPublisher

    recovered = CapturingPublisher()
    relay_ok = OutboxRelay(
        session_factory=session_factory, publisher=recovered, batch_size=10, poll_interval_seconds=0.01
    )
    assert await relay_ok.drain_once() == 1
    assert len(recovered.published) == 1
    assert await _pending_rows(session_factory) == []


@pytest.mark.asyncio
async def test_relay_marks_published_and_does_not_resend(
    session_factory, idempotency_store, publisher, outbox_relay
) -> None:
    """한 번 나간 메시지는 다시 나가지 않는다."""
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        topic="request-topic",
    )
    await job_service.create_job(payload={"input": "x"}, idempotency_key="once-key")

    assert await outbox_relay.drain_once() == 1
    assert await outbox_relay.drain_once() == 0
    assert len(publisher.published) == 1


@pytest.mark.asyncio
async def test_outbox_preserves_order_on_partial_failure(session_factory) -> None:
    """앞 메시지 발행이 실패하면 뒤 메시지를 먼저 보내지 않는다."""

    class FailsSecond(EventPublisherPort):
        def __init__(self) -> None:
            self.sent: list[dict] = []

        async def publish(self, topic, event, headers=None) -> None:
            if event.get("seq") == 2:
                raise RuntimeError("kafka down")
            self.sent.append(event)

    from app.adapters.messaging.outbox_relay import OutboxRelay

    async with session_factory() as session:
        repository = SqlAlchemyOutboxRepository(session)
        for seq in (1, 2, 3):
            await repository.add(topic="t", payload={"seq": seq})
        await session.commit()

    publisher = FailsSecond()
    relay = OutboxRelay(
        session_factory=session_factory, publisher=publisher, batch_size=10, poll_interval_seconds=0.01
    )

    assert await relay.drain_once() == 1
    assert [event["seq"] for event in publisher.sent] == [1]
    pending = await _pending_rows(session_factory)
    assert sorted(row.payload["seq"] for row in pending) == [2, 3]
