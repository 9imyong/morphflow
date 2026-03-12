from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "fault-monitoring-system"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    worker_metrics_port: int = 9000
    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/fault_monitoring"
    redis_url: str = "redis://localhost:6379/0"
    architecture_mode: Literal["A", "B", "C", "BC"] = "A"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_request_topic: str = "request-topic"
    kafka_inference_topic: str = "inference-topic"
    kafka_retry_topic_request: str = "retry-topic"
    kafka_retry_topic_downstream: str = "retry-downstream-topic"
    kafka_dlq_topic: str = "dlq-topic"
    kafka_downstream_topic: str = "downstream-topic"
    kafka_topic_auto_configure: bool = True
    kafka_topic_replication_factor: int = 1
    kafka_partitions_worker_topic: int = 1
    kafka_partitions_downstream_topic: int = 1
    kafka_partitions_dlq: int = 1
    worker_role: Literal["unified", "inference", "downstream"] = "unified"
    worker_processor_backend: Literal["simulator", "dummy"] = "simulator"
    inference_max_concurrency: int = 2
    inference_simulated_latency_ms: int = 700
    inference_simulated_gpu_utilization: float = 0.8
    inference_simulated_failure_rate: float = 0.0
    inference_batch_enabled: bool = True
    inference_batch_size: int = 8
    inference_batch_timeout_ms: int = 50
    inference_batch_overhead_ms: int = 120
    downstream_simulated_latency_ms: int = 300
    kafka_consumer_batch_enabled: bool = True
    kafka_consumer_batch_max_records: int = 64
    kafka_consumer_batch_timeout_ms: int = 200
    retry_max_count: int = 3
    retry_backoff_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0
    retry_backoff_max_seconds: float = 30.0
    idempotency_ttl_seconds: int = 3600
    worker_processing_ttl_seconds: int = 1800
    log_level: str = "INFO"
    tracing_enabled: bool = True
    otel_exporter_otlp_endpoint: str = "http://jaeger:4317"
    otel_service_name_api: str = "morphflow-api"
    otel_service_name_worker: str = "morphflow-worker"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
