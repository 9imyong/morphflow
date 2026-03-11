from __future__ import annotations

import logging
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.cache.redis_idempotency import RedisIdempotencyStore
from app.adapters.processing.downstream_dummy import DownstreamDummyProcessor
from app.adapters.processing.factory import build_primary_processor
from app.application.pipeline_services import DownstreamPipelineService, InferencePipelineService
from app.application.worker_service import WorkerService
from app.core.config import Settings
from app.ports.publisher import EventPublisherPort
from app.ports.worker_role import WorkerRolePort


logger = logging.getLogger(__name__)


class UnifiedWorkerRole(WorkerRolePort):
    role_name = "unified"

    def __init__(self, service: Any) -> None:
        self._service = service

    async def handle_event(self, event: dict) -> tuple[bool, str | None]:
        return await self._service.handle_event(event)


class InferenceWorkerRole(WorkerRolePort):
    role_name = "inference"

    def __init__(self, service: Any) -> None:
        self._service = service

    async def handle_event(self, event: dict) -> tuple[bool, str | None]:
        # In C/BC mode this role runs inference and publishes downstream events.
        return await self._service.handle_event(event)


class DownstreamWorkerRole(WorkerRolePort):
    role_name = "downstream"

    def __init__(self, service: Any) -> None:
        self._service = service

    async def handle_event(self, event: dict) -> tuple[bool, str | None]:
        # In C/BC mode this role finalizes job with downstream post-processing.
        return await self._service.handle_event(event)


def build_worker_role(
    *,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    publisher: EventPublisherPort,
) -> WorkerRolePort:
    if settings.worker_role == "unified":
        service = WorkerService(
            session_factory=session_factory,
            idempotency_store=RedisIdempotencyStore(
                redis=redis,
                ttl_seconds=settings.idempotency_ttl_seconds,
                processing_ttl_seconds=settings.worker_processing_ttl_seconds,
            ),
            processor=build_primary_processor(settings),
        )
        return UnifiedWorkerRole(service)
    if settings.worker_role == "inference":
        if settings.architecture_mode in {"C", "BC"}:
            service = InferencePipelineService(
                session_factory=session_factory,
                idempotency_store=RedisIdempotencyStore(
                    redis=redis,
                    ttl_seconds=settings.idempotency_ttl_seconds,
                    processing_ttl_seconds=settings.worker_processing_ttl_seconds,
                ),
                processor=build_primary_processor(settings),
                publisher=publisher,
                downstream_topic=settings.kafka_downstream_topic,
            )
        else:
            service = WorkerService(
                session_factory=session_factory,
                idempotency_store=RedisIdempotencyStore(
                    redis=redis,
                    ttl_seconds=settings.idempotency_ttl_seconds,
                    processing_ttl_seconds=settings.worker_processing_ttl_seconds,
                ),
                processor=build_primary_processor(settings),
            )
        return InferenceWorkerRole(service)
    if settings.worker_role == "downstream":
        if settings.architecture_mode in {"C", "BC"}:
            service = DownstreamPipelineService(
                session_factory=session_factory,
                processor=DownstreamDummyProcessor(base_latency_ms=settings.downstream_simulated_latency_ms),
            )
        else:
            service = WorkerService(
                session_factory=session_factory,
                idempotency_store=RedisIdempotencyStore(
                    redis=redis,
                    ttl_seconds=settings.idempotency_ttl_seconds,
                    processing_ttl_seconds=settings.worker_processing_ttl_seconds,
                ),
                processor=build_primary_processor(settings),
            )
        return DownstreamWorkerRole(service)

    logger.warning("Unknown worker_role=%s, fallback to unified", settings.worker_role)
    service = WorkerService(
        session_factory=session_factory,
        idempotency_store=RedisIdempotencyStore(
            redis=redis,
            ttl_seconds=settings.idempotency_ttl_seconds,
            processing_ttl_seconds=settings.worker_processing_ttl_seconds,
        ),
        processor=build_primary_processor(settings),
    )
    return UnifiedWorkerRole(service)


def resolve_worker_topic(settings: Settings) -> str:
    if settings.worker_role == "unified":
        return settings.kafka_request_topic
    if settings.worker_role == "inference":
        # Inference consumes the same ingress stream in B/C/BC modes.
        return settings.kafka_request_topic
    return settings.kafka_downstream_topic


def resolve_worker_group_id(settings: Settings) -> str:
    mode = settings.architecture_mode.lower()
    if settings.worker_role == "unified":
        return f"architecture-{mode}-worker"
    return f"architecture-{mode}-worker-{settings.worker_role}"
