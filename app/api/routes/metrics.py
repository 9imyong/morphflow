from fastapi import APIRouter

from app.core.metrics import metrics_response


router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics():
    return metrics_response()
