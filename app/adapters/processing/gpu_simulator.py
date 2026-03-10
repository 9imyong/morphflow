from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any

from app.core.metrics import (
    INFERENCE_ACTIVE_JOBS,
    INFERENCE_PROCESSING_SECONDS,
    INFERENCE_SEMAPHORE_WAIT_SECONDS,
    INFERENCE_SIMULATED_GPU_UTILIZATION,
)
from app.ports.task_processor import TaskProcessorPort


class GpuInferenceSimulator(TaskProcessorPort):
    def __init__(
        self,
        *,
        max_concurrency: int,
        base_latency_ms: int,
        simulated_gpu_utilization: float,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._base_latency_ms = max(1, base_latency_ms)
        self._simulated_gpu_utilization = min(max(simulated_gpu_utilization, 0.0), 1.0)

    async def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        wait_started = perf_counter()
        async with self._semaphore:
            INFERENCE_SEMAPHORE_WAIT_SECONDS.observe(perf_counter() - wait_started)
            INFERENCE_ACTIVE_JOBS.inc()
            INFERENCE_SIMULATED_GPU_UTILIZATION.set(self._simulated_gpu_utilization)
            started = perf_counter()
            try:
                # Optional request-based override for controlled load experiments.
                override_ms = payload.get("options", {}).get("simulate_inference_ms")
                latency_ms = int(override_ms) if isinstance(override_ms, (int, float)) else self._base_latency_ms
                await asyncio.sleep(max(1, latency_ms) / 1000)

                content = payload.get("input", {}).get("content", "")
                return {
                    "message": "gpu inference simulator completed",
                    "mode": "simulated-gpu",
                    "echo": content,
                    "length": len(content),
                    "simulated_latency_ms": latency_ms,
                    "simulated_gpu_utilization": self._simulated_gpu_utilization,
                }
            finally:
                INFERENCE_PROCESSING_SECONDS.observe(perf_counter() - started)
                INFERENCE_ACTIVE_JOBS.dec()
