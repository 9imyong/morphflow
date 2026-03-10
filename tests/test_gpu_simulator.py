from __future__ import annotations

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
    )
    with pytest.raises(RuntimeError, match="simulated inference failure"):
        await simulator.process({"input": {"content": "boom"}, "options": {}})


def test_primary_processor_is_swappable() -> None:
    simulator_settings = Settings(worker_processor_backend="simulator")
    dummy_settings = Settings(worker_processor_backend="dummy")
    assert isinstance(build_primary_processor(simulator_settings), GpuInferenceSimulator)
    assert build_primary_processor(dummy_settings).__class__.__name__ == "DummyTaskProcessor"
