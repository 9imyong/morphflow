"""outbox_messages 에 쌓인 메시지를 Kafka 로 내보내는 릴레이.

상태 변경과 발행을 한 트랜잭션에 묶을 수는 없다(DB 와 Kafka 는 서로 다른
자원이다). 대신 발행할 메시지를 상태 변경과 같은 트랜잭션에 적재해 두고,
커밋된 뒤 이 릴레이가 읽어 발행한다. 발행 직전에 프로세스가 죽어도 행이
PENDING 으로 남아 다음 주기에 다시 나간다.

전달 보장은 at-least-once 다. 같은 메시지가 두 번 나갈 수 있으므로 소비
측의 멱등 처리가 함께 있어야 한다.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.db.repositories import SqlAlchemyOutboxRepository
from app.core.metrics import (
    OUTBOX_PENDING_BACKLOG,
    OUTBOX_PUBLISH_FAILURE_TOTAL,
    OUTBOX_PUBLISHED_TOTAL,
)

logger = logging.getLogger(__name__)


class OutboxRelay:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        publisher: Any,
        batch_size: int,
        poll_interval_seconds: float,
    ) -> None:
        self._session_factory = session_factory
        self._publisher = publisher
        self._batch_size = max(1, batch_size)
        self._poll_interval = max(0.05, poll_interval_seconds)
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def drain_once(self) -> int:
        """대기 중인 메시지를 한 배치 발행하고 발행 건수를 돌려준다."""
        published = 0
        async with self._session_factory() as session:
            async with session.begin():
                repository = SqlAlchemyOutboxRepository(session)
                messages = await repository.fetch_pending(self._batch_size)
                if not messages:
                    OUTBOX_PENDING_BACKLOG.set(0)
                    return 0

                OUTBOX_PENDING_BACKLOG.set(len(messages))
                sent_ids: list[int] = []
                for message in messages:
                    try:
                        await self._publisher.publish(
                            message["topic"],
                            message["payload"],
                            headers=message["headers"] or None,
                        )
                    except Exception as exc:
                        # 실패한 메시지는 PENDING 으로 남겨 다음 주기에 재시도한다.
                        # 순서를 지키기 위해 이 배치의 남은 메시지는 건드리지 않는다.
                        OUTBOX_PUBLISH_FAILURE_TOTAL.inc()
                        await repository.mark_failed(message["id"], f"{type(exc).__name__}: {exc}")
                        logger.warning(
                            "outbox publish failed message_id=%s topic=%s error=%s",
                            message["message_id"],
                            message["topic"],
                            type(exc).__name__,
                        )
                        break
                    sent_ids.append(message["id"])
                    published += 1

                await repository.mark_published(sent_ids)

        if published:
            OUTBOX_PUBLISHED_TOTAL.inc(published)
        return published

    async def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                published = await self.drain_once()
            except Exception:
                logger.exception("outbox relay iteration failed")
                published = 0
            if published == 0:
                # 보낼 게 없을 때만 쉰다. 밀려 있으면 연속으로 비운다.
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._poll_interval)
                except asyncio.TimeoutError:
                    pass

    def start(self) -> None:
        if self._task is None:
            self._stopping.clear()
            self._task = asyncio.create_task(self._loop(), name="outbox-relay")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stopping.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
