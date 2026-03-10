from __future__ import annotations

from fastapi import APIRouter, Depends, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container
from app.api.schemas import HealthResponse
from app.core.container import AppContainer


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok", details={"service": "alive"})


@router.get("/ready", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def ready(container: AppContainer = Depends(get_container)) -> HealthResponse:
    details: dict[str, str] = {}

    async with container.session_factory() as session:
        assert isinstance(session, AsyncSession)
        await session.execute(text("SELECT 1"))
        details["database"] = "ok"

    assert isinstance(container.redis, Redis)
    await container.redis.ping()
    details["redis"] = "ok"

    details["kafka_publisher"] = "ok"
    return HealthResponse(status="ok", details=details)
