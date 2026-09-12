---
id: TASK-20260318-23
title: Networking Overlay 추가 (MetalLB + Envoy Gateway)
status: Done
owner: 김용준
created: 2026-03-18
updated: 2026-03-18
---

# 작업: Networking Overlay 추가 (MetalLB + Envoy Gateway)

## Status

`Done`

## Objective

kind 환경에서 MetalLB와 Envoy Gateway, HTTPRoute 기반의 API 진입 경로 템플릿을 제공합니다.

## Context

NodePort는 동작하지만 실제 클러스터의 진입 방식과 다릅니다. Gateway API 기반 경로를 미리 검증해 두면 운영 클러스터로 옮길 때 진입 구성만 교체하면 됩니다.

## Scope

- MetalLB IP pool과 L2Advertisement 템플릿
- Gateway·GatewayClass·HTTPRoute 템플릿
- 관측 도구용 경로 분리
- 설치·검증 절차 문서

## Out of Scope

- TLS 종료와 인증서 관리
- 외부 DNS 연동

## Requirements

- 요구사항: [REQ-platform-001](../../requirements/REQ-platform-001-bottleneck-adaptive-pipeline.md)

## Implementation Plan

MetalLB로 LoadBalancer 주소를 확보하고 Envoy Gateway가 HTTPRoute를 처리하도록 구성합니다. 주소 대역은 kind 네트워크에 따라 달라지므로 스크립트로 자동 반영합니다.

## TODO Checklist

- [x] WU-1: `deploy/k8s/overlays/networking` 생성
- [x] WU-2: MetalLB IP pool·L2Advertisement 템플릿 추가
- [x] WU-3: Gateway·HTTPRoute 템플릿 추가
- [x] WU-4: 설치·검증 절차 README 추가
- [x] WU-5: 저장소 README에 사용 경로 반영

## 인수 조건

- [x] `make net-apply`로 주소 대역이 자동 반영되고 Gateway가 생성됩니다.
- [x] HTTPRoute를 통해 API에 접근할 수 있습니다.

## Validation

- [x] `make net-status`로 Gateway·HTTPRoute·Service 상태 확인
- [ ] 장시간 운영 검증 — 미실행

## 위험과 되돌리기

별도 오버레이이므로 적용하지 않으면 기존 NodePort 경로가 그대로 동작합니다.

## Related Documents

- 아키텍처: [배포 구조](../../architecture/deployment.md)
- 운영 문서: [배포 및 되돌리기](../../operations/deployment.md)

## Progress Notes

| 날짜 | 상태 | 내용 |
|---|---|---|
| 2026-03-18 | Done | 템플릿과 절차 문서 추가 |

## 완료 보고

- 변경 결과: networking 오버레이와 주소 대역 자동 설정 스크립트 추가
- 실행한 검증: Gateway·HTTPRoute 생성과 접근 확인
- 갱신한 문서: 오버레이 README, 저장소 README
- 남은 위험: MetalLB 주소 대역은 `docker network inspect kind` 결과에 맞춰야 함. Envoy Gateway 설치 전에 Gateway API 리소스를 적용하면 CRD 오류 발생
