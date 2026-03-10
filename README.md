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

## Run (Development)

```bash
docker compose -f docker-compose.dev.yml --env-file env/.env.dev up --build
```

If local ports conflict, adjust `*_HOST_PORT` values in `env/.env.dev`.

API endpoints:

- `POST /jobs`
- `GET /jobs/{job_id}`
- `GET /health/live`
- `GET /health/ready`
- `GET /metrics`

Worker metrics are exposed on port `9000`.

## Readiness (Dependency-Aware)

`GET /health/ready` checks real dependencies and returns:
- `200 OK`: all dependencies are ready
- `503 Service Unavailable`: at least one dependency is not ready

Checked dependencies:
1. Database (`SELECT 1`)
2. Redis (`PING`)
3. Kafka producer bootstrap readiness

Response shape:
- `status`: `ok` or `degraded`
- `dependencies`: per dependency `{status, detail}`
- `details`: compact map (`ok`/`error`) for quick checks

Startup/readiness relation:
1. Compose startup order (`depends_on`) controls launch sequencing only.
2. Real traffic readiness must rely on `/health/ready` because dependencies may still be warming up after container start.
3. In this project, `migrate` runs first, then `api/worker` start; `/health/ready` is the runtime gate for DB/Redis/Kafka usability.

## DB Migration (Alembic)

Migration files:
- `alembic/env.py`
- `alembic/versions/*.py`

Apply latest migration:

```bash
alembic upgrade head
```

Rollback one revision:

```bash
alembic downgrade -1
```

Compose-based apply (recommended):

```bash
docker compose -f docker-compose.dev.yml --env-file env/.env.dev up -d migrate
docker compose -f docker-compose.dev.yml --env-file env/.env.dev up -d
```

Reset and re-apply (development only):

```bash
docker compose -f docker-compose.dev.yml --env-file env/.env.dev down -v
docker compose -f docker-compose.dev.yml --env-file env/.env.dev up -d postgres
docker compose -f docker-compose.dev.yml --env-file env/.env.dev run --rm migrate
```

## CI Validation

GitHub Actions workflow:
- `.github/workflows/ci.yml`

CI executes the minimum verification set:
1. `pytest -q`
2. `alembic upgrade head`
3. `alembic check` (detects missing migration/schema drift)

## Incident Runbook

- Scenario-based runbook for Kafka lag / worker delay / DB latency / Redis outage:
  - `docs/incident_runbook_abctransition.md`

## Load Test

- k6 load script: `tests/perf/jobs_load_test.js`
- latest report: `docs/perf_test_report_20260310.md`
- B-mode validation report: `docs/perf_test_report_bmode_20260310.md`
- B-mode compose override: `deploy/docker-compose.bmode.override.yml`

## E2E Verification Example

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

Duplicate request test (same `Idempotency-Key` should return the same `job_id`):

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: sample-key-1" \
  -d '{"input":{"type":"text","content":"sample request"},"options":{"priority":"normal"}}'
```

Operational checks:

1. `POST /jobs` returns `202` and initial status `PENDING`
2. worker consumes Kafka `request-topic`
3. job transitions `PENDING -> PROCESSING -> SUCCESS`
4. `GET /jobs/{job_id}` returns final result
5. duplicate request with same `Idempotency-Key` returns same `job_id`

## Retry / DLQ Strategy

Worker consumer behavior:
- consumes primary topic (`request-topic` or role topic) and `retry-topic`
- on transient processing failure, republishes same payload to `retry-topic`
- when retry count exceeds `RETRY_MAX_COUNT`, publishes same payload to `dlq-topic`

Headers used:
- `retry-count`
- `original-topic`
- `error-reason`

Retry configuration (`env/.env.dev`, `env/.env.prod`):
- `KAFKA_RETRY_TOPIC`
- `KAFKA_DLQ_TOPIC`
- `RETRY_MAX_COUNT`
- `RETRY_BACKOFF_SECONDS`
- `RETRY_BACKOFF_MULTIPLIER`
- `RETRY_BACKOFF_MAX_SECONDS`

Prometheus metrics:
- `retry_published_total`
- `retry_failure_total`
- `dlq_messages_total`

DLQ inspect/replay example:

```bash
# 1) Inspect DLQ payloads
docker exec -it $(docker compose -f docker-compose.dev.yml ps -q kafka) \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic dlq-topic \
  --from-beginning

# 2) After root-cause fix, replay selected payload to request-topic
docker exec -i $(docker compose -f docker-compose.dev.yml ps -q kafka) \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 \
  --topic request-topic
```

Operator flow:
1. identify root cause from `error-reason` and worker logs
2. fix issue (code/config/dependency)
3. replay selected DLQ messages to primary topic
4. verify `dlq_messages_total` trend stabilizes

## Observability Stack

Start service stack first, then start observability stack:

```bash
docker compose -f docker-compose.dev.yml --env-file env/.env.dev up -d
docker compose -f deploy/observability-compose.yml up -d
```

Endpoints:

- Prometheus: `http://localhost:9091`
- Grafana: `http://localhost:3000`
- Elasticsearch: `http://localhost:9200`
- Kibana: `http://localhost:5601`

Prometheus target/alert checks:

```bash
curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
curl -s http://localhost:9091/api/v1/rules | jq '.data.groups[] | {group: .name, rules: [.rules[].name]}'
```

Kibana log check:

```bash
curl -s "http://localhost:9200/morphflow-*/_search?size=1&sort=@timestamp:desc" | jq '.hits.hits[0]._source'
```

Exporter coverage in observability compose:
- `kafka-exporter` for consumer lag metrics
- `redis-exporter` for Redis metrics
- `postgres-exporter` for PostgreSQL metrics

## Extension Points

- `app.ports.task_processor.TaskProcessorPort` keeps inference logic replaceable.
- `app.application.worker_service.WorkerService` separates job state management from processing details.
- `app.ports.worker_role.WorkerRolePort` and `app.workers.roles` define role-oriented expansion points.
- `app.domain.events.EventType` and Kafka topic settings support `downstream-topic`, `retry-topic`, and `dlq-topic`.
- `app.domain.models.JobStatus` already reserves comments for future states such as `INFERENCE_DONE` and `PARTIAL_SUCCESS`.

Worker role/topic expansion settings:
- `WORKER_ROLE`: `unified` | `inference` | `downstream`
- `KAFKA_REQUEST_TOPIC`
- `KAFKA_INFERENCE_TOPIC`
- `KAFKA_DOWNSTREAM_TOPIC`

Current behavior:
- `unified` consumes `KAFKA_REQUEST_TOPIC`
- `inference` consumes `KAFKA_INFERENCE_TOPIC`
- `downstream` consumes `KAFKA_DOWNSTREAM_TOPIC`

At this stage, inference/downstream roles intentionally reuse the same processing path as A architecture, so the code structure is ready for B/C specialization without breaking current runtime behavior.

## Notes

- This version implements Architecture A only.
- B mode can split the processor into a dedicated inference worker while keeping the same event envelope and repository contracts.
- C mode can add a downstream publisher/consumer pair without changing the API contract or base job model.
