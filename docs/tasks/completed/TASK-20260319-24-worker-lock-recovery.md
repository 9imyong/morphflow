---
id: TASK-20260319-24
title: 워커 잠금 경합 복구 경로 보강
status: Done
owner: 김용준
created: 2026-03-19
updated: 2026-03-19
---

# 작업: 워커 잠금 경합 복구 경로 보강

## Status

`Done`

## Objective

처리 잠금 확보에 실패했을 때 이를 성공으로 처리하지 않고, 재시도를 통해 복구 가능한 경로로 동작하게 합니다.

## Context

기존 구현은 잠금 확보 실패를 성공으로 간주해 오프셋을 커밋했습니다. 실제로는 다른 워커가 처리 중이거나 이전 처리가 비정상 종료된 상황인데, 커밋해 버리면 **해당 메시지가 조용히 사라집니다.** 아무도 그 작업을 완료하지 않았는데 큐에서는 없어진 상태가 됩니다.

## Scope

- `WorkerService`와 `InferencePipelineService`의 잠금 실패 분기
- 처리 시작 이벤트 기록 순서

## Out of Scope

- 잠금 경합과 일반 실패의 분리 (후속 과제)
- 후단 경로의 처리 잠금 도입

## Requirements

- 요구사항: [REQ-platform-001](../../requirements/REQ-platform-001-bottleneck-adaptive-pipeline.md) (REQ-platform-001-04)

## Implementation Plan

잠금 확보에 실패하면 데이터베이스의 현재 상태를 확인합니다. 이미 `SUCCESS`인 경우에만 안전하게 커밋하고, 그 외에는 `IN_PROGRESS_LOCK`을 반환해 재시도 경로로 보냅니다.

## TODO Checklist

- [x] WU-1: `WorkerService`에서 잠금 실패 시 `SUCCESS` 상태만 커밋, 그 외는 `IN_PROGRESS_LOCK` 반환
- [x] WU-2: `InferencePipelineService`에도 동일 분기 적용
- [x] WU-3: 장시간 처리 전에 `PROCESSING_STARTED` 이벤트를 먼저 기록하도록 순서 조정
- [x] WU-4: 회귀 테스트 실행

## 인수 조건

- [x] 잠금 경합 상황에서 메시지가 유실되지 않습니다.
- [x] 이미 완료된 작업의 중복 메시지는 정상 커밋됩니다.

## Validation

- [x] `tests/test_c_architecture_flow.py`
- [x] `tests/test_retry_runtime.py`
- [x] `tests/test_api_worker_integration.py`
- 결과: `10 passed`

## 위험과 되돌리기

잠금 경합이 재시도 횟수를 소모하므로 장시간 처리 중인 작업의 중복 메시지가 DLQ로 갈 수 있습니다. 되돌리려면 이전 분기 로직으로 복원하면 되지만, 그 경우 메시지 유실 경로가 되살아납니다.

## Related Documents

- 아키텍처: [실행 흐름](../../architecture/runtime.md), [공통 개념](../../architecture/crosscutting-concepts.md)
- ADR: [ADR-0002](../../decisions/ADR-0002-idempotency-strategy.md)
- 운영 문서: [재시도·DLQ 급증 런북](../../operations/runbooks/RUNBOOK-retry-dlq-surge.md)

## Progress Notes

| 날짜 | 상태 | 내용 |
|---|---|---|
| 2026-03-19 | Done | 분기 수정과 회귀 테스트 통과 |

## 완료 보고

- 변경 결과: 잠금 경합 시 조용한 메시지 소실 경로를 제거하고 재시도 토픽 경유 복구를 강제
- 실행한 검증: 회귀 테스트 3종, `10 passed`
- 갱신한 문서: 이 작업 문서 (기준 문서 반영은 본 이관 작업에서 수행)
- 남은 위험: 잠금 경합이 일반 실패와 동일하게 재시도 횟수를 소모함. [위험과 기술 부채](../../architecture/risks-technical-debt.md)에서 추적
