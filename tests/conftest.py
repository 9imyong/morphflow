from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.adapters.db.models import Base
from app.ports.idempotency import IdempotencyPort, IdempotencyRecord
from app.ports.publisher import EventPublisherPort
from app.ports.task_processor import TaskProcessorPort


class InMemoryIdempotencyStore(IdempotencyPort):
    def __init__(self) -> None:
        self._request_records: dict[str, IdempotencyRecord] = {}
        self._job_records: dict[str, IdempotencyRecord] = {}

    async def get_request_record(self, key: str) -> IdempotencyRecord | None:
        return self._request_records.get(key)

    async def reserve_request(self, key: str, job_id: str) -> bool:
        if key in self._request_records:
            return False
        self._request_records[key] = IdempotencyRecord(key=key, job_id=job_id, status="PROCESSING")
        return True

    async def complete_request(self, key: str, job_id: str) -> None:
        self._request_records[key] = IdempotencyRecord(key=key, job_id=job_id, status="COMPLETED")

    async def reserve_job_processing(self, job_id: str) -> bool:
        if job_id in self._job_records and self._job_records[job_id].status == "COMPLETED":
            return False
        if job_id in self._job_records and self._job_records[job_id].status == "PROCESSING":
            return False
        self._job_records[job_id] = IdempotencyRecord(key=job_id, job_id=job_id, status="PROCESSING")
        return True

    async def complete_job_processing(self, job_id: str, success: bool) -> None:
        status = "COMPLETED" if success else "FAILED"
        self._job_records[job_id] = IdempotencyRecord(key=job_id, job_id=job_id, status=status)


class CapturingPublisher(EventPublisherPort):
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish(self, topic: str, event: dict) -> None:
        self.published.append((topic, event))


class SuccessProcessor(TaskProcessorPort):
    async def process(self, payload: dict) -> dict:
        return {"echo": payload}


class FailingProcessor(TaskProcessorPort):
    async def process(self, payload: dict) -> dict:
        raise RuntimeError("processor failed")


@dataclass
class TestContainer:
    job_service_obj: object

    def job_service(self) -> object:
        return self.job_service_obj


@pytest_asyncio.fixture
async def session_factory(tmp_path: Path) -> async_sessionmaker[AsyncSession]:
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
def idempotency_store() -> InMemoryIdempotencyStore:
    return InMemoryIdempotencyStore()


@pytest.fixture
def publisher() -> CapturingPublisher:
    return CapturingPublisher()
