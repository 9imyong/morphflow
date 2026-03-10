from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from prometheus_client import start_http_server
from redis.asyncio import from_url

from app.adapters.messaging.kafka import KafkaEventPublisher
from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.logging import configure_logging
from app.core.metrics import DLQ_MESSAGES_TOTAL, RETRY_FAILURE_TOTAL, RETRY_PUBLISHED_TOTAL
from app.workers.roles import build_worker_role, resolve_worker_group_id, resolve_worker_topic


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


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings)
    start_http_server(settings.worker_metrics_port)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    redis = from_url(settings.redis_url, decode_responses=True)
    publisher = KafkaEventPublisher(settings.kafka_bootstrap_servers)
    role_handler = build_worker_role(settings=settings, session_factory=session_factory, redis=redis, publisher=publisher)
    consume_topic = resolve_worker_topic(settings)
    consume_topics = list(dict.fromkeys([consume_topic, settings.kafka_retry_topic]))
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
    try:
        async for message in consumer:
            headers = _decode_headers(message.headers)
            if message.topic == settings.kafka_retry_topic:
                original_topic = headers.get(ORIGINAL_TOPIC_HEADER, consume_topic)
                if original_topic != consume_topic:
                    logger.info(
                        "skip retry message for different role topic=%s expected=%s",
                        original_topic,
                        consume_topic,
                    )
                    await consumer.commit()
                    continue

            success, error = await role_handler.handle_event(message.value)

            if success:
                await consumer.commit()
                continue

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
                await publisher.publish(settings.kafka_retry_topic, message.value, headers=retry_headers)
                RETRY_PUBLISHED_TOTAL.inc()
                logger.warning(
                    "message retry scheduled job_id=%s from_topic=%s retry_count=%d",
                    message.value.get("job_id"),
                    message.topic,
                    next_retry_count,
                )
            else:
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

            await consumer.commit()
    finally:
        await publisher.stop()
        await consumer.stop()
        await redis.aclose()
        await engine.dispose()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
