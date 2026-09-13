from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import nullcontext
from typing import Any

from aiokafka import AIOKafkaConsumer
from prometheus_client import start_http_server
from redis.asyncio import from_url

from app.adapters.messaging.kafka import KafkaEventPublisher
from app.adapters.messaging.outbox_relay import OutboxRelay
from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.kafka_topics import ensure_kafka_topics
from app.core.logging import configure_logging
from app.core.metrics import (
    DLQ_MESSAGES_TOTAL,
    RETRY_DEFERRED_TOTAL,
    RETRY_FAILURE_TOTAL,
    RETRY_PUBLISHED_TOTAL,
)
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
# 이 시각(epoch ms) 전에는 재시도 메시지를 처리하지 않는다.
RETRY_AT_HEADER = "retry-at"


def _now_ms() -> int:
    return int(time.time() * 1000)


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
            # 여기서 sleep 하면 poll 이 그만큼 멈춘다. 백오프가 길어지면
            # max_poll_interval_ms 를 넘겨 리밸런스가 나고, 그 사이 다른
            # 파티션도 함께 멈춘다. 지연은 헤더로 넘기고 즉시 발행한다.
            retry_headers = {
                RETRY_COUNT_HEADER: str(next_retry_count),
                ORIGINAL_TOPIC_HEADER: original_topic,
                ERROR_REASON_HEADER: error_reason,
                RETRY_AT_HEADER: str(_now_ms() + int(delay_seconds * 1000)),
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


def _resume_due_partitions(consumer: Any, paused_until: dict[Any, float]) -> None:
    """백오프 시각이 지난 파티션을 다시 읽기 시작한다."""
    if not paused_until:
        return
    now = _now_ms()
    due = [tp for tp, resume_at in paused_until.items() if resume_at <= now]
    for tp in due:
        paused_until.pop(tp, None)
        consumer.resume(tp)


def _retry_due_at(headers: dict[str, str]) -> int:
    raw = headers.get(RETRY_AT_HEADER)
    if raw is None:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


async def _consume_partition(
    *,
    consumer: Any,
    topic_partition: Any,
    messages: list[Any],
    paused_until: dict[Any, float],
    tracer: Any,
    consumer_group: str,
    consume_topic: str,
    retry_topic: str,
    role_handler: Any,
    publisher: KafkaEventPublisher,
    settings: Any,
) -> tuple[Any, int | None]:
    """한 파티션의 메시지를 순서대로 처리하고 커밋할 오프셋을 돌려준다.

    성공한 마지막 메시지의 다음 오프셋만 커밋 대상으로 올린다. 중간에서
    멈추면 그 지점으로 seek 해 두므로 다음 poll 에서 다시 읽는다.
    (예전에는 실패 시 커밋만 건너뛰었는데, 컨슈머 위치는 이미 전진한
    뒤라 실패한 메시지를 영영 다시 보지 못했다.)
    """
    commit_offset: int | None = None

    for message in messages:
        headers = _decode_headers(message.headers)

        # 아직 백오프 시각이 되지 않은 재시도 메시지는 처리하지 않는다.
        # 되돌려 두고 파티션을 잠시 멈춘다. 다른 파티션은 계속 돈다.
        if message.topic == retry_topic:
            due_at = _retry_due_at(headers)
            if due_at > _now_ms():
                consumer.seek(topic_partition, message.offset)
                consumer.pause(topic_partition)
                paused_until[topic_partition] = due_at
                RETRY_DEFERRED_TOTAL.inc()
                return topic_partition, commit_offset

        try:
            await _handle_message(
                message=message,
                tracer=tracer,
                consumer_group=consumer_group,
                consume_topic=consume_topic,
                retry_topic=retry_topic,
                role_handler=role_handler,
                publisher=publisher,
                settings=settings,
            )
        except Exception as exc:
            logger.error(
                "worker message handling failed topic=%s partition=%s offset=%s error=%s",
                message.topic,
                message.partition,
                message.offset,
                exc,
            )
            # 이 메시지부터 다시 읽는다.
            consumer.seek(topic_partition, message.offset)
            return topic_partition, commit_offset

        commit_offset = message.offset + 1

    return topic_partition, commit_offset


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
    # downstream 발행은 outbox 를 거친다. 워커도 릴레이를 하나 띄워
    # 자기가 적재한 메시지를 내보낸다.
    outbox_relay = OutboxRelay(
        session_factory=session_factory,
        publisher=publisher,
        batch_size=settings.outbox_relay_batch_size,
        poll_interval_seconds=settings.outbox_relay_poll_interval_seconds,
    )
    outbox_relay.start()
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
    paused_until: dict[Any, float] = {}
    try:
        while True:
            max_records = 1
            timeout_ms = 1000
            if settings.kafka_consumer_batch_enabled:
                max_records = max(1, settings.kafka_consumer_batch_max_records)
                timeout_ms = max(1, settings.kafka_consumer_batch_timeout_ms)
            _resume_due_partitions(consumer, paused_until)
            polled = await consumer.getmany(timeout_ms=timeout_ms, max_records=max_records)
            if not polled:
                continue

            # 파티션끼리는 병렬로, 한 파티션 안에서는 순서대로 처리한다.
            # 배치 전체를 gather 로 풀면 같은 파티션의 메시지 순서가 뒤집혀
            # job 상태 전이가 어긋날 수 있다.
            results = await asyncio.gather(
                *[
                    _consume_partition(
                        consumer=consumer,
                        topic_partition=topic_partition,
                        messages=messages,
                        paused_until=paused_until,
                        tracer=tracer,
                        consumer_group=consumer_group,
                        consume_topic=consume_topic,
                        retry_topic=retry_topic,
                        role_handler=role_handler,
                        publisher=publisher,
                        settings=settings,
                    )
                    for topic_partition, messages in polled.items()
                ]
            )

            # 성공한 접두부까지만 커밋한다. 실패 지점 이후는 offset 을 되돌려
            # 두었으므로 다음 poll 에서 다시 읽힌다.
            offsets = {tp: offset for tp, offset in results if offset is not None}
            if offsets:
                await consumer.commit(offsets)
    finally:
        await outbox_relay.stop()
        await publisher.stop()
        await consumer.stop()
        await redis.aclose()
        await engine.dispose()
        shutdown_tracing()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
