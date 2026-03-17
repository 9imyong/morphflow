#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${1:-morphflow}"
OVERLAY="${2:-base}"
NAMESPACE="${NAMESPACE:-morphflow}"
WITH_MIGRATE="${WITH_MIGRATE:-false}"

if [[ "${3:-}" == "--with-migrate" ]]; then
  WITH_MIGRATE="true"
fi

if [[ "$OVERLAY" == "base" ]]; then
  KUSTOMIZE_PATH="deploy/k8s/base"
else
  KUSTOMIZE_PATH="deploy/k8s/overlays/$OVERLAY"
fi

kubectl cluster-info --context "kind-$CLUSTER_NAME" >/dev/null
kubectl apply -k "$KUSTOMIZE_PATH" --context "kind-$CLUSTER_NAME"

if [[ "$WITH_MIGRATE" == "true" ]]; then
  kubectl delete job morphflow-migrate -n "$NAMESPACE" --ignore-not-found --context "kind-$CLUSTER_NAME"
  kubectl apply -f deploy/k8s/base/migrate-job.yaml -n "$NAMESPACE" --context "kind-$CLUSTER_NAME"
  kubectl wait --for=condition=complete job/morphflow-migrate -n "$NAMESPACE" --timeout=240s --context "kind-$CLUSTER_NAME"
fi

kubectl rollout status statefulset/postgres -n "$NAMESPACE" --timeout=240s --context "kind-$CLUSTER_NAME"
kubectl rollout status deploy/redis -n "$NAMESPACE" --timeout=240s --context "kind-$CLUSTER_NAME"
kubectl rollout status deploy/kafka -n "$NAMESPACE" --timeout=240s --context "kind-$CLUSTER_NAME"
kubectl rollout status deploy/api -n "$NAMESPACE" --timeout=240s --context "kind-$CLUSTER_NAME"
kubectl rollout status deploy/worker -n "$NAMESPACE" --timeout=240s --context "kind-$CLUSTER_NAME"

if kubectl get deploy downstream-worker -n "$NAMESPACE" --context "kind-$CLUSTER_NAME" >/dev/null 2>&1; then
  kubectl rollout status deploy/downstream-worker -n "$NAMESPACE" --timeout=240s --context "kind-$CLUSTER_NAME"
fi

echo "kind deployment completed (overlay=$OVERLAY, with_migrate=$WITH_MIGRATE)"
