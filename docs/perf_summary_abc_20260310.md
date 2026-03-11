# A/B/C 성능 비교 요약 (2026-03-10)

## 1. 목적
현재 확보된 성능 데이터를 기준으로 A/B/C 모드의 처리 특성을 비교하고, 전환 판단 근거를 정리한다.

---

## 2. 측정 범위
- A 모드: k6 실측 완료 (`docs/perf_test_report_20260310.md`)
- B 모드: k6 실측 완료 (`docs/perf_test_report_bmode_20260310.md`)
- C 모드: k6 실측 완료 (`docs/perf_test_report_cmode_20260311.md`)

---

## 3. 요약 표

| 항목 | A 모드 | B 모드 | C 모드 |
|---|---:|---:|---|
| 최대 실측 부하 | 50 VU | 50 VU | 50 VU |
| HTTP req/s (50 VU) | 449.04 | 316.73 | 451.11 |
| p95 (50 VU, ms) | 28.34 | 18.64 | 32.03 |
| 실패율 (50 VU) | 0.00% | 0.35% | 0.00% |
| 주요 lag 지표 | `max lag` 13384 | inference group `max` 10716 | downstream group `max_over_time` 1 |
| stage p95 | worker p95 ~0.7375s | inference p95 ~0.9875s | downstream p95 ~0.7375s |

---

## 4. 해석

### A 모드
- API 수용량은 높지만(`jobs_created_total`) worker 완료율(`jobs_success_total`) 대비 유입량이 커서 lag 누적.
- 단일 경로 구조로 병목이 한 worker 내부에 혼합되어 나타남.

### B 모드
- inference 경로 분리 및 `inference_*` 메트릭 관측 가능.
- 동시성 2, 지연 900ms 조건에서 inference lag 누적과 일부 실패율이 관측되어 병목 재현 가능.

### C 모드
- inference -> downstream 분리 경로가 10/30/50 VU에서 실측 검증됨.
- downstream lag는 낮게 유지(max 1, current 0).
- downstream p95 latency는 약 0.7375s로 관측됨.

---

## 5. Kafka lag / latency 관점 전환 판단
- A -> B: inference 지표 악화(inference lag/p95/GPU util)
- A/B -> C: downstream lag/p95 및 후단 연동 지연 증가
- B+C: inference 안정화 이후에도 downstream만 악화될 때

---

## 6. 후속 권장 실험
1. C 모드 전용 부하 테스트(10/30/50 VU) 재실행
2. downstream worker replica 1/2/3 비교
3. inference/downstream 동시 scale 조합 실험으로 SLO 경계값 도출
