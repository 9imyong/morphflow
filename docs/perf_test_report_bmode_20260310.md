# B 아키텍처 검증 보고서 (GPU Inference Simulator, 2026-03-10 / 배치 재실측 2026-03-12)

## 1. 목적
B 모드에서 다음 두 가지를 검증한다.
- 기존 병목 재현 가능 상태 유지 여부
- 2026-03-12 반영한 배치 처리(`Kafka consume batch + GPU micro-batch`)의 실효성

---

## 2. 실행 조건
- Compose: `docker-compose.dev.yml + deploy/docker-compose.bmode.override.yml`
- worker role/group:
  - role: `inference`
  - consumer group: `architecture-main-worker`
- 주요 런타임 설정:
  - `INFERENCE_MAX_CONCURRENCY=2`
  - `INFERENCE_SIMULATED_LATENCY_MS=900` (bmode override)
  - `INFERENCE_BATCH_ENABLED=true` (앱 기본값)
  - `KAFKA_CONSUMER_BATCH_ENABLED=true` (앱 기본값)

---

## 3. k6 실측 결과 (2026-03-12 재실행)

| 시나리오 | HTTP req/s | p95 (ms) | 실패율 | iterations/s |
|---|---:|---:|---:|---:|
| B VU 10 | 93.85 | 14.02 | 0.00% | 46.92 |
| B VU 30 | 278.64 | 16.60 | 0.00% | 139.32 |
| B VU 50 | 428.71 | 53.93 | 0.00% | 214.36 |

산출물:
- `reports/perf/k6_bmode_vus10.json`
- `reports/perf/k6_bmode_vus30.json`
- `reports/perf/k6_bmode_vus50.json`

---

## 4. Kafka lag 관측 (재실측 구간)
- 부하 시작 전(`architecture-main-worker`, request-topic): `2465`
- 부하 10/30/50 VU 연속 실행 후: `11627`

해석:
- API 수용량은 크게 증가했지만, 단일 파티션/단일 consumer 구간의 처리 용량보다 입력이 크면 lag는 계속 누적된다.
- 즉, 배치 처리만으로는 "과다 유입 대비 lag 억제"가 충분치 않고 파티션/워커 스케일링이 함께 필요하다.

---

## 5. 이전(2026-03-10) 대비 변화
- 50 VU 기준:
  - HTTP req/s: `316.73 -> 428.71`
  - p95(ms): `18.64 -> 53.93`
  - 실패율: `0.35% -> 0.00%`
- 정리:
  - 처리량/안정성은 개선
  - tail latency(p95)는 증가
  - 처리 백엔드 용량 한계 구간에서는 lag 누적 지속

---

## 6. 결론 및 후속
- 결론:
  - B 모드 배치 처리 반영은 유효하며, API 처리량/에러율 관점에서 개선을 확인했다.
  - 다만 lag 관점의 근본 개선에는 토픽 파티션 확장 + worker 수평 확장이 필수다.

- 권장 후속:
1. `request-topic` 파티션 증설(예: 1 -> 4)
2. worker replica를 파티션 수에 맞춰 증설(예: 1 -> 4)
3. 배치 파라미터(`INFERENCE_BATCH_SIZE`, `INFERENCE_BATCH_TIMEOUT_MS`) A/B 실험으로 p95와 lag를 동시 최적화
