from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import JobEventModel, JobModel, OutboxMessageModel
from app.domain.models import Job, JobStatus, allowed_source_statuses

# 행 잠금(SELECT ... FOR UPDATE SKIP LOCKED)을 지원하는 방언
_ROW_LOCK_DIALECTS = frozenset({"postgresql", "mysql", "mariadb"})


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
        clear_error: bool = False,
        expected_statuses: Sequence[str] | None = None,
    ) -> Job | None:
        """조건부 UPDATE 로 상태를 바꾸고, 실제로 바뀐 경우에만 Job 을 돌려준다.

        읽고-바꾸고-쓰는 방식은 두 워커가 같은 job 을 잡았을 때 늦게 끝난
        쪽이 앞선 결과를 덮어쓴다. WHERE 에 현재 상태를 걸고 rowcount 로
        승패를 판정한다.
        """
        target = JobStatus(status)
        sources = (
            frozenset(JobStatus(s) for s in expected_statuses)
            if expected_statuses is not None
            else allowed_source_statuses(target)
        )
        if not sources:
            raise ValueError(f"no allowed source status for transition to {target}")

        values: dict[str, object] = {"status": target.value, "updated_at": func.now()}
        if result is not None:
            values["result"] = result
        if clear_error:
            values["error_message"] = None
        elif error is not None:
            values["error_message"] = error

        statement = (
            update(JobModel)
            .where(JobModel.id == job_id, JobModel.status.in_([s.value for s in sources]))
            .values(**values)
            .returning(JobModel)
        )
        row = (await self.session.execute(statement)).scalar_one_or_none()
        if row is None:
            # 행이 없거나, 이미 다른 전이가 일어나 조건을 벗어났다.
            return None
        return Job(
            id=row.id,
            status=JobStatus(row.status),
            request_payload=row.request_payload,
            result=row.result,
            error=row.error_message,
            retry_count=row.retry_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
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


class SqlAlchemyOutboxRepository:
    """상태 변경과 같은 트랜잭션에 발행 예정 메시지를 적재한다."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, *, topic: str, payload: dict, headers: dict[str, str] | None = None) -> str:
        message_id = str(uuid4())
        self.session.add(
            OutboxMessageModel(
                message_id=message_id,
                topic=topic,
                payload=payload,
                headers=headers,
                status="PENDING",
            )
        )
        return message_id

    async def fetch_pending(self, limit: int) -> list[dict]:
        """발행 대기 메시지를 가져온다.

        여러 릴레이가 동시에 돌 수 있으므로 행을 잠가 같은 메시지를 두 번
        보내지 않게 한다. SQLite 처럼 행 잠금이 없는 방언에서는 생략한다
        (테스트 전용이고 릴레이도 하나만 돈다).
        """
        statement = (
            select(OutboxMessageModel)
            .where(OutboxMessageModel.status == "PENDING")
            .order_by(OutboxMessageModel.id)
            .limit(limit)
        )
        if self.session.bind is not None and self.session.bind.dialect.name in _ROW_LOCK_DIALECTS:
            statement = statement.with_for_update(skip_locked=True)
        rows = (await self.session.execute(statement)).scalars().all()
        return [
            {
                "id": row.id,
                "message_id": row.message_id,
                "topic": row.topic,
                "payload": row.payload,
                "headers": row.headers,
                "attempts": row.attempts,
            }
            for row in rows
        ]

    async def mark_published(self, message_ids: Sequence[int]) -> None:
        if not message_ids:
            return
        await self.session.execute(
            update(OutboxMessageModel)
            .where(OutboxMessageModel.id.in_(list(message_ids)))
            .values(status="PUBLISHED", published_at=datetime.now(timezone.utc), last_error=None)
        )

    async def mark_failed(self, message_id: int, error: str) -> None:
        # 상태는 PENDING 으로 둔다. 다음 주기에 다시 집어 재발행한다.
        await self.session.execute(
            update(OutboxMessageModel)
            .where(OutboxMessageModel.id == message_id)
            .values(attempts=OutboxMessageModel.attempts + 1, last_error=error[:500])
        )
