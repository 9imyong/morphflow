from __future__ import annotations

import json

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

    async def publish(self, topic: str, event: dict) -> None:
        await self._producer.send_and_wait(topic, event)
        JOB_EVENT_PUBLISHED_TOTAL.inc()

    async def readiness(self) -> tuple[bool, str]:
        if not self._started:
            return False, "producer not started"
        try:
            is_bootstrapped = await self._producer.client.bootstrap()
            if not is_bootstrapped:
                return False, "kafka bootstrap not ready"
            return True, "ok"
        except Exception as exc:
            return False, str(exc)
