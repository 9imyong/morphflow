class EventPublisherPort:
    async def publish(self, topic: str, event: dict, headers: dict[str, str] | None = None) -> None:
        raise NotImplementedError
