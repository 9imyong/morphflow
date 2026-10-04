---
id: ADR-0008
title: Job 상태 갱신을 조건부 전이(CAS)로 제한
status: 승인됨
date: 2026-09-13
decision_makers: [김용준]
related_requirements: [REQ-platform-001]
supersedes: null
superseded_by: null
---

# ADR-0008: Job 상태 갱신을 조건부 전이(CAS)로 제한

## 맥락

`update_status`는 현재 상태를 보지 않고 새 상태를 덮어썼습니다. 재시도나 처리 잠금 만료로 같은 Job을 두 워커가 잡으면, 늦게 끝난 쪽의 결과가 앞선 결과를 지웁니다. 이미 `SUCCESS`로 끝난 Job이 뒤늦게 도착한 실패로 `FAILED`가 되는 경우가 실제로 가능했습니다.

메시지는 at-least-once로 전달되므로 같은 Job에 대한 상태 쓰기가 여러 번, 순서 없이 도착하는 것을 전제해야 합니다.

## 결정 기준

- 늦게 도착한 쓰기가 앞선 결과를 덮어쓰지 못하는가
- 경쟁에서 진 쪽이 자신이 졌다는 사실을 알 수 있는가
- 처리 중 행을 오래 잠그지 않는가
- 허용되는 상태 전이를 한 곳에서 관리하는가

## 검토한 대안

### 대안 1: 읽고-바꾸고-쓰기 유지

- 장점: 기존 코드 그대로
- 단점: 읽기와 쓰기 사이의 경쟁을 막지 못함
- 위험: 결과 덮어쓰기가 조용히 발생

### 대안 2: `SELECT ... FOR UPDATE` 비관적 잠금

- 장점: 잠금을 쥔 동안 다른 쓰기를 확실히 막음
- 단점: 추론 시간 동안 트랜잭션과 행 잠금을 유지해야 함
- 위험: 처리 지연이 DB 커넥션 고갈로 번짐

### 대안 3: 허용 전이표 + 조건부 UPDATE

- 장점: 잠금 없이 한 문장으로 판정. `RETURNING`으로 실제 변경 여부를 바로 확인
- 단점: 호출부가 "변경 없음"을 경쟁 패배로 처리해야 함
- 위험: 전이표가 실제 흐름과 어긋나면 정상 전이가 거부됨

## 결정

대안 3을 채택합니다.

- 도메인에 허용 전이표 `ALLOWED_TRANSITIONS`를 둡니다(`app/domain/models.py`).

  ```text
  PENDING    -> PROCESSING, FAILED
  PROCESSING -> SUCCESS, FAILED, PROCESSING
  SUCCESS    -> (종착)
  ```

- 상태 변경은 `UPDATE ... WHERE id = ? AND status IN (허용된 출발 상태) RETURNING *`로만 합니다.
- 바뀐 행이 없으면 `None`을 돌려주고, 호출부는 이를 경쟁 패배로 보고 재처리하지 않습니다.
- 밀린 전이는 `job_transition_conflict_total{target_status}`로 집계합니다.

## 결과

### 긍정적 결과

- `SUCCESS` 이후 도착한 `FAILED`가 반영되지 않습니다.
- `PENDING`에서 `SUCCESS`로 건너뛰는 잘못된 전이가 거부됩니다.
- 중복 전달된 메시지가 이미 끝난 Job을 다시 처리하지 않습니다.

### 부정적 결과와 비용

- 상태 조건만으로는 **lease 인계 직후의 옛 소유자 쓰기**를 막지 못합니다. 인계 후에도 상태는 `PROCESSING`이라 옛 소유자의 `PROCESSING -> SUCCESS`가 조건을 통과합니다. 이 문제는 [ADR-0009](ADR-0009-db-lease-fencing-token.md)의 펜싱 토큰으로 막습니다.
- downstream 워커는 아직 lease를 쓰지 않고 상태 조건만 겁니다. downstream을 여러 개로 늘리면 같은 Job을 중복 처리할 수 있습니다([위험과 기술 부채](../architecture/risks-technical-debt.md)).

## 검증 방법

`tests/test_status_cas_and_outbox.py`

- `test_failed_cannot_overwrite_success`
- `test_success_requires_processing`
- `test_only_one_worker_claims_the_job`
- `test_duplicate_delivery_does_not_reprocess`
