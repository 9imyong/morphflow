from __future__ import annotations

from app.core.config import Settings
from app.core.kafka_topics import build_topic_partition_targets


def test_build_topic_partition_targets_from_settings() -> None:
    settings = Settings(
        kafka_request_topic="request-topic",
        kafka_inference_topic="inference-topic",
        kafka_retry_topic_request="retry-topic",
        kafka_retry_topic_downstream="retry-downstream-topic",
        kafka_dlq_topic="dlq-topic",
        kafka_downstream_topic="downstream-topic",
        kafka_partitions_worker_topic=3,
        kafka_partitions_downstream_topic=5,
        kafka_partitions_dlq=1,
    )

    targets = build_topic_partition_targets(settings)
    assert targets == {
        "request-topic": 3,
        "inference-topic": 3,
        "retry-topic": 3,
        "retry-downstream-topic": 5,
        "dlq-topic": 1,
        "downstream-topic": 5,
    }
