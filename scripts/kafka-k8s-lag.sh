#!/usr/bin/env bash
set -euo pipefail

K8S_CONTEXT="${K8S_CONTEXT:-kind-local-dev}"
NAMESPACE="${NAMESPACE:-morphflow}"
KAFKA_TARGET="${KAFKA_TARGET:-deploy/kafka}"
BOOTSTRAP_SERVER="${BOOTSTRAP_SERVER:-localhost:9092}"
WATCH_MODE=false
WATCH_INTERVAL="${WATCH_INTERVAL:-2}"
SUMMARY_ONLY=false

usage() {
  cat <<'EOF'
Usage:
  kafka-k8s-lag.sh [GROUP_ID]
  kafka-k8s-lag.sh --role <inference|downstream>
  kafka-k8s-lag.sh --all
  kafka-k8s-lag.sh --watch [--interval N] [--all|GROUP_ID]
  kafka-k8s-lag.sh --summary [--all|GROUP_ID]

Options:
  --context <ctx>       Kubernetes context (default: kind-local-dev)
  --namespace <ns>      Kubernetes namespace (default: morphflow)
  --target <resource>   Kafka exec target (default: deploy/kafka)
  --bootstrap <addr>    Kafka bootstrap-server (default: localhost:9092)
  --role <role>         inference -> architecture-main-worker
                        downstream -> architecture-main-worker-downstream
  --all                 Describe all consumer groups
  --summary             Print sum/max lag only
  --watch               Watch mode (refresh if output changed)
  --interval <sec>      Watch interval seconds (default: 2)
  -h, --help            Show help
EOF
}

MODE="single"
GROUP_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --context)
      K8S_CONTEXT="${2:-}"
      shift 2
      ;;
    --namespace)
      NAMESPACE="${2:-}"
      shift 2
      ;;
    --target)
      KAFKA_TARGET="${2:-}"
      shift 2
      ;;
    --bootstrap)
      BOOTSTRAP_SERVER="${2:-}"
      shift 2
      ;;
    --role)
      role="${2:-}"
      case "$role" in
        inference) GROUP_ID="architecture-main-worker" ;;
        downstream) GROUP_ID="architecture-main-worker-downstream" ;;
        *)
          echo "invalid role: $role (inference|downstream)" >&2
          exit 1
          ;;
      esac
      shift 2
      ;;
    --all)
      MODE="all"
      shift
      ;;
    --summary)
      SUMMARY_ONLY=true
      shift
      ;;
    --watch)
      WATCH_MODE=true
      shift
      ;;
    --interval)
      WATCH_INTERVAL="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -z "$GROUP_ID" ]]; then
        GROUP_ID="$1"
      else
        echo "unexpected argument: $1" >&2
        exit 1
      fi
      shift
      ;;
  esac
done

if [[ "$MODE" == "single" && -z "$GROUP_ID" ]]; then
  GROUP_ID="architecture-main-worker"
fi

if ! [[ "$WATCH_INTERVAL" =~ ^[0-9]+$ ]]; then
  echo "--interval must be a non-negative integer: $WATCH_INTERVAL" >&2
  exit 1
fi

kubectl_exec() {
  local cmd="$1"
  local attempts=0
  local max_attempts=4
  local delay=2
  local out=""

  while (( attempts < max_attempts )); do
    set +e
    out="$(kubectl exec -n "$NAMESPACE" --context "$K8S_CONTEXT" "$KAFKA_TARGET" -- sh -lc "$cmd" 2>&1)"
    rc=$?
    set -e

    if [[ $rc -eq 0 ]]; then
      printf '%s\n' "$out"
      return 0
    fi

    # Recoverable API hiccups under high load on single-node kind.
    if printf '%s' "$out" | grep -qiE 'TLS handshake timeout|Unable to connect to the server|timed out waiting for the condition'; then
      attempts=$((attempts + 1))
      sleep "$delay"
      continue
    fi

    printf '%s\n' "$out" >&2
    return "$rc"
  done

  printf '%s\n' "$out" >&2
  return 1
}

describe_group() {
  local group="$1"
  kubectl_exec "/opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server '$BOOTSTRAP_SERVER' --describe --group '$group'"
}

list_groups() {
  kubectl_exec "/opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server '$BOOTSTRAP_SERVER' --list"
}

summary_group() {
  local group="$1"
  describe_group "$group" | awk '
    NR==1 {next}
    NF>=6 {
      lag=$6
      if (lag ~ /^[0-9]+$/) {
        sum += lag
        if (lag > max) max = lag
      }
    }
    END {
      printf "group=%s sum_lag=%d max_lag=%d\n", "'"$group"'", sum, max
    }'
}

run_once() {
  if [[ "$MODE" == "all" ]]; then
    if [[ "$SUMMARY_ONLY" == "true" ]]; then
      while IFS= read -r g; do
        [[ -z "$g" ]] && continue
        summary_group "$g"
      done < <(list_groups)
      return 0
    fi

    while IFS= read -r g; do
      [[ -z "$g" ]] && continue
      echo "===== $g ====="
      describe_group "$g"
      echo
    done < <(list_groups)
    return 0
  fi

  if [[ "$SUMMARY_ONLY" == "true" ]]; then
    summary_group "$GROUP_ID"
  else
    echo "describing consumer group: $GROUP_ID"
    describe_group "$GROUP_ID"
  fi
}

if [[ "$WATCH_MODE" != "true" ]]; then
  run_once
  exit 0
fi

prev=""
while true; do
  if current="$(run_once 2>&1)"; then
    :
  else
    current="ERROR: failed to query consumer groups"$'\n'"$current"
  fi

  if [[ "$current" != "$prev" ]]; then
    printf '\033[H\033[2J'
    printf '[%s] context=%s ns=%s interval=%ss\n\n%s\n' \
      "$(date '+%Y-%m-%d %H:%M:%S')" "$K8S_CONTEXT" "$NAMESPACE" "$WATCH_INTERVAL" "$current"
    prev="$current"
  fi
  sleep "$WATCH_INTERVAL"
done
