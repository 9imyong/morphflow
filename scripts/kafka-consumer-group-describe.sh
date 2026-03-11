#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.dev.yml}"
ENV_FILE="${ENV_FILE:-env/.env.dev}"
KAFKA_SERVICE="${KAFKA_SERVICE:-kafka}"
GROUP_ID="${1:-${KAFKA_GROUP_ID:-}}"
WORKER_ROLE_RAW="${2:-${WORKER_ROLE:-}}"

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

if [[ -n "$GROUP_ID" ]]; then
  echo "describing consumer group: $GROUP_ID" >&2
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$KAFKA_SERVICE" \
    bash -lc '/opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}" --describe --group "'"$GROUP_ID"'"'
  exit 0
fi

echo "describing all consumer groups" >&2
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$KAFKA_SERVICE" \
  bash -lc 'for g in $(/opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}" --list); do echo "===== ${g} ====="; /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}" --describe --group "${g}"; echo; done'
