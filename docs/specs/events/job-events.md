# 이벤트 명세: 작업 이벤트

## 개요

| 항목 | 내용 |
|---|---|
| 소유 팀 | 김용준 |
| 발생 조건 | 작업 접수, 처리 시작, 단계 완료, 실패 시점 |
| 발행 채널 | `request-topic`, `downstream-topic`, `retry-topic`, `retry-downstream-topic`, `dlq-topic` |
| 계약 위치 | [`asyncapi.yaml`](asyncapi.yaml), [`schemas/job-event-envelope.json`](schemas/job-event-envelope.json) |

## 의미

모든 이벤트는 **이미 일어난 사실**을 나타냅니다.

| event_type | 의미 | 발행 주체 | Kafka 발행 |
|---|---|---|---|
| `REQUESTED` | 작업이 접수되어 저장되었다 | `api` | `request-topic` |
| `PROCESSING_STARTED` | 워커가 처리를 시작했다 | 워커 | 기록만 |
| `PROCESSING_COMPLETED` | 워커가 처리를 완료했다 (A·B 모드) | 워커 | 기록만 |
| `INFERENCE_COMPLETED` | 추론이 완료되었다 (C·BC 모드) | 추론 워커 | `downstream-topic` |
| `DOWNSTREAM_COMPLETED` | 후단 처리가 완료되었다 | 후단 워커 | 기록만 |
| `FAILED` | 처리가 실패했다 | 워커 | 기록만 |

"기록만"은 `job_events` 테이블에만 남고 Kafka로 발행되지 않는다는 뜻입니다. 따라서 **Kafka 토픽을 구독해도 전체 생애주기를 알 수 없으며**, 이력의 기준은 데이터베이스입니다.

## 전달 규칙

- **전달 보장**: at-least-once. 오프셋은 처리 후 커밋합니다.
- **순서 보장 범위**: 없음. 메시지에 파티션 키를 지정하지 않으므로 같은 `job_id`의 이벤트도 서로 다른 파티션에 분산될 수 있습니다.
- **중복 가능성**: 있습니다. 커밋 전 장애, 배치 재처리, 재시도 토픽 재유입이 모두 중복 경로입니다.
- **소비자 멱등성 기준**: `job_id`입니다. 소비자는 Redis 처리 잠금과 데이터베이스 상태 확인으로 중복 처리를 방지해야 합니다. 자세한 내용은 [ADR-0002](../../decisions/ADR-0002-idempotency-strategy.md)에 있습니다.
- **재시도와 실패 보관**: `RETRY_MAX_COUNT`까지 재시도 채널을 순환한 뒤 `dlq-topic`으로 격리합니다. [ADR-0003](../../decisions/ADR-0003-retry-and-dlq.md)을 따릅니다.

순서를 보장하지 않는 대신 멱등성으로 정합성을 확보하는 구조입니다. 순서 의존적인 소비자를 추가하려면 파티션 키 도입을 먼저 결정해야 합니다.

## 재시도 헤더

| 헤더 | 값 | 용도 |
|---|---|---|
| `retry-count` | 문자열 정수 | 재시도 횟수. 파싱 실패 시 0으로 간주 |
| `original-topic` | 최초 발행 채널 | 워커가 자신의 경로가 아닌 재시도 메시지를 건너뛰는 데 사용 |
| `error-reason` | 실패 사유 문자열 | DLQ 적재 원인 분류 |

## 스키마와 호환성

- 구조의 기준은 [`schemas/job-event-envelope.json`](schemas/job-event-envelope.json)입니다.
- Envelope의 최상위 필드는 **아키텍처 모드와 무관하게 고정**합니다. 변경하려면 ADR이 필요합니다.
- `payload` 내부는 채널별로 다르며 필드 추가는 하위 호환으로 봅니다.
- `event_type` 값 추가는 소비자가 모르는 값을 만들 수 있으므로, 소비자는 알 수 없는 `event_type`을 무시하도록 구현해야 합니다.
- `trace_id`는 현재 작업 생성 시 발급하는 UUID이며 OpenTelemetry 추적 ID와 일치하지 않습니다. 연결은 [위험과 기술 부채](../../architecture/risks-technical-debt.md)에서 추적합니다.

## 보안과 보존

- 이벤트 `payload`에는 클라이언트가 보낸 입력이 그대로 포함됩니다. 개인정보가 포함될 수 있는 입력을 받게 되면 분류와 마스킹 정책이 선행되어야 합니다.
- Kafka 보존 기간은 브로커 기본값을 따르며 별도로 설정하지 않았습니다.
- `job_events` 테이블에는 보존 정책이 없어 무기한 증가합니다.
