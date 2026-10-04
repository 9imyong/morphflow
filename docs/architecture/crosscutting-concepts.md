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

## 멱등성과 작업 소유권

요청과 처리 단계를 다른 수단으로 방어합니다.

| 단계 | 수단 | 주체 | 목적 | 근거 |
|---|---|---|---|---|
| 요청 멱등성 | Redis `idem:req:{Idempotency-Key}` 예약 | `api` | 같은 키의 재요청이 Job을 중복 생성하지 않음 | [ADR-0002](../decisions/ADR-0002-idempotency-strategy.md) |
| 상태 전이 | 허용 전이표 + 조건부 UPDATE(CAS) | 워커 | 늦게 도착한 쓰기가 앞선 결과를 덮어쓰지 않음 | [ADR-0008](../decisions/ADR-0008-conditional-status-transition.md) |
| 작업 소유권 | `jobs` 행의 lease + `lease_epoch` 펜싱 토큰 | 추론 워커 | 같은 Job을 두 워커가 동시에 처리하지 않고, 소유권을 잃은 워커의 쓰기를 차단 | [ADR-0009](../decisions/ADR-0009-db-lease-fencing-token.md) |
| 발행 보장 | 트랜잭셔널 아웃박스 | `api`, 추론 워커 | 상태 변경과 발행의 원자성 | [ADR-0010](../decisions/ADR-0010-transactional-outbox.md) |

원칙은 다음과 같습니다.

- 최종 판단은 데이터베이스 상태입니다. Redis는 요청 단계 중복 생성만 막습니다.
- 메시지는 at-least-once로 전달됩니다. 같은 메시지가 여러 번, 순서 없이 와도 CAS와 lease가 중복을 흡수해야 합니다.
- 상태 조건만으로는 lease 인계 직후 옛 소유자의 쓰기를 막지 못하므로 결과 기록에는 항상 epoch을 함께 겁니다.

## 오류 처리

- 업무 실패와 시스템 예외를 구분하지 않고 동일한 재시도·DLQ 경로로 처리합니다.
- 워커 역할은 `(성공 여부, 오류 사유)` 형태를 반환하며, 오류 사유는 `error-reason` 헤더로 전파됩니다.
- API는 실패를 상태 코드로 알리고, 처리 실패는 `GET /jobs/{job_id}`의 `status`와 `error`로 노출합니다.
- 재시도 정책과 DLQ 격리는 [ADR-0003](../decisions/ADR-0003-retry-and-dlq.md), 백오프와 오프셋 커밋 방식은 [ADR-0011](../decisions/ADR-0011-retry-at-header-and-prefix-commit.md)을 따릅니다.

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
