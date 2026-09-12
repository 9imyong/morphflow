# 모니터링

## 관측 스택

| 종류 | 도구 | 로컬 주소 |
|---|---|---|
| 지표 | Prometheus | `http://localhost:9091` (kind: `30901`) |
| 대시보드 | Grafana | `http://localhost:3000` (kind: `30300`) |
| 추적 | Jaeger | `http://localhost:16686` (kind: `30686`) |
| 로그 | Fluent Bit → Elasticsearch → Kibana | `http://localhost:5601` |

수집 대상은 API `/metrics`, 워커 메트릭 포트(9000), Kafka·Redis·PostgreSQL exporter, 컨테이너 stdout 로그입니다.

## 서비스 수준 목표

| 지표 | 목표 | 측정 구간 | 담당 |
|---|---|---|---|
| 작업 접수 성공률 | 99% 이상 | `http_requests_total` 중 5xx 비율 | 김용준 |
| 접수 응답 지연 | p95 200ms 미만 | k6 또는 `http_req_duration` | 김용준 |
| 적체 해소 | lag이 지속 증가하지 않음 | `kafka_consumergroup_lag` | 김용준 |
| 영구 실패 | DLQ 적재 0건 유지 | `dlq_messages_total` | 김용준 |

실측 결과는 [품질](../architecture/quality.md)에 있습니다.

## 핵심 지표

### 단계별 처리 시간

병목 구간을 지목하려면 아래 세 지표를 **함께** 봅니다. 하나만 보면 어느 단계가 느린지 알 수 없습니다.

| 지표 | 의미 |
|---|---|
| `job_processing_seconds` | 워커의 전체 처리 시간 (A·B 모드) |
| `inference_processing_seconds` | 추론 단계 소요 시간 |
| `downstream_processing_seconds` | 후단 단계 소요 시간 |

### 처리량과 결과

| 지표 | 의미 |
|---|---|
| `jobs_created_total` | 접수된 작업 수 |
| `jobs_success_total` / `jobs_failure_total` | A·B 모드의 완료·실패 수 |
| `downstream_success_total` / `downstream_failure_total` | C·BC 모드의 최종 완료·실패 수 |
| `jobs_duplicate_total` | 멱등성으로 중복 제거된 요청 수 |

C·BC 모드에서 최종 완료 수는 `downstream_success_total`입니다. **`jobs_success_total`을 완료량으로 쓰면 안 됩니다.**

### 추론 자원

| 지표 | 의미 |
|---|---|
| `inference_active_jobs` | 동시 처리 중인 추론 작업 수 |
| `inference_semaphore_wait_seconds` | 동시성 제한 대기 시간 |
| `inference_simulated_gpu_utilization` | 시뮬레이션 GPU 사용률 (설정값 반영) |
| `inference_simulated_failure_total` | 시뮬레이션 실패 횟수 |

### 신뢰성

| 지표 | 의미 |
|---|---|
| `retry_failure_total` | 처리 실패 횟수 |
| `retry_published_total` | 재시도 채널로 재발행된 횟수 |
| `dlq_messages_total` | DLQ로 격리된 메시지 수 |
| `job_events_published_total` | Kafka로 발행된 이벤트 수 |
| `kafka_consumergroup_lag` | 컨슈머 그룹별 적체 |

## 경보

기준 파일은 `deploy/observability/prometheus-rules.yml`입니다.

| 경보 | 발동 조건 | 지속 | 연결 런북 |
|---|---|---|---|
| `ApiDown` | `up{job="api"} == 0` | 2분 | [장애 대응](incident-response.md) |
| `WorkerDown` | `up{job="worker"} == 0` | 2분 | [장애 대응](incident-response.md) |
| `KafkaExporterDown` | `up{job="kafka_consumer_lag"} == 0` | 3분 | [Kafka 적체](runbooks/RUNBOOK-kafka-consumer-lag.md) |
| `RedisExporterDown` | `up{job="redis_exporter"} == 0` | 3분 | [Redis 장애](runbooks/RUNBOOK-redis-outage.md) |
| `PostgresExporterDown` | `up{job="postgres_exporter"} == 0` | 3분 | [데이터베이스 지연](runbooks/RUNBOOK-database-latency.md) |
| `KafkaConsumerLagHigh` | `max(kafka_consumergroup_lag) > 100` | 5분 | [Kafka 적체](runbooks/RUNBOOK-kafka-consumer-lag.md) |
| `DownstreamConsumerLagHigh` | downstream 그룹 lag > 100 | 5분 | [후단 병목](runbooks/RUNBOOK-downstream-bottleneck.md) |
| `WorkerProcessingTimeHigh` | `job_processing_seconds` p95 > 5s | 10분 | [워커 지연](runbooks/RUNBOOK-worker-processing-delay.md) |
| `DownstreamProcessingTimeHigh` | `downstream_processing_seconds` p95 > 5s | 10분 | [후단 병목](runbooks/RUNBOOK-downstream-bottleneck.md) |
| `InferenceConcurrencySaturated` | `max(inference_active_jobs) >= 2` | 5분 | [워커 지연](runbooks/RUNBOOK-worker-processing-delay.md) |
| `DlqMessagesDetected` | `increase(dlq_messages_total[5m]) > 0` | 2분 | [재시도·DLQ 급증](runbooks/RUNBOOK-retry-dlq-surge.md) |
| `PostgresResponseSlow` | 읽기 대기 시간 증가 | 10분 | [데이터베이스 지연](runbooks/RUNBOOK-database-latency.md) |

`InferenceConcurrencySaturated`의 임계값 2는 `INFERENCE_MAX_CONCURRENCY` 기본값과 같습니다. 동시성 설정을 바꾸면 이 경보 임계값도 함께 조정해야 합니다.

## 점검 명령

```bash
# 수집 대상 상태
curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# 경보 규칙 목록
curl -s http://localhost:9091/api/v1/rules | jq '.data.groups[] | {group: .name, rules: [.rules[].name]}'

# 최근 로그 1건
curl -s "http://localhost:9200/morphflow-*/_search?size=1&sort=@timestamp:desc" | jq '.hits.hits[0]._source'

# 컨슈머 그룹 적체
scripts/kafka-consumer-group-describe.sh
scripts/kafka-k8s-lag.sh
```

## 알려진 한계

- HTTP 지표 라벨에 원본 경로가 들어가 `GET /jobs/{job_id}` 호출마다 시계열이 늘어납니다.
- 이벤트의 `trace_id`가 Jaeger 추적 ID와 연결되지 않아 로그에서 추적으로 이동할 수 없습니다.
- 로그가 구조화 형식이 아니라 `job_id` 기준 검색이 어렵습니다.

자세한 내용은 [위험과 기술 부채](../architecture/risks-technical-debt.md)에 있습니다.
