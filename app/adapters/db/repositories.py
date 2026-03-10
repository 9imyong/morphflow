from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import JobEventModel, JobModel
from app.domain.models import Job, JobStatus


class SqlAlchemyJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, job: Job) -> None:
        self.session.add(
            JobModel(
                id=job.id,
                request_payload=job.request_payload,
                status=job.status.value,
                retry_count=job.retry_count,
                result=job.result,
                error_message=job.error,
            )
        )

    async def get(self, job_id: str) -> Job | None:
        model = await self.session.get(JobModel, job_id)
        if model is None:
            return None
        return Job(
            id=model.id,
            status=JobStatus(model.status),
            request_payload=model.request_payload,
            result=model.result,
            error=model.error_message,
            retry_count=model.retry_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def update_status(
        self,
        job_id: str,
        status: str,
        *,
        result: dict | None = None,
        error: str | None = None,
    ) -> Job | None:
        model = await self.session.get(JobModel, job_id)
        if model is None:
            return None
        model.status = status
        if result is not None:
            model.result = result
        if error is not None:
            model.error_message = error
        await self.session.flush()
        # Keep model state fully loaded in async context to avoid lazy-load after flush.
        await self.session.refresh(model)
        return Job(
            id=model.id,
            status=JobStatus(model.status),
            request_payload=model.request_payload,
            result=model.result,
            error=model.error_message,
            retry_count=model.retry_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class SqlAlchemyJobEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, event: dict) -> None:
        self.session.add(
            JobEventModel(
                event_id=event["event_id"],
                job_id=event["job_id"],
                event_type=event["event_type"],
                source=event["source"],
                trace_id=event["trace_id"],
                payload=event["payload"],
            )
        )

    async def list_for_job(self, job_id: str) -> list[JobEventModel]:
        result = await self.session.execute(select(JobEventModel).where(JobEventModel.job_id == job_id))
        return list(result.scalars())
