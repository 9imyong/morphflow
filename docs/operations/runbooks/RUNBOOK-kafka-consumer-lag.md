---
id: RUNBOOK-queue-001
title: Kafka 컨슈머 적체 급증
owners: [김용준]
last_validated: 2026-03-18
severity: 높음
---

# 런북: Kafka 컨슈머 적체 급증

## 발동 조건과 영향

- 경보: `KafkaConsumerLagHigh` (`max(kafka_consumergroup_lag) > 100`, 5분 지속)
- 동반 경보: `WorkerProcessingTimeHigh`

사용자 영향은 **접수는 정상이지만 완료가 지연**되는 형태로 나타납니다. `POST /jobs`는 계속 `202`를 반환하므로 클라이언트는 이상을 느끼지 못하지만, `GET /jobs/{job_id}`가 오랫동안 `PENDING`에 머무릅니다.

## 사전 조건과 안전 수칙

- 필요한 접근: Prometheus, Kafka 컨슈머 그룹 조회 권한, 워커 배포 변경 권한
- 실행하면 안 되는 조건: 원인 파악 전 컨슈머 그룹 오프셋을 임의로 이동시키지 않습니다. 미처리 작업이 영구 유실됩니다.
- 데이터 손실 가능성: 오프셋을 조작하지 않는 한 없습니다. 적체는 지연이지 유실이 아닙니다.

## 진단

1. 수집 대상이 살아 있는지 확인합니다.

   ```bash
   curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
   ```

   정상: 모든 항목 `health: "up"`. `kafka_consumer_lag`이 `down`이면 적체가 아니라 **수집 실패**입니다.

2. 어느 그룹이 밀리는지 확인합니다.

   ```bash
   scripts/kafka-consumer-group-describe.sh     # Compose
   scripts/kafka-k8s-lag.sh                     # Kubernetes
   ```

   - `architecture-main-worker`가 밀림 → 추론 경로 문제
   - `architecture-main-worker-downstream`이 밀림 → [후단 병목 런북](RUNBOOK-downstream-bottleneck.md)으로 이동

3. 유입과 처리 속도를 비교합니다.

   ```promql
   sum(rate(jobs_created_total[5m]))
   sum(rate(jobs_success_total[5m]))
   sum(rate(downstream_success_total[5m]))
   ```

   유입이 처리를 지속적으로 넘으면 용량 부족이고, 처리율이 0에 가까우면 워커가 멈춘 것입니다.

4. 워커 상태를 확인합니다.

   ```bash
   kubectl get pods -n morphflow --context kind-local-dev
   kubectl logs deploy/worker -n morphflow --context kind-local-dev --tail=100
   ```

   **같은 `job_id`가 로그에 반복 등장하면 특정 메시지에서 처리가 막혔을 수 있습니다.** [위험과 기술 부채](../../architecture/risks-technical-debt.md)의 예외 처리 항목을 참조하고 [재시도·DLQ 런북](RUNBOOK-retry-dlq-surge.md)으로 이동합니다.

## 완화와 복구

1. 워커를 수평 확장합니다. 가장 안전하고 되돌리기 쉬운 조치입니다.

   ```bash
   kubectl scale deploy/worker -n morphflow --replicas=4 --context kind-local-dev
   ```

   **파티션 수를 넘는 워커는 유휴 상태가 됩니다.** 현재 진입 토픽 파티션은 8이므로 8을 넘겨 늘리지 않습니다.

2. 파티션이 부족하면 늘립니다. 파티션은 축소할 수 없으므로 신중하게 결정합니다.

   ```bash
   # KAFKA_PARTITIONS_WORKER_TOPIC 값을 올린 뒤 재배포하면 기동 시 자동 확장됩니다
   kubectl edit configmap morphflow-app-config -n morphflow --context kind-local-dev
   ```

3. 반복 오류로 죽는 워커가 있으면 해당 파드를 분리 재기동합니다.

   ```bash
   kubectl delete pod <pod-name> -n morphflow --context kind-local-dev
   ```

4. 적체가 감소 추세로 돌아서면 확장을 **단계적으로** 축소합니다. 한 번에 원래 수준으로 되돌리지 않습니다.

중단 조건: 확장 후에도 처리율이 오르지 않으면 용량 문제가 아니므로 확장을 멈추고 [워커 지연 런북](RUNBOOK-worker-processing-delay.md)으로 이동합니다.

## 검증

- `kafka_consumergroup_lag`이 감소 추세로 전환되고 임계치 아래로 복귀
- 처리율(`jobs_success_total` 또는 `downstream_success_total`)이 유입률에 근접
- 실패율과 `dlq_messages_total`이 증가하지 않음
- 30분간 재발 없음

## 에스컬레이션

확장으로 해소되지 않고 반복되면 아키텍처 모드 전환을 검토합니다. 판단 기준은 [장애 대응](../incident-response.md)의 전환 판단 표에 있습니다.

## 이력

| 날짜 | 검증 또는 사용 결과 | 수행자 | 후속 조치 |
|---|---|---|---|
| 2026-03-18 | 기존 Runbook 문서에서 이관 후 현재 지표·그룹 이름 기준으로 정정 | 김용준 | 없음 |
