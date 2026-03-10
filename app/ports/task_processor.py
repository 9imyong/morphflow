from __future__ import annotations

from typing import Any


class TaskProcessorPort:
    async def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
