#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${1:-morphflow}"
K8S_NODE_IMAGE="${K8S_NODE_IMAGE:-kindest/node:v1.35.0}"
HOST_API_PORT="${HOST_API_PORT:-18000}"

if kind get clusters | grep -qx "$CLUSTER_NAME"; then
  echo "kind cluster already exists: $CLUSTER_NAME"
  exit 0
fi

cat <<CFG | kind create cluster --name "$CLUSTER_NAME" --image "$K8S_NODE_IMAGE" --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraPortMappings:
      - containerPort: 30081
        hostPort: ${HOST_API_PORT}
        protocol: TCP
CFG

echo "created kind cluster: $CLUSTER_NAME (host api port: $HOST_API_PORT)"
