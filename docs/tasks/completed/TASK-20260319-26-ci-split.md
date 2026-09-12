---
id: TASK-20260319-26
title: CI 워크플로 분리와 K8s 매니페스트 검증 추가
status: Done
owner: 김용준
created: 2026-03-19
updated: 2026-03-19
---

# 작업: CI 워크플로 분리와 K8s 매니페스트 검증 추가

## Status

`Done`

## Objective

CI 실패 원인을 빠르게 식별할 수 있도록 테스트·마이그레이션·매니페스트 검증을 분리합니다.

## Context

단일 작업으로 묶여 있으면 어느 단계에서 실패했는지 로그를 열어야 알 수 있고, 한 단계 실패가 나머지 검증을 막습니다.

## Scope

- CI 작업 분리
- 매니페스트 렌더 검증 추가
- 워크플로 공통 설정 정리

## Out of Scope

- CRD 스키마 기반 엄격 검증
- kind 기반 smoke test

## Requirements

- 요구사항: [REQ-platform-001](../../requirements/REQ-platform-001-bottleneck-adaptive-pipeline.md)

## Implementation Plan

네 개 작업으로 분리하고 각각 독립 실행되게 합니다: `unit-tests`, `static-checks`, `migration-check`, `k8s-manifest-validate`.

## TODO Checklist

- [x] WU-1: 단일 작업을 `unit-tests`와 `migration-check`로 분리
- [x] WU-2: `k8s-manifest-validate` 작업 추가
- [x] WU-3: 공통 안정화 설정 반영 (`workflow_dispatch`, concurrency 취소, 타임아웃, pip 캐시)

## 인수 조건

- [x] 각 검증이 독립 작업으로 표시되어 실패 지점을 즉시 알 수 있습니다.
- [x] `deploy/k8s`의 모든 kustomization이 렌더 검증됩니다.

## Validation

- [x] CI 실행으로 네 작업 통과 확인

## 위험과 되돌리기

워크플로 파일만 변경했으므로 이전 버전으로 되돌리면 즉시 복구됩니다.

## Related Documents

- 가이드: [테스트 안내](../../guides/testing.md)
- ADR: [ADR-0005](../../decisions/ADR-0005-kind-based-local-kubernetes.md)

## Progress Notes

| 날짜 | 상태 | 내용 |
|---|---|---|
| 2026-03-19 | Done | 네 개 작업 분리와 검증 완료 |

## 완료 보고

- 변경 결과: CI를 네 개 작업으로 분리하고 매니페스트 렌더 검증 추가
- 실행한 검증: CI 전체 통과
- 갱신한 문서: 없음 (본 이관 작업에서 [테스트 안내](../../guides/testing.md)에 반영)
- 남은 위험: 렌더 검증 중심이며 CRD 스키마 검증과 kind smoke test는 미적용
