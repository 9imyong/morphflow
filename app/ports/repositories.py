from __future__ import annotations

from app.domain.models import Job


class JobRepositoryPort:
    async def add(self, job: Job) -> None:
        raise NotImplementedError

    async def get(self, job_id: str) -> Job | None:
        raise NotImplementedError

    async def update_status(
        self,
        job_id: str,
        status: str,
        *,
        result: dict | None = None,
        error: str | None = None,
        clear_error: bool = False,
    ) -> Job | None:
        raise NotImplementedError


class JobEventRepositoryPort:
    async def add(self, event: dict) -> None:
        raise NotImplementedError
