from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    input: dict[str, Any]
    options: dict[str, Any] = Field(default_factory=dict)


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
