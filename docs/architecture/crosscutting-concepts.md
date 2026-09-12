---
status: 현재
owners: [김용준]
last_reviewed: 2026-09-13
---

# 공통 개념

## 문서 목적

여러 구성 요소가 일관되게 따라야 하는 횡단 설계 원칙을 설명합니다. 정확한 API나 스키마 계약은 기술 명세에 둡니다.

## 언제 수정하는가

- 인증, 권한, 오류, 로깅, 관측성 같은 공통 정책이 바뀔 때
- 여러 구성 요소에 반복되는 구현 방식이 표준화될 때
- 보안 또는 개인정보 처리 원칙이 달라질 때

## 멱등성

두 단계로 방어합니다. 결정 배경은 [ADR-0002](../decisions/ADR-0002-idempotency-strategy.md)에 있습니다.

| 단계 | 키 | 생성 주체 | 목적 |
|---|---|---|---|
| 요청 멱등성 | `idem:req:{Idempotency-Key}` | `api` | 같은 키의 재요청이 Job을 중복 생성하지 않음 |
| 처리 멱등성 | `idem:job:{job_id}` | 워커 | 같은 Job을 두 워커가 동시에 처리하지 않음 |

원칙은 다음과 같습니다.

- 예약은 `SET key value NX EX ttl`로 수행하고, TTL로 영구 잠금을 방지합니다.
- **성공 시에만 잠금을 유지**하고(`COMPLETED`, `IDEMPOTENCY_TTL_SECONDS`), 실패 시에는 삭제해 재시도가 가능하게 합니다.
- 잠금 확보에 실패하면 데이터베이스의 현재 상태를 확인합니다. 이미 `SUCCESS`면 안전하게 커밋하고, 그 외에는 재시도 경로로 보냅니다.
- Redis는 1차 방어일 뿐이며 최종 판단은 데이터베이스 상태입니다. Redis가 비어 있어도 중복 완료가 발생하지 않아야 합니다.

## 오류 처리

- 업무 실패와 시스템 예외를 구분하지 않고 동일한 재시도·DLQ 경로로 처리합니다.
- 워커 역할은 `(성공 여부, 오류 사유)` 형태를 반환하며, 오류 사유는 `error-reason` 헤더로 전파됩니다.
- API는 실패를 상태 코드로 알리고, 처리 실패는 `GET /jobs/{job_id}`의 `status`와 `error`로 노출합니다.
- 재시도 정책과 DLQ 격리는 [ADR-0003](../decisions/ADR-0003-retry-and-dlq.md)을 따릅니다.

## 이벤트 Envelope

모든 이벤트는 동일한 봉투 구조를 사용하며 모드 전환과 무관하게 유지합니다. 필드 정의와 호환성 규칙은 [이벤트 명세](../specs/events/README.md)에 있습니다.

- 발행 주체는 `source`로 구분합니다: `api`, `worker`, `inference-worker`, `downstream-worker`
- 파티션 키는 지정하지 않습니다. 따라서 **같은 Job의 이벤트 순서는 토픽 간에 보장되지 않으며**, 순서 대신 멱등성으로 정합성을 확보합니다.

## 설정

- 모든 설정은 환경 변수로 주입하며 `app/core/config.py`의 `Settings`가 유일한 정의 지점입니다.
- 기본값은 로컬 실행이 가능한 값으로 두고, 환경별 차이는 Compose `env_file`과 Kubernetes ConfigMap·Secret으로 표현합니다.
- 동작을 바꾸는 설정(`ARCHITECTURE_MODE`, `WORKER_ROLE`, 배치·재시도 파라미터)은 코드 분기가 아니라 설정으로만 전환합니다.

## 관측 가능성

| 종류 | 수집 방식 | 비고 |
|---|---|---|
| 지표 | API는 `/metrics`, 워커는 9000 포트 | Prometheus가 수집 |
| 추적 | OpenTelemetry → OTLP gRPC → Jaeger | FastAPI, aiokafka, SQLAlchemy, Redis 자동 계측 |
| 로그 | 컨테이너 stdout → Fluent Bit → Elasticsearch | Kibana에서 조회 |

원칙은 다음과 같습니다.

- 단계별 지연을 **분리해서** 계측합니다. `job_processing_seconds`, `inference_processing_seconds`, `downstream_processing_seconds`가 각각 존재해야 병목 구간을 지목할 수 있습니다.
- 워커 트레이스는 역할별 서비스 이름으로 분리합니다(`morphflow-worker-{role}`).
- 지표 이름과 라벨은 모드 전환과 무관하게 고정합니다. 전환 전후 비교가 가능해야 하기 때문입니다.

현재 로그는 구조화 JSON이 아니며 이벤트의 `trace_id`가 OpenTelemetry 추적 ID와 연결되지 않습니다. [위험과 기술 부채](risks-technical-debt.md)에서 추적합니다.

## 인증과 권한

현재 API는 인증을 요구하지 않으며 신뢰 경계 안에서만 호출된다고 가정합니다. 외부 노출이 필요해지면 인증 방식 결정이 선행되어야 합니다.

## 관련 문서

- [실행 흐름](runtime.md)
- [이벤트 명세](../specs/events/README.md)
- [모니터링](../operations/monitoring.md)
- [ADR](../decisions/README.md)
