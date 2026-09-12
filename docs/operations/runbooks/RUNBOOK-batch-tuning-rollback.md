---
id: RUNBOOK-worker-002
title: 배치 처리 튜닝과 롤백
owners: [김용준]
last_validated: 2026-03-18
severity: 낮음
---

# 런북: 배치 처리 튜닝과 롤백

## 발동 조건과 영향

- 증상: 배치 설정 변경 후 tail latency(p95) 상승, 적체가 해소되지 않음
- 적용 대상: 추론 마이크로배치와 Kafka 소비 배치

배치는 처리량을 올리는 대신 대기 시간을 추가합니다. 잘못 설정하면 처리량 이득 없이 지연만 커집니다.

## 사전 조건과 안전 수칙

- 필요한 접근: 설정 변경과 워커 재배포 권한
- 실행하면 안 되는 조건: 적체가 이미 심각한 상황에서 배치 파라미터만 조정하지 않습니다. **단일 파티션·단일 워커 구성에서는 배치만으로 적체를 해소할 수 없습니다.** 확장이 선행되어야 합니다.
- 데이터 손실 가능성: 없습니다.

## 진단

1. 현재 설정을 확인합니다.

   ```bash
   kubectl get configmap morphflow-app-config -n morphflow --context kind-local-dev -o yaml | grep -E 'BATCH'
   ```

   관련 설정:

   - `INFERENCE_BATCH_ENABLED`, `INFERENCE_BATCH_SIZE`, `INFERENCE_BATCH_TIMEOUT_MS`, `INFERENCE_BATCH_OVERHEAD_MS`
   - `KAFKA_CONSUMER_BATCH_ENABLED`, `KAFKA_CONSUMER_BATCH_MAX_RECORDS`, `KAFKA_CONSUMER_BATCH_TIMEOUT_MS`

2. 세 지표를 **동시에** 확인합니다. 하나만 보고 판단하지 않습니다.

   ```promql
   max(kafka_consumergroup_lag)
   histogram_quantile(0.95, sum(rate(inference_processing_seconds_bucket[5m])) by (le))
   sum(rate(jobs_failure_total[5m]))
   ```

## 완화와 복구

### 튜닝 시작점

| 상황 | `INFERENCE_BATCH_SIZE` | `INFERENCE_BATCH_TIMEOUT_MS` |
|---|---|---|
| 저트래픽·지연 민감 | 4 | 20~30 |
| 고트래픽·처리량 우선 | 8~16 | 50~100 |

| 상황 | `KAFKA_CONSUMER_BATCH_MAX_RECORDS` | `KAFKA_CONSUMER_BATCH_TIMEOUT_MS` |
|---|---|---|
| 일반 | 32~128 | 100~300 |

1. tail latency가 문제면 **타임아웃을 먼저 줄입니다.** 배치 크기보다 대기 시간이 p95에 직접적입니다.
2. 적체가 계속 증가하면 배치 조정을 멈추고 파티션·워커 확장을 병행합니다.
3. 한 번에 하나의 파라미터만 바꾸고 재측정합니다.

### 안전 모드 롤백

```bash
kubectl set env deploy/worker -n morphflow --context kind-local-dev \
  INFERENCE_BATCH_ENABLED=false KAFKA_CONSUMER_BATCH_ENABLED=false
```

롤백 후 적체 추세를 다시 확인하고, 재활성화는 **소비 배치 → 추론 배치 순서**로 단계적으로 수행합니다.

중단 조건: 안전 모드에서도 지표가 개선되지 않으면 배치가 원인이 아니므로 [워커 지연 런북](RUNBOOK-worker-processing-delay.md)으로 이동합니다.

## 검증

- p95가 목표 범위로 복귀
- 적체가 증가 추세가 아님
- 실패율이 증가하지 않음
- 세 지표가 동시에 악화되지 않음

## 에스컬레이션

배치 조정으로 해결되지 않으면 구조 문제입니다. 파티션 증설과 워커 확장을 우선하고, 그래도 남으면 모드 전환을 검토합니다.

## 이력

| 날짜 | 검증 또는 사용 결과 | 수행자 | 후속 조치 |
|---|---|---|---|
| 2026-03-12 | B 모드 배치 적용 후 재실측. 처리량·실패율 개선, p95 증가 확인 | 김용준 | 파티션·워커 확장 선행 필요 |
| 2026-03-18 | 기존 Runbook 문서에서 이관 | 김용준 | 없음 |
