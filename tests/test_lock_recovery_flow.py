"""lease 경합과 회수 동작 검증.

예전에는 Redis SETNX 결과를 흉내 내는 가짜 저장소로 경합을 만들었다. 지금은
소유권이 jobs 행에 있으므로, 실제로 다른 워커가 lease 를 쥔 상태를 만들어
검증한다.
"""
from __future__ import annotations

import pytest

from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.adapters.db.models import JobModel
from app.adapters.db.repositories import SqlAlchemyJobRepository
from app.application.job_service import JobService
from app.application.pipeline_services import InferencePipelineService
from app.application.worker_service import WorkerService
from app.domain.models import JobStatus


class SuccessProcessor:
    async def process(self, payload: dict) -> dict:
        return {"echo": payload}


class InferenceSuccessProcessor:
    async def process(self, payload: dict) -> dict:
        return {"mode": "simulated-gpu", "echo": payload.get("input", {}).get("content", "")}


async def _expire_lease(session_factory, job_id: str) -> None:
    """시간이 흘러 lease 가 만료된 상황을 만든다.

    claim_for_passing 을 다시 부르는 것으로는 흉내 낼 수 없다. 살아 있는
    lease 는 재선점 자체를 막기 때문이다.
    """
    async with session_factory() as session:
        await session.execute(
            update(JobModel)
            .where(JobModel.id == job_id)
            .values(lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
        await session.commit()


async def _status_of(session_factory, job_id: str) -> JobStatus:
    async with session_factory() as session:
        job = await SqlAlchemyJobRepository(session).get(job_id)
    assert job is not None
    return job.status


async def _create_event(job_service, publisher, outbox_relay, *, key: str, content: str):
    created = await job_service.create_job(
        payload={"input": {"type": "text", "content": content}, "options": {}},
        idempotency_key=key,
    )
    await outbox_relay.drain_once()
    return created, publisher.published[-1][1]


@pytest.mark.asyncio
async def test_live_lease_blocks_second_worker_then_expiry_allows_takeover(
    session_factory, idempotency_store, publisher, outbox_relay
) -> None:
    """살아 있는 lease 는 다른 워커를 막고, 만료되면 회수된다."""
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        topic="request-topic",
    )
    created, event = await _create_event(
        job_service, publisher, outbox_relay, key="lease-worker-key", content="lease-recovery"
    )

    # 다른 워커가 먼저 선점한 상태를 만든다.
    async with session_factory() as session:
        holder = await SqlAlchemyJobRepository(session).claim_for_processing(
            created.id, owner="worker-A", lease_seconds=3600
        )
        await session.commit()
    assert holder is not None

    worker_b = WorkerService(
        session_factory=session_factory, processor=SuccessProcessor(), worker_id="worker-B"
    )

    ok, error = await worker_b.handle_event(event)
    assert ok is False
    assert error == "LEASE_HELD", "살아 있는 lease 를 뚫고 처리했다"

    # lease 가 만료되면(= 앞선 워커가 죽었다고 본다) 회수할 수 있다.
    await _expire_lease(session_factory, created.id)

    ok, error = await worker_b.handle_event(event)
    assert ok is True and error is None

    updated = await job_service.get_job(created.id)
    assert updated is not None
    assert updated.status == JobStatus.SUCCESS


@pytest.mark.asyncio
async def test_expired_owner_cannot_write_result_after_takeover(
    session_factory, idempotency_store, publisher, outbox_relay
) -> None:
    """lease 를 빼앗긴 워커는 결과를 쓰지 못한다 (펜싱).

    Redis 락에는 이 장치가 없어, TTL 이 만료된 뒤 뒤늦게 끝난 워커가
    인계받은 워커의 결과를 덮어썼다.
    """
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        topic="request-topic",
    )
    created, _ = await _create_event(
        job_service, publisher, outbox_relay, key="fencing-key", content="fencing"
    )

    async with session_factory() as session:
        repository = SqlAlchemyJobRepository(session)
        stale = await repository.claim_for_processing(created.id, owner="worker-A", lease_seconds=-1)
        await session.commit()
    assert stale is not None

    # 만료된 lease 를 다른 워커가 회수한다 (epoch 증가).
    async with session_factory() as session:
        repository = SqlAlchemyJobRepository(session)
        fresh = await repository.claim_for_processing(created.id, owner="worker-B", lease_seconds=3600)
        await session.commit()
    assert fresh is not None
    assert fresh.epoch > stale.epoch

    # 이 시점의 상태는 여전히 PROCESSING 이다. 즉 상태 조건만으로는 옛 소유자의
    # 쓰기를 막을 수 없다. 막아 주는 것은 오직 epoch 비교(펜싱)다.
    assert await _status_of(session_factory, created.id) == JobStatus.PROCESSING

    async with session_factory() as session:
        repository = SqlAlchemyJobRepository(session)
        rejected = await repository.update_status(
            created.id,
            JobStatus.SUCCESS.value,
            result={"by": "worker-A"},
            lease_owner="worker-A",
            lease_epoch=stale.epoch,
            release_lease=True,
        )
        await session.commit()

    assert rejected is None, "빼앗긴 워커가 결과를 썼다"
    assert await _status_of(session_factory, created.id) == JobStatus.PROCESSING

    # 현재 소유자의 쓰기는 통과한다.
    async with session_factory() as session:
        repository = SqlAlchemyJobRepository(session)
        written = await repository.update_status(
            created.id,
            JobStatus.SUCCESS.value,
            result={"by": "worker-B"},
            lease_owner="worker-B",
            lease_epoch=fresh.epoch,
            release_lease=True,
        )
        await session.commit()
    assert written is not None

    final = await job_service.get_job(created.id)
    assert final is not None
    assert final.status == JobStatus.SUCCESS
    assert final.result == {"by": "worker-B"}


@pytest.mark.asyncio
async def test_renew_lease_fails_after_takeover(session_factory, idempotency_store, publisher, outbox_relay) -> None:
    """소유권을 잃은 뒤에는 연장도 실패한다."""
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        topic="request-topic",
    )
    created, _ = await _create_event(
        job_service, publisher, outbox_relay, key="renew-key", content="renew"
    )

    async with session_factory() as session:
        repository = SqlAlchemyJobRepository(session)
        first = await repository.claim_for_processing(created.id, owner="worker-A", lease_seconds=-1)
        await session.commit()
    assert first is not None

    async with session_factory() as session:
        repository = SqlAlchemyJobRepository(session)
        # 아직 아무도 안 가져갔으면 연장된다.
        assert await repository.renew_lease(
            created.id, owner="worker-A", epoch=first.epoch, lease_seconds=-1
        ) is True
        # 다른 워커가 회수
        await repository.claim_for_processing(created.id, owner="worker-B", lease_seconds=3600)
        await session.commit()

    async with session_factory() as session:
        repository = SqlAlchemyJobRepository(session)
        renewed = await repository.renew_lease(
            created.id, owner="worker-A", epoch=first.epoch, lease_seconds=600
        )
        await session.commit()

    assert renewed is False


@pytest.mark.asyncio
async def test_inference_lease_contention_then_recovers(
    session_factory, idempotency_store, publisher, outbox_relay
) -> None:
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        topic="request-topic",
    )
    created, inference_event = await _create_event(
        job_service, publisher, outbox_relay, key="lease-inference-key", content="lease-inference"
    )

    async with session_factory() as session:
        await SqlAlchemyJobRepository(session).claim_for_processing(
            created.id, owner="other-inference", lease_seconds=3600
        )
        await session.commit()

    inference_service = InferencePipelineService(
        session_factory=session_factory,
        processor=InferenceSuccessProcessor(),
        downstream_topic="downstream-topic",
        worker_id="inference-B",
    )

    ok, error = await inference_service.handle_event(inference_event)
    assert ok is False
    assert error == "LEASE_HELD"

    # lease 만료 후 회수
    await _expire_lease(session_factory, created.id)

    ok, error = await inference_service.handle_event(inference_event)
    assert ok is True and error is None

    await outbox_relay.drain_once()
    assert publisher.published[-1][0] == "downstream-topic"

    mid_state = await job_service.get_job(created.id)
    assert mid_state is not None
    assert mid_state.status == JobStatus.PROCESSING
