# Networking Overlay (kind + MetalLB + Envoy Gateway)

이 디렉토리는 Gateway API 기반 라우팅 템플릿이다.

## 1) 사전 설치

### MetalLB 설치
```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml --context kind-local-dev
kubectl wait --for=condition=available deploy/controller -n metallb-system --timeout=180s --context kind-local-dev
```

### Envoy Gateway 설치 (표준 quickstart)
```bash
kubectl apply -f https://github.com/envoyproxy/gateway/releases/download/v1.5.4/install.yaml --context kind-local-dev
kubectl wait --for=condition=available deploy/envoy-gateway -n envoy-gateway-system --timeout=180s --context kind-local-dev
```

## 2) kind 네트워크 대역 확인
```bash
docker network inspect kind | jq -r '.[0].IPAM.Config[0].Subnet'
```

위 결과에 맞게 `metallb-ip-pool.yaml`의 address range를 조정한다.

또는 자동 반영:
```bash
make net-pool K8S_CONTEXT=kind-local-dev KIND_NETWORK=kind
```

## 3) overlay 적용
```bash
kubectl apply -k deploy/k8s/overlays/networking --context kind-local-dev
```

또는 자동 반영 + apply:
```bash
make net-apply K8S_CONTEXT=kind-local-dev KIND_NETWORK=kind
```

## 4) 확인

### GatewayClass
```bash
kubectl get gatewayclass --context kind-local-dev
```

### Gateway 주소
```bash
kubectl get gateway -n morphflow morphflow-gateway --context kind-local-dev
```

### HTTPRoute 상태
```bash
kubectl get httproute -n morphflow api-route --context kind-local-dev -o yaml
```

### 테스트
LB IP를 확인한 뒤 Host 헤더로 요청:
```bash
LB_IP=$(kubectl -n envoy-gateway-system get svc -l gateway.envoyproxy.io/owning-gateway-name=morphflow-gateway -o jsonpath='{.items[0].status.loadBalancer.ingress[0].ip}' --context kind-local-dev)
curl -H "Host: morphflow.local" "http://${LB_IP}/health/live"
```
