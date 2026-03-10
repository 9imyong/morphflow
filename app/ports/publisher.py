class EventPublisherPort:
    async def publish(self, topic: str, event: dict) -> None:
        raise NotImplementedError
