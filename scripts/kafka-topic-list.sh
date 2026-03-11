#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.dev.yml}"
ENV_FILE="${ENV_FILE:-env/.env.dev}"
KAFKA_SERVICE="${KAFKA_SERVICE:-kafka}"
TOPIC_FILTER="${1:-${KAFKA_TOPIC_FILTER:-}}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "env file not found: $ENV_FILE" >&2
  exit 1
fi

if [[ -n "$TOPIC_FILTER" ]]; then
  echo "listing kafka topics (filter: $TOPIC_FILTER)" >&2
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$KAFKA_SERVICE" \
    bash -lc '/opt/kafka/bin/kafka-topics.sh --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}" --list | grep -E "'"$TOPIC_FILTER"'" || true'
  exit 0
fi

echo "listing kafka topics" >&2
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$KAFKA_SERVICE" \
  bash -lc '/opt/kafka/bin/kafka-topics.sh --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}" --list'
