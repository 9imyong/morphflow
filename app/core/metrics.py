from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response


JOB_CREATED_TOTAL = Counter("jobs_created_total", "Number of jobs created")
JOB_DUPLICATE_TOTAL = Counter("jobs_duplicate_total", "Number of duplicate job requests")
JOB_PROCESSING_SECONDS = Histogram("job_processing_seconds", "End-to-end worker processing duration")
JOB_SUCCESS_TOTAL = Counter("jobs_success_total", "Number of successful jobs")
JOB_FAILURE_TOTAL = Counter("jobs_failure_total", "Number of failed jobs")
JOB_EVENT_PUBLISHED_TOTAL = Counter("job_events_published_total", "Number of Kafka events published")
HTTP_REQUESTS_TOTAL = Counter("http_requests_total", "HTTP requests handled", ["method", "path", "status"])


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
