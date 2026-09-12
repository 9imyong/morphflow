# 배포 및 되돌리기

## 책임과 승인

- 배포 담당: 김용준
- 승인 필요 조건: 데이터베이스 스키마 변경, 아키텍처 모드 전환
- 허용 배포 시간: 제한 없음 (로컬 검증 환경)

## 배포 전 점검

- [ ] 변경 범위와 위험을 확인합니다.
- [ ] `pytest -q`와 CI의 `static-checks`를 통과합니다.
- [ ] 스키마 변경이 있으면 `alembic check`로 드리프트가 없는지 확인합니다.
- [ ] 매니페스트 변경이 있으면 `kubectl kustomize`가 렌더에 성공하는지 확인합니다.
- [ ] 대시보드와 경보가 동작 중인지 확인합니다.
- [ ] 되돌릴 이미지 태그 또는 이전 매니페스트를 확인합니다.

## Compose 환경

### 기본(A 모드)

```bash
docker compose -f docker-compose.dev.yml --env-file env/.env.dev up -d --build
```

기대 결과: `migrate`가 성공적으로 종료된 뒤 `api`와 `worker`가 기동합니다.

### 모드 전환

```bash
# B 모드 (추론 역할 분리)
docker compose -f docker-compose.dev.yml -f deploy/docker-compose.bmode.override.yml \
  --env-file env/.env.dev up -d --build

# C 모드 (후단 워커 추가)
docker compose -f docker-compose.dev.yml -f deploy/docker-compose.cmode.override.yml \
  --env-file env/.env.dev up -d --build

# BC 모드
docker compose -f docker-compose.dev.yml -f deploy/docker-compose.bcmode.override.yml \
  --env-file env/.env.dev up -d --build
```

### 관측 스택

```bash
docker compose -f deploy/observability-compose.yml up -d
```

## Kubernetes(kind) 환경

### 최초 구성

```bash
# 1) 클러스터 생성 (NodePort 30081 → 호스트 18000)
scripts/kind-create-cluster.sh local-dev

# 2) 이미지 빌드와 로드
make kind-rebuild

# 3) 배포
scripts/k8s-deploy-kind.sh local-dev base
```

포트가 충돌하면 `HOST_API_PORT=28000 scripts/kind-create-cluster.sh local-dev`로 변경합니다.

### 검증

```bash
curl -s http://localhost:18000/health/live
curl -s http://localhost:18000/health/ready
```

기대 결과: `/health/live`는 항상 `200`, `/health/ready`는 모든 의존성이 정상일 때 `200`입니다. `503`이면 응답 본문의 `dependencies`에서 실패한 항목을 확인합니다.

### 스키마 변경이 포함된 배포

```bash
scripts/k8s-deploy-kind.sh local-dev base --with-migrate
```

마이그레이션 Job은 **기본 배포에 포함되지 않습니다.** 스키마 변경이 있는데 이 옵션을 빼면 애플리케이션이 옛 스키마로 기동합니다.

### Kubernetes 모드 전환

```bash
scripts/k8s-deploy-kind.sh local-dev bmode
scripts/k8s-deploy-kind.sh local-dev cmode
scripts/k8s-deploy-kind.sh local-dev bcmode
```

진입 토픽과 컨슈머 그룹이 고정되어 있으므로 전환 시 백로그와 오프셋이 유지됩니다. 근거는 [ADR-0004](../decisions/ADR-0004-fixed-ingress-topic-and-group.md)에 있습니다.

전환 후 확인:

```bash
kubectl get pods -n morphflow --context kind-local-dev
scripts/kafka-k8s-lag.sh
```

### 선택적 오버레이

```bash
# 관측 스택
kubectl apply -k deploy/k8s/overlays/observability --context kind-local-dev

# lag 기반 자동 확장 (KEDA 필요)
kubectl apply -k deploy/k8s/overlays/autoscaling-keda/amode --context kind-local-dev

# Gateway 기반 네트워킹 (MetalLB + Envoy Gateway 필요)
make net-install K8S_CONTEXT=kind-local-dev
make net-apply K8S_CONTEXT=kind-local-dev KIND_NETWORK=kind
```

HPA 동작에는 클러스터에 `metrics-server`가 필요합니다.

## 배포 검증

- [ ] `/health/ready`가 `200`을 반환합니다.
- [ ] `POST /jobs` → `GET /jobs/{job_id}`가 `SUCCESS`에 도달합니다.
- [ ] `kafka_consumergroup_lag`이 증가 추세가 아닙니다.
- [ ] `dlq_messages_total`이 증가하지 않습니다.
- [ ] 워커 로그에 소비와 처리 기록이 남습니다.

## 되돌리기

### 판단 기준

- `/health/ready`가 회복되지 않음
- 오류율 또는 DLQ 적재가 배포 직후 증가
- lag이 배포 전보다 뚜렷하게 악화

### 절차

```bash
# Kubernetes
kubectl rollout undo deploy/api -n morphflow --context kind-local-dev
kubectl rollout undo deploy/worker -n morphflow --context kind-local-dev

# Compose
docker compose -f docker-compose.dev.yml --env-file env/.env.dev up -d --build
```

### 데이터 호환성

스키마 변경이 포함된 배포를 되돌릴 때는 **애플리케이션을 먼저 되돌리고 스키마는 그대로 둡니다.** 컬럼 추가는 이전 버전과 호환되므로 즉시 `alembic downgrade`를 실행하지 않습니다. 컬럼 삭제나 타입 변경을 되돌려야 하면 트래픽을 멈춘 뒤 수행합니다.

### 완료 확인

되돌린 뒤 위 [배포 검증](#배포-검증) 항목을 다시 확인합니다.

## 관련 문서

- [배포 구조](../architecture/deployment.md)
- [모니터링](monitoring.md)
- [장애 대응](incident-response.md)
