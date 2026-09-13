from __future__ import annotations

from uuid import uuid4

from app.adapters.db.repositories import (
    SqlAlchemyJobEventRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyOutboxRepository,
)
from app.core.metrics import (
    DOWNSTREAM_EVENT_PUBLISHED_TOTAL,
    DOWNSTREAM_FAILURE_TOTAL,
    DOWNSTREAM_SUCCESS_TOTAL,
    JOB_FAILURE_TOTAL,
    JOB_LEASE_TAKEOVER_TOTAL,
    JOB_TRANSITION_CONFLICT_TOTAL,
)
from app.domain.events import EventType, build_event
from app.domain.models import JobStatus
from app.ports.task_processor import TaskProcessorPort
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class InferencePipelineService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        processor: TaskProcessorPort,
        downstream_topic: str,
        lease_seconds: int = 1800,
        worker_id: str | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.processor = processor
        self.downstream_topic = downstream_topic
        self.lease_seconds = lease_seconds
        # 프로세스마다 고유해야 펜싱이 의미를 갖는다.
        self.worker_id = worker_id or f"inference-{uuid4()}"

    async def handle_event(self, event: dict) -> tuple[bool, str | None]:
        job_id = event["job_id"]
        trace_id = event["trace_id"]

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
                    return True, None
                JOB_TRANSITION_CONFLICT_TOTAL.labels(target_status=JobStatus.PROCESSING.value).inc()
                return False, "LEASE_HELD"

            if lease.epoch > 1:
                JOB_LEASE_TAKEOVER_TOTAL.inc()

            await event_repository.add(
                build_event(
                    job_id=job_id,
                    event_type=EventType.PROCESSING_STARTED,
                    source="inference-worker",
                    trace_id=trace_id,
                    payload={"lease_epoch": lease.epoch},
                )
            )
            await session.commit()

        try:
            request_payload = event["payload"]["request"]
            inference_result = await self.processor.process(request_payload)

            downstream_event = build_event(
                job_id=job_id,
                event_type=EventType.INFERENCE_COMPLETED,
                source="inference-worker",
                trace_id=trace_id,
                payload={
                    "request": request_payload,
                    "inference_result": inference_result,
                },
            )

            # 이벤트 로그와 downstream 발행 메시지를 한 트랜잭션에 함께 쓴다.
            # 커밋 뒤 바로 publish 하던 기존 방식은 발행이 실패하면 downstream 이
            # 그 job 을 영영 보지 못했다.
            async with self.session_factory() as session:
                event_repository = SqlAlchemyJobEventRepository(session)
                outbox_repository = SqlAlchemyOutboxRepository(session)
                await event_repository.add(
                    build_event(
                        job_id=job_id,
                        event_type=EventType.INFERENCE_COMPLETED,
                        source="inference-worker",
                        trace_id=trace_id,
                        payload={"result": inference_result},
                    )
                )
                await outbox_repository.add(topic=self.downstream_topic, payload=downstream_event)
                await session.commit()

            DOWNSTREAM_EVENT_PUBLISHED_TOTAL.inc()
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
                    # lease 를 빼앗긴 뒤의 실패다. 인계받은 쪽 결과를 덮지 않는다.
                    await session.rollback()
                    return False, str(exc)
                await event_repository.add(
                    build_event(
                        job_id=job_id,
                        event_type=EventType.FAILED,
                        source="inference-worker",
                        trace_id=trace_id,
                        payload={"error": str(exc)},
                    )
                )
                await session.commit()
            JOB_FAILURE_TOTAL.inc()
            return False, str(exc)


class DownstreamPipelineService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        processor: TaskProcessorPort,
    ) -> None:
        self.session_factory = session_factory
        self.processor = processor

    async def handle_event(self, event: dict) -> tuple[bool, str | None]:
        job_id = event["job_id"]
        trace_id = event["trace_id"]

        try:
            async with self.session_factory() as session:
                job_repository = SqlAlchemyJobRepository(session)
                existing = await job_repository.get(job_id)
                if existing is None:
                    raise ValueError(f"Job not found for downstream event: {job_id}")
                if existing.status == JobStatus.SUCCESS:
                    return True, None

            downstream_result = await self.processor.process(event["payload"])

            async with self.session_factory() as session:
                job_repository = SqlAlchemyJobRepository(session)
                event_repository = SqlAlchemyJobEventRepository(session)
                await job_repository.update_status(
                    job_id,
                    JobStatus.SUCCESS.value,
                    result={"inference": event["payload"].get("inference_result"), "downstream": downstream_result},
                    clear_error=True,
                )
                await event_repository.add(
                    build_event(
                        job_id=job_id,
                        event_type=EventType.DOWNSTREAM_COMPLETED,
                        source="downstream-worker",
                        trace_id=trace_id,
                        payload={"result": downstream_result},
                    )
                )
                await session.commit()

            DOWNSTREAM_SUCCESS_TOTAL.inc()
            return True, None
        except Exception as exc:
            async with self.session_factory() as session:
                job_repository = SqlAlchemyJobRepository(session)
                event_repository = SqlAlchemyJobEventRepository(session)
                await job_repository.update_status(job_id, JobStatus.FAILED.value, error=str(exc))
                await event_repository.add(
                    build_event(
                        job_id=job_id,
                        event_type=EventType.FAILED,
                        source="downstream-worker",
                        trace_id=trace_id,
                        payload={"error": str(exc)},
                    )
                )
                await session.commit()
            DOWNSTREAM_FAILURE_TOTAL.inc()
            return False, str(exc)
