# Fault Monitoring System

Kafka 기반 EDA AI inference pipeline skeleton.
현재 A/B/C 아키텍처 전환 구조, Retry/DLQ, Observability(EFK 포함)까지 반영된 상태다.

## 1. 빠른 시작

기본(A 모드):
```bash
docker compose -f docker-compose.dev.yml --env-file env/.env.dev up -d --build
```

Observability:
```bash
docker compose -f deploy/observability-compose.yml up -d
```

## 2. 아키텍처 모드 실행

### A 모드 (기본)
- API -> `request-topic` -> unified worker
- 실행:
```bash
docker compose -f docker-compose.dev.yml --env-file env/.env.dev up -d --build
```

### B 모드 (추론 분리)
- API -> `request-topic` -> inference worker
- processor backend 기본값: `simulator` (`WORKER_PROCESSOR_BACKEND`)
- 실행:
```bash
docker compose -f docker-compose.dev.yml -f deploy/docker-compose.bmode.override.yml --env-file env/.env.dev up -d --build
```

### C 모드 (downstream 분리)
- API -> `request-topic` -> inference worker -> `downstream-topic` -> downstream worker
- 실행:
```bash
docker compose -f docker-compose.dev.yml -f deploy/docker-compose.cmode.override.yml --env-file env/.env.dev up -d --build
```

## 3. 핵심 엔드포인트

- `POST /jobs`
- `GET /jobs/{job_id}`
- `GET /health/live`
- `GET /health/ready`
- `GET /metrics`

## 4. Retry / DLQ 운영

### 토픽
- `request-topic`
- `retry-topic` (request/inference retry)
- `retry-downstream-topic` (downstream retry)
- `dlq-topic`

### 헤더
- `retry-count`
- `original-topic`
- `error-reason`

### 정책
- retry backoff: exponential
- `RETRY_MAX_COUNT` 초과 시 DLQ 전송
- DLQ는 원본 payload 유지

### Inference Simulator 설정
- `WORKER_PROCESSOR_BACKEND=simulator|dummy`
- `INFERENCE_MAX_CONCURRENCY`
- `INFERENCE_SIMULATED_LATENCY_MS`
- `INFERENCE_SIMULATED_FAILURE_RATE`
- `INFERENCE_SIMULATED_GPU_UTILIZATION`

관련 메트릭:
- `inference_processing_seconds`
- `inference_semaphore_wait_seconds`
- `inference_active_jobs`
- `inference_simulated_gpu_utilization`
- `inference_simulated_failure_total`

### DLQ 확인/재처리
```bash
# DLQ 확인
docker exec -it $(docker compose -f docker-compose.dev.yml ps -q kafka) \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic dlq-topic \
  --from-beginning

# 원인 수정 후 재주입
docker exec -i $(docker compose -f docker-compose.dev.yml ps -q kafka) \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 \
  --topic request-topic
```

## 5. Observability 구조

### 구성
- Metrics: Prometheus
- Dashboard: Grafana
- Tracing: OpenTelemetry -> Jaeger
  - FastAPI request span
  - aiokafka producer/consumer span
  - SQLAlchemy query span
  - Redis command span
- Logs: Fluent Bit -> Elasticsearch -> Kibana (EFK)
- Exporters: kafka/redis/postgres

### 접속
- Prometheus: `http://localhost:9091`
- Grafana: `http://localhost:3000`
- Jaeger: `http://localhost:16686`
- Elasticsearch: `http://localhost:9200`
- Kibana: `http://localhost:5601`

### 점검 명령
```bash
curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
curl -s http://localhost:9091/api/v1/rules | jq '.data.groups[] | {group: .name, rules: [.rules[].name]}'
curl -s "http://localhost:9200/morphflow-*/_search?size=1&sort=@timestamp:desc" | jq '.hits.hits[0]._source'
```

## 6. 테스트 실행

전체 핵심 테스트:
```bash
uv run --extra dev pytest -q
```

C 경로 시나리오 테스트:
```bash
uv run --extra dev pytest -q tests/test_c_architecture_flow.py
```

## 7. 마이그레이션

적용:
```bash
alembic upgrade head
```

롤백:
```bash
alembic downgrade -1
```

## 8. Kubernetes(Kind) 배포

### 범위
- 1차 범위: `api`, `worker`, `postgres`, `redis`, `kafka`, `migrate job`
- 경로: `deploy/k8s/base`
- 진입: NodePort `30081` (기본 호스트 `18000`으로 매핑)
- override 대응: `deploy/k8s/overlays/{bmode,cmode,bcmode}`
- observability: `deploy/k8s/overlays/observability` (Prometheus/Grafana/Jaeger/exporters)

### 실행 순서
```bash
# 1) kind 클러스터 생성
scripts/kind-create-cluster.sh morphflow

# 2) 앱 이미지 빌드
docker build -t morphflow-app:kind .

# 3) kind 노드로 이미지 로드
scripts/kind-load-images.sh morphflow

# 4) 기본(A) 배포 (migrate 생략)
scripts/k8s-deploy-kind.sh morphflow base
```

검증:
```bash
curl -s http://localhost:18000/health/live
curl -s http://localhost:18000/health/ready
```

마이그레이션이 필요한 경우(스키마 변경 시점):
```bash
scripts/k8s-deploy-kind.sh morphflow base --with-migrate
```

아키텍처 모드 overlay:
```bash
# B 모드
scripts/k8s-deploy-kind.sh morphflow bmode

# C 모드 (downstream-worker 포함)
scripts/k8s-deploy-kind.sh morphflow cmode

# BC 모드 (downstream-worker 포함)
scripts/k8s-deploy-kind.sh morphflow bcmode
```

Observability overlay:
```bash
kubectl apply -k deploy/k8s/overlays/observability --context kind-local-dev
```

주요 접속(NodePort):
- Grafana: `http://localhost:30300`
- Prometheus: `http://localhost:30901`
- Jaeger UI: `http://localhost:30686`

Networking overlay (MetalLB + Envoy Gateway + HTTPRoute):
```bash
kubectl apply -k deploy/k8s/overlays/networking --context kind-local-dev
```

또는 자동 대역 반영 + 적용:
```bash
make net-apply K8S_CONTEXT=kind-local-dev KIND_NETWORK=kind
```

상세 설치/검증 가이드:
- `deploy/k8s/overlays/networking/README.md`

포트 충돌 시:
```bash
HOST_API_PORT=28000 scripts/kind-create-cluster.sh morphflow
```

전환 전략(Compose -> Kind -> k3s) 상세:
- `docs/k8s_kind_transition_plan_20260317.md`

## 9. 운영 문서

- 아키텍처/운영 최종 패키지:
  - `docs/architecture_operations_package_20260310.md`
- A/B/C 성능 요약:
  - `docs/perf_summary_abc_20260310.md`
- C 모드 부하 실측 보고서:
  - `docs/perf_test_report_cmode_20260311.md`
- 상세 아키텍처 스펙:
  - `docs/codex_working_spec_abctransition.md`
- 장애 Runbook:
  - `docs/incident_runbook_abctransition.md`
- Compose -> Kind 전환 계획/기록:
  - `docs/k8s_kind_transition_plan_20260317.md`
- 작업 로그:
  - `docs/work_progress_log.md`
