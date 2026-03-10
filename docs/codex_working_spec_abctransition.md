# 병목 기반 전환형 아키텍처 작업 문서 (for Codex)

## 1. 문서 목적
이 문서는 Codex가 실제 구현 작업을 수행할 수 있도록, 서비스 구조/전환 조건/컴포넌트 책임/데이터 모델/작업 순서/완료 기준을 명확히 정의한 작업 문서다.

핵심 목표는 다음과 같다.

1. **공통 비동기 이벤트 기반 골격(A)** 을 먼저 구현한다.
2. 운영 중 병목 위치에 따라 **GPU/추론 병목 대응 모드(B)** 또는 **다운스트림 병목 대응 모드(C)** 로 전환 가능하게 설계한다.
3. Redis 기반 멱등성과 DB 제약조건을 함께 사용해 중복 처리를 방지한다.
4. 장애 예측/대응/복구/데이터 분석이 가능한 수준의 모니터링 구조를 함께 넣는다.

---

## 2. 프로젝트 배경 및 요구사항
수습 평가 과제 요구사항:

- 장애 예측: APM, 로그 수집 등 모니터링 기법
- 장애 대응: Scale-up/out, HA, EDA(Event Driven Architecture)
- 장애 복구: Fail-over/back, Backup 전략, 후속조치
- 가산점: 데이터 분석을 위한 지표 수집
- 실제 개발 서버에 최소 2종 이상 아키텍처를 실제로 올릴 수 있어야 함

본 문서는 이를 만족하기 위해, **서로 완전히 다른 3개 시스템**이 아니라,
**공통 골격 위에서 병목에 따라 전환 가능한 단일 서비스**를 설계한다.

---

## 3. 아키텍처 개요

### 3.1 전환형 구조 정의
- **A = 기본 비동기 공통 골격**
- **B = GPU/추론 병목 대응 모드**
- **C = 다운스트림 병목 대응 모드**

A/B/C는 별도 서비스가 아니라 같은 서비스의 운영 모드다.
처음에는 A로 시작하고, 병목에 따라 B 또는 C, 또는 B+C 조합형으로 진화한다.

### 3.2 전환 원칙
- A → B: 추론/GPU 구간이 병목일 때
- A → C: 저장/업로드/외부 API/후처리 구간이 병목일 때
- B → B+C: 추론 병목을 분리한 뒤 후단 병목도 추가로 발생할 때

### 3.3 공통 불변 조건
아래 요소는 A/B/C 전환과 관계없이 최대한 유지한다.

- API 인터페이스
- Job 상태 모델
- 이벤트 Envelope 형식
- Redis 멱등성 키 전략
- DB 스키마
- 메트릭 이름/라벨
- 로그 포맷
- Trace ID 전파 방식

---

## 4. 아키텍처 상세

### 4.1 아키텍처 A: 기본 비동기 공통 골격

#### 목적
- 빠르게 실제 개발 서버에 올릴 수 있는 기본 구조
- EDA 기반 요청/처리 분리
- 이후 B/C 전환을 위한 공통 기반 확보

#### 처리 흐름
1. Client가 API 요청
2. API가 유효성 검증
3. Job 생성 및 DB에 `PENDING` 상태 저장
4. Redis 멱등성 체크
5. Kafka `request-topic` 발행
6. Unified Worker가 consume
7. 작업 수행
8. 결과 저장
9. Job 상태를 `SUCCESS` 또는 `FAILED` 로 변경

#### 특징
- 단일 request topic
- unified worker가 추론 + 저장 + 후처리 일부를 담당
- 구조가 단순하고 구현 속도가 빠름

#### 한계
- 병목이 발생해도 구간별 분리 관측이 제한적
- 추론이 느려도, 저장이 느려도 worker 전체가 점유됨

---

### 4.2 아키텍처 B: GPU/추론 병목 대응 모드

#### 적용 조건
아래 조건이 일정 기준 이상 관측되면 B로 전환한다.

- inference p95 latency 지속 증가
- GPU utilization 지속 고점
- GPU VRAM 여유 부족
- Kafka lag 증가
- worker 처리 시간 대부분이 추론 구간에 집중

#### 구조 변화
- unified worker 내부 책임 중 **추론 책임을 전용 inference worker** 로 분리
- GPU semaphore / 동시성 제어 도입
- 필요 시 batch 처리 도입
- topic은 기본적으로 request-topic 유지 가능하되, 구현 편의상 inference-topic 분리도 허용

#### 처리 흐름
1. API → request-topic 발행
2. Inference Worker가 consume
3. GPU 자원 점유 제어(semaphore)
4. 추론 수행
5. 핵심 결과 저장
6. 상태 갱신

#### 목표
- 중복 추론 방지
- GPU 자원 낭비 방지
- 추론 latency 안정화

---

### 4.3 아키텍처 C: 다운스트림 병목 대응 모드

#### 적용 조건
아래 조건이 일정 기준 이상 관측되면 C로 전환한다.

- inference 완료 후 final completion까지 지연 증가
- DB write latency 증가
- 파일 업로드 지연 누적
- 외부 API timeout/retry 증가
- 알림/후처리 실패율 증가

#### 구조 변화
- 추론 완료 이후 작업을 downstream topic으로 분리
- downstream worker가 저장/업로드/API 호출/알림을 담당
- 부분 성공(partial success) 상태를 관리 가능하게 함

#### 처리 흐름
1. API → request-topic 발행
2. Worker 또는 Inference Worker가 핵심 처리 수행
3. 핵심 결과 저장
4. `downstream-topic` 이벤트 발행
5. Downstream Worker가 후속 작업 수행
6. 전체 완료 상태 갱신

#### 목표
- 추론 경로와 후단 처리 경로 분리
- 외부 시스템 장애가 본 추론 경로를 막지 않도록 격리
- 재처리 단위를 다운스트림 이벤트 수준으로 분리

---

## 5. 최종 권장 진화 형태
실제 구현 목표는 다음과 같다.

### Phase 1
A 구조 구현

### Phase 2
병목에 따라 아래 중 하나 수행
- A → B
- A → C

### Phase 3
필요 시 B + C 결합

즉 최종 형태는 다음이 될 수 있다.

```text
Client
  ↓
Nginx
  ↓
FastAPI API
  ↓
Kafka request-topic
  ↓
Inference Worker (B)
  ↓
핵심 결과 저장
  ↓
Kafka downstream-topic (C)
  ↓
Downstream Worker
  ↓
DB / Storage / External API / Notification
```

---

## 6. 멱등성 설계

### 6.1 목적
다음 상황에서 중복 처리를 방지한다.

- 클라이언트 재시도
- producer 재전송
- consumer 재처리
- retry topic 재유입
- offset commit 전 장애

### 6.2 원칙
- **Redis = 빠른 1차 멱등성 체크**
- **DB Unique Constraint = 최종 2차 보장**

### 6.3 Redis 키 전략
다음 형태를 기본으로 한다.

```text
idem:req:{idempotency_key}
idem:job:{job_id}
idem:infer:{job_id}
idem:downstream:{job_id}:{task_type}
```

### 6.4 상태값
- `PROCESSING`
- `COMPLETED`
- `FAILED`

또는 JSON 문자열로 저장 가능:

```json
{
  "status": "COMPLETED",
  "job_id": "job-123",
  "result_ref": "result-123",
  "updated_at": "2026-03-10T12:00:00+09:00"
}
```

### 6.5 처리 방식
Redis `SET key value NX EX ttl` 패턴을 기본으로 사용한다.

- 키가 없으면 최초 처리로 간주
- 키가 있으면 중복 처리로 간주
- TTL을 둬서 영구 락 방지

### 6.6 TTL 권장안
- `PROCESSING`: 300~1800초
- `COMPLETED`: 3600~86400초

### 6.7 DB 제약조건
최종 결과 저장 테이블에는 아래와 같은 unique 보장을 둔다.

예시:
- `job_id` unique
- `event_id` unique
- `job_id + task_type` unique

---

## 7. 이벤트 Envelope 표준
A/B/C 전환과 관계없이 공통 이벤트 스키마를 유지한다.

```json
{
  "event_id": "uuid",
  "job_id": "uuid",
  "event_type": "REQUESTED",
  "trace_id": "trace-uuid",
  "source": "api",
  "created_at": "2026-03-10T12:00:00+09:00",
  "payload": {}
}
```

### 필드 정의
- `event_id`: 이벤트 자체 고유 ID
- `job_id`: 동일 작업 추적용 ID
- `event_type`: 상태/단계 구분
- `trace_id`: trace 연계용 ID
- `source`: 이벤트 발행 주체
- `created_at`: 발행 시각
- `payload`: 단계별 실제 데이터

### event_type 예시
- `REQUESTED`
- `INFERENCE_STARTED`
- `INFERENCE_COMPLETED`
- `DOWNSTREAM_REQUESTED`
- `DOWNSTREAM_COMPLETED`
- `FAILED`

---

## 8. Job 상태 모델
전환 가능한 구조를 위해 Job 상태 체계를 통일한다.

### 기본 상태
- `PENDING`
- `PROCESSING`
- `SUCCESS`
- `FAILED`

### 확장 상태
- `INFERENCE_PROCESSING`
- `INFERENCE_DONE`
- `DOWNSTREAM_PROCESSING`
- `PARTIAL_SUCCESS`
- `RETRYING`

### 상태 전이 예시
```text
PENDING
  → PROCESSING
  → INFERENCE_PROCESSING
  → INFERENCE_DONE
  → DOWNSTREAM_PROCESSING
  → SUCCESS
```

실패 케이스:
```text
PENDING
  → PROCESSING
  → FAILED
```

부분 성공:
```text
INFERENCE_DONE
  → DOWNSTREAM_PROCESSING
  → PARTIAL_SUCCESS
```

---

## 9. 저장소 모델 초안

### 9.1 jobs 테이블
| 컬럼 | 설명 |
|---|---|
| id | job_id |
| request_payload | 최초 요청 payload |
| status | 현재 상태 |
| retry_count | 재시도 횟수 |
| result_ref | 결과 참조값 |
| error_message | 오류 메시지 |
| created_at | 생성시각 |
| updated_at | 수정시각 |

### 9.2 job_events 테이블
| 컬럼 | 설명 |
|---|---|
| id | PK |
| event_id | 이벤트 ID(unique) |
| job_id | 연관 job |
| event_type | 이벤트 종류 |
| payload | 이벤트 내용 |
| created_at | 생성시각 |

### 9.3 downstream_tasks 테이블 (선택)
| 컬럼 | 설명 |
|---|---|
| id | PK |
| job_id | 연관 job |
| task_type | upload / notify / external_api 등 |
| status | 상태 |
| retry_count | 재시도 횟수 |
| last_error | 최근 오류 |
| created_at | 생성시각 |
| updated_at | 수정시각 |

---

## 10. API 스펙

### 10.1 작업 생성
`POST /jobs`

#### 헤더
- `Idempotency-Key`: optional but strongly recommended

#### 요청 예시
```json
{
  "input": {
    "type": "text",
    "content": "sample request"
  },
  "options": {
    "priority": "normal"
  }
}
```

#### 응답 예시
```json
{
  "job_id": "uuid",
  "status": "PENDING"
}
```

### 10.2 작업 조회
`GET /jobs/{job_id}`

#### 응답 예시
```json
{
  "job_id": "uuid",
  "status": "INFERENCE_DONE",
  "result_ref": null,
  "error_message": null
}
```

### 10.3 헬스체크
- `GET /health/live`
- `GET /health/ready`

### 10.4 메트릭
- `GET /metrics`

---

## 11. 토픽 설계

### 최소 토픽
- `request-topic`

### 확장 토픽
- `downstream-topic`
- `retry-topic`
- `dlq-topic`

### 규칙
- 초기 A에서는 `request-topic` 중심으로 시작
- B 필요 시 inference 분리 로직 추가
- C 필요 시 `downstream-topic` 추가
- 실패 재처리 정책에 따라 `retry-topic`, `dlq-topic` 도입

---

## 12. 모니터링 및 장애 예측 지표

### 12.1 API 지표
- request count
- success/failure count
- p50/p95/p99 latency
- 5xx rate

### 12.2 Queue 지표
- topic lag
- consume rate
- retry count
- dlq count

### 12.3 Worker 지표
- processing duration
- success/failure ratio
- retry ratio

### 12.4 GPU/추론 지표 (B)
- inference duration
- GPU utilization
- GPU memory used
- semaphore wait time

### 12.5 다운스트림 지표 (C)
- DB write latency
- upload latency
- external API timeout count
- downstream retry count

### 12.6 시스템 지표
- CPU
- memory
- disk
- network
- container restart count

### 12.7 로그/트레이스
- structured JSON logging
- trace_id 포함
- request_id / job_id / event_id 포함

---

## 13. 전환 판단 기준
Codex는 아래 기준을 만족하도록 구조를 설계해야 한다. 기준값은 config로 외부화한다.

### A → B 전환 판단
다음이 일정 기간 지속되면 B 전환 후보로 본다.

- inference p95 latency > threshold
- GPU utilization > threshold
- VRAM free < threshold
- request-topic lag 증가
- worker total processing time 중 inference 비율 과다

### A → C 전환 판단
다음이 일정 기간 지속되면 C 전환 후보로 본다.

- inference 완료 후 completion latency > threshold
- DB write latency > threshold
- upload latency > threshold
- external API timeout 증가
- downstream retry 증가

### B + C 결합 판단
- B 적용 후 inference latency는 안정화되었으나 end-to-end latency가 여전히 높은 경우
- 다운스트림 지표만 지속 악화되는 경우

---

## 14. 장애 대응 및 복구 전략

### 14.1 대응
- Scale-up: CPU/memory 증설
- Scale-out: API/worker 인스턴스 추가
- HA: Nginx upstream + 다중 API 인스턴스
- Retry: 일시 장애 재시도
- DLQ: 영구 실패 격리

### 14.2 복구
- container restart
- backlog replay
- readiness check 후 재투입
- 원인 분석(RCA) 후 threshold 또는 구조 재조정

### 14.3 백업
- DB dump
- 설정 파일 백업
- 결과 파일/Object storage 백업

---

## 15. 권장 기술 스택
- API: FastAPI
- Worker: Python consumer
- Message Broker: Kafka
- Cache/Idempotency: Redis
- DB: PostgreSQL 또는 MySQL
- Reverse Proxy: Nginx
- Metrics: Prometheus
- Dashboard: Grafana
- Logs: Loki + Promtail 또는 EFK
- Trace: OpenTelemetry + Jaeger
- Container: Docker Compose

---

## 16. 권장 디렉토리 구조
```text
project/
├─ app/
│  ├─ api/
│  │  ├─ routes/
│  │  └─ schemas/
│  ├─ application/
│  │  ├─ services/
│  │  ├─ commands/
│  │  └─ queries/
│  ├─ domain/
│  │  ├─ models/
│  │  ├─ enums/
│  │  └─ events/
│  ├─ infrastructure/
│  │  ├─ db/
│  │  ├─ redis/
│  │  ├─ kafka/
│  │  ├─ logging/
│  │  └─ monitoring/
│  ├─ workers/
│  │  ├─ unified_worker.py
│  │  ├─ inference_worker.py
│  │  ├─ downstream_worker.py
│  │  └─ retry_worker.py
│  ├─ common/
│  │  ├─ idempotency.py
│  │  ├─ envelope.py
│  │  ├─ tracing.py
│  │  └─ config.py
│  └─ main.py
├─ deploy/
│  ├─ docker-compose.yml
│  ├─ nginx/
│  ├─ prometheus/
│  ├─ grafana/
│  └─ loki/
├─ scripts/
│  ├─ backup.sh
│  ├─ restore.sh
│  └─ smoke_test.sh
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ e2e/
└─ docs/
   ├─ README.md
   ├─ ARCHITECTURE.md
   ├─ RUNBOOK.md
   └─ MONITORING.md
```

---

## 17. Codex 작업 범위

### 17.1 1차 목표 (Must)
1. FastAPI 기반 API 서버 구현
2. `/jobs`, `/jobs/{job_id}`, `/health/live`, `/health/ready`, `/metrics` 구현
3. Redis 멱등성 모듈 구현
4. Kafka producer/consumer 구현
5. A 구조(unified worker) 구현
6. jobs / job_events 테이블 및 migration 작성
7. Docker Compose로 전체 기동 가능하게 구성
8. Prometheus scrape 가능하도록 메트릭 노출

### 17.2 2차 목표 (Should)
1. B 구조용 inference worker 분리
2. GPU semaphore/concurrency config 추가
3. C 구조용 downstream topic/worker 분리
4. retry/dlq 처리 추가
5. trace_id 기반 구조화 로그 추가

### 17.3 3차 목표 (Nice to have)
1. Grafana dashboard sample 추가
2. backup/restore script 추가
3. smoke test 및 load test 스크립트 추가
4. 전환 조건 점검용 관리 스크립트 추가

---

## 18. Codex 구현 지침

### 18.1 구현 스타일
- Python 3.11+
- typing 적극 사용
- Pydantic 기반 request/response model
- config는 env 기반 외부화
- 로깅은 JSON structured logging
- 함수/클래스 책임 분리

### 18.2 주의사항
- A/B/C가 서로 다른 프로젝트처럼 갈라지면 안 됨
- 공통 envelope, 상태 모델, API는 유지해야 함
- Redis 멱등성만 믿지 말고 DB unique 제약도 같이 설계
- worker 내부 로직은 추후 분리 배포 가능하게 모듈화
- config로 실행 모드를 전환 가능하게 설계

### 18.3 실행 모드 예시
```text
ARCH_MODE=A
ARCH_MODE=B
ARCH_MODE=C
ARCH_MODE=BC
```

또는 feature flag 방식 허용:
```text
ENABLE_INFERENCE_SPLIT=true
ENABLE_DOWNSTREAM_SPLIT=true
```

---

## 19. 환경변수 예시
```env
APP_ENV=dev
ARCH_MODE=A
API_PORT=8000
DB_URL=postgresql://user:pass@db:5432/app
REDIS_URL=redis://redis:6379/0
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
REQUEST_TOPIC=request-topic
DOWNSTREAM_TOPIC=downstream-topic
RETRY_TOPIC=retry-topic
DLQ_TOPIC=dlq-topic
IDEMPOTENCY_TTL_PROCESSING=600
IDEMPOTENCY_TTL_COMPLETED=86400
GPU_MAX_CONCURRENCY=1
ENABLE_INFERENCE_SPLIT=false
ENABLE_DOWNSTREAM_SPLIT=false
PROMETHEUS_ENABLED=true
```

---

## 20. 테스트 시나리오

### 20.1 A 검증
- 정상 요청 생성 가능
- unified worker가 consume 후 완료 처리
- 동일 Idempotency-Key 재요청 시 같은 job_id 반환

### 20.2 B 검증
- inference worker 분리 시 기존 API/상태모델 유지
- 중복 추론 방지
- semaphore 설정이 적용됨

### 20.3 C 검증
- downstream topic 발행/consume 정상 동작
- downstream 실패 시 partial_success 또는 downstream_failed 처리 가능
- 동일 downstream task 중복 실행 방지

### 20.4 장애 검증
- worker 중단 후 재기동
- 메시지 재처리 시 멱등성 유지
- retry 및 dlq 흐름 검증

---

## 21. 완료 기준 (Definition of Done)
다음 조건을 만족하면 1차 완료로 본다.

1. Docker Compose 한 번으로 전체 서비스 기동 가능
2. API 요청 시 job 생성 및 상태 조회 가능
3. Redis 멱등성으로 중복 요청 방지 가능
4. Kafka consumer가 메시지 처리 후 상태 갱신 가능
5. 최소한 A 구조가 동작함
6. B/C로 확장 가능한 코드 구조가 반영됨
7. 메트릭, 헬스체크, 기본 로그가 확인 가능
8. README에 실행 방법이 정리됨

2차 완료 기준:
1. B 또는 C 중 하나 이상 실제 분리 동작 확인
2. retry/dlq 또는 downstream split 검증
3. 기본 대시보드 또는 샘플 쿼리 제공

---

## 22. Codex에게 직접 줄 작업 요청 문구
아래 문구를 그대로 Codex 입력용 프롬프트로 사용 가능하다.

### Codex Prompt
이 프로젝트의 목표는 FastAPI + Kafka + Redis + DB 기반의 전환형 비동기 아키텍처를 구현하는 것이다.

요구사항:
1. 기본 모드는 A(기본 비동기 공통 골격)로 구현한다.
2. 이후 B(GPU/추론 병목 대응), C(다운스트림 병목 대응)로 전환 가능한 구조여야 한다.
3. API, 이벤트 envelope, 상태 모델, 멱등성 키 전략은 A/B/C에서 공통으로 유지한다.
4. Redis SETNX + TTL 기반 멱등성 처리와 DB unique constraint를 함께 고려한다.
5. 최소 구현 범위는 `/jobs`, `/jobs/{job_id}`, `/health/live`, `/health/ready`, `/metrics`, Kafka producer/consumer, unified worker, Docker Compose 환경이다.
6. 코드 구조는 이후 unified worker를 inference worker와 downstream worker로 분리 배포할 수 있도록 모듈화한다.
7. config/env 기반으로 아키텍처 모드 또는 feature flag 전환이 가능해야 한다.
8. Prometheus metrics, structured logging, trace_id propagation을 고려한다.

우선순위:
- 1순위: A 구조 실제 동작
- 2순위: B/C 분리 가능한 구조 반영
- 3순위: retry/dlq/downstream split 샘플 구현

산출물:
- 실행 가능한 프로젝트 구조
- Docker Compose
- API/worker 코드
- migration 또는 스키마 정의
- README
- 샘플 env

---

## 23. 추가 메모
- 실제 서버 시연용이면 A를 먼저 올리고, 이후 B 또는 C 기능 플래그를 켜서 구조 진화를 보여주는 방식이 가장 현실적이다.
- 평가 문맥상 “설계만 한 것”보다 “공통 골격을 실제로 구현했고, 병목에 따라 분리 가능한 구조를 코드 레벨에서 반영했다”가 더 중요하다.
