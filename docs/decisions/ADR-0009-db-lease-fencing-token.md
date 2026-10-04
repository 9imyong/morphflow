---
id: ADR-0009
title: 작업 소유권을 Redis 잠금 대신 DB lease와 펜싱 토큰으로 관리
status: 승인됨
date: 2026-09-13
decision_makers: [김용준]
related_requirements: [REQ-platform-001]
supersedes: ADR-0002
superseded_by: null
---

# ADR-0009: 작업 소유권을 Redis 잠금 대신 DB lease와 펜싱 토큰으로 관리

> [ADR-0002](ADR-0002-idempotency-strategy.md) 중 **처리 단계 잠금(`idem:job:{job_id}`)만** 대체합니다. 요청 단계 멱등성(`idem:req:{Idempotency-Key}`)은 그대로 유지합니다.

## 맥락

[ADR-0002](ADR-0002-idempotency-strategy.md)는 워커가 Job을 처리하기 전에 Redis `SET NX EX`로 `idem:job:{job_id}`를 예약했습니다. 이 방식에는 두 가지 문제가 있었습니다.

- 추론이 TTL보다 길어지면 TTL이 만료되는 순간 다른 워커가 같은 Job을 잡습니다. 외부 호출이 두 번 일어납니다.
- 뒤늦게 끝난 첫 워커는 자신이 소유권을 잃었다는 사실을 모릅니다. 인계받은 워커의 결과를 덮어씁니다.

[ADR-0008](ADR-0008-conditional-status-transition.md)의 상태 조건도 이를 막지 못합니다. 인계 직후 상태는 여전히 `PROCESSING`이라 옛 소유자의 `PROCESSING -> SUCCESS`가 조건을 통과하기 때문입니다.

## 결정 기준

- 죽은 워커의 Job을 다른 워커가 회수할 수 있는가
- 소유권을 잃은 워커의 쓰기가 반드시 거부되는가
- 소유권 판정과 상태 전이가 원자적으로 이루어지는가
- 저장소가 하나 늘거나 줄 때 정합성 판단이 흩어지지 않는가

## 검토한 대안

### 대안 1: Redis 잠금 유지, TTL만 늘림

- 장점: 변경 최소
- 단점: 만료 순간의 동시 처리 문제는 그대로. 죽은 워커의 회수가 늦어짐
- 위험: 옛 소유자의 쓰기를 막을 수단이 여전히 없음

### 대안 2: Redlock 등 분산 잠금

- 장점: Redis 단일 장애점 완화
- 단점: 잠금이 만료된 뒤의 쓰기를 막지 못하는 점은 같음. 펜싱 토큰이 별도로 필요
- 위험: 운영 복잡도만 늘고 핵심 문제는 남음

### 대안 3: `jobs` 행의 lease + 단조 증가 epoch(펜싱 토큰)

- 장점: 선점과 `PROCESSING` 전이를 한 번의 조건부 UPDATE로 처리. 결과 기록 시 epoch 비교로 옛 소유자를 확실히 차단
- 단점: 상태 저장소(DB)에 쓰기가 늘어남. lease 만료 판정이 워커 시계에 의존
- 위험: lease가 실제 처리 시간보다 짧으면 살아 있는 워커의 Job이 회수됨

## 결정

대안 3을 채택합니다.

- `jobs`에 `lease_owner`, `lease_expires_at`, `lease_epoch`를 추가합니다(migration `20260913_0003`).
- **선점** (`claim_for_processing`): `PENDING`·`FAILED`이거나 lease가 만료된 `PROCESSING`일 때만 성공합니다. 성공하면 `lease_epoch`가 1 증가합니다.
- **결과 기록** (`update_status`): `WHERE lease_owner = ? AND lease_epoch = ?`를 함께 겁니다. 소유권을 빼앗긴 워커의 쓰기는 조건에서 탈락하고, 그 워커는 인계받은 쪽의 결과를 정답으로 보고 조용히 종료합니다.
- **연장** (`renew_lease`): 같은 owner·epoch일 때만 성공합니다.
- 살아 있는 lease를 만나면 `LEASE_HELD`로 재시도 경로에 넘깁니다.
- 회수 횟수는 `job_lease_takeover_total`로 집계합니다.
- Redis는 요청 단위 멱등성만 담당하도록 `IdempotencyPort`를 축소합니다.

## 결과

### 긍정적 결과

- 살아 있는 lease는 두 번째 워커를 막고, 만료 후에는 회수됩니다.
- 인계 직후 옛 소유자의 쓰기가 거부됩니다. 펜싱 조건을 제거하면 해당 테스트가 실패하는 것을 확인했습니다.
- 소유권 판정의 기준이 DB 하나로 모였습니다.

### 부정적 결과와 비용

- lease 만료 판정에 각 워커의 시계를 씁니다. 워커 간 시계가 크게 어긋나면 회수 시점이 흔들리므로 NTP 동기화를 전제합니다.
- `renew_lease`는 구현돼 있지만 **처리 루프에서 아직 호출하지 않습니다.** lease 길이는 `WORKER_PROCESSING_TTL_SECONDS`(기본 1800초)로 고정이며, 이보다 오래 걸리는 처리는 살아 있어도 회수됩니다. 쓰기는 펜싱으로 막히지만 처리 자체는 중복됩니다.
- `LEASE_HELD`도 재시도 횟수를 소모합니다. 정상 처리 중인 Job의 중복 메시지가 `RETRY_MAX_COUNT`를 넘기면 DLQ로 갑니다.
- downstream 워커에는 아직 lease를 적용하지 않았습니다.

### 후속 작업

- [ ] 장시간 처리 중 `renew_lease` 주기 호출
- [ ] `LEASE_HELD`를 일반 실패와 분리해 재시도 횟수에서 제외
- [ ] downstream 워커에 lease 적용

## 검증 방법

`tests/test_lock_recovery_flow.py`

- `test_live_lease_blocks_second_worker_then_expiry_allows_takeover`
- `test_expired_owner_cannot_write_result_after_takeover`
- `test_renew_lease_fails_after_takeover`
- `test_inference_lease_contention_then_recovers`
