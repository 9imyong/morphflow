from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobCreateRequest(BaseModel):
    input: dict[str, Any] = Field(
        ...,
        description="Inference input payload",
        examples=[{"type": "text", "content": "hello morphflow"}],
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional runtime controls",
        examples=[{"priority": "normal", "simulate_inference_ms": 900, "simulate_inference_failure_rate": 0.1}],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "input": {"type": "text", "content": "예시용 컨탠츠"},
                "options": {
                    "priority": "normal",
                    "simulate_inference_ms": 900,
                    "simulate_inference_failure_rate": 0.1,
                },
            }
        }
    )


class JobResponse(BaseModel):
    job_id: str
    status: str


class JobDetailResponse(BaseModel):
    job_id: str
    status: str
    result: dict[str, Any] | None
    error: str | None


class HealthResponse(BaseModel):
    status: str
    dependencies: dict[str, dict[str, str]]
    details: dict[str, str]
