#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.dev.yml}"
ENV_FILE="${ENV_FILE:-env/.env.dev}"
KAFKA_SERVICE="${KAFKA_SERVICE:-kafka}"
WATCH_MODE=false
WATCH_INTERVAL="${WATCH_INTERVAL:-2}"

usage() {
  cat <<'EOF'
Usage:
  kafka-consumer-group-describe.sh [GROUP_ID] [WORKER_ROLE]
  kafka-consumer-group-describe.sh --watch [--interval N] [GROUP_ID] [WORKER_ROLE]

Examples:
  ./scripts/kafka-consumer-group-describe.sh
  ./scripts/kafka-consumer-group-describe.sh architecture-main-worker
  ./scripts/kafka-consumer-group-describe.sh '' downstream
  ./scripts/kafka-consumer-group-describe.sh --watch --interval 2
EOF
}

POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --watch)
      WATCH_MODE=true
      shift
      ;;
    --interval)
      WATCH_INTERVAL="${2:-}"
      if [[ -z "$WATCH_INTERVAL" ]]; then
        echo "--interval requires a numeric value" >&2
        exit 1
      fi
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

GROUP_ID="${POSITIONAL[0]:-${KAFKA_GROUP_ID:-}}"
WORKER_ROLE_RAW="${POSITIONAL[1]:-${WORKER_ROLE:-}}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "env file not found: $ENV_FILE" >&2
  exit 1
fi

if [[ -z "$GROUP_ID" && -n "$WORKER_ROLE_RAW" ]]; then
  case "$WORKER_ROLE_RAW" in
    unified|inference|downstream) ;;
    *)
      echo "invalid WORKER_ROLE: $WORKER_ROLE_RAW (allowed: unified|inference|downstream)" >&2
      exit 1
      ;;
  esac

  if [[ "$WORKER_ROLE_RAW" == "downstream" ]]; then
    GROUP_ID="architecture-main-worker-downstream"
  else
    GROUP_ID="architecture-main-worker"
  fi
fi

if ! [[ "$WATCH_INTERVAL" =~ ^[0-9]+$ ]]; then
  echo "WATCH interval must be a non-negative integer: $WATCH_INTERVAL" >&2
  exit 1
fi

run_once() {
  if [[ -n "$GROUP_ID" ]]; then
    echo "describing consumer group: $GROUP_ID"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$KAFKA_SERVICE" \
      bash -lc '/opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}" --describe --group "'"$GROUP_ID"'"'
    return 0
  fi

  echo "describing all consumer groups"
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$KAFKA_SERVICE" \
    bash -lc 'for g in $(/opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}" --list); do echo "===== ${g} ====="; /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}" --describe --group "${g}"; echo; done'
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
    printf '[%s] interval=%ss\n\n%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$WATCH_INTERVAL" "$current"
    prev="$current"
  fi
  sleep "$WATCH_INTERVAL"
done
