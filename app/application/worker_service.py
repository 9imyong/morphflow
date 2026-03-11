from __future__ import annotations

from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.db.repositories import SqlAlchemyJobEventRepository, SqlAlchemyJobRepository
from app.core.metrics import JOB_FAILURE_TOTAL, JOB_PROCESSING_SECONDS, JOB_SUCCESS_TOTAL
from app.domain.events import EventType, build_event
from app.domain.models import JobStatus
from app.ports.idempotency import IdempotencyPort
from app.ports.task_processor import TaskProcessorPort


class WorkerService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        idempotency_store: IdempotencyPort,
        processor: TaskProcessorPort,
    ) -> None:
        self.session_factory = session_factory
        self.idempotency_store = idempotency_store
        self.processor = processor

    async def handle_event(self, event: dict) -> tuple[bool, str | None]:
        job_id = event["job_id"]
        trace_id = event["trace_id"]

        reserved = await self.idempotency_store.reserve_job_processing(job_id)
        if not reserved:
            return True, None

        started_at = perf_counter()
        try:
            async with self.session_factory() as session:
                job_repository = SqlAlchemyJobRepository(session)
                event_repository = SqlAlchemyJobEventRepository(session)

                await job_repository.update_status(job_id, JobStatus.PROCESSING.value)
                await event_repository.add(
                    build_event(
                        job_id=job_id,
                        event_type=EventType.PROCESSING_STARTED,
                        source="worker",
                        trace_id=trace_id,
                        payload={},
                    )
                )
                await session.commit()

            result = await self.processor.process(event["payload"]["request"])

            async with self.session_factory() as session:
                job_repository = SqlAlchemyJobRepository(session)
                event_repository = SqlAlchemyJobEventRepository(session)
                await job_repository.update_status(
                    job_id,
                    JobStatus.SUCCESS.value,
                    result=result,
                    clear_error=True,
                )
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
                        source="worker",
                        trace_id=trace_id,
                        payload={"error": str(exc)},
                    )
                )
                await session.commit()
            JOB_FAILURE_TOTAL.inc()
            await self.idempotency_store.complete_job_processing(job_id, success=False)
            return False, str(exc)
        finally:
            JOB_PROCESSING_SECONDS.observe(perf_counter() - started_at)
