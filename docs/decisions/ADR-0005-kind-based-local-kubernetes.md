---
id: ADR-0005
title: Compose에서 kind 기반 Kubernetes로 실행 환경 전환
status: 승인됨
date: 2026-03-17
decision_makers: [김용준]
related_requirements: [REQ-platform-001]
supersedes: null
superseded_by: null
---

# ADR-0005: Compose에서 kind 기반 Kubernetes로 실행 환경 전환

## 맥락

Docker Compose로 전체 스택을 기동할 수 있었지만, 확장·복구·배포 정책을 Compose로는 표현할 수 없었습니다. HPA, 프로브 기반 기동 순서, 롤아웃, 오버레이 기반 환경 분리는 Kubernetes 리소스로만 검증할 수 있습니다.

동시에 상태 저장소(PostgreSQL·Redis·Kafka)를 클러스터 밖 Compose에 두고 앱만 클러스터에 올리는 방식도 가능했습니다.

## 결정 기준

- 전체 처리 경로를 Kubernetes 안에서 재현할 수 있는가
- Compose의 `depends_on` 기동 순서를 대체할 수 있는가
- 이후 실제 클러스터로 옮길 때 매니페스트를 재사용할 수 있는가

## 검토한 대안

### 대안 1: 앱만 클러스터에 올리고 상태 저장소는 Compose 유지

- 장점: 마이그레이션 범위가 작고 기존 데이터 유지
- 단점: 클러스터 외부 의존이 남아 네트워크 경계와 기동 순서를 검증할 수 없음
- 위험: Kubernetes 리소스 자체의 검증이 불완전

### 대안 2: 상태 저장소를 포함해 전체를 클러스터에 배포

- 장점: API → Kafka → Worker → DB 전 경로를 클러스터 안에서 재현. 매니페스트 자체를 검증 가능
- 단점: StatefulSet·PVC·브로커 설정을 직접 다뤄야 함
- 위험: 단일 노드 환경의 스토리지 제약

## 결정

대안 2를 채택하되 범위를 나눕니다.

- 1차: `api`, `worker`, `migrate`, `postgres`, `redis`, `kafka`를 `deploy/k8s/base`에 배포
- 2차: 관측 스택을 `overlays/observability`로 분리 이관
- Compose의 `depends_on`은 다음으로 대체합니다.
  - `initContainer`(busybox + nc)로 의존 소켓 대기
  - `api` readiness `/health/ready`, liveness `/health/live`
  - 워커는 메트릭 포트 TCP 프로브
  - 스키마 적용은 별도 `Job`(`morphflow-migrate`)으로 선행
- 모드 차이는 Kustomize 오버레이로 표현하고 이미지는 공유합니다.

## 결과

### 긍정적 결과

- 전체 경로를 kind 단일 노드에서 재현하고 E2E로 검증했습니다.
- 매니페스트 렌더 검증을 CI(`k8s-manifest-validate`)에 포함했습니다.
- 이후 KEDA·Gateway 오버레이를 같은 base 위에 추가할 수 있었습니다.

### 부정적 결과와 비용

- 단일 노드·단일 인스턴스 구성이므로 고가용성은 검증 대상이 아닙니다.
- Kafka는 KRaft 단일 노드이며 `Recreate` 전략이라 재배포 시 짧은 중단이 발생합니다.
- 마이그레이션 Job이 기본 배포에서 제외되어 스키마 변경 시 `--with-migrate`를 기억해야 합니다.

### 후속 작업

- [x] base 매니페스트와 모드별 오버레이 구성
- [x] CI 렌더 검증 추가
- [ ] k3s 등 실제 클러스터용 오버레이 추가(ingressClass, storageClass, 리소스 상한, 비밀 분리)
- [ ] CI에 kind smoke test 추가

## 검증 방법

`scripts/k8s-deploy-kind.sh`의 롤아웃 확인과 `/health/live`·`/health/ready` 응답, `POST /jobs` → `GET /jobs/{id}` 경로로 확인합니다. 절차는 [운영 배포 문서](../operations/deployment.md)에 있습니다.
