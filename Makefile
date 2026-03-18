SHELL := /bin/zsh

K8S_CONTEXT ?= kind-local-dev
KIND_NETWORK ?= kind
KIND_CLUSTER ?= local-dev
APP_IMAGE ?= morphflow-app:kind
K8S_OVERLAY ?= base

.PHONY: kind-image-build
kind-image-build:
	docker build -t $(APP_IMAGE) .

.PHONY: kind-image-load
kind-image-load:
	scripts/kind-load-images.sh $(KIND_CLUSTER)

.PHONY: kind-rebuild
kind-rebuild: kind-image-build kind-image-load

.PHONY: kind-deploy
kind-deploy:
	scripts/k8s-deploy-kind.sh $(KIND_CLUSTER) $(K8S_OVERLAY)

.PHONY: kind-rebuild-deploy
kind-rebuild-deploy: kind-rebuild kind-deploy

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
