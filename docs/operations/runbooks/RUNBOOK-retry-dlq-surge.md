---
id: RUNBOOK-reliability-001
title: 재시도·DLQ 급증
owners: [김용준]
last_validated: 2026-03-18
severity: 높음
---

# 런북: 재시도·DLQ 급증

## 발동 조건과 영향

- 경보: `DlqMessagesDetected` (`increase(dlq_messages_total[5m]) > 0`, 2분 지속)
- 증상: `retry_published_total` 급증, 동일 `error-reason` 반복

DLQ 적재는 **재시도 한도를 소진한 영구 실패**를 뜻합니다. 해당 작업은 자동 복구되지 않으며 수동 재주입이 필요합니다.

## 사전 조건과 안전 수칙

- 필요한 접근: Kafka 콘솔 도구, 워커 로그
- 실행하면 안 되는 조건: 원인을 수정하기 전에 DLQ를 일괄 재주입하지 않습니다. 같은 실패를 반복하며 적체만 늘립니다.
- 데이터 손실 가능성: DLQ 메시지는 원본 payload를 보존하므로 재주입이 가능합니다. 토픽 보존 기간이 지나면 사라집니다.

## 진단

1. 실패 유형을 헤더로 분류합니다.

   ```bash
   scripts/kafka-dlq-consume.sh
   ```

   `error-reason`, `original-topic`, `retry-count` 헤더로 분류합니다.

   | `error-reason` 패턴 | 분류 | 대응 |
   |---|---|---|
   | 스키마·필수 필드 관련 | 고정 오류 | 재주입 금지. 원인 수정 먼저 |
   | 연결·타임아웃 관련 | 일시 오류 | 의존성 회복 후 재주입 |
   | `IN_PROGRESS_LOCK` | **오탐 가능성** | 아래 참조 |

2. `IN_PROGRESS_LOCK`이 다수면 실제 실패가 아닐 수 있습니다. 잠금 경합이 재시도 횟수를 소모하는 알려진 한계 때문이며, 원본 작업은 정상 처리되었을 수 있습니다. 해당 `job_id`의 실제 상태를 확인합니다.

   ```sql
   SELECT id, status, error_message, updated_at FROM jobs WHERE id IN ('<job_id>', ...);
   ```

   `SUCCESS`라면 DLQ 메시지는 무시해도 됩니다. 자세한 내용은 [위험과 기술 부채](../../architecture/risks-technical-debt.md)에 있습니다.

3. 최근 배포와 외부 의존성 상태를 확인합니다.

   ```bash
   kubectl rollout history deploy/worker -n morphflow --context kind-local-dev
   curl -s http://localhost:18000/health/ready | jq
   ```

4. 재시도 비율을 확인합니다.

   ```promql
   increase(retry_published_total[5m])
   increase(retry_failure_total[5m])
   increase(dlq_messages_total[5m])
   ```

## 완화와 복구

1. 고정 오류면 **즉시 재주입을 중단**하고 원인을 수정합니다. 배포가 원인이면 되돌립니다.

2. 원인 수정 후 샘플 1건만 재주입해 정상 처리를 확인합니다.

   ```bash
   docker exec -i $(docker compose -f docker-compose.dev.yml ps -q kafka) \
     /opt/kafka/bin/kafka-console-producer.sh \
     --bootstrap-server kafka:9092 \
     --topic request-topic
   ```

3. 샘플이 성공하면 배치 재주입합니다. 재주입 전 `RETRY_MAX_COUNT`와 백오프 설정이 적절한지 확인합니다.

4. 재주입 후 적체, 실패율, DLQ 증가율이 안정화되는지 관찰합니다.

중단 조건: 재주입한 메시지가 다시 DLQ로 가면 즉시 멈추고 원인 분석으로 돌아갑니다.

## 검증

- `dlq_messages_total` 증가가 멈춤
- 재주입한 작업이 `SUCCESS`에 도달
- `retry_published_total` 증가율이 평시 수준으로 복귀
- 30분간 재발 없음

## 에스컬레이션

추론 구간 오류가 주원인이면 A → B, 후단 저장·연동 실패가 주원인이면 A → C 전환을 검토합니다. 다만 전환 전에 오류 유형이 구조 문제인지 개별 결함인지 먼저 판단합니다.

## 이력

| 날짜 | 검증 또는 사용 결과 | 수행자 | 후속 조치 |
|---|---|---|---|
| 2026-03-18 | 기존 Runbook 문서에서 이관. `IN_PROGRESS_LOCK` 오탐 판별 절차 추가 | 김용준 | 잠금 경합 분리 개선 필요 |
