from __future__ import annotations

from collections.abc import Sequence

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
        expected_statuses: Sequence[str] | None = None,
    ) -> Job | None:
        """상태를 조건부로 바꾼다.

        expected_statuses 를 주면 현재 상태가 그 안에 있을 때만 갱신하고,
        아니면 아무것도 쓰지 않고 None 을 돌려준다. 호출부는 None 을
        "경쟁에서 밀렸다"로 해석해야 한다.

        생략하면 도메인의 전이 규칙에서 출발 상태를 유도한다.
        """
        raise NotImplementedError


class JobEventRepositoryPort:
    async def add(self, event: dict) -> None:
        raise NotImplementedError


class OutboxRepositoryPort:
    async def add(self, *, topic: str, payload: dict, headers: dict[str, str] | None = None) -> str:
        """발행할 메시지를 현재 트랜잭션에 적재하고 message_id 를 돌려준다."""
        raise NotImplementedError

    async def fetch_pending(self, limit: int) -> list[dict]:
        """발행 대기 메시지를 잠그고 가져온다. 다른 릴레이와 겹치지 않는다."""
        raise NotImplementedError

    async def mark_published(self, message_ids: Sequence[int]) -> None:
        raise NotImplementedError

    async def mark_failed(self, message_id: int, error: str) -> None:
        raise NotImplementedError
