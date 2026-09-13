from __future__ import annotations

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
    JOB_TRANSITION_CONFLICT_TOTAL,
)
from app.domain.events import EventType, build_event
from app.domain.models import JobStatus
from app.ports.idempotency import IdempotencyPort
from app.ports.task_processor import TaskProcessorPort
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class InferencePipelineService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        idempotency_store: IdempotencyPort,
        processor: TaskProcessorPort,
        downstream_topic: str,
    ) -> None:
        self.session_factory = session_factory
        self.idempotency_store = idempotency_store
        self.processor = processor
        self.downstream_topic = downstream_topic

    async def handle_event(self, event: dict) -> tuple[bool, str | None]:
        job_id = event["job_id"]
        trace_id = event["trace_id"]

        reserved = await self.idempotency_store.reserve_job_processing(job_id)
        if not reserved:
            async with self.session_factory() as session:
                job_repository = SqlAlchemyJobRepository(session)
                existing = await job_repository.get(job_id)
                # Completed jobs are safe to ack; active/failed states should retry for lease takeover.
                if existing is not None and existing.status == JobStatus.SUCCESS:
                    return True, None
            return False, "IN_PROGRESS_LOCK"

        try:
            request_payload = event["payload"]["request"]
            async with self.session_factory() as session:
                job_repository = SqlAlchemyJobRepository(session)
                event_repository = SqlAlchemyJobEventRepository(session)
                claimed = await job_repository.update_status(job_id, JobStatus.PROCESSING.value)
                if claimed is None:
                    # 이미 종료된 job 이거나 다른 워커가 선점했다. 여기서 멈춘다.
                    JOB_TRANSITION_CONFLICT_TOTAL.labels(target_status=JobStatus.PROCESSING.value).inc()
                    await session.rollback()
                    await self.idempotency_store.complete_job_processing(job_id, success=False)
                    return True, None
                await event_repository.add(
                    build_event(
                        job_id=job_id,
                        event_type=EventType.PROCESSING_STARTED,
                        source="inference-worker",
                        trace_id=trace_id,
                        payload={},
                    )
                )
                await session.commit()

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
            await self.idempotency_store.complete_job_processing(job_id, success=True)
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
                        source="inference-worker",
                        trace_id=trace_id,
                        payload={"error": str(exc)},
                    )
                )
                await session.commit()
            JOB_FAILURE_TOTAL.inc()
            await self.idempotency_store.complete_job_processing(job_id, success=False)
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
