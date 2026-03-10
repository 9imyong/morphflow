from __future__ import annotations

from app.core.config import Settings
from app.workers.roles import resolve_worker_group_id, resolve_worker_topic


def _settings(role: str) -> Settings:
    return Settings(
        worker_role=role,
        kafka_request_topic="request-topic",
        kafka_inference_topic="inference-topic",
        kafka_downstream_topic="downstream-topic",
    )


def test_unified_role_topic_and_group() -> None:
    settings = _settings("unified")
    assert resolve_worker_topic(settings) == "request-topic"
    assert resolve_worker_group_id(settings) == "architecture-a-worker"


def test_inference_role_topic_and_group() -> None:
    settings = _settings("inference")
    assert resolve_worker_topic(settings) == "inference-topic"
    assert resolve_worker_group_id(settings) == "architecture-a-worker-inference"


def test_downstream_role_topic_and_group() -> None:
    settings = _settings("downstream")
    assert resolve_worker_topic(settings) == "downstream-topic"
    assert resolve_worker_group_id(settings) == "architecture-a-worker-downstream"
