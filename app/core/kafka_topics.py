from __future__ import annotations

import logging

from app.core.config import Settings


logger = logging.getLogger(__name__)


def build_topic_partition_targets(settings: Settings) -> dict[str, int]:
    worker_partitions = max(1, settings.kafka_partitions_worker_topic)
    downstream_partitions = max(1, settings.kafka_partitions_downstream_topic)
    return {
        settings.kafka_request_topic: worker_partitions,
        settings.kafka_inference_topic: worker_partitions,
        settings.kafka_retry_topic_request: worker_partitions,
        settings.kafka_retry_topic_downstream: downstream_partitions,
        settings.kafka_dlq_topic: max(1, settings.kafka_partitions_dlq),
        settings.kafka_downstream_topic: downstream_partitions,
    }


async def ensure_kafka_topics(settings: Settings) -> None:
    if not settings.kafka_topic_auto_configure:
        return

    from aiokafka.admin import AIOKafkaAdminClient, NewPartitions, NewTopic

    targets = build_topic_partition_targets(settings)
    admin = AIOKafkaAdminClient(bootstrap_servers=settings.kafka_bootstrap_servers)
    await admin.start()
    try:
        existing = set(await admin.list_topics())
        missing = [name for name in targets if name not in existing]
        if missing:
            topics = [
                NewTopic(
                    name=name,
                    num_partitions=targets[name],
                    replication_factor=max(1, settings.kafka_topic_replication_factor),
                )
                for name in missing
            ]
            await admin.create_topics(new_topics=topics)
            logger.info("created kafka topics: %s", ",".join(missing))

        described = await admin.describe_topics(list(targets.keys()))
        expand_map: dict[str, NewPartitions] = {}
        for topic_meta in described:
            name = str(topic_meta["topic"])
            current = len(topic_meta.get("partitions", []))
            target = targets.get(name, current)
            if target > current:
                expand_map[name] = NewPartitions(total_count=target)
        if expand_map:
            await admin.create_partitions(expand_map)
            logger.info(
                "expanded kafka partitions: %s",
                ",".join(f"{name}->{part.total_count}" for name, part in expand_map.items()),
            )
    finally:
        await admin.close()
