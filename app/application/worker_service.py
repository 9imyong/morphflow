from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.db.repositories import SqlAlchemyJobEventRepository, SqlAlchemyJobRepository
from app.core.metrics import (
    JOB_FAILURE_TOTAL,
    JOB_LEASE_TAKEOVER_TOTAL,
    JOB_PROCESSING_SECONDS,
    JOB_SUCCESS_TOTAL,
    JOB_TRANSITION_CONFLICT_TOTAL,
)
from app.domain.events import EventType, build_event
from app.domain.models import JobStatus
from app.ports.task_processor import TaskProcessorPort


class WorkerService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        processor: TaskProcessorPort,
        lease_seconds: int = 1800,
        worker_id: str | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.processor = processor
        self.lease_seconds = lease_seconds
        # 프로세스마다 고유해야 펜싱이 의미를 갖는다.
        self.worker_id = worker_id or f"worker-{uuid4()}"

    async def handle_event(self, event: dict) -> tuple[bool, str | None]:
        job_id = event["job_id"]
        trace_id = event["trace_id"]

        # 선점과 상태 전이를 한 번의 조건부 UPDATE 로 처리한다. Redis SETNX 는
        # TTL 이 만료되는 순간 두 워커가 같은 job 을 동시에 처리하는 것을 막지
        # 못했다. lease 는 만료 시 회수를 허용하되, 결과 기록 때 epoch 을
        # 검사해 빼앗긴 워커의 쓰기를 차단한다.
        async with self.session_factory() as session:
            job_repository = SqlAlchemyJobRepository(session)
            event_repository = SqlAlchemyJobEventRepository(session)

            lease = await job_repository.claim_for_processing(
                job_id, owner=self.worker_id, lease_seconds=self.lease_seconds
            )
            if lease is None:
                await session.rollback()
                existing = await job_repository.get(job_id)
                if existing is not None and existing.status == JobStatus.SUCCESS:
                    # 이미 끝난 작업. 중복 전달이므로 조용히 ack 한다.
                    return True, None
                # 다른 워커의 lease 가 살아 있다. 만료 뒤 회수할 수 있게 재시도로 넘긴다.
                JOB_TRANSITION_CONFLICT_TOTAL.labels(target_status=JobStatus.PROCESSING.value).inc()
                return False, "LEASE_HELD"

            if lease.epoch > 1:
                JOB_LEASE_TAKEOVER_TOTAL.inc()

            await event_repository.add(
                build_event(
                    job_id=job_id,
                    event_type=EventType.PROCESSING_STARTED,
                    source="worker",
                    trace_id=trace_id,
                    payload={"lease_epoch": lease.epoch},
                )
            )
            await session.commit()

        started_at = perf_counter()
        try:
            result = await self.processor.process(event["payload"]["request"])

            async with self.session_factory() as session:
                job_repository = SqlAlchemyJobRepository(session)
                event_repository = SqlAlchemyJobEventRepository(session)
                committed = await job_repository.update_status(
                    job_id,
                    JobStatus.SUCCESS.value,
                    result=result,
                    clear_error=True,
                    lease_owner=self.worker_id,
                    lease_epoch=lease.epoch,
                    release_lease=True,
                )
                if committed is None:
                    # 처리 도중 lease 를 빼앗겼다. 인계받은 워커의 결과가 정답이다.
                    await session.rollback()
                    JOB_TRANSITION_CONFLICT_TOTAL.labels(target_status=JobStatus.SUCCESS.value).inc()
                    return True, None
                await event_repository.add(
                    build_event(
                        job_id=job_id,
                        event_type=EventType.PROCESSING_COMPLETED,
                        source="worker",
                        trace_id=trace_id,
                        payload={"result": result},
                    )
                )
                await session.commit()

            JOB_SUCCESS_TOTAL.inc()
            return True, None
        except Exception as exc:
            async with self.session_factory() as session:
                job_repository = SqlAlchemyJobRepository(session)
                event_repository = SqlAlchemyJobEventRepository(session)
                marked = await job_repository.update_status(
                    job_id,
                    JobStatus.FAILED.value,
                    error=str(exc),
                    lease_owner=self.worker_id,
                    lease_epoch=lease.epoch,
                    release_lease=True,
                )
                if marked is None:
                    await session.rollback()
                    return False, str(exc)
                await event_repository.add(
                    build_event(
                        job_id=job_id,
                        event_type=EventType.FAILED,
                        source="worker",
                        trace_id=trace_id,
                        payload={"error": str(exc)},
                    )
                )
                await session.commit()
            JOB_FAILURE_TOTAL.inc()
            return False, str(exc)
        finally:
            JOB_PROCESSING_SECONDS.observe(perf_counter() - started_at)
