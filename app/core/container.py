from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapters.cache.redis_idempotency import RedisIdempotencyStore
from app.adapters.messaging.kafka import KafkaEventPublisher
from app.adapters.processing.factory import build_primary_processor
from app.application.job_service import JobService
from app.application.worker_service import WorkerService
from app.core.config import Settings


@dataclass
class AppContainer:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis
    publisher: KafkaEventPublisher

    def job_service(self) -> JobService:
        if self.settings.architecture_mode in {"B", "C", "BC"}:
            publish_topic = self.settings.kafka_inference_topic
        else:
            publish_topic = self.settings.kafka_request_topic

        return JobService(
            session_factory=self.session_factory,
            idempotency_store=RedisIdempotencyStore(
                redis=self.redis,
                ttl_seconds=self.settings.idempotency_ttl_seconds,
                processing_ttl_seconds=self.settings.worker_processing_ttl_seconds,
            ),
            publisher=self.publisher,
            topic=publish_topic,
        )

    def worker_service(self) -> WorkerService:
        return WorkerService(
            session_factory=self.session_factory,
            idempotency_store=RedisIdempotencyStore(
                redis=self.redis,
                ttl_seconds=self.settings.idempotency_ttl_seconds,
                processing_ttl_seconds=self.settings.worker_processing_ttl_seconds,
            ),
            processor=build_primary_processor(self.settings),
        )
