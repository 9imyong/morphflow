from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings


logger = logging.getLogger(__name__)

_TRACING_AVAILABLE = True
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.aiokafka import AIOKafkaInstrumentor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except Exception:  # pragma: no cover - optional dependency fallback
    _TRACING_AVAILABLE = False
    trace = None  # type: ignore[assignment]
    OTLPSpanExporter = None  # type: ignore[assignment]
    AIOKafkaInstrumentor = None  # type: ignore[assignment]
    FastAPIInstrumentor = None  # type: ignore[assignment]
    RedisInstrumentor = None  # type: ignore[assignment]
    SQLAlchemyInstrumentor = None  # type: ignore[assignment]
    Resource = None  # type: ignore[assignment]
    TracerProvider = None  # type: ignore[assignment]
    BatchSpanProcessor = None  # type: ignore[assignment]

_redis_instrumented = False
_aiokafka_instrumented = False
_sqlalchemy_engines: set[int] = set()


def _build_provider(settings: Settings, service_name: str) -> Any | None:
    if not settings.tracing_enabled:
        return None
    if not _TRACING_AVAILABLE:
        logger.warning("Tracing dependencies are not installed; tracing disabled")
        return None

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def setup_fastapi_tracing(app: Any, settings: Settings) -> None:
    provider = _build_provider(settings, settings.otel_service_name_api)
    if provider is None:
        return
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor().instrument_app(app, tracer_provider=provider)
    logger.info("OpenTelemetry tracing enabled for API endpoint=%s", settings.otel_exporter_otlp_endpoint)


def setup_worker_tracing(settings: Settings) -> Any:
    service_name = settings.otel_service_name_worker
    # Keep backward compatibility while splitting worker traces by role.
    if service_name == "morphflow-worker":
        service_name = f"morphflow-worker-{settings.worker_role}"

    provider = _build_provider(settings, service_name)
    if provider is None:
        return None
    trace.set_tracer_provider(provider)
    logger.info(
        "OpenTelemetry tracing enabled for worker endpoint=%s service_name=%s role=%s",
        settings.otel_exporter_otlp_endpoint,
        service_name,
        settings.worker_role,
    )
    return trace.get_tracer(service_name)


def instrument_runtime_libraries(*, engine: Any | None = None, redis_client: Any | None = None) -> None:
    if not _TRACING_AVAILABLE:
        return

    global _redis_instrumented, _aiokafka_instrumented

    # Auto-instrument aiokafka producer/consumer spans.
    if not _aiokafka_instrumented:
        AIOKafkaInstrumentor().instrument()
        _aiokafka_instrumented = True

    # Auto-instrument Redis command spans.
    if not _redis_instrumented:
        RedisInstrumentor().instrument()
        _redis_instrumented = True

    # Auto-instrument SQLAlchemy spans per concrete engine.
    if engine is not None:
        target_engine = getattr(engine, "sync_engine", engine)
        engine_id = id(target_engine)
        if engine_id not in _sqlalchemy_engines:
            SQLAlchemyInstrumentor().instrument(engine=target_engine)
            _sqlalchemy_engines.add(engine_id)


def shutdown_tracing() -> None:
    if not _TRACING_AVAILABLE:
        return
    provider = trace.get_tracer_provider()
    shutdown = getattr(provider, "shutdown", None)
    if callable(shutdown):
        shutdown()
