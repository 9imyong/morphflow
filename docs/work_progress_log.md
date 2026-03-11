# 작업 진행도/작업 단위 기록 문서

## 1. 목적
이 문서는 작업 상태를 빠르게 이해할 수 있도록, 다음 두 가지를 표준 형식으로 기록한다.

1. 작업 진행도(%)와 상태
2. 작업 단위(Work Unit)별 상세 내역

---

## 2. 상태 기준

- `TODO`: 아직 시작하지 않음
- `IN_PROGRESS`: 진행 중
- `BLOCKED`: 외부 이슈로 중단
- `DONE`: 완료

---

## 3. 진행도(%) 기준

- `0%`: 착수 전
- `10~30%`: 요구사항/코드 구조 파악
- `40~70%`: 구현/수정 진행
- `80~90%`: 테스트/검증 진행
- `100%`: 반영 완료 + 검증 완료

진행도는 대략치가 아니라, 실제 완료된 작업 단위 수를 기준으로 업데이트한다.

---

## 4. 작업 단위 정의

작업 단위는 아래 조건을 만족하면 1개로 본다.

- 독립적으로 완료/검증 가능
- 산출물(코드, 문서, 설정) 위치가 명확
- 완료 기준(DoD)이 한 줄로 정의 가능

권장 크기:
- 30분~2시간 내 완료 가능한 크기

---

## 5. 기록 템플릿

아래 형식으로 항목을 추가한다.

```md
### [Task-YYYYMMDD-번호] 작업 제목
- 상태: TODO | IN_PROGRESS | BLOCKED | DONE
- 진행도: 0~100%
- 담당: Codex / 사용자명
- 시작일: YYYY-MM-DD
- 최근 업데이트: YYYY-MM-DD
- 목표(DoD): 한 줄 완료 기준
- 작업 단위:
  - [ ] WU-1: 작업 단위 설명
  - [ ] WU-2: 작업 단위 설명
  - [ ] WU-3: 작업 단위 설명
- 메모/이슈:
  - 이슈 또는 결정사항
```

---

## 6. 현재 작업 기록

### [Task-20260310-01] 작업 진행도/작업 단위 문서화
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): 팀이 공통 포맷으로 진행도와 작업 단위를 이해/추적할 수 있는 문서를 `docs`에 추가한다.
- 작업 단위:
  - [x] WU-1: 기존 `docs` 문서 구조 확인
  - [x] WU-2: 진행도 기준/상태 정의 정리
  - [x] WU-3: 재사용 가능한 기록 템플릿 작성
  - [x] WU-4: 현재 요청 작업을 예시로 첫 기록 추가
- 메모/이슈:
  - 이후 작업부터 본 문서에 동일 포맷으로 누적 기록

### [Task-20260310-02] Kafka KRaft 전환(ZooKeeper 제거, 4.0.0)
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): 개발용 Compose에서 ZooKeeper 의존성을 제거하고 Kafka 이미지를 `apache/kafka:4.0.0`으로 고정한다.
- 작업 단위:
  - [x] WU-1: 기존 Kafka/ZooKeeper compose 설정 확인
  - [x] WU-2: ZooKeeper 서비스 제거 및 Kafka KRaft 환경 변수 적용
  - [x] WU-3: Kafka 이미지 버전 `apache/kafka:4.0.0` 고정
  - [x] WU-4: 변경 사항 문서 로그 반영
- 메모/이슈:
  - 단일 브로커 KRaft 구성으로 로컬 개발 환경 기준

### [Task-20260310-03] 운영용 Compose 기본 구성 추가
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): `docker-compose.prod.yml`을 실행 가능한 기본 운영 스택으로 구성한다.
- 작업 단위:
  - [x] WU-1: `env/.env.prod`와 dev compose 기준으로 서비스 요구사항 정리
  - [x] WU-2: `api/worker/postgres/redis/kafka/prometheus` 서비스 정의
  - [x] WU-3: Kafka를 ZooKeeper 없는 `apache/kafka:4.0.0` KRaft로 구성
  - [x] WU-4: `docker compose config`로 유효성 검증
- 메모/이슈:
  - 현재는 단일 노드 운영 기본안이며, HA/replication은 후속 작업 범위

### [Task-20260310-04] A 아키텍처 E2E 실행 검증
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): docker compose 환경에서 API → Kafka → Worker → DB 파이프라인이 정상 동작하는지 검증한다.
- 작업 단위:
  - [x] WU-1: docker compose 전체 서비스 기동(api/worker/postgres/redis/kafka)
  - [x] WU-2: POST /jobs 요청 테스트
  - [x] WU-3: Kafka request-topic 메시지 발행 확인(오프셋 증가 확인)
  - [x] WU-4: Worker consume 및 처리 확인
  - [x] WU-5: Job 상태(PENDING → PROCESSING → SUCCESS) DB 반영 확인
  - [x] WU-6: GET /jobs/{job_id} 결과 조회 확인
  - [x] WU-7: Idempotency-Key 중복 요청 테스트
- 메모/이슈:
  - Apache Kafka 4.0 env 변수 형식(`KAFKA_*`)으로 compose 수정
  - worker 처리 중 `MissingGreenlet` 버그를 수정(`SqlAlchemyJobRepository.update_status`)
  - Worker 재시작 + 동일 job 이벤트 재주입 후 중복 처리 방지 확인
  - Kafka consumer group(`architecture-a-worker`) lag=0 확인

### [Task-20260310-05] Observability 스택 구축
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): 관측 스택 compose 및 설계 문서/실행 문서를 추가해 운영 판단 근거를 명시한다.
- 작업 단위:
  - [x] WU-1: `deploy/observability-compose.yml` 생성(prometheus/grafana/fluent-bit/elasticsearch/kibana)
  - [x] WU-2: Observability 설정 파일 생성(prometheus, fluent-bit)
  - [x] WU-3: 아키텍처 문서에 `Observability Architecture` 섹션 추가
  - [x] WU-4: README 실행/검증 가이드 업데이트
  - [x] WU-5: observability compose 실제 기동 및 `ps` 상태 확인
- 메모/이슈:
  - 서비스 compose 네트워크(`morphflow_default`)를 외부 네트워크로 재사용
  - Kafka lag/Redis/Postgres exporter 스크랩 대상은 Prometheus 설정에 반영

### [Task-20260310-06] Observability 완성(Exporter + 알람/대시보드)
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): exporter 실제 배포와 알람/대시보드 기본 구성을 통해 A/B/C 전환 판단 지표를 즉시 확인 가능한 상태로 만든다.
- 작업 단위:
  - [x] WU-1: observability compose에 `kafka/redis/postgres exporter` 서비스 추가
  - [x] WU-2: Prometheus rule 파일(`prometheus-rules.yml`) 추가 및 alert rule 로드
  - [x] WU-3: Grafana provisioning(datasource/dashboard provider) 및 기본 대시보드 추가
  - [x] WU-4: README에 targets/rules/log 검증 명령 추가
  - [x] WU-5: compose 재기동 후 Prometheus targets/rules, Kibana/Elasticsearch 로그 수집 확인
- 메모/이슈:
  - Prometheus targets 확인 결과 `api/worker/kafka_exporter/redis_exporter/postgres_exporter` 모두 `up`
  - `worker_job_processing_seconds_bucket`는 워커 측 해당 metric이 존재할 때 `WorkerProcessingTimeHigh` 알람이 실측 동작

### [Task-20260310-07] DB 마이그레이션 체계 도입
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): Job/Event 스키마를 Alembic 기반으로 전환하고 compose 환경에서 적용/검증 가능하게 만든다.
- 작업 단위:
  - [x] WU-1: Alembic 초기 설정 파일(`alembic.ini`, `alembic/env.py`, `script.py.mako`) 추가
  - [x] WU-2: Job/Event 기준 initial migration(`20260310_0001`) 생성
  - [x] WU-3: 앱/워커 시작 시 `create_all` 제거
  - [x] WU-4: compose에 `migrate` 서비스 추가 및 `depends_on: service_completed_successfully` 적용
  - [x] WU-5: README에 migration 적용/롤백/초기화 절차 추가
  - [x] WU-6: `docker compose up -d --build migrate` + `alembic_version` 조회로 적용 검증
- 메모/이슈:
  - Docker 이미지에 Alembic 파일이 포함되도록 `Dockerfile`에 `COPY alembic/`, `COPY alembic.ini` 추가
  - 기존 create_all 기반 DB가 이미 존재하는 환경은 `alembic stamp head` 또는 DB 재초기화 후 적용 권장

### [Task-20260310-08] API/Worker 통합 테스트 보강
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): 핵심 비동기 처리 흐름과 멱등성/상태 전이를 자동 테스트로 검증한다.
- 작업 단위:
  - [x] WU-1: POST /jobs 정상 생성 테스트 추가
  - [x] WU-2: GET /jobs/{job_id} 상태 조회 테스트 추가
  - [x] WU-3: 동일 Idempotency-Key 중복 요청 테스트 추가
  - [x] WU-4: Worker consume 후 상태 전이(PENDING → PROCESSING → SUCCESS) 테스트 추가
  - [x] WU-5: 실패 시 FAILED 반영 테스트 추가
  - [x] WU-6: 중복 consume 방어 테스트 추가
- 메모/이슈:
  - 외부 인프라 의존을 줄이기 위해 `sqlite+aiosqlite` 기반 통합 테스트로 구성
  - 실행 검증: `uv run --extra dev pytest -q tests/test_api_worker_integration.py tests/test_event_envelope.py` (`7 passed`)

### [Task-20260310-09] CI 검증 파이프라인 추가
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): 테스트와 Alembic 마이그레이션 검증이 CI에서 자동 수행되도록 구성한다.
- 작업 단위:
  - [x] WU-1: CI workflow 파일 추가
  - [x] WU-2: pytest 실행 단계 추가
  - [x] WU-3: `alembic upgrade head` 검증 단계 추가
  - [x] WU-4: migration 누락/스키마 드리프트 방지 체크(`alembic check`) 추가
  - [x] WU-5: README에 CI 검증 항목 반영
- 메모/이슈:
  - CI 최소 기준: `pytest -q` + `alembic upgrade head` + `alembic check`
  - Postgres service container 기반으로 migration 검증 수행

### [Task-20260310-10] Readiness/운영 상태 점검 고도화
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): 서비스 준비 상태를 실제 의존성 기준으로 판별할 수 있도록 readiness 체크를 고도화한다.
- 작업 단위:
  - [x] WU-1: DB readiness 체크 추가
  - [x] WU-2: Redis readiness 체크 추가
  - [x] WU-3: Kafka readiness 체크 추가
  - [x] WU-4: `/health/ready` 응답 구조 개선
  - [x] WU-5: compose/startup 순서와 readiness 관계 문서화
- 메모/이슈:
  - `/health/ready`는 dependency-aware 방식으로 전환되어 하나라도 실패 시 `503` 반환
  - 실행 검증: `uv run --extra dev pytest -q tests/test_health_readiness.py tests/test_api_worker_integration.py tests/test_event_envelope.py` (`9 passed`)

### [Task-20260310-11] A/B/C 확장 포인트 코드 구조화
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): 현재 A 아키텍처 코드베이스에서 B/C 구조로 확장 가능한 역할 분리 포인트를 코드와 문서에 명시한다.
- 작업 단위:
  - [x] WU-1: worker role 인터페이스 정리
  - [x] WU-2: inference/downstream 분리 포인트 추가
  - [x] WU-3: topic 명 분리 가능 설정 추가
  - [x] WU-4: 전환 기준(metric 기반) 문서화
  - [x] WU-5: README/architecture 문서 업데이트
- 메모/이슈:
  - `WorkerRolePort` + `app.workers.roles`로 역할 분리 구조를 고정하고, 현재는 A 경로를 유지하기 위해 inference/downstream도 동일 처리 경로를 재사용
  - 실행 검증: `uv run --extra dev pytest -q tests/test_worker_roles.py tests/test_health_readiness.py tests/test_api_worker_integration.py tests/test_event_envelope.py` (`12 passed`)

### [Task-20260310-12] 장애 시나리오별 Runbook 문서화
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): 주요 장애 시나리오별 예측 지표, 1차 대응, 복구, 후속조치를 문서화한다.
- 작업 단위:
  - [x] WU-1: Kafka lag 급증 시나리오 정리
  - [x] WU-2: Worker 처리 지연 시나리오 정리
  - [x] WU-3: DB latency 증가 시나리오 정리
  - [x] WU-4: Redis 장애 시나리오 정리
  - [x] WU-5: 후속 RCA/재발방지 절차 정리
- 메모/이슈:
  - `docs/incident_runbook_abctransition.md` 신규 문서로 시나리오별 `탐지 지표 -> 1차 대응 -> 복구 -> RCA` 표준화
  - 각 시나리오에 A/B/C 전환 판단 기준을 연결해 운영 의사결정 근거를 명시

### [Task-20260310-13] 부하 테스트 및 성능 지표 수집
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): 서비스 부하 상황에서 처리량과 지연을 측정하고 A/B/C 전환 판단 지표를 확보한다.
- 작업 단위:
  - [x] WU-1: k6 기반 부하 테스트 스크립트 작성
  - [x] WU-2: 동시 사용자 10/30/50 테스트
  - [x] WU-3: Grafana metrics 캡처(Prometheus query 기반 수치 캡처)
  - [x] WU-4: Kafka lag / worker latency 분석
  - [x] WU-5: 결과 문서화
- 메모/이슈:
  - 스크립트: `tests/perf/jobs_load_test.js`, 결과 JSON: `reports/perf/k6_vus10|30|50.json`
  - 보고서: `docs/perf_test_report_20260310.md` (k6 수치 + Prometheus 지표 + A/B/C 전환 판단 포함)

### [Task-20260310-14] GPU 추론 최소 연결 및 B 아키텍처 검증
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): inference worker를 실제 GPU 추론 또는 GPU inference simulator와 연결하여 B 아키텍처 병목을 검증 가능한 상태로 만든다.
- 작업 단위:
  - [x] WU-1: inference-topic 및 inference worker 실제 동작 경로 구현
  - [x] WU-2: DummyTaskProcessor 대신 GPU inference simulator 추가
  - [x] WU-3: semaphore / concurrency 설정 적용
  - [x] WU-4: GPU util / worker latency / Kafka lag 관측 metrics 연결
  - [x] WU-5: 부하 테스트 재실행 및 결과 문서화
- 메모/이슈:
  - B 모드 override compose: `deploy/docker-compose.bmode.override.yml`
  - 보고서: `docs/perf_test_report_bmode_20260310.md`, 결과 JSON: `reports/perf/k6_bmode_vus10|30|50.json`
  - B 모드 50VU에서 실패율(약 0.35%) 및 inference lag 누적 재현으로 병목 검증 가능 상태 확인

### [Task-20260310-15] Retry / DLQ 전략 구현
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): Kafka 기반 EDA 구조에서 실패 이벤트의 무한 재처리를 방지하도록 retry topic 및 DLQ 전략을 구현한다.
- 작업 단위:
  - [x] WU-1: `retry-topic`, `dlq-topic` 설정 및 env 변수 정의
  - [x] WU-2: `retry-count`/`original-topic`/`error-reason` header 기반 재시도 로직 구현
  - [x] WU-3: exponential backoff 정책 및 retry publish 구현
  - [x] WU-4: retry 초과 이벤트의 DLQ 전송 및 원본 payload 유지
  - [x] WU-5: `retry_published_total`, `retry_failure_total`, `dlq_messages_total` metric/alert 반영
  - [x] WU-6: README/working spec/runbook에 DLQ 운영 및 replay 절차 반영
- 메모/이슈:
  - worker는 기본 consume topic + `retry-topic`을 함께 구독
  - 실패 시 idempotency lock은 해제해 retry 처리 가능하도록 조정

### [Task-20260310-16] C 아키텍처 최소 실구현
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): 추론 완료 이후 저장/후처리 구간을 downstream topic 및 downstream worker로 분리하여 C 아키텍처 최소 실행 버전을 구현한다.
- 작업 단위:
  - [x] WU-1: downstream-topic 설정/환경값 정비 및 C 모드 topic 라우팅 반영
  - [x] WU-2: inference 완료 후 downstream event publish 경로 구현
  - [x] WU-3: downstream worker role/consumer 동작 경로 구현
  - [x] WU-4: downstream dummy task 분리 실행 및 최종 SUCCESS 반영
  - [x] WU-5: downstream lag/latency 관측용 metric 및 alert rule 추가
  - [x] WU-6: README/architecture/runbook 문서에 C 경로 반영
  - [x] WU-7: 시나리오 테스트(`tests/test_c_architecture_flow.py`)로 분리 동작 검증
- 메모/이슈:
  - `ARCHITECTURE_MODE=C|BC`에서 API는 `inference-topic`으로 발행하고, inference worker는 `downstream-topic`으로 전달
  - downstream worker는 후처리 완료 시 job 결과를 `inference + downstream` 구조로 저장
  - compose 실행용 override: `deploy/docker-compose.cmode.override.yml`

### [Task-20260310-17] 운영/아키텍처 최종 정리 및 문서 패키징
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): A/B/C 아키텍처, Retry/DLQ, Observability를 운영 관점에서 종합 정리한 최종 문서 패키지를 완성한다.
- 작업 단위:
  - [x] WU-1: A/B/C 아키텍처 비교(흐름/병목/전환 기준) 정리
  - [x] WU-2: Observability 구조(Prometheus/Grafana/EFK/exporter/alert) 문서화
  - [x] WU-3: Retry/DLQ 흐름 다이어그램(`request/retry/dlq-topic`) 추가
  - [x] WU-4: A/B/C 성능 비교 요약 문서 생성
  - [x] WU-5: 운영 Runbook 핵심 대응 절차 요약 정리
  - [x] WU-6: README 실행/모드/observability/테스트 섹션 최종 재정리
- 메모/이슈:
  - 최종 패키지 문서: `docs/architecture_operations_package_20260310.md`
  - 성능 요약 문서: `docs/perf_summary_abc_20260310.md`
  - C 모드는 현재 시나리오 검증까지 완료, k6 부하 실측은 후속 태스크로 권장

### [Task-20260310-18] Dummy Processor를 Inference Simulator로 대체
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): 실제 GPU 모델 연동 전 단계에서 inference 병목/동시성/지연/실패/재시도 검증이 가능하도록 기본 processor를 simulator로 전환한다.
- 작업 단위:
  - [x] WU-1: simulator failure rate 설정값 및 metric 추가
  - [x] WU-2: processor factory(`simulator|dummy`) 추가로 교체 가능한 구조 유지
  - [x] WU-3: unified/inference/downstream(non-C) 경로의 기본 processor를 simulator로 전환
  - [x] WU-4: env(dev/prod) 설정값 추가
  - [x] WU-5: simulator 단위 테스트 및 기존 통합 테스트 검증
- 메모/이슈:
  - `WORKER_PROCESSOR_BACKEND=dummy`로 언제든 기존 dummy 경로 사용 가능
  - 검증 결과: `uv run --extra dev pytest -q ...` (`22 passed`)

### [Task-20260310-19] C 아키텍처 부하 테스트 실측
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-11
- 목표(DoD): C architecture에서 inference/downstream 분리 효과를 실제 부하 테스트로 검증한다.
- 작업 단위:
  - [x] WU-1: k6 부하 테스트 실행(10/30/50 VU)
  - [x] WU-2: downstream lag 실측(query 기반)
  - [x] WU-3: downstream latency 실측(query 기반)
  - [x] WU-4: A/B/C 성능 비교 문서 업데이트
- 메모/이슈:
  - C 모드 보고서: `docs/perf_test_report_cmode_20260311.md`
  - 결과 JSON: `reports/perf/k6_cmode_vus10.json`, `reports/perf/k6_cmode_vus30.json`, `reports/perf/k6_cmode_vus50.json`
  - downstream worker metric 수집을 위해 `deploy/observability/prometheus.yml`의 worker scrape target에 `downstream-worker:9001` 추가
