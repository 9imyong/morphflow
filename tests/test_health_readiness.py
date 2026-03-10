from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_container
from app.api.routes import health


class FakeSession:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    async def execute(self, _query) -> None:
        if self.should_fail:
            raise RuntimeError("db unavailable")


class FakeSessionFactory:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def __call__(self):
        return self

    async def __aenter__(self) -> FakeSession:
        return FakeSession(should_fail=self.should_fail)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakeRedis:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    async def ping(self) -> None:
        if self.should_fail:
            raise RuntimeError("redis unavailable")


class FakePublisher:
    def __init__(self, is_ready: bool = True, detail: str = "ok") -> None:
        self.is_ready = is_ready
        self.detail = detail

    async def readiness(self) -> tuple[bool, str]:
        return self.is_ready, self.detail


@dataclass
class FakeContainer:
    session_factory: FakeSessionFactory
    redis: FakeRedis
    publisher: FakePublisher


def _build_test_app(container: FakeContainer) -> FastAPI:
    app = FastAPI()
    app.include_router(health.router)
    app.dependency_overrides[get_container] = lambda: container
    return app


def test_ready_returns_200_when_all_dependencies_are_healthy() -> None:
    container = FakeContainer(
        session_factory=FakeSessionFactory(should_fail=False),
        redis=FakeRedis(should_fail=False),
        publisher=FakePublisher(is_ready=True, detail="ok"),
    )
    app = _build_test_app(container)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["details"] == {"database": "ok", "redis": "ok", "kafka": "ok"}


def test_ready_returns_503_when_kafka_is_not_ready() -> None:
    container = FakeContainer(
        session_factory=FakeSessionFactory(should_fail=False),
        redis=FakeRedis(should_fail=False),
        publisher=FakePublisher(is_ready=False, detail="kafka bootstrap not ready"),
    )
    app = _build_test_app(container)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["details"]["kafka"] == "error"
    assert "kafka bootstrap not ready" in body["dependencies"]["kafka"]["detail"]
