---
id: TASK-20260317-22
title: K8s Overlay 추가 (B·C·BC + Observability)
status: Done
owner: 김용준
created: 2026-03-17
updated: 2026-03-17
---

# 작업: K8s Overlay 추가 (B·C·BC + Observability)

## Status

`Done`

## Objective

Compose override와 동일한 운영 흐름을 Kustomize 오버레이로 제공하고, 관측 스택을 독립 오버레이로 분리합니다.

## Context

[TASK-20260317-21](TASK-20260317-21-compose-to-kind.md)에서 base 매니페스트를 만들었지만 모드 전환 수단이 없었습니다. Compose에서는 override 파일로 전환하던 것을 Kubernetes에서도 동일하게 제공해야 했습니다.

## Scope

- `bmode`, `cmode`, `bcmode` 오버레이
- C·BC 모드용 `downstream-worker` 배포 단위
- `observability` 오버레이
- 렌더 검증

## Out of Scope

- 네트워킹 진입 경로 ([TASK-20260318-23](TASK-20260318-23-networking-overlay.md))
- lag 기반 자동 확장

## Requirements

- 요구사항: [REQ-platform-001](../../requirements/REQ-platform-001-bottleneck-adaptive-pipeline.md)

## Implementation Plan

모드 차이를 ConfigMap 패치와 워커 추가로만 표현하고 이미지는 공유합니다.

## TODO Checklist

- [x] WU-1: `bmode`·`cmode`·`bcmode` 오버레이 생성과 base 패치 구성
- [x] WU-2: C·BC 모드용 `downstream-worker` 추가
- [x] WU-3: `observability` 오버레이 구성
- [x] WU-4: base와 오버레이 전체 렌더 검증
- [x] WU-5: 실행 가이드 문서 갱신

## 인수 조건

- [x] 모드별 오버레이가 `kubectl kustomize`로 렌더됩니다.
- [x] C·BC 오버레이에서 `downstream-worker`가 생성됩니다.

## Validation

- [x] `kubectl kustomize` 렌더 검증
- [x] 오버레이 배포 후 롤아웃 확인

## 위험과 되돌리기

오버레이는 base를 변경하지 않으므로 적용을 중단하면 base 상태로 돌아갑니다.

## Related Documents

- 아키텍처: [배포 구조](../../architecture/deployment.md)
- ADR: [ADR-0001](../../decisions/ADR-0001-transitional-architecture-modes.md), [ADR-0005](../../decisions/ADR-0005-kind-based-local-kubernetes.md)
- 운영 문서: [배포 및 되돌리기](../../operations/deployment.md)

## Progress Notes

| 날짜 | 상태 | 내용 |
|---|---|---|
| 2026-03-17 | Done | 오버레이 구성과 렌더 검증 완료 |

## 완료 보고

- 변경 결과: 모드별·관측용 오버레이 추가. `scripts/k8s-deploy-kind.sh`가 기본 배포에서 마이그레이션을 생략하고 `--with-migrate`에서만 실행하도록 변경
- 실행한 검증: 전체 kustomization 렌더
- 갱신한 문서: 저장소 README, 전환 문서
- 남은 위험: 관측 오버레이는 kustomize 로드 제한 때문에 설정 파일을 오버레이 내부 `configs/`에 복제해 관리하므로 Compose 쪽 설정과 이중 관리됨
