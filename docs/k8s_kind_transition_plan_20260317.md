# Compose -> Kind 전환 계획/구현 기록 (2026-03-17)

## 1. 목표
현재 Compose 기반 스택을 Kubernetes 리소스로 전환하고, Kind에서 최소 실행/연결/검증 가능한 기준선을 만든다.

## 2. 전환 대상 분류(WU-1)
- Core App
  - `api`, `worker`, `migrate`
- Core Dependency
  - `postgres`, `redis`, `kafka`
- Observability
  - Compose 기준: `prometheus`, `grafana`, `jaeger`, `elasticsearch`, `kibana`, `fluent-bit`, exporters

## 3. 1차 범위 결정(WU-4)
- 선택: 상태성 서비스(Postgres/Redis/Kafka)를 Kind 내부에 최소 배포
- 이유:
  - Kind 단독으로 API -> Kafka -> Worker -> DB 경로를 재현 가능
  - Compose 외부 의존을 제거해 Kubernetes 리소스 자체 검증 가능
- 보류:
  - Observability 전체(EFK/Jaeger/exporter)는 2차 이관
  - 1차는 API/worker/core dependency + health/e2e 검증 우선

## 4. depends_on 재해석(WU-5)
Compose `depends_on`은 Kubernetes에서 아래로 대체한다.
- `initContainer`(`busybox + nc`)로 postgres/redis/kafka 소켓 대기
- API readiness: `/health/ready`
- API liveness: `/health/live`
- Worker readiness/liveness: metrics 포트(9000) 기반 TCP probe
- DB 마이그레이션: 별도 `Job`(`morphflow-migrate`)로 선 적용

## 5. 리소스 구조(WU-2, WU-3)
- 경로: `deploy/k8s/base`
- 주요 리소스:
  - `namespace.yaml`
  - `configmap-app.yaml`
  - `secret-app.yaml`
  - `postgres.yaml`(StatefulSet + Service + PVC)
  - `redis.yaml`(Deployment + Service + PVC)
  - `kafka.yaml`(Deployment + Service + PVC)
  - `migrate-job.yaml`
  - `api.yaml`(Deployment + ClusterIP + NodePort)
  - `worker.yaml`(Deployment + Service)
  - `kustomization.yaml`

### Compose override 대응 Overlay
- `deploy/k8s/overlays/bmode`
- `deploy/k8s/overlays/cmode`
- `deploy/k8s/overlays/bcmode`
- `deploy/k8s/overlays/observability`

## 6. Kind 실행 절차(WU-6, WU-7)
- 클러스터 생성(포트 매핑 포함):
  - `scripts/kind-create-cluster.sh morphflow`
  - 기본 host port: `18000` (`HOST_API_PORT`로 변경 가능)
- 앱 이미지 빌드:
  - `docker build -t morphflow-app:kind .`
- 이미지 로드:
  - `scripts/kind-load-images.sh morphflow`
- 리소스 배포 + migrate + rollout 확인:
  - 기본: `scripts/k8s-deploy-kind.sh morphflow base`
  - 스키마 변경 시: `scripts/k8s-deploy-kind.sh morphflow base --with-migrate`
  - B/C/BC 모드: `scripts/k8s-deploy-kind.sh morphflow <bmode|cmode|bcmode>`
  - observability: `kubectl apply -k deploy/k8s/overlays/observability --context kind-morphflow`
- 진입 경로:
  - NodePort `30081` -> host `18000` 매핑
  - `http://localhost:18000/health/live`

## 7. 최소 E2E 검증(WU-8)
- API health 확인
- `POST /jobs` 호출
- `GET /jobs/{job_id}` 상태 확인
- worker 로그에서 consume/처리 확인

## 8. Kind -> k3s 전환 전략(WU-9)
- 공통점:
  - Kubernetes 매니페스트(`deploy/k8s/base`) 재사용
  - probe/initContainer/Job 기반 기동 순서 동일
- 차이점:
  - Kind: 로컬 Docker 기반, `kind load docker-image` 필요
  - k3s: 노드 런타임(containerd)에 맞는 이미지 배포 방식(레지스트리 push/pull) 필요
  - StorageClass/Ingress/LoadBalancer 구현은 k3s 환경 기본값에 맞춰 조정 필요
- 권장 순서:
  1. Kind에서 매니페스트 안정화
  2. k3s overlay 추가(`ingressClass`, `storageClass`, `resource requests/limits`, `secret 분리`)
  3. CI에서 `kubectl apply -k` + smoke test 자동화
