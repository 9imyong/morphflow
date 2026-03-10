from fastapi import FastAPI

from app.api.routes import health, jobs, metrics
from app.core.lifespan import lifespan
from app.core.metrics import HTTP_REQUESTS_TOTAL


app = FastAPI(title="Fault Monitoring System", lifespan=lifespan)


@app.middleware("http")
async def record_http_metrics(request, call_next):
    response = await call_next(request)
    HTTP_REQUESTS_TOTAL.labels(request.method, request.url.path, response.status_code).inc()
    return response


app.include_router(jobs.router)
app.include_router(health.router)
app.include_router(metrics.router)
