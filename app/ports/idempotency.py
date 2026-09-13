from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class IdempotencyRecord:
    key: str
    job_id: str | None
    status: str


class IdempotencyPort:
    """요청 단위 멱등성만 담당한다.

    작업 소유권은 jobs 테이블의 lease 가 맡는다. Redis TTL 기반 락은
    만료 순간 두 워커가 같은 job 을 처리하는 것을 막지 못했다.
    """

    async def get_request_record(self, key: str) -> IdempotencyRecord | None:
        raise NotImplementedError

    async def reserve_request(self, key: str, job_id: str) -> bool:
        raise NotImplementedError

    async def complete_request(self, key: str, job_id: str) -> None:
        raise NotImplementedError
