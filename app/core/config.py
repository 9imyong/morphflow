from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "fault-monitoring-system"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    worker_metrics_port: int = 9000
    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/fault_monitoring"
    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_request_topic: str = "request-topic"
    idempotency_ttl_seconds: int = 3600
    worker_processing_ttl_seconds: int = 1800
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
