from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import from_url

from app.adapters.messaging.kafka import KafkaEventPublisher
from app.adapters.messaging.outbox_relay import OutboxRelay
from app.core.config import get_settings
from app.core.container import AppContainer
from app.core.database import create_engine, create_session_factory
from app.core.kafka_topics import ensure_kafka_topics
from app.core.logging import configure_logging
from app.core.tracing import instrument_runtime_libraries, shutdown_tracing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    redis = from_url(settings.redis_url, decode_responses=True)
    instrument_runtime_libraries(engine=engine, redis_client=redis)
    await ensure_kafka_topics(settings)
    publisher = KafkaEventPublisher(settings.kafka_bootstrap_servers)
    await publisher.start()
    # API 는 Kafka 로 직접 쏘지 않고 outbox 에 적재만 한다. 실제 발행은 릴레이가 맡는다.
    outbox_relay = OutboxRelay(
        session_factory=session_factory,
        publisher=publisher,
        batch_size=settings.outbox_relay_batch_size,
        poll_interval_seconds=settings.outbox_relay_poll_interval_seconds,
    )
    outbox_relay.start()
    app.state.container = AppContainer(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        redis=redis,
        publisher=publisher,
    )
    app.state.outbox_relay = outbox_relay
    try:
        yield
    finally:
        await outbox_relay.stop()
        await publisher.stop()
        await redis.aclose()
        await engine.dispose()
        shutdown_tracing()
