---
id: TASK-20260317-21
title: Compose 기반 스택의 Kind 배포 전환
status: Done
owner: 김용준
created: 2026-03-17
updated: 2026-03-17
---

# 작업: Compose 기반 스택의 Kind 배포 전환

## Status

`Done`

## Objective

Compose 기반 API·worker·PostgreSQL·Redis·Kafka 스택을 Kubernetes 매니페스트로 전환하고, kind 클러스터에서 최소 실행·연결·검증이 가능하게 만듭니다.

## Context

Compose로는 확장·프로브 기반 기동 순서·롤아웃·오버레이 기반 환경 분리를 표현할 수 없었습니다. 목적은 운영용 클러스터 완성이 아니라 **Kubernetes 리소스 구조 자체의 검증**입니다.

## Scope

- `deploy/k8s/base` 매니페스트 작성
- 상태 저장소를 포함한 전체 스택의 클러스터 내부 배포
- 프로브와 마이그레이션 Job 기반 기동 순서
- kind 클러스터 생성과 이미지 로드 절차

## Out of Scope

- 관측 스택 이관 (2차로 분리, [TASK-20260317-22](TASK-20260317-22-k8s-overlays.md))
- 운영 클러스터(k3s) 전환

## Requirements

- 요구사항: [REQ-platform-001](../../requirements/REQ-platform-001-bottleneck-adaptive-pipeline.md)

## Implementation Plan

Compose의 `depends_on`을 Kubernetes 방식으로 재해석했습니다.

| Compose | Kubernetes 대체 |
|---|---|
| `depends_on: service_healthy` | `initContainer`(busybox + nc)로 소켓 대기 |
| API 기동 확인 | readiness `/health/ready`, liveness `/health/live` |
| worker 기동 확인 | 메트릭 포트 9000 TCP 프로브 |
| `migrate` 서비스 선행 | 별도 `Job`(`morphflow-migrate`) |

## TODO Checklist

- [x] WU-1: Compose 서비스를 전환 대상 기준으로 분류
- [x] WU-2: `deploy/k8s/base`에 공통 리소스 작성
- [x] WU-3: API·worker Deployment와 Service 작성, 설정 주입 정리
- [x] WU-4: PostgreSQL·Redis·Kafka의 클러스터 내부 배포 결정과 문서화
- [x] WU-5: readiness·liveness 프로브 반영과 동작 검증
- [x] WU-6: 클러스터 생성 스크립트와 이미지 로드 절차 문서화
- [x] WU-7: NodePort 진입 경로 검증
- [x] WU-8: 최소 E2E 검증(API → Kafka → Worker → DB)
- [x] WU-9: 전환 전략과 차이점 문서 반영

## 인수 조건

- [x] kind에서 `/health/live`와 `/health/ready`가 정상 응답합니다.
- [x] `POST /jobs` → `GET /jobs/{job_id}` 경로가 클러스터 안에서 완결됩니다.
- [x] 외부 Compose 의존 없이 전체 경로가 동작합니다.

## Validation

- [x] 최소 E2E 확인
- [x] 프로브 동작 확인
- [ ] 자동화된 smoke test — 미실행. CI 통합은 후속 작업으로 분리

## 위험과 되돌리기

Compose 구성을 제거하지 않고 유지했으므로 문제 발생 시 Compose 실행으로 되돌릴 수 있습니다.

## Related Documents

- 아키텍처: [배포 구조](../../architecture/deployment.md)
- ADR: [ADR-0005](../../decisions/ADR-0005-kind-based-local-kubernetes.md)
- 운영 문서: [배포 및 되돌리기](../../operations/deployment.md)

## Progress Notes

| 날짜 | 상태 | 내용 |
|---|---|---|
| 2026-03-17 | In Progress | 전환 대상 분류와 1차 범위 결정 |
| 2026-03-17 | Done | E2E 검증 완료 |

## 완료 보고

- 변경 결과: `deploy/k8s/base` 매니페스트 세트와 kind 실행 스크립트 추가
- 실행한 검증: 프로브 응답, 최소 E2E 경로
- 갱신한 문서: 저장소 README, 전환 계획 문서
- 남은 위험: 단일 노드·단일 인스턴스 구성이므로 고가용성은 검증 대상이 아님. k3s 오버레이 미작성
