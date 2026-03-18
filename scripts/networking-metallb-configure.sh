#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${1:-kind-local-dev}"
KIND_NETWORK="${KIND_NETWORK:-kind}"
POOL_FILE="deploy/k8s/overlays/networking/metallb-ip-pool.yaml"
CONFIGURE_ONLY="${CONFIGURE_ONLY:-false}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq command not found" >&2
  exit 1
fi

SUBNET=$(docker network inspect "$KIND_NETWORK" | jq -r '.[0].IPAM.Config[0].Subnet')
if [[ -z "$SUBNET" || "$SUBNET" == "null" ]]; then
  echo "failed to detect subnet from docker network: $KIND_NETWORK" >&2
  exit 1
fi

BASE_CIDR="${SUBNET%/*}"
OCT1=$(echo "$BASE_CIDR" | cut -d. -f1)
OCT2=$(echo "$BASE_CIDR" | cut -d. -f2)
OCT3=$(echo "$BASE_CIDR" | cut -d. -f3)

if [[ -z "$OCT1" || -z "$OCT2" || -z "$OCT3" ]]; then
  echo "unexpected subnet format: $SUBNET" >&2
  exit 1
fi

RANGE_START="${OCT1}.${OCT2}.${OCT3}.200"
RANGE_END="${OCT1}.${OCT2}.${OCT3}.250"
NEW_RANGE="${RANGE_START}-${RANGE_END}"

awk -v new_range="$NEW_RANGE" '
  /^  addresses:/ { print; in_addr=1; next }
  in_addr==1 && /^    - / { print "    - " new_range; in_addr=0; next }
  { print }
' "$POOL_FILE" > "$POOL_FILE.tmp"
mv "$POOL_FILE.tmp" "$POOL_FILE"

echo "configured MetalLB pool range: $NEW_RANGE"
if [[ "$CONFIGURE_ONLY" == "true" ]]; then
  echo "CONFIGURE_ONLY=true, skip kubectl apply"
  exit 0
fi

echo "applying networking overlay to context: $CONTEXT"
kubectl apply -k deploy/k8s/overlays/networking --context "$CONTEXT"
