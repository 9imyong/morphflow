# A/B/C 성능 비교 요약 (2026-03-10)

## 1. 목적
현재 확보된 성능 데이터를 기준으로 A/B/C 모드의 처리 특성을 비교하고, 전환 판단 근거를 정리한다.

---

## 2. 측정 범위
- A 모드: k6 실측 완료 (`docs/perf_test_report_20260310.md`)
- B 모드: k6 실측 완료 (`docs/perf_test_report_bmode_20260310.md`)
- C 모드: 최소 분리 시나리오 테스트 완료 (`tests/test_c_architecture_flow.py`), k6 부하 실측은 후속

---

## 3. 요약 표

| 항목 | A 모드 | B 모드 | C 모드 |
|---|---:|---:|---|
| 최대 실측 부하 | 50 VU | 50 VU | 시나리오 테스트 |
| HTTP req/s (50 VU) | 449.04 | 316.73 | 미측정 |
| p95 (50 VU, ms) | 28.34 | 18.64 | 미측정 |
| 실패율 (50 VU) | 0.00% | 0.35% | 미측정 |
| 주요 lag 지표 | `max lag` 13384 | inference group `max` 10716 | downstream group 관측 체계 구축 |
| worker p95 | ~0.7375s | ~0.983s | downstream p95 metric 추가 완료 |

---

## 4. 해석

### A 모드
- API 수용량은 높지만(`jobs_created_total`) worker 완료율(`jobs_success_total`) 대비 유입량이 커서 lag 누적.
- 단일 경로 구조로 병목이 한 worker 내부에 혼합되어 나타남.

### B 모드
- inference 경로 분리 및 `inference_*` 메트릭 관측 가능.
- 동시성 2, 지연 900ms 조건에서 inference lag 누적과 일부 실패율이 관측되어 병목 재현 가능.

### C 모드
- inference -> downstream 분리 경로는 시나리오 테스트로 검증됨.
- downstream 병목 측정용 metric/alert(`downstream_processing_seconds`, `DownstreamConsumerLagHigh`) 준비 완료.
- k6 기반 C 모드 부하 실측은 다음 단계 필요.

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

