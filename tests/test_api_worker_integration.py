from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.db.repositories import SqlAlchemyJobEventRepository
from app.api.dependencies import get_container
from app.api.routes import jobs
from app.application.job_service import JobService
from app.application.worker_service import WorkerService
from app.domain.models import JobStatus


class SuccessProcessor:
    async def process(self, payload: dict) -> dict:
        return {"echo": payload}


class FailingProcessor:
    async def process(self, payload: dict) -> dict:
        raise RuntimeError("processor failed")


@dataclass
class AppTestContainer:
    job_service_obj: object

    def job_service(self) -> object:
        return self.job_service_obj


@pytest.fixture
def app_with_job_service(session_factory, idempotency_store, publisher):
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        publisher=publisher,
        topic="request-topic",
    )
    app = FastAPI()
    app.include_router(jobs.router)
    app.dependency_overrides[get_container] = lambda: AppTestContainer(job_service_obj=job_service)
    return app, job_service, publisher


@pytest.mark.asyncio
async def test_post_jobs_creates_pending_job(app_with_job_service):
    app, job_service, _publisher = app_with_job_service

    with TestClient(app) as client:
        response = client.post(
            "/jobs",
            headers={"Idempotency-Key": "key-post-create"},
            json={"input": {"type": "text", "content": "hello"}, "options": {"priority": "normal"}},
        )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == JobStatus.PENDING.value
    saved = await job_service.get_job(body["job_id"])
    assert saved is not None
    assert saved.status == JobStatus.PENDING


@pytest.mark.asyncio
async def test_get_jobs_returns_current_status(app_with_job_service):
    app, job_service, _publisher = app_with_job_service
    created = await job_service.create_job(
        payload={"input": {"type": "text", "content": "status"}, "options": {}},
        idempotency_key="key-get-status",
    )

    with TestClient(app) as client:
        response = client.get(f"/jobs/{created.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == created.id
    assert body["status"] == JobStatus.PENDING.value


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_returns_same_job_id(app_with_job_service):
    app, _job_service, _publisher = app_with_job_service

    with TestClient(app) as client:
        first = client.post(
            "/jobs",
            headers={"Idempotency-Key": "dup-key-1"},
            json={"input": {"type": "text", "content": "dup"}, "options": {}},
        )
        second = client.post(
            "/jobs",
            headers={"Idempotency-Key": "dup-key-1"},
            json={"input": {"type": "text", "content": "dup"}, "options": {}},
        )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]


@pytest.mark.asyncio
async def test_worker_success_path_updates_status_and_events(session_factory, idempotency_store, publisher):
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        publisher=publisher,
        topic="request-topic",
    )
    worker_service = WorkerService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        processor=SuccessProcessor(),
    )

    created = await job_service.create_job(
        payload={"input": {"type": "text", "content": "worker-success"}, "options": {}},
        idempotency_key="worker-success-key",
    )
    assert created.status == JobStatus.PENDING

    event = publisher.published[-1][1]
    await worker_service.handle_event(event)

    updated = await job_service.get_job(created.id)
    assert updated is not None
    assert updated.status == JobStatus.SUCCESS
    assert updated.result is not None

    async with session_factory() as session:
        events = await SqlAlchemyJobEventRepository(session).list_for_job(created.id)
    event_types = [item.event_type for item in events]
    assert "PROCESSING_STARTED" in event_types
    assert "PROCESSING_COMPLETED" in event_types


@pytest.mark.asyncio
async def test_worker_failure_sets_failed_status(session_factory, idempotency_store, publisher):
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        publisher=publisher,
        topic="request-topic",
    )
    worker_service = WorkerService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        processor=FailingProcessor(),
    )

    created = await job_service.create_job(
        payload={"input": {"type": "text", "content": "worker-fail"}, "options": {}},
        idempotency_key="worker-fail-key",
    )

    event = publisher.published[-1][1]
    await worker_service.handle_event(event)

    failed = await job_service.get_job(created.id)
    assert failed is not None
    assert failed.status == JobStatus.FAILED
    assert failed.error is not None
    assert "processor failed" in failed.error


@pytest.mark.asyncio
async def test_duplicate_consume_is_idempotent(session_factory, idempotency_store, publisher):
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        publisher=publisher,
        topic="request-topic",
    )
    worker_service = WorkerService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        processor=SuccessProcessor(),
    )

    created = await job_service.create_job(
        payload={"input": {"type": "text", "content": "dup-consume"}, "options": {}},
        idempotency_key="dup-consume-key",
    )
    event = publisher.published[-1][1]

    await worker_service.handle_event(event)
    await worker_service.handle_event(event)

    updated = await job_service.get_job(created.id)
    assert updated is not None
    assert updated.status == JobStatus.SUCCESS

    async with session_factory() as session:
        events = await SqlAlchemyJobEventRepository(session).list_for_job(created.id)
    counter = Counter(item.event_type for item in events)
    assert counter["PROCESSING_STARTED"] == 1
    assert counter["PROCESSING_COMPLETED"] == 1
