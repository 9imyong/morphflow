from __future__ import annotations

import json

from aiokafka import AIOKafkaProducer

from app.core.metrics import JOB_EVENT_PUBLISHED_TOTAL
from app.ports.publisher import EventPublisherPort


class KafkaEventPublisher(EventPublisherPort):
    def __init__(self, bootstrap_servers: str) -> None:
        self.bootstrap_servers = bootstrap_servers
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        )

    async def start(self) -> None:
        await self._producer.start()

    async def stop(self) -> None:
        await self._producer.stop()

    async def publish(self, topic: str, event: dict) -> None:
        await self._producer.send_and_wait(topic, event)
        JOB_EVENT_PUBLISHED_TOTAL.inc()
