from __future__ import annotations

import asyncio

import pytest

from app.adapters.processing.factory import build_primary_processor
from app.adapters.processing.gpu_simulator import GpuInferenceSimulator
from app.core.config import Settings


@pytest.mark.asyncio
async def test_gpu_simulator_returns_inference_payload() -> None:
    simulator = GpuInferenceSimulator(
        max_concurrency=2,
        base_latency_ms=1,
        simulated_gpu_utilization=0.75,
        failure_rate=0.0,
        batch_enabled=False,
        batch_size=8,
        batch_timeout_ms=50,
        batch_overhead_ms=120,
    )
    result = await simulator.process({"input": {"content": "hello"}, "options": {}})
    assert result["mode"] == "simulated-gpu"
    assert result["echo"] == "hello"


@pytest.mark.asyncio
async def test_gpu_simulator_failure_rate_can_force_failure() -> None:
    simulator = GpuInferenceSimulator(
        max_concurrency=1,
        base_latency_ms=1,
        simulated_gpu_utilization=0.5,
        failure_rate=1.0,
        batch_enabled=False,
        batch_size=8,
        batch_timeout_ms=50,
        batch_overhead_ms=120,
    )
    with pytest.raises(RuntimeError, match="simulated inference failure"):
        await simulator.process({"input": {"content": "boom"}, "options": {}})


def test_primary_processor_is_swappable() -> None:
    simulator_settings = Settings(worker_processor_backend="simulator")
    dummy_settings = Settings(worker_processor_backend="dummy")
    assert isinstance(build_primary_processor(simulator_settings), GpuInferenceSimulator)
    assert build_primary_processor(dummy_settings).__class__.__name__ == "DummyTaskProcessor"


@pytest.mark.asyncio
async def test_primary_processor_can_disable_gpu_batch() -> None:
    settings = Settings(
        worker_processor_backend="simulator",
        inference_batch_enabled=True,
        inference_simulated_latency_ms=1,
    )
    processor = build_primary_processor(settings, disable_batch=True)
    result1, result2 = await asyncio.gather(
        processor.process({"input": {"content": "one"}, "options": {}}),
        processor.process({"input": {"content": "two"}, "options": {}}),
    )
    assert result1["simulated_batch_size"] == 1
    assert result2["simulated_batch_size"] == 1


@pytest.mark.asyncio
async def test_gpu_simulator_micro_batch_combines_concurrent_requests() -> None:
    simulator = GpuInferenceSimulator(
        max_concurrency=2,
        base_latency_ms=1,
        simulated_gpu_utilization=0.8,
        failure_rate=0.0,
        batch_enabled=True,
        batch_size=8,
        batch_timeout_ms=50,
        batch_overhead_ms=1,
    )

    result1, result2 = await asyncio.gather(
        simulator.process({"input": {"content": "one"}, "options": {}}),
        simulator.process({"input": {"content": "two"}, "options": {}}),
    )
    assert result1["simulated_batch_size"] == 2
    assert result2["simulated_batch_size"] == 2
