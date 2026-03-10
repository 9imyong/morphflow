from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from prometheus_client import start_http_server
from redis.asyncio import from_url

from app.adapters.cache.redis_idempotency import RedisIdempotencyStore
from app.adapters.processing.dummy import DummyTaskProcessor
from app.application.worker_service import WorkerService
from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory, init_db
from app.core.logging import configure_logging


logger = logging.getLogger(__name__)


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings)
    start_http_server(settings.worker_metrics_port)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    await init_db(engine)

    redis = from_url(settings.redis_url, decode_responses=True)
    service = WorkerService(
        session_factory=session_factory,
        idempotency_store=RedisIdempotencyStore(
            redis=redis,
            ttl_seconds=settings.idempotency_ttl_seconds,
            processing_ttl_seconds=settings.worker_processing_ttl_seconds,
        ),
        processor=DummyTaskProcessor(),
    )

    consumer = AIOKafkaConsumer(
        settings.kafka_request_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="architecture-a-worker",
        enable_auto_commit=False,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        auto_offset_reset="earliest",
    )

    await consumer.start()
    logger.info("worker started")
    try:
        async for message in consumer:
            await service.handle_event(message.value)
            await consumer.commit()
    finally:
        await consumer.stop()
        await redis.aclose()
        await engine.dispose()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
