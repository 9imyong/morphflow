# 데이터 사전

모든 컬럼을 복제하지 않고, 이름만으로 오해할 수 있거나 정책적으로 중요한 항목만 기록합니다. 전체 구조는 [데이터 구조 개요](schema.md)와 마이그레이션을 참조합니다.

| 데이터 항목 | 업무 의미 | 소유자 | 민감도 | 보존 기간 | 비고 |
|---|---|---|---|---|---|
| `jobs.id` | 작업 식별자. 클라이언트에게 `job_id`로 노출 | `api` | 내부 | 작업 수명 동안 | UUID 문자열. 생성 후 변경 없음 |
| `jobs.request_payload` | 클라이언트가 보낸 입력 원본 | `api` | **주의** | 정책 미정 | 가공 없이 보관. 개인정보 포함 입력을 받게 되면 분류·마스킹 정책이 선행되어야 함 |
| `jobs.status` | 현재 처리 상태 | 워커 | 내부 | 작업 수명 동안 | C·BC 모드에서 `PROCESSING`은 추론 중과 후단 대기 중을 모두 포함 |
| `jobs.result` | 처리 결과 | 워커 | 내부 | 정책 미정 | 완료 시점에만 기록. 완료 후 덮어쓰지 않음 |
| `jobs.error_message` | 최근 실패 사유 | 워커 | 내부 | 작업 수명 동안 | 재시도가 성공하면 `NULL`로 지워짐. **실패 이력이 아니라 현재 오류 상태** |
| `jobs.retry_count` | 재시도 횟수 | 없음 | 내부 | 해당 없음 | **현재 미사용.** 항상 0. 실제 기준은 Kafka `retry-count` 헤더 |
| `job_events.event_id` | 이벤트 고유 식별자 | 발행 주체 | 내부 | 무기한 | 유니크 제약으로 중복 기록 차단 |
| `job_events.trace_id` | 작업 흐름 상관관계 식별자 | `api` | 내부 | 무기한 | **OpenTelemetry 추적 ID가 아님.** 작업 생성 시 발급하는 별도 UUID |
| `job_events.source` | 이벤트를 남긴 주체 | 발행 주체 | 내부 | 무기한 | `api`, `worker`, `inference-worker`, `downstream-worker` |
| `job_events.payload` | 단계별 데이터 | 발행 주체 | **주의** | 무기한 | 요청 원본과 처리 결과를 포함할 수 있음 |

## 주의가 필요한 항목

- **`error_message`는 이력이 아닙니다.** 재시도가 성공하면 지워지므로 실패 분석에는 `job_events`의 `FAILED` 이벤트를 사용해야 합니다.
- **`retry_count`를 신뢰하지 마십시오.** 애플리케이션이 갱신하지 않습니다.
- **`trace_id`로 Jaeger를 조회할 수 없습니다.** 추적 시스템과 연결되지 않은 별도 식별자입니다.
- `request_payload`와 `job_events.payload`는 보존 정책이 없어 무기한 누적됩니다.

## 관련 문서

- [데이터 구조 개요](schema.md)
- [데이터 아키텍처](../../architecture/data.md)
