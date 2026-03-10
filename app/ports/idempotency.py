from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class IdempotencyRecord:
    key: str
    job_id: str | None
    status: str


class IdempotencyPort:
    async def get_request_record(self, key: str) -> IdempotencyRecord | None:
        raise NotImplementedError

    async def reserve_request(self, key: str, job_id: str) -> bool:
        raise NotImplementedError

    async def complete_request(self, key: str, job_id: str) -> None:
        raise NotImplementedError

    async def reserve_job_processing(self, job_id: str) -> bool:
        raise NotImplementedError

    async def complete_job_processing(self, job_id: str, success: bool) -> None:
        raise NotImplementedError
