# 부하 테스트 및 성능 지표 보고서 (2026-03-10)

## 1. 목적
A 아키텍처 기준에서 부하 상황의 처리량/지연을 측정하고, A/B/C 전환 판단용 기초 지표를 확보한다.

---

## 2. 테스트 조건
- 대상 API: `POST /jobs`, `GET /jobs/{job_id}`
- 도구: k6 (Docker, `grafana/k6`)
- 테스트 시간: 각 시나리오 60초
- 동시 사용자(VU): 10 / 30 / 50
- 스택: `docker-compose.dev.yml` + `deploy/observability-compose.yml`
- 스크립트: `tests/perf/jobs_load_test.js`

실행 명령 예시:
```bash
docker run --rm -v "$PWD:/work" -w /work grafana/k6 run tests/perf/jobs_load_test.js \
  -e BASE_URL=http://host.docker.internal:8000 \
  -e VUS=10 -e DURATION=1m --summary-export reports/perf/k6_vus10.json
```

---

## 3. k6 결과 요약

| 시나리오 | HTTP req/s | POST+GET p95 (ms) | 실패율 | iterations/s |
|---|---:|---:|---:|---:|
| VU 10 | 91.86 | 24.05 | 0.00% | 45.93 |
| VU 30 | 283.45 | 7.56 | 0.00% | 141.72 |
| VU 50 | 449.04 | 28.34 | 0.00% | 224.52 |

원본 산출물:
- `reports/perf/k6_vus10.json`
- `reports/perf/k6_vus30.json`
- `reports/perf/k6_vus50.json`

---

## 4. Prometheus 지표 수집 (Grafana 패널 캡처 미포함)

측정 시점(약 2026-03-10 14:51 KST) Prometheus query 결과:

1. Kafka lag (15분 최대)
- query: `max_over_time(kafka_consumergroup_lag[15m])`
- result: **13441**

2. Kafka lag (현재)
- query: `max(kafka_consumergroup_lag)`
- result: **13384**

3. Worker 처리 지연 p95
- query: `histogram_quantile(0.95, sum(rate(job_processing_seconds_bucket[5m])) by (le))`
- result: **0.7375 s**

4. API job 생성 처리율
- query: `sum(rate(jobs_created_total[5m]))`
- result: **46.49 jobs/s**

5. Worker 성공 처리율
- query: `sum(rate(jobs_success_total[5m]))`
- result: **1.48 jobs/s**

---

## 5. Kafka lag / Worker latency 분석

관찰:
- API 요청 유입 처리율(`jobs_created_total`) 대비 worker 완료율(`jobs_success_total`)이 크게 낮다.
- 그 결과 `kafka_consumergroup_lag`가 큰 폭으로 누적되며 빠르게 해소되지 않는다.
- worker p95 처리시간(약 0.74초)은 안정적이지만, 단일 worker 처리용량 한계로 backlog가 누적되는 패턴이다.

해석:
- 현재 A 아키텍처 단일 worker 기준으로는 고부하(특히 50 VU)에서 **지속 가능한 소비량 < 유입량** 상태.
- 즉시 장애는 아니지만, 장시간 지속 시 처리 지연/큐 적체 리스크가 높다.

A/B/C 전환 판단 연결:
1. **단기 대응**: worker scale-out 우선
2. 추론 단계 병목이 확인되면 **A -> B** (inference role 실구현 분리)
3. 저장/후단 연동 병목이 지배적이면 **A -> C** (downstream role 실구현 분리)

권장 후속 실험:
1. worker replica 2/3/5 단계별 재측정 (lag 감소 곡선 비교)
2. 요청 payload 크기/처리시간 분포별 부하 프로파일 분리
3. 10분 이상 soak test로 backlog 수렴 여부 확인

---

## 6. 결론
- 테스트 자체는 10/30/50 VU 모두 HTTP 실패율 0%로 통과했다.
- 그러나 운영 핵심 지표 관점에서는 Kafka lag 누적이 커서, 현 구조에서 처리용량 개선(scale 또는 B/C 분리)이 필요하다.

추가 메모:
- 본 보고서는 Grafana 대시보드 스크린샷/내보내기를 포함하지 않는다.
- 수치는 모두 Prometheus API query 결과를 기준으로 기록했다.
