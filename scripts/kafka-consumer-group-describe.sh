#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.dev.yml}"
ENV_FILE="${ENV_FILE:-env/.env.dev}"
KAFKA_SERVICE="${KAFKA_SERVICE:-kafka}"
GROUP_ID="${1:-${KAFKA_GROUP_ID:-}}"
ARCH_MODE_RAW="${ARCHITECTURE_MODE:-}"
WORKER_ROLE_RAW="${2:-${WORKER_ROLE:-}}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "env file not found: $ENV_FILE" >&2
  exit 1
fi

if [[ -z "$GROUP_ID" && -n "$ARCH_MODE_RAW" ]]; then
  ARCH_MODE="$(printf '%s' "$ARCH_MODE_RAW" | tr '[:lower:]' '[:upper:]')"
  case "$ARCH_MODE" in
    A|B|C|BC) ;;
    *)
      echo "invalid ARCHITECTURE_MODE: $ARCH_MODE (allowed: A|B|C|BC)" >&2
      exit 1
      ;;
  esac

  if [[ -z "$WORKER_ROLE_RAW" ]]; then
    case "$ARCH_MODE" in
      A) WORKER_ROLE_RAW="unified" ;;
      B|C|BC) WORKER_ROLE_RAW="inference" ;;
    esac
  fi

  case "$WORKER_ROLE_RAW" in
    unified|inference|downstream) ;;
    *)
      echo "invalid WORKER_ROLE: $WORKER_ROLE_RAW (allowed: unified|inference|downstream)" >&2
      exit 1
      ;;
  esac

  MODE_LOWER="$(printf '%s' "$ARCH_MODE" | tr '[:upper:]' '[:lower:]')"
  if [[ "$WORKER_ROLE_RAW" == "unified" ]]; then
    GROUP_ID="architecture-${MODE_LOWER}-worker"
  else
    GROUP_ID="architecture-${MODE_LOWER}-worker-${WORKER_ROLE_RAW}"
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
