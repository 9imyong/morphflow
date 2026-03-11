#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.dev.yml}"
ENV_FILE="${ENV_FILE:-env/.env.dev}"
KAFKA_SERVICE="${KAFKA_SERVICE:-kafka}"
DLQ_TOPIC="${1:-${KAFKA_DLQ_TOPIC:-dlq-topic}}"
MAX_MESSAGES="${2:-${MAX_MESSAGES:-20}}"
FROM_BEGINNING="${FROM_BEGINNING:-true}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "env file not found: $ENV_FILE" >&2
  exit 1
fi

if ! [[ "$MAX_MESSAGES" =~ ^[0-9]+$ ]]; then
  echo "MAX_MESSAGES must be a non-negative integer: $MAX_MESSAGES" >&2
  exit 1
fi

FROM_BEGINNING_FLAG=""
if [[ "$FROM_BEGINNING" == "true" ]]; then
  FROM_BEGINNING_FLAG="--from-beginning"
fi

echo "consuming topic=$DLQ_TOPIC max_messages=$MAX_MESSAGES from_beginning=$FROM_BEGINNING" >&2
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$KAFKA_SERVICE" \
  bash -lc '/opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}" \
    --topic "'"$DLQ_TOPIC"'" \
    '"$FROM_BEGINNING_FLAG"' \
    --max-messages "'"$MAX_MESSAGES"'" \
    --property print.timestamp=true \
    --property print.headers=true \
    --property print.key=true'
