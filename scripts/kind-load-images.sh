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
  kind load docker-image "$image" --name "$CLUSTER_NAME"
  echo "loaded image into kind: $image"
done
