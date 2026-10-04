---
id: ADR-0010
title: Kafka 발행을 트랜잭셔널 아웃박스로 전환
status: 승인됨
date: 2026-09-13
decision_makers: [김용준]
related_requirements: [REQ-platform-001]
supersedes: null
superseded_by: null
---

# ADR-0010: Kafka 발행을 트랜잭셔널 아웃박스로 전환

## 맥락

API는 Job을 DB에 커밋한 뒤 Kafka에 따로 발행했고, 추론 워커도 결과 커밋과 downstream 발행을 따로 했습니다. DB와 Kafka는 한 트랜잭션에 묶이지 않으므로 그 사이에서 프로세스가 죽거나 발행이 실패하면 메시지가 유실됩니다.

- Job은 `PENDING`으로 남고 아무도 다시 보지 않습니다.
- 같은 멱등성 키로 재요청하면 고착된 Job을 정상 접수로 돌려줍니다.
- downstream은 그 Job을 영영 받지 못합니다.

## 결정 기준

- 상태 변경이 커밋되면 발행도 반드시 일어나는가
- 발행 실패가 상태를 오염시키지 않는가
- 같은 Job의 메시지 순서가 유지되는가
- 릴레이를 여러 개 띄워도 같은 메시지를 동시에 집지 않는가

## 검토한 대안

### 대안 1: 발행 후 커밋 / 커밋 후 발행 순서 조정

- 장점: 구조 변경 없음
- 단점: 어느 순서든 둘 사이의 실패 창은 남음
- 위험: 유실 또는 존재하지 않는 Job에 대한 메시지 발생

### 대안 2: 고착된 `PENDING` Job을 주기적으로 다시 발행

- 장점: 기존 발행 경로 유지
- 단점: "고착" 판정 기준이 시간 추측에 의존. downstream 발행 유실은 다루지 못함
- 위험: 정상 대기 중인 Job을 중복 발행

### 대안 3: 트랜잭셔널 아웃박스 + 폴링 릴레이

- 장점: 발행할 메시지를 상태 변경과 같은 트랜잭션에 적재해 둘의 원자성을 DB가 보장
- 단점: 테이블과 릴레이가 추가됨. 발행 지연이 폴링 주기만큼 늘어남
- 위험: 전달 보장이 at-least-once이므로 소비 측 멱등 처리가 필수

### 대안 4: CDC(Debezium 등)로 아웃박스 테이블 전송

- 장점: 폴링 없이 로그 기반으로 전송
- 단점: Kafka Connect와 커넥터 운영이 추가됨
- 위험: 현재 규모에 비해 운영 비용이 큼

## 결정

대안 3을 채택합니다.

- `outbox_messages` 테이블을 추가합니다(migration `20260913_0002`).
- API의 Job 생성과 추론 워커의 downstream 발행은 상태 변경과 **같은 트랜잭션**에 아웃박스 행을 적재합니다.
- `OutboxRelay`가 커밋된 `PENDING` 행을 id 순으로 읽어 발행하고 `PUBLISHED`로 표시합니다.
  - 발행 실패 시 상태는 `PENDING`으로 두고 `attempts`만 올려 다음 주기에 재시도합니다.
  - 배치 중간에서 실패하면 뒤 메시지를 보내지 않아 순서가 뒤집히지 않습니다.
  - 행을 `FOR UPDATE SKIP LOCKED`로 가져와 여러 릴레이가 같은 행을 집지 않습니다.
- 설정: `OUTBOX_RELAY_BATCH_SIZE`(기본 100), `OUTBOX_RELAY_POLL_INTERVAL_SECONDS`(기본 0.5)
- 지표: `outbox_published_total`, `outbox_publish_failure_total`, `outbox_pending_backlog`

## 결과

### 긍정적 결과

- 커밋 직후 프로세스가 죽어도 행이 `PENDING`으로 남아 다음 주기에 발행됩니다.
- 발행 실패 후 Kafka가 복구되면 남은 메시지가 그대로 나갑니다.

### 부정적 결과와 비용

- 전달 보장은 at-least-once입니다. 발행 후 `PUBLISHED` 표시 전에 죽으면 같은 메시지가 다시 나갑니다. 소비 측은 [ADR-0008](ADR-0008-conditional-status-transition.md)·[ADR-0009](ADR-0009-db-lease-fencing-token.md)의 조건부 전이와 lease로 중복을 흡수합니다.
- 릴레이는 행 잠금을 쥔 트랜잭션 안에서 Kafka에 발행합니다. Kafka가 느려지면 트랜잭션이 길어집니다.
- 재시도·DLQ 발행은 아웃박스를 거치지 않고 워커가 직접 합니다. 발행 후 오프셋 커밋 전에 죽으면 재시도 메시지가 중복될 수 있으나, 이 역시 소비 측 멱등 처리로 흡수합니다.
- `outbox_messages`의 `PUBLISHED` 행을 정리하는 보존 정책이 아직 없습니다.

## 검증 방법

`tests/test_status_cas_and_outbox.py`

- `test_job_creation_writes_outbox_not_kafka`
- `test_publish_failure_keeps_message_for_retry`
- `test_relay_marks_published_and_does_not_resend`
- `test_outbox_preserves_order_on_partial_failure`
