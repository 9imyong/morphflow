from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.dependencies import get_container
from app.api.schemas import JobCreateRequest, JobDetailResponse, JobResponse
from app.core.container import AppContainer


router = APIRouter(tags=["jobs"])


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    request: JobCreateRequest,
    container: AppContainer = Depends(get_container),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JobResponse:
    job = await container.job_service().create_job(request.model_dump(), idempotency_key)
    return JobResponse(job_id=job.id, status=job.status.value)


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job(job_id: str, container: AppContainer = Depends(get_container)) -> JobDetailResponse:
    job = await container.job_service().get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobDetailResponse(job_id=job.id, status=job.status.value, result=job.result, error=job.error)
