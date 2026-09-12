# 용어집

프로젝트에서 의미가 모호하거나 팀별로 다르게 쓰일 수 있는 용어를 기록합니다.

| 용어 | 정의 | 사용하지 않을 표현 | 비고 |
|---|---|---|---|
| 작업 (Job) | 클라이언트가 요청한 처리 단위. `jobs` 테이블의 한 행이며 클라이언트에게는 `job_id`로 노출 | 태스크, 요청 | 코드의 `Job`, API의 `job_id` |
| 이벤트 (Event) | 이미 일어난 사실의 기록. `job_events`의 한 행이자 Kafka 메시지 | 메시지, 로그 | 구조는 Envelope 참조 |
| Envelope | 모든 이벤트가 공유하는 공통 봉투 구조 | 페이로드, 스키마 | `payload`는 Envelope **안의** 한 필드 |
| 모드 (Mode) | `ARCHITECTURE_MODE` 값인 `A`·`B`·`C`·`BC`. 시스템 전체의 운영 형태 | 아키텍처, 버전 | 별도 서비스가 아니라 같은 서비스의 운영 형태 |
| 역할 (Role) | `WORKER_ROLE` 값인 `unified`·`inference`·`downstream`. 개별 워커의 담당 | 워커 타입 | 모드와 역할은 다른 축. 조합 규칙은 [구성 요소](architecture/building-blocks.md) 참조 |
| 진입 토픽 | API가 발행하고 워커가 소비하는 최초 채널(`request-topic`) | 요청 토픽, 인입 토픽 | 모드와 무관하게 고정 ([ADR-0004](decisions/ADR-0004-fixed-ingress-topic-and-group.md)) |
| 추론 (Inference) | 작업의 핵심 처리 단계 | GPU 처리, 연산 | 현재는 시뮬레이터가 특성만 재현 ([ADR-0006](decisions/ADR-0006-gpu-inference-simulator.md)) |
| 후단 (Downstream) | 추론 이후의 저장·전달·알림 단계 | 다운스트림, 후처리 | C·BC 모드에서만 별도 워커로 분리 |
| 적체 (Lag) | 컨슈머 그룹이 아직 처리하지 못한 메시지 수 | 지연, 밀림 | **지연이지 유실이 아님.** 지표는 `kafka_consumergroup_lag` |
| 요청 멱등성 키 | 클라이언트가 보내는 `Idempotency-Key`. 작업 중복 생성을 막음 | 멱등키 | Redis `idem:req:*` |
| 처리 잠금 | 워커가 작업 처리 전 확보하는 Redis 예약. 동시 처리를 막음 | 락, 멱등키 | Redis `idem:job:*`. 요청 멱등성 키와 **다른 것** |
| 재시도 (Retry) | 실패한 메시지를 재시도 채널로 재발행해 다시 처리하는 것 | 리트라이 | 횟수 기준은 `retry-count` 헤더 |
| DLQ | 재시도 한도를 초과한 메시지의 격리 채널(`dlq-topic`) | 데드레터, 실패 큐 | 자동 복구되지 않으며 수동 재주입 필요 |
| 재주입 (Replay) | DLQ 메시지를 원인 수정 후 다시 진입 토픽에 넣는 것 | 리플레이, 재처리 | 원인 수정 전 재주입 금지 |
| 전환 (Transition) | 관측 지표를 근거로 모드를 바꾸는 계획된 변경 | 마이그레이션, 스위칭 | 장애 대응 중에는 수행하지 않음 |

## 혼동하기 쉬운 구분

- **요청 멱등성 키와 처리 잠금은 다릅니다.** 전자는 API가 작업 중복 생성을 막고, 후자는 워커가 동시 처리를 막습니다. 둘 다 Redis를 쓰지만 목적과 수명이 다릅니다.
- **모드와 역할은 다른 축입니다.** 같은 `inference` 역할이라도 모드가 A·B면 직접 완료하고 C·BC면 후단으로 넘깁니다.
- **`FAILED`는 최종 상태가 아닐 수 있습니다.** 재시도가 남아 있으면 이후 `SUCCESS`로 바뀝니다.
- **완료 지표는 모드마다 다릅니다.** A·B는 `jobs_success_total`, C·BC는 `downstream_success_total`입니다.

새 용어를 추가할 때는 구현 이름과 사용자에게 노출되는 이름의 차이도 함께 기록합니다.
