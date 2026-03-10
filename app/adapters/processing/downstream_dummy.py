from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any

from app.core.metrics import DOWNSTREAM_PROCESSING_SECONDS
from app.ports.task_processor import TaskProcessorPort


class DownstreamDummyProcessor(TaskProcessorPort):
    def __init__(self, *, base_latency_ms: int = 300) -> None:
        self._base_latency_ms = max(1, base_latency_ms)

    async def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        started = perf_counter()
        try:
            await asyncio.sleep(self._base_latency_ms / 1000)
            request = payload.get("request", {})
            inference_result = payload.get("inference_result", {})
            return {
                "message": "downstream dummy completed",
                "persisted": True,
                "notified": True,
                "input_length": len(request.get("input", {}).get("content", "")),
                "inference_mode": inference_result.get("mode"),
            }
        finally:
            DOWNSTREAM_PROCESSING_SECONDS.observe(perf_counter() - started)
