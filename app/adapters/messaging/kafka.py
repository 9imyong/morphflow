from __future__ import annotations

import json
from inspect import isawaitable

from aiokafka import AIOKafkaProducer

from app.core.metrics import JOB_EVENT_PUBLISHED_TOTAL
from app.ports.publisher import EventPublisherPort


class KafkaEventPublisher(EventPublisherPort):
    def __init__(self, bootstrap_servers: str) -> None:
        self.bootstrap_servers = bootstrap_servers
        self._started = False
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        )

    async def start(self) -> None:
        await self._producer.start()
        self._started = True

    async def stop(self) -> None:
        if self._started:
            await self._producer.stop()
            self._started = False

    async def publish(self, topic: str, event: dict, headers: dict[str, str] | None = None) -> None:
        kafka_headers = None
        if headers:
            kafka_headers = [(key, value.encode("utf-8")) for key, value in headers.items()]
        # Use send() directly to avoid headers arg collisions under aiokafka OTel instrumentation.
        result = await self._producer.send(topic, value=event, headers=kafka_headers)
        if isawaitable(result):
            await result
        JOB_EVENT_PUBLISHED_TOTAL.inc()

    async def readiness(self) -> tuple[bool, str]:
        if not self._started:
            return False, "producer not started"
        try:
            brokers = list(self._producer.client.cluster.brokers())
            if brokers:
                return True, f"ok ({len(brokers)} broker(s))"

            # Try bootstrap only when metadata is empty.
            is_bootstrapped = await self._producer.client.bootstrap()
            brokers = list(self._producer.client.cluster.brokers())
            if is_bootstrapped or brokers:
                return True, f"ok ({len(brokers)} broker(s))"
            return False, "kafka bootstrap not ready"
        except Exception as exc:
            return False, str(exc)
