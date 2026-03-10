# B 아키텍처 검증 보고서 (GPU Inference Simulator, 2026-03-10)

## 1. 목적
Task-20260310-14 목표인 "B 아키텍처 병목 검증 가능 상태"를 확인하기 위해,
- API -> inference-topic 발행
- inference worker(시뮬레이터 + semaphore) 소비
- inference 관련 메트릭 노출
- 10/30/50 VU 부하 재실행
을 검증했다.

---

## 2. 구현 요약
- API 발행 토픽: `ARCHITECTURE_MODE=B`일 때 `kafka_inference_topic` 사용
- Worker role: `WORKER_ROLE=inference`일 때 inference-topic consume
- Processor: `GpuInferenceSimulator`
  - semaphore 기반 동시성 제한 (`INFERENCE_MAX_CONCURRENCY`)
  - 시뮬레이션 지연 (`INFERENCE_SIMULATED_LATENCY_MS`)
  - 시뮬레이션 GPU 사용률 (`INFERENCE_SIMULATED_GPU_UTILIZATION`)

B 모드 검증용 compose override:
- `deploy/docker-compose.bmode.override.yml`

---

## 3. B 모드 실행 조건
- `ARCHITECTURE_MODE=B`
- `WORKER_ROLE=inference`
- `INFERENCE_MAX_CONCURRENCY=2`
- `INFERENCE_SIMULATED_LATENCY_MS=900`
- `INFERENCE_SIMULATED_GPU_UTILIZATION=0.85`

실행 확인 로그:
- worker subscribe topic: `inference-topic`
- consumer group: `architecture-a-worker-inference`

---

## 4. k6 재실행 결과 (B 모드)

| 시나리오 | HTTP req/s | p95 (ms) | 실패율 | iterations/s |
|---|---:|---:|---:|---:|
| B VU 10 | 92.18 | 23.32 | 0.00% | 46.09 |
| B VU 30 | 282.13 | 9.19 | 0.00% | 141.07 |
| B VU 50 | 316.73 | 18.64 | 0.35% | 158.92 |

산출물:
- `reports/perf/k6_bmode_vus10.json`
- `reports/perf/k6_bmode_vus30.json`
- `reports/perf/k6_bmode_vus50.json`

---

## 5. Prometheus 관측 지표 (B 모드)

1. Inference 동시 처리량(15m 최대)
- query: `max_over_time(inference_active_jobs[15m])`
- result(worker): **1**

2. Simulated GPU Utilization(15m 최대)
- query: `max_over_time(inference_simulated_gpu_utilization[15m])`
- result(worker): **0.85**

3. Inference stage p95 latency
- query: `histogram_quantile(0.95, sum(rate(inference_processing_seconds_bucket[5m])) by (le))`
- result: **0.9875 s**

4. End-to-end worker p95 latency
- query: `histogram_quantile(0.95, sum(rate(job_processing_seconds_bucket[5m])) by (le))`
- result: **0.983 s** (약)

5. Inference consumer group lag(15m 최대)
- query: `max_over_time(kafka_consumergroup_lag{consumergroup="architecture-a-worker-inference"}[15m])`
- result: **10716**

6. Throughput 비교 지표
- `sum(rate(jobs_created_total[5m]))` = **35.72/s**
- `sum(rate(jobs_success_total[5m]))` = **0.845/s**

---

## 6. 해석 (B 병목 검증 관점)
- inference-topic + inference worker 경로는 실제 동작한다.
- inference-specific 메트릭(`inference_*`)이 노출되어 GPU 병목 관측 기반이 생겼다.
- 현재 설정(동시성 2, 900ms)에서는 50 VU에서 실패율(0.35%)이 발생하고 lag가 누적된다.
- 즉, "B 아키텍처 병목을 관측/재현 가능한 상태"는 달성되었고,
  다음 단계는 동시성/워커 수/지연 파라미터를 조정해 목표 SLO를 맞추는 작업이다.

권장 후속:
1. inference worker replica 2~5 단계별 확장 실험
2. `INFERENCE_MAX_CONCURRENCY` 2/4/8 실험
3. 시뮬레이터를 실제 GPU runtime adapter로 교체
