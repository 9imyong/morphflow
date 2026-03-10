from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from prometheus_client import start_http_server
from redis.asyncio import from_url

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.logging import configure_logging
from app.workers.roles import build_worker_role, resolve_worker_group_id, resolve_worker_topic


logger = logging.getLogger(__name__)


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings)
    start_http_server(settings.worker_metrics_port)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    redis = from_url(settings.redis_url, decode_responses=True)
    role_handler = build_worker_role(settings=settings, session_factory=session_factory, redis=redis)
    consume_topic = resolve_worker_topic(settings)
    consumer_group = resolve_worker_group_id(settings)

    consumer = AIOKafkaConsumer(
        consume_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=consumer_group,
        enable_auto_commit=False,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        auto_offset_reset="earliest",
    )

    await consumer.start()
    logger.info("worker started role=%s topic=%s group_id=%s", settings.worker_role, consume_topic, consumer_group)
    try:
        async for message in consumer:
            await role_handler.handle_event(message.value)
            await consumer.commit()
    finally:
        await consumer.stop()
        await redis.aclose()
        await engine.dispose()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
