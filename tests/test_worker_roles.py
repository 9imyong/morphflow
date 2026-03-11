from __future__ import annotations

from app.core.config import Settings
from app.workers.roles import resolve_worker_group_id, resolve_worker_retry_topic, resolve_worker_topic


def _settings(role: str, mode: str = "A") -> Settings:
    return Settings(
        architecture_mode=mode,
        worker_role=role,
        kafka_request_topic="request-topic",
        kafka_inference_topic="inference-topic",
        kafka_retry_topic_request="retry-topic",
        kafka_retry_topic_downstream="retry-downstream-topic",
        kafka_downstream_topic="downstream-topic",
    )


def test_unified_role_topic_and_group() -> None:
    settings = _settings("unified")
    assert resolve_worker_topic(settings) == "request-topic"
    assert resolve_worker_retry_topic(settings) == "retry-topic"
    assert resolve_worker_group_id(settings) == "architecture-main-worker"


def test_inference_role_topic_and_group() -> None:
    settings = _settings("inference")
    assert resolve_worker_topic(settings) == "request-topic"
    assert resolve_worker_retry_topic(settings) == "retry-topic"
    assert resolve_worker_group_id(settings) == "architecture-main-worker"


def test_downstream_role_topic_and_group() -> None:
    settings = _settings("downstream")
    assert resolve_worker_topic(settings) == "downstream-topic"
    assert resolve_worker_retry_topic(settings) == "retry-downstream-topic"
    assert resolve_worker_group_id(settings) == "architecture-main-worker-downstream"


def test_group_id_is_stable_across_architecture_modes() -> None:
    inference_c = _settings("inference", mode="C")
    downstream_c = _settings("downstream", mode="C")
    unified_b = _settings("unified", mode="B")
    unified_bc = _settings("unified", mode="BC")

    assert resolve_worker_group_id(inference_c) == "architecture-main-worker"
    assert resolve_worker_group_id(downstream_c) == "architecture-main-worker-downstream"
    assert resolve_worker_group_id(unified_b) == "architecture-main-worker"
    assert resolve_worker_group_id(unified_bc) == "architecture-main-worker"
