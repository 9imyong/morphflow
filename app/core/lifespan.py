from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import from_url

from app.adapters.messaging.kafka import KafkaEventPublisher
from app.core.config import get_settings
from app.core.container import AppContainer
from app.core.database import create_engine, create_session_factory
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    redis = from_url(settings.redis_url, decode_responses=True)
    publisher = KafkaEventPublisher(settings.kafka_bootstrap_servers)
    await publisher.start()
    app.state.container = AppContainer(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        redis=redis,
        publisher=publisher,
    )
    try:
        yield
    finally:
        await publisher.stop()
        await redis.aclose()
        await engine.dispose()
