from __future__ import annotations

import asyncio
from typing import Any

from app.ports.task_processor import TaskProcessorPort


class DummyTaskProcessor(TaskProcessorPort):
    async def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0.5)
        content = payload.get("input", {}).get("content", "")
        return {
            "message": "dummy processing completed",
            "echo": content,
            "length": len(content),
        }
