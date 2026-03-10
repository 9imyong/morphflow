from __future__ import annotations

from app.adapters.processing.dummy import DummyTaskProcessor
from app.adapters.processing.gpu_simulator import GpuInferenceSimulator
from app.core.config import Settings
from app.ports.task_processor import TaskProcessorPort


def build_primary_processor(settings: Settings) -> TaskProcessorPort:
    if settings.worker_processor_backend == "dummy":
        return DummyTaskProcessor()
    return GpuInferenceSimulator(
        max_concurrency=settings.inference_max_concurrency,
        base_latency_ms=settings.inference_simulated_latency_ms,
        simulated_gpu_utilization=settings.inference_simulated_gpu_utilization,
        failure_rate=settings.inference_simulated_failure_rate,
    )
