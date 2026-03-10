from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.db.repositories import SqlAlchemyJobEventRepository, SqlAlchemyJobRepository
from app.core.metrics import JOB_CREATED_TOTAL, JOB_DUPLICATE_TOTAL
from app.domain.events import EventType, build_event
from app.domain.models import Job, JobStatus
from app.ports.idempotency import IdempotencyPort
from app.ports.publisher import EventPublisherPort


class JobService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        idempotency_store: IdempotencyPort,
        publisher: EventPublisherPort,
        topic: str,
    ) -> None:
        self.session_factory = session_factory
        self.idempotency_store = idempotency_store
        self.publisher = publisher
        self.topic = topic

    async def create_job(self, payload: dict, idempotency_key: str | None) -> Job:
        request_key = idempotency_key or str(uuid4())
        existing = await self.idempotency_store.get_request_record(request_key)
        if existing and existing.job_id:
            JOB_DUPLICATE_TOTAL.inc()
            job = await self.get_job(existing.job_id)
            if job is None:
                raise ValueError(f"Idempotent job not found for key {request_key}")
            return job

        job_id = str(uuid4())
        trace_id = str(uuid4())
        reserved = await self.idempotency_store.reserve_request(request_key, job_id)
        if not reserved:
            existing = await self.idempotency_store.get_request_record(request_key)
            if existing and existing.job_id:
                JOB_DUPLICATE_TOTAL.inc()
                job = await self.get_job(existing.job_id)
                if job is None:
                    raise ValueError(f"Idempotent job not found for key {request_key}")
                return job
            raise ValueError("Unable to reserve idempotency key")

        event = build_event(
            job_id=job_id,
            event_type=EventType.REQUESTED,
            source="api",
            trace_id=trace_id,
            payload={"request": payload},
        )
        job = Job(id=job_id, status=JobStatus.PENDING, request_payload=payload)

        async with self.session_factory() as session:
            job_repository = SqlAlchemyJobRepository(session)
            event_repository = SqlAlchemyJobEventRepository(session)
            await job_repository.add(job)
            await event_repository.add(event)
            await session.commit()

        await self.publisher.publish(self.topic, event)
        await self.idempotency_store.complete_request(request_key, job_id)
        JOB_CREATED_TOTAL.inc()
        return job

    async def get_job(self, job_id: str) -> Job | None:
        async with self.session_factory() as session:
            job_repository = SqlAlchemyJobRepository(session)
            return await job_repository.get(job_id)
