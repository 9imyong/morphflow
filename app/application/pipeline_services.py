from __future__ import annotations

from app.adapters.db.repositories import SqlAlchemyJobEventRepository, SqlAlchemyJobRepository
from app.core.metrics import (
    DOWNSTREAM_EVENT_PUBLISHED_TOTAL,
    DOWNSTREAM_FAILURE_TOTAL,
    DOWNSTREAM_SUCCESS_TOTAL,
    JOB_FAILURE_TOTAL,
)
from app.domain.events import EventType, build_event
from app.domain.models import JobStatus
from app.ports.idempotency import IdempotencyPort
from app.ports.publisher import EventPublisherPort
from app.ports.task_processor import TaskProcessorPort
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class InferencePipelineService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        idempotency_store: IdempotencyPort,
        processor: TaskProcessorPort,
        publisher: EventPublisherPort,
        downstream_topic: str,
    ) -> None:
        self.session_factory = session_factory
        self.idempotency_store = idempotency_store
        self.processor = processor
        self.publisher = publisher
        self.downstream_topic = downstream_topic

    async def handle_event(self, event: dict) -> tuple[bool, str | None]:
        job_id = event["job_id"]
        trace_id = event["trace_id"]

        reserved = await self.idempotency_store.reserve_job_processing(job_id)
        if not reserved:
            return True, None

        try:
            request_payload = event["payload"]["request"]
            inference_result = await self.processor.process(request_payload)

            async with self.session_factory() as session:
                job_repository = SqlAlchemyJobRepository(session)
                event_repository = SqlAlchemyJobEventRepository(session)
                await job_repository.update_status(job_id, JobStatus.PROCESSING.value)
                await event_repository.add(
                    build_event(
                        job_id=job_id,
                        event_type=EventType.INFERENCE_COMPLETED,
                        source="inference-worker",
                        trace_id=trace_id,
                        payload={"result": inference_result},
                    )
                )
                await session.commit()

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
            await self.publisher.publish(self.downstream_topic, downstream_event)
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
                    error=None,
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
