# Fault Monitoring System

Architecture A minimum runnable scaffold for an event-driven job processing service. The current build focuses on:

- FastAPI API for job creation and lookup
- PostgreSQL-backed job and event persistence
- Redis idempotency for API and worker duplicate protection
- Kafka `request-topic` producer and consumer
- Dummy processing service behind a replaceable processor interface
- Liveness, readiness, and Prometheus metrics endpoints
- Docker Compose development stack

## Directory Layout

```text
app/
  api/
  application/
  domain/
  ports/
  adapters/
  workers/
  core/
deploy/
docs/
tests/
```

## Run

```bash
docker compose -f docker-compose.dev.yml --env-file env/.env.dev up --build
```

API endpoints:

- `POST /jobs`
- `GET /jobs/{job_id}`
- `GET /health/live`
- `GET /health/ready`
- `GET /metrics`

Worker metrics are exposed on port `9000`.

## Example

Create a job:

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: sample-key-1" \
  -d '{"input":{"type":"text","content":"sample request"},"options":{"priority":"normal"}}'
```

Fetch a job:

```bash
curl http://localhost:8000/jobs/<job_id>
```

## Extension Points

- `app.ports.task_processor.TaskProcessorPort` keeps inference logic replaceable.
- `app.application.worker_service.WorkerService` separates job state management from processing details.
- `app.domain.events.EventType` and Kafka topic settings keep room for `downstream-topic`, retry, and DLQ expansion.
- `app.domain.models.JobStatus` already reserves comments for future states such as `INFERENCE_DONE` and `PARTIAL_SUCCESS`.

## Notes

- This version implements Architecture A only.
- B mode can split the processor into a dedicated inference worker while keeping the same event envelope and repository contracts.
- C mode can add a downstream publisher/consumer pair without changing the API contract or base job model.
