from __future__ import annotations

import asyncio
import json
import logging
from contextlib import nullcontext
from typing import Any

from aiokafka import AIOKafkaConsumer
from prometheus_client import start_http_server
from redis.asyncio import from_url

from app.adapters.messaging.kafka import KafkaEventPublisher
from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.kafka_topics import ensure_kafka_topics
from app.core.logging import configure_logging
from app.core.metrics import DLQ_MESSAGES_TOTAL, RETRY_FAILURE_TOTAL, RETRY_PUBLISHED_TOTAL
from app.core.tracing import instrument_runtime_libraries, setup_worker_tracing, shutdown_tracing
from app.workers.roles import (
    build_worker_role,
    resolve_worker_group_id,
    resolve_worker_retry_topic,
    resolve_worker_topic,
)


logger = logging.getLogger(__name__)
RETRY_COUNT_HEADER = "retry-count"
ERROR_REASON_HEADER = "error-reason"
ORIGINAL_TOPIC_HEADER = "original-topic"


def _decode_headers(headers: list[tuple[str, bytes | None]] | None) -> dict[str, str]:
    decoded: dict[str, str] = {}
    if not headers:
        return decoded
    for key, value in headers:
        if value is None:
            continue
        decoded[key] = value.decode("utf-8", errors="replace")
    return decoded


def _parse_retry_count(headers: dict[str, str]) -> int:
    raw = headers.get(RETRY_COUNT_HEADER, "0")
    try:
        value = int(raw)
    except ValueError:
        return 0
    return max(0, value)


def _compute_retry_backoff_seconds(retry_count: int, *, base: float, multiplier: float, max_seconds: float) -> float:
    retry_count = max(1, retry_count)
    delay = base * (multiplier ** (retry_count - 1))
    return min(delay, max_seconds)


async def _handle_message(
    *,
    message: Any,
    tracer: Any,
    consumer_group: str,
    consume_topic: str,
    retry_topic: str,
    role_handler: Any,
    publisher: KafkaEventPublisher,
    settings: Any,
) -> None:
    span_ctx = (
        tracer.start_as_current_span("worker.consume")
        if tracer is not None
        else nullcontext()
    )
    with span_ctx as span:
        headers = _decode_headers(message.headers)
        if span is not None:
            span.set_attribute("kafka.topic", message.topic)
            span.set_attribute("kafka.partition", message.partition)
            span.set_attribute("worker.group_id", consumer_group)
            span.set_attribute("worker.role", settings.worker_role)
            span.set_attribute("architecture.mode", settings.architecture_mode)
            if isinstance(message.value, dict):
                job_id = message.value.get("job_id")
                if job_id:
                    span.set_attribute("job.id", str(job_id))

        if message.topic == retry_topic:
            original_topic = headers.get(ORIGINAL_TOPIC_HEADER, consume_topic)
            if original_topic != consume_topic:
                logger.info(
                    "skip retry message for different role topic=%s expected=%s",
                    original_topic,
                    consume_topic,
                )
                return

        success, error = await role_handler.handle_event(message.value)

        if success:
            return

        RETRY_FAILURE_TOTAL.inc()
        retry_count = _parse_retry_count(headers)
        original_topic = headers.get(ORIGINAL_TOPIC_HEADER, message.topic)
        error_reason = (error or "unknown processing error").strip()

        if retry_count < settings.retry_max_count:
            next_retry_count = retry_count + 1
            delay_seconds = _compute_retry_backoff_seconds(
                next_retry_count,
                base=settings.retry_backoff_seconds,
                multiplier=settings.retry_backoff_multiplier,
                max_seconds=settings.retry_backoff_max_seconds,
            )
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

            retry_headers = {
                RETRY_COUNT_HEADER: str(next_retry_count),
                ORIGINAL_TOPIC_HEADER: original_topic,
                ERROR_REASON_HEADER: error_reason,
            }
            await publisher.publish(retry_topic, message.value, headers=retry_headers)
            RETRY_PUBLISHED_TOTAL.inc()
            logger.warning(
                "message retry scheduled job_id=%s from_topic=%s retry_count=%d",
                message.value.get("job_id"),
                message.topic,
                next_retry_count,
            )
            if span is not None:
                span.set_attribute("retry.scheduled", True)
                span.set_attribute("retry.count", next_retry_count)
            return

        dlq_headers = {
            RETRY_COUNT_HEADER: str(retry_count),
            ORIGINAL_TOPIC_HEADER: original_topic,
            ERROR_REASON_HEADER: error_reason,
        }
        await publisher.publish(settings.kafka_dlq_topic, message.value, headers=dlq_headers)
        DLQ_MESSAGES_TOTAL.inc()
        logger.error(
            "message moved to dlq job_id=%s from_topic=%s retry_count=%d",
            message.value.get("job_id"),
            message.topic,
            retry_count,
        )
        if span is not None:
            span.set_attribute("dlq.moved", True)
            span.set_attribute("retry.count", retry_count)


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings)
    tracer = setup_worker_tracing(settings)
    start_http_server(settings.worker_metrics_port)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    redis = from_url(settings.redis_url, decode_responses=True)
    instrument_runtime_libraries(engine=engine, redis_client=redis)
    await ensure_kafka_topics(settings)
    publisher = KafkaEventPublisher(settings.kafka_bootstrap_servers)
    role_handler = build_worker_role(settings=settings, session_factory=session_factory, redis=redis, publisher=publisher)
    consume_topic = resolve_worker_topic(settings)
    retry_topic = resolve_worker_retry_topic(settings)
    consume_topics = list(dict.fromkeys([consume_topic, retry_topic]))
    consumer_group = resolve_worker_group_id(settings)

    consumer = AIOKafkaConsumer(
        *consume_topics,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=consumer_group,
        enable_auto_commit=False,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        auto_offset_reset="earliest",
    )

    await publisher.start()
    await consumer.start()
    logger.info(
        "worker started role=%s topics=%s group_id=%s retry_max=%d",
        settings.worker_role,
        ",".join(consume_topics),
        consumer_group,
        settings.retry_max_count,
    )
    logger.info(
        "worker batch consume enabled=%s max_records=%d timeout_ms=%d",
        settings.kafka_consumer_batch_enabled,
        settings.kafka_consumer_batch_max_records,
        settings.kafka_consumer_batch_timeout_ms,
    )
    try:
        while True:
            max_records = 1
            timeout_ms = 1000
            if settings.kafka_consumer_batch_enabled:
                max_records = max(1, settings.kafka_consumer_batch_max_records)
                timeout_ms = max(1, settings.kafka_consumer_batch_timeout_ms)
            polled = await consumer.getmany(timeout_ms=timeout_ms, max_records=max_records)
            messages = [message for batch in polled.values() for message in batch]
            if not messages:
                continue

            tasks = [
                asyncio.create_task(
                    _handle_message(
                        message=message,
                        tracer=tracer,
                        consumer_group=consumer_group,
                        consume_topic=consume_topic,
                        retry_topic=retry_topic,
                        role_handler=role_handler,
                        publisher=publisher,
                        settings=settings,
                    )
                )
                for message in messages
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            batch_failed = False
            for result in results:
                if isinstance(result, Exception):
                    batch_failed = True
                    logger.error("worker batch message handling failed: %s", result)
            if batch_failed:
                continue
            await consumer.commit()
    finally:
        await publisher.stop()
        await consumer.stop()
        await redis.aclose()
        await engine.dispose()
        shutdown_tracing()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
