from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response


JOB_CREATED_TOTAL = Counter("jobs_created_total", "Number of jobs created")
JOB_DUPLICATE_TOTAL = Counter("jobs_duplicate_total", "Number of duplicate job requests")
JOB_PROCESSING_SECONDS = Histogram("job_processing_seconds", "End-to-end worker processing duration")
INFERENCE_PROCESSING_SECONDS = Histogram("inference_processing_seconds", "Inference stage duration")
INFERENCE_SEMAPHORE_WAIT_SECONDS = Histogram(
    "inference_semaphore_wait_seconds", "Time spent waiting for inference semaphore"
)
INFERENCE_ACTIVE_JOBS = Gauge("inference_active_jobs", "In-flight inference jobs")
INFERENCE_SIMULATED_GPU_UTILIZATION = Gauge(
    "inference_simulated_gpu_utilization", "Simulated GPU utilization (0.0~1.0)"
)
JOB_SUCCESS_TOTAL = Counter("jobs_success_total", "Number of successful jobs")
JOB_FAILURE_TOTAL = Counter("jobs_failure_total", "Number of failed jobs")
JOB_EVENT_PUBLISHED_TOTAL = Counter("job_events_published_total", "Number of Kafka events published")
RETRY_PUBLISHED_TOTAL = Counter("retry_published_total", "Number of retry messages published")
DLQ_MESSAGES_TOTAL = Counter("dlq_messages_total", "Number of messages sent to DLQ")
RETRY_FAILURE_TOTAL = Counter("retry_failure_total", "Number of failed processing attempts")
HTTP_REQUESTS_TOTAL = Counter("http_requests_total", "HTTP requests handled", ["method", "path", "status"])


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
