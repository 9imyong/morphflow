from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.container import AppContainer


@dataclass
class DummyPublisher:
    async def publish(self, topic: str, event: dict, headers: dict[str, str] | None = None) -> None:
        return None


@dataclass
class DummyRedis:
    async def get(self, key: str):
        return None

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        return True


def _container(settings: Settings) -> AppContainer:
    return AppContainer(
        settings=settings,
        engine=None,  # type: ignore[arg-type]
        session_factory=None,  # type: ignore[arg-type]
        redis=DummyRedis(),  # type: ignore[arg-type]
        publisher=DummyPublisher(),  # type: ignore[arg-type]
    )


def test_job_service_uses_request_topic_in_mode_a() -> None:
    settings = Settings(architecture_mode="A", kafka_request_topic="request-topic", kafka_inference_topic="inference-topic")
    container = _container(settings)
    assert container.job_service().topic == "request-topic"


def test_job_service_uses_inference_topic_in_mode_b() -> None:
    settings = Settings(architecture_mode="B", kafka_request_topic="request-topic", kafka_inference_topic="inference-topic")
    container = _container(settings)
    assert container.job_service().topic == "inference-topic"


def test_job_service_uses_inference_topic_in_mode_c() -> None:
    settings = Settings(architecture_mode="C", kafka_request_topic="request-topic", kafka_inference_topic="inference-topic")
    container = _container(settings)
    assert container.job_service().topic == "inference-topic"
