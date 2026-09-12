---
id: RUNBOOK-downstream-001
title: 후단 처리 병목
owners: [김용준]
last_validated: 2026-03-18
severity: 보통
---

# 런북: 후단 처리 병목

## 발동 조건과 영향

- 경보: `DownstreamConsumerLagHigh`, `DownstreamProcessingTimeHigh`
- 적용 모드: **C·BC 모드에서만 발생합니다.** A·B 모드에는 후단 워커가 없습니다.

작업이 `PROCESSING` 상태에 장시간 머무릅니다. 추론은 이미 끝났지만 최종 완료가 기록되지 않은 상태입니다.

## 사전 조건과 안전 수칙

- 필요한 접근: Prometheus, 후단 워커 배포 변경 권한
- 실행하면 안 되는 조건: 후단 워커를 2개 이상으로 늘릴 때는 주의합니다. 현재 후단 경로에는 처리 잠금이 없어 같은 작업을 동시에 처리할 수 있습니다. [위험과 기술 부채](../../architecture/risks-technical-debt.md)를 확인하십시오.
- 데이터 손실 가능성: 없습니다.

## 진단

1. 후단 그룹의 적체를 확인합니다.

   ```promql
   max(kafka_consumergroup_lag{consumergroup="architecture-main-worker-downstream"})
   max_over_time(kafka_consumergroup_lag{consumergroup="architecture-main-worker-downstream"}[15m])
   ```

2. 후단 처리 시간과 완료율을 확인합니다.

   ```promql
   histogram_quantile(0.95, sum(rate(downstream_processing_seconds_bucket[5m])) by (le))
   sum(rate(downstream_success_total[5m]))
   sum(rate(downstream_failure_total[5m]))
   ```

3. 추론 단계는 정상인지 대조합니다. 추론이 함께 느리면 후단 문제가 아니라 공통 자원 문제입니다.

   ```promql
   histogram_quantile(0.95, sum(rate(inference_processing_seconds_bucket[5m])) by (le))
   ```

4. 장시간 `PROCESSING` 작업을 확인합니다.

   ```sql
   SELECT id, status, updated_at FROM jobs
   WHERE status = 'PROCESSING' AND updated_at < now() - interval '15 minutes'
   ORDER BY updated_at;
   ```

5. 후단 처리의 실제 대상(저장·전달)이 느린지 확인합니다. 현재 후단 처리는 더미 구현이므로 지연의 대부분은 `DOWNSTREAM_SIMULATED_LATENCY_MS` 설정값입니다.

## 완화와 복구

1. 후단 워커를 확장합니다.

   ```bash
   kubectl scale deploy/downstream-worker -n morphflow --replicas=2 --context kind-local-dev
   ```

   **확장 전 위 안전 수칙의 처리 잠금 부재를 확인하십시오.**

2. 후단 토픽 파티션이 1이면 확장 효과가 없습니다. `KAFKA_PARTITIONS_DOWNSTREAM_TOPIC`을 올린 뒤 재배포합니다.

3. 외부 연동 장애가 원인이면 해당 의존성을 먼저 복구합니다.

4. 적체가 감소하면 단계적으로 축소합니다.

중단 조건: 확장 후에도 처리율이 오르지 않으면 파티션 수 또는 외부 의존성이 상한입니다.

## 검증

- 후단 적체가 감소 추세로 전환
- `downstream_processing_seconds` p95가 기준치로 복귀
- 장시간 `PROCESSING` 작업이 해소
- `downstream_failure_total`이 증가하지 않음

## 에스컬레이션

이 시나리오는 **이미 C 경로가 적용된 상태**이므로 추가 모드 전환 대상이 아닙니다. 후단 경로 안에서의 확장과 작업 단위 세분화를 검토합니다. 세분화 구상은 [RFC-0002](../../rfcs/RFC-0002-downstream-task-granularity.md)에 있습니다.

## 이력

| 날짜 | 검증 또는 사용 결과 | 수행자 | 후속 조치 |
|---|---|---|---|
| 2026-03-18 | 기존 Runbook 문서에서 이관. 컨슈머 그룹 이름을 실제 값으로 정정 | 김용준 | 후단 처리 잠금 추가 필요 |
