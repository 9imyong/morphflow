"""컨슈머 오프셋 처리와 재시도 백오프 검증.

두 가지를 고정한다.
1. 처리에 실패하면 그 지점으로 offset 을 되돌려 다시 읽는다.
   (커밋만 건너뛰면 컨슈머 위치는 이미 전진해 메시지를 영영 놓친다.)
2. 백오프가 남은 재시도 메시지는 poll 루프를 재우지 않고 파티션만 멈춘다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.workers import runner
from app.workers.runner import _consume_partition, _now_ms, _resume_due_partitions


@dataclass(frozen=True)
class TopicPartition:
    topic: str
    partition: int


@dataclass
class FakeMessage:
    topic: str
    partition: int
    offset: int
    value: dict
    headers: list[tuple[str, bytes]] = field(default_factory=list)


class FakeConsumer:
    def __init__(self) -> None:
        self.seeks: list[tuple[TopicPartition, int]] = []
        self.paused: list[TopicPartition] = []
        self.resumed: list[TopicPartition] = []

    def seek(self, tp: TopicPartition, offset: int) -> None:
        self.seeks.append((tp, offset))

    def pause(self, tp: TopicPartition) -> None:
        self.paused.append(tp)

    def resume(self, tp: TopicPartition) -> None:
        self.resumed.append(tp)


class RecordingHandler:
    """지정한 job_id 에서 예외를 던지는 핸들러."""

    def __init__(self, explode_on: str | None = None) -> None:
        self.seen: list[str] = []
        self.explode_on = explode_on

    async def handle_event(self, event: dict) -> tuple[bool, str | None]:
        job_id = event["job_id"]
        if job_id == self.explode_on:
            raise RuntimeError("handler blew up")
        self.seen.append(job_id)
        return True, None


class NoopPublisher:
    async def publish(self, topic: str, event: dict, headers: dict[str, str] | None = None) -> None:
        return None


@dataclass
class FakeSettings:
    worker_role: str = "unified"
    architecture_mode: str = "A"
    retry_max_count: int = 3
    retry_backoff_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0
    retry_backoff_max_seconds: float = 30.0
    kafka_dlq_topic: str = "dlq-topic"


def _message(offset: int, job_id: str, *, topic: str = "request-topic", headers=None) -> FakeMessage:
    return FakeMessage(
        topic=topic,
        partition=0,
        offset=offset,
        value={"job_id": job_id, "trace_id": "t", "payload": {"request": {}}},
        headers=headers or [],
    )


async def _run(consumer, tp, messages, handler, paused_until=None):
    return await _consume_partition(
        consumer=consumer,
        topic_partition=tp,
        messages=messages,
        paused_until=paused_until if paused_until is not None else {},
        tracer=None,
        consumer_group="g",
        consume_topic="request-topic",
        retry_topic="retry-topic",
        role_handler=handler,
        publisher=NoopPublisher(),
        settings=FakeSettings(),
    )


@pytest.mark.asyncio
async def test_all_success_commits_past_last_message() -> None:
    consumer = FakeConsumer()
    tp = TopicPartition("request-topic", 0)
    handler = RecordingHandler()

    _, offset = await _run(consumer, tp, [_message(10, "a"), _message(11, "b")], handler)

    assert offset == 12
    assert handler.seen == ["a", "b"]
    assert consumer.seeks == []


@pytest.mark.asyncio
async def test_failure_rewinds_to_failed_offset() -> None:
    """실패 지점으로 되돌려야 그 메시지를 다시 읽는다."""
    consumer = FakeConsumer()
    tp = TopicPartition("request-topic", 0)
    handler = RecordingHandler(explode_on="b")

    _, offset = await _run(
        consumer, tp, [_message(10, "a"), _message(11, "b"), _message(12, "c")], handler
    )

    # a 까지만 커밋한다.
    assert offset == 11
    # b 부터 다시 읽도록 되돌린다.
    assert consumer.seeks == [(tp, 11)]
    # c 는 이번에 처리하지 않는다. 순서를 건너뛰지 않기 위함.
    assert handler.seen == ["a"]


@pytest.mark.asyncio
async def test_first_message_failure_commits_nothing() -> None:
    consumer = FakeConsumer()
    tp = TopicPartition("request-topic", 0)
    handler = RecordingHandler(explode_on="a")

    _, offset = await _run(consumer, tp, [_message(10, "a"), _message(11, "b")], handler)

    assert offset is None, "실패했는데 커밋 대상이 잡혔다"
    assert consumer.seeks == [(tp, 10)]
    assert handler.seen == []


@pytest.mark.asyncio
async def test_partition_order_is_preserved_within_partition() -> None:
    consumer = FakeConsumer()
    tp = TopicPartition("request-topic", 0)
    handler = RecordingHandler()

    await _run(consumer, tp, [_message(i, f"job-{i}") for i in range(5)], handler)

    assert handler.seen == [f"job-{i}" for i in range(5)]


# --------------------------------------------------------------------------
# 재시도 백오프
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_not_due_retry_pauses_partition_instead_of_sleeping() -> None:
    """백오프가 남았으면 처리하지 않고 파티션만 멈춘다."""
    consumer = FakeConsumer()
    tp = TopicPartition("retry-topic", 0)
    handler = RecordingHandler()
    paused_until: dict[Any, float] = {}
    due_at = _now_ms() + 5_000

    message = _message(
        7,
        "later",
        topic="retry-topic",
        headers=[
            (runner.RETRY_AT_HEADER, str(due_at).encode()),
            (runner.ORIGINAL_TOPIC_HEADER, b"request-topic"),
        ],
    )

    _, offset = await _run(consumer, tp, [message], handler, paused_until)

    assert handler.seen == [], "아직 때가 아닌데 처리했다"
    assert offset is None
    assert consumer.seeks == [(tp, 7)]
    assert consumer.paused == [tp]
    assert paused_until[tp] == due_at


@pytest.mark.asyncio
async def test_due_retry_is_processed() -> None:
    consumer = FakeConsumer()
    tp = TopicPartition("retry-topic", 0)
    handler = RecordingHandler()
    due_at = _now_ms() - 1

    message = _message(
        7,
        "now",
        topic="retry-topic",
        headers=[
            (runner.RETRY_AT_HEADER, str(due_at).encode()),
            (runner.ORIGINAL_TOPIC_HEADER, b"request-topic"),
        ],
    )

    _, offset = await _run(consumer, tp, [message], handler)

    assert handler.seen == ["now"]
    assert offset == 8
    assert consumer.paused == []


def test_resume_only_fires_for_elapsed_partitions() -> None:
    consumer = FakeConsumer()
    ready = TopicPartition("retry-topic", 0)
    waiting = TopicPartition("retry-topic", 1)
    paused_until = {ready: _now_ms() - 1, waiting: _now_ms() + 10_000}

    _resume_due_partitions(consumer, paused_until)

    assert consumer.resumed == [ready]
    assert waiting in paused_until and ready not in paused_until
