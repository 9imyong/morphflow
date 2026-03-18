#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${1:-morphflow}"
APP_IMAGE="${APP_IMAGE:-morphflow-app:kind}"
DEPENDENCY_IMAGES=(
  "postgres:16-alpine"
  "redis:7-alpine"
  "apache/kafka:4.0.0"
  "busybox:1.36"
)

resolve_registry_ref() {
  local image="$1"
  if [[ "$image" == *"/"* ]]; then
    printf "docker.io/%s" "$image"
  else
    printf "docker.io/library/%s" "$image"
  fi
}

pull_into_kind_node() {
  local image="$1"
  local node
  local registry_ref
  registry_ref="$(resolve_registry_ref "$image")"
  node="$(kind get nodes --name "$CLUSTER_NAME" | head -n 1)"
  if [[ -z "$node" ]]; then
    echo "failed to resolve kind node name for cluster: $CLUSTER_NAME" >&2
    return 1
  fi
  echo "fallback: pulling image in kind node via ctr: $registry_ref"
  docker exec "$node" ctr --namespace=k8s.io images pull "$registry_ref" >/dev/null
}

if ! docker image inspect "$APP_IMAGE" >/dev/null 2>&1; then
  echo "image not found: $APP_IMAGE"
  echo "run: docker build -t $APP_IMAGE ."
  exit 1
fi

kind load docker-image "$APP_IMAGE" --name "$CLUSTER_NAME"
echo "loaded image into kind: $APP_IMAGE"

for image in "${DEPENDENCY_IMAGES[@]}"; do
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    echo "pulling missing dependency image: $image"
    docker pull "$image" >/dev/null
  fi
  if kind load docker-image "$image" --name "$CLUSTER_NAME"; then
    echo "loaded image into kind: $image"
  else
    echo "kind load failed for $image, trying node-local pull fallback"
    pull_into_kind_node "$image"
    echo "loaded image into kind via fallback: $image"
  fi
done
