from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text

from app.api.dependencies import get_container
from app.api.schemas import HealthResponse
from app.core.container import AppContainer


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok", dependencies={}, details={"service": "alive"})


@router.get("/ready", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def ready(response: Response, container: AppContainer = Depends(get_container)) -> HealthResponse:
    dependencies: dict[str, dict[str, str]] = {}

    try:
        async with container.session_factory() as session:
            await session.execute(text("SELECT 1"))
        dependencies["database"] = {"status": "ok", "detail": "connection ok"}
    except Exception as exc:
        dependencies["database"] = {"status": "error", "detail": str(exc)}

    try:
        await container.redis.ping()
        dependencies["redis"] = {"status": "ok", "detail": "ping ok"}
    except Exception as exc:
        dependencies["redis"] = {"status": "error", "detail": str(exc)}

    try:
        is_ready, detail = await container.publisher.readiness()
        if not is_ready:
            raise RuntimeError(detail)
        dependencies["kafka"] = {"status": "ok", "detail": detail}
    except Exception as exc:
        dependencies["kafka"] = {"status": "error", "detail": str(exc)}

    all_ok = all(item["status"] == "ok" for item in dependencies.values())
    response.status_code = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    details = {name: item["status"] for name, item in dependencies.items()}
    return HealthResponse(status="ok" if all_ok else "degraded", dependencies=dependencies, details=details)
