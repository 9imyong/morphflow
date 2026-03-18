SHELL := /bin/zsh

K8S_CONTEXT ?= kind-local-dev
KIND_NETWORK ?= kind

.PHONY: net-install
net-install:
	kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml --context $(K8S_CONTEXT)
	kubectl wait --for=condition=available deploy/controller -n metallb-system --timeout=180s --context $(K8S_CONTEXT)
	kubectl apply --server-side --force-conflicts -f https://github.com/envoyproxy/gateway/releases/download/v1.5.4/install.yaml --context $(K8S_CONTEXT)
	kubectl wait --for=condition=available deploy/envoy-gateway -n envoy-gateway-system --timeout=180s --context $(K8S_CONTEXT)

.PHONY: net-apply
net-apply:
	KIND_NETWORK=$(KIND_NETWORK) scripts/networking-metallb-configure.sh $(K8S_CONTEXT)

.PHONY: net-pool
net-pool:
	CONFIGURE_ONLY=true KIND_NETWORK=$(KIND_NETWORK) scripts/networking-metallb-configure.sh $(K8S_CONTEXT)

.PHONY: net-status
net-status:
	kubectl get gateway -n morphflow morphflow-gateway --context $(K8S_CONTEXT)
	kubectl get httproute -n morphflow api-route --context $(K8S_CONTEXT)
	kubectl get svc -n envoy-gateway-system --context $(K8S_CONTEXT)
