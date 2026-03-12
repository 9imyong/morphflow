from __future__ import annotations

import asyncio
import random
from contextlib import nullcontext
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.core.metrics import (
    INFERENCE_ACTIVE_JOBS,
    INFERENCE_PROCESSING_SECONDS,
    INFERENCE_SEMAPHORE_WAIT_SECONDS,
    INFERENCE_SIMULATED_FAILURE_TOTAL,
    INFERENCE_SIMULATED_GPU_UTILIZATION,
)
from app.ports.task_processor import TaskProcessorPort

_TRACE_AVAILABLE = True
try:
    from opentelemetry import trace
except Exception:  # pragma: no cover - optional dependency fallback
    _TRACE_AVAILABLE = False
    trace = None  # type: ignore[assignment]


class GpuInferenceSimulator(TaskProcessorPort):
    @dataclass(slots=True)
    class _BatchItem:
        payload: dict[str, Any]
        future: asyncio.Future[dict[str, Any]]
        queued_at: float

    def __init__(
        self,
        *,
        max_concurrency: int,
        base_latency_ms: int,
        simulated_gpu_utilization: float,
        failure_rate: float,
        batch_enabled: bool,
        batch_size: int,
        batch_timeout_ms: int,
        batch_overhead_ms: int,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._base_latency_ms = max(1, base_latency_ms)
        self._simulated_gpu_utilization = min(max(simulated_gpu_utilization, 0.0), 1.0)
        self._failure_rate = min(max(failure_rate, 0.0), 1.0)
        self._batch_enabled = batch_enabled
        self._batch_size = max(1, batch_size)
        self._batch_timeout_seconds = max(1, batch_timeout_ms) / 1000
        self._batch_overhead_ms = max(0, batch_overhead_ms)
        self._batch_lock = asyncio.Lock()
        self._batch_queue: list[GpuInferenceSimulator._BatchItem] = []
        self._batch_event = asyncio.Event()
        self._batch_flush_task: asyncio.Task[None] | None = None
        self._tracer = trace.get_tracer("morphflow.gpu-simulator") if _TRACE_AVAILABLE else None

    async def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._batch_enabled:
            return await self._run_single(payload)
        return await self._enqueue_and_wait(payload)

    async def _enqueue_and_wait(self, payload: dict[str, Any]) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        item = GpuInferenceSimulator._BatchItem(
            payload=payload,
            future=loop.create_future(),
            queued_at=perf_counter(),
        )
        async with self._batch_lock:
            self._batch_queue.append(item)
            if self._batch_flush_task is None or self._batch_flush_task.done():
                self._batch_flush_task = asyncio.create_task(self._batch_flush_loop())
            if len(self._batch_queue) >= self._batch_size:
                self._batch_event.set()
        span_ctx = self._start_span("inference.batch_wait")
        with span_ctx as span:
            if span is not None:
                span.set_attribute("inference.batch.queue_size_target", self._batch_size)
            result = await item.future
            if span is not None:
                span.set_attribute("inference.batch.actual_size", result.get("simulated_batch_size", 1))
            return result

    async def _batch_flush_loop(self) -> None:
        while True:
            wait_started = perf_counter()
            try:
                await asyncio.wait_for(self._batch_event.wait(), timeout=self._batch_timeout_seconds)
            except TimeoutError:
                pass
            self._batch_event.clear()

            async with self._batch_lock:
                if not self._batch_queue:
                    self._batch_flush_task = None
                    return
                batch = self._batch_queue[: self._batch_size]
                del self._batch_queue[: self._batch_size]
                if len(self._batch_queue) >= self._batch_size:
                    self._batch_event.set()
            with self._start_span("inference.batch_flush") as span:
                if span is not None:
                    span.set_attribute("inference.batch.wait_seconds", perf_counter() - wait_started)
                    span.set_attribute("inference.batch.size", len(batch))
                await self._run_batch(batch)

    async def _run_single(self, payload: dict[str, Any]) -> dict[str, Any]:
        wait_started = perf_counter()
        async with self._semaphore:
            INFERENCE_SEMAPHORE_WAIT_SECONDS.observe(perf_counter() - wait_started)
            INFERENCE_ACTIVE_JOBS.inc()
            INFERENCE_SIMULATED_GPU_UTILIZATION.set(self._simulated_gpu_utilization)
            started = perf_counter()
            try:
                latency_ms = self._resolve_latency_ms(payload)
                await asyncio.sleep(max(1, latency_ms) / 1000)
                if self._should_fail(payload):
                    INFERENCE_SIMULATED_FAILURE_TOTAL.inc()
                    raise RuntimeError("simulated inference failure")
                return self._build_result(payload, latency_ms=latency_ms, batch_size=1)
            finally:
                INFERENCE_PROCESSING_SECONDS.observe(perf_counter() - started)
                INFERENCE_ACTIVE_JOBS.dec()

    async def _run_batch(self, items: list[_BatchItem]) -> None:
        if len(items) == 1:
            item = items[0]
            try:
                result = await self._run_single(item.payload)
                item.future.set_result(result)
            except Exception as exc:
                item.future.set_exception(exc)
            return

        wait_started = perf_counter()
        async with self._semaphore:
            semaphore_wait = perf_counter() - wait_started
            started = perf_counter()
            INFERENCE_ACTIVE_JOBS.inc(len(items))
            INFERENCE_SIMULATED_GPU_UTILIZATION.set(self._simulated_gpu_utilization)
            for item in items:
                INFERENCE_SEMAPHORE_WAIT_SECONDS.observe(semaphore_wait + (started - item.queued_at))
            try:
                with self._start_span("inference.batch_execute") as span:
                    if span is not None:
                        span.set_attribute("inference.batch.size", len(items))
                        span.set_attribute("inference.batch.overhead_ms", self._batch_overhead_ms)
                        span.set_attribute("inference.gpu.utilization", self._simulated_gpu_utilization)
                    latencies = [self._resolve_latency_ms(item.payload) for item in items]
                    await asyncio.sleep((max(latencies) + self._batch_overhead_ms) / 1000)
                    for item, latency_ms in zip(items, latencies):
                        with self._start_span("inference.item_finalize") as item_span:
                            if item_span is not None:
                                item_span.set_attribute("inference.item.latency_ms", latency_ms)
                                item_span.set_attribute("inference.batch.size", len(items))
                            if self._should_fail(item.payload):
                                INFERENCE_SIMULATED_FAILURE_TOTAL.inc()
                                item.future.set_exception(RuntimeError("simulated inference failure"))
                                if item_span is not None:
                                    item_span.set_attribute("inference.item.failed", True)
                                continue
                            item.future.set_result(
                                self._build_result(item.payload, latency_ms=latency_ms, batch_size=len(items))
                            )
                            if item_span is not None:
                                item_span.set_attribute("inference.item.failed", False)
            finally:
                elapsed = perf_counter() - started
                for _ in items:
                    INFERENCE_PROCESSING_SECONDS.observe(elapsed)
                INFERENCE_ACTIVE_JOBS.dec(len(items))

    def _resolve_latency_ms(self, payload: dict[str, Any]) -> int:
        # Optional request-based override for controlled load experiments.
        override_ms = payload.get("options", {}).get("simulate_inference_ms")
        return int(override_ms) if isinstance(override_ms, (int, float)) else self._base_latency_ms

    def _should_fail(self, payload: dict[str, Any]) -> bool:
        override_failure_rate = payload.get("options", {}).get("simulate_inference_failure_rate")
        failure_rate = float(override_failure_rate) if isinstance(override_failure_rate, (int, float)) else self._failure_rate
        failure_rate = min(max(failure_rate, 0.0), 1.0)
        return random.random() < failure_rate

    def _build_result(self, payload: dict[str, Any], *, latency_ms: int, batch_size: int) -> dict[str, Any]:
        content = payload.get("input", {}).get("content", "")
        return {
            "message": "gpu inference simulator completed",
            "mode": "simulated-gpu",
            "echo": content,
            "length": len(content),
            "simulated_latency_ms": latency_ms,
            "simulated_gpu_utilization": self._simulated_gpu_utilization,
            "simulated_batch_size": batch_size,
        }

    def _start_span(self, name: str) -> Any:
        if self._tracer is None:
            return nullcontext()
        return self._tracer.start_as_current_span(name)
