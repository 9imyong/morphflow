---
id: RUNBOOK-worker-001
title: 워커 처리 지연
owners: [김용준]
last_validated: 2026-03-18
severity: 보통
---

# 런북: 워커 처리 지연

## 발동 조건과 영향

- 경보: `WorkerProcessingTimeHigh` (`job_processing_seconds` p95 > 5초, 10분 지속)
- 동반 경보: `InferenceConcurrencySaturated`

작업이 `PROCESSING` 상태에 머무는 시간이 길어지고, 누적되면 적체로 이어집니다.

## 사전 조건과 안전 수칙

- 필요한 접근: Prometheus, 워커 로그와 배포 변경 권한
- 실행하면 안 되는 조건: 원인 확인 없이 동시성(`INFERENCE_MAX_CONCURRENCY`)을 크게 올리지 않습니다. 자원 경합으로 지연이 악화될 수 있습니다.
- 데이터 손실 가능성: 없습니다.

## 진단

1. 어느 단계가 느린지 구분합니다. **이것이 이 런북의 핵심입니다.**

   ```promql
   histogram_quantile(0.95, sum(rate(job_processing_seconds_bucket[5m])) by (le))
   histogram_quantile(0.95, sum(rate(inference_processing_seconds_bucket[5m])) by (le))
   histogram_quantile(0.95, sum(rate(downstream_processing_seconds_bucket[5m])) by (le))
   ```

   - 전체와 추론이 함께 높음 → 추론 구간 병목
   - 전체는 높은데 추론은 정상 → 저장·전달 구간 병목. [데이터베이스 지연 런북](RUNBOOK-database-latency.md) 확인
   - 후단만 높음 → [후단 병목 런북](RUNBOOK-downstream-bottleneck.md)

2. 동시성 포화 여부를 확인합니다.

   ```promql
   max(inference_active_jobs)
   histogram_quantile(0.95, sum(rate(inference_semaphore_wait_seconds_bucket[5m])) by (le))
   ```

   세마포어 대기 시간이 길면 처리 능력이 아니라 **동시성 설정이 상한**입니다.

3. 최근 배포와 설정 변경을 확인합니다.

   ```bash
   kubectl rollout history deploy/worker -n morphflow --context kind-local-dev
   ```

4. 자원 사용률을 확인합니다.

   ```bash
   kubectl top pods -n morphflow --context kind-local-dev
   ```

## 완화와 복구

1. 최근 배포가 원인으로 의심되면 먼저 되돌립니다.

   ```bash
   kubectl rollout undo deploy/worker -n morphflow --context kind-local-dev
   ```

2. 세마포어 대기가 길고 자원 여유가 있으면 동시성을 **한 단계씩** 올립니다. `INFERENCE_MAX_CONCURRENCY`를 변경하면 `InferenceConcurrencySaturated` 경보 임계값도 함께 조정해야 합니다.

3. 자원이 포화 상태면 확장이 우선입니다. [Kafka 적체 런북](RUNBOOK-kafka-consumer-lag.md)의 확장 절차를 따릅니다.

4. 배치 설정이 tail latency를 키우는 것으로 의심되면 [배치 튜닝 런북](RUNBOOK-batch-tuning-rollback.md)으로 이동합니다.

중단 조건: 조치 후에도 p95가 개선되지 않으면 추가 변경을 멈추고 단계별 지표를 다시 수집합니다.

## 검증

- 해당 단계의 p95가 기준치로 복귀
- 적체가 증가하지 않음
- 실패율과 재시도 발생량이 증가하지 않음

## 에스컬레이션

지연이 특정 단계에 반복적으로 집중되면 해당 단계의 분리를 검토합니다. [장애 대응](../incident-response.md)의 전환 판단 표를 따릅니다.

## 이력

| 날짜 | 검증 또는 사용 결과 | 수행자 | 후속 조치 |
|---|---|---|---|
| 2026-03-18 | 기존 Runbook 문서에서 이관. 단계 구분 진단을 앞으로 이동 | 김용준 | 없음 |
