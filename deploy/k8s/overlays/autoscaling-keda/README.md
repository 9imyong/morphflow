# KEDA Autoscaling Overlays

KEDA 기반 Kafka lag autoscaling 오버레이다.

## 사전 조건
- KEDA가 클러스터에 설치되어 있어야 한다.

예시 설치:
```bash
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm upgrade --install keda kedacore/keda -n keda --create-namespace
```

## 적용
- A 모드(unified worker):
```bash
kubectl apply -k deploy/k8s/overlays/autoscaling-keda/amode --context kind-local-dev
```

- B 모드(inference worker):
```bash
kubectl apply -k deploy/k8s/overlays/autoscaling-keda/bmode --context kind-local-dev
```

- C 모드(inference + downstream):
```bash
kubectl apply -k deploy/k8s/overlays/autoscaling-keda/cmode --context kind-local-dev
```

- BC 모드(inference + downstream):
```bash
kubectl apply -k deploy/k8s/overlays/autoscaling-keda/bcmode --context kind-local-dev
```

## 확인
```bash
kubectl get scaledobject -n morphflow --context kind-local-dev
kubectl get hpa -n morphflow --context kind-local-dev
```

주의:
- worker/downstream-worker는 KEDA가 HPA를 생성하므로, 기존 HPA 리소스는 overlay에서 제거한다.
- `maxReplicaCount`는 topic partition 수 이하로 유지한다.
