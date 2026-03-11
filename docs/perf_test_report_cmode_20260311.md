# C 아키텍처 부하 테스트 보고서 (2026-03-11)

## 1. 목적
C architecture(inference/downstream 분리)에서 실제 부하(10/30/50 VU) 기준으로 처리량/지연과 downstream 관측 지표를 실측한다.

---

## 2. 실행 조건
- compose:
  - `docker-compose.dev.yml`
  - `deploy/docker-compose.cmode.override.yml`
- observability:
  - `deploy/observability-compose.yml`
- worker 구성:
  - `worker` = inference role
  - `downstream-worker` = downstream role
- 부하 도구:
  - `tests/perf/jobs_load_test.js`
  - k6 60초, VU 10/30/50

실행 명령:
```bash
docker run --rm -v "$PWD:/work" -w /work grafana/k6 run tests/perf/jobs_load_test.js \
  -e BASE_URL=http://host.docker.internal:8000 \
  -e VUS=10 -e DURATION=1m --summary-export reports/perf/k6_cmode_vus10.json

docker run --rm -v "$PWD:/work" -w /work grafana/k6 run tests/perf/jobs_load_test.js \
  -e BASE_URL=http://host.docker.internal:8000 \
  -e VUS=30 -e DURATION=1m --summary-export reports/perf/k6_cmode_vus30.json

docker run --rm -v "$PWD:/work" -w /work grafana/k6 run tests/perf/jobs_load_test.js \
  -e BASE_URL=http://host.docker.internal:8000 \
  -e VUS=50 -e DURATION=1m --summary-export reports/perf/k6_cmode_vus50.json
```

---

## 3. k6 결과 요약 (C 모드)

| 시나리오 | HTTP req/s | p95 (ms) | 실패율 | iterations/s |
|---|---:|---:|---:|---:|
| C VU 10 | 92.08 | 21.39 | 0.00% | 46.04 |
| C VU 30 | 277.68 | 20.60 | 0.00% | 138.84 |
| C VU 50 | 451.11 | 32.03 | 0.00% | 225.55 |

산출물:
- `reports/perf/k6_cmode_vus10.json`
- `reports/perf/k6_cmode_vus30.json`
- `reports/perf/k6_cmode_vus50.json`

---

## 4. downstream 관측 지표 (Prometheus)

측정 시점: 2026-03-11 KST

1. downstream consumer lag (15m max)
- query: `max_over_time(kafka_consumergroup_lag{consumergroup="architecture-a-worker-downstream"}[15m])`
- result: **1**

2. downstream consumer lag (current)
- query: `max(kafka_consumergroup_lag{consumergroup="architecture-a-worker-downstream"})`
- result: **1**

3. downstream processing p95 latency
- query: `histogram_quantile(0.95, sum(rate(downstream_processing_seconds_bucket[5m])) by (le))`
- result: **0.7375 s**

4. downstream success throughput
- query: `sum(rate(downstream_success_total[5m]))`
- result: **0.8858 /s**

참고:
- C 경로에서 최종 완료는 `downstream_success_total`이 핵심 지표이며,
  기존 `jobs_success_total`은 C 경로 완료량 비교 지표로 사용하기 어렵다.

---

## 5. 해석
- C 모드에서 inference/downstream 분리 경로는 부하 조건에서도 안정적으로 동작했다.
- downstream lag는 낮게 유지(`max 1`, `current 1`)되어 큐 적체는 제한적이다.
- downstream p95는 약 0.74s로 관측되며, 설정된 downstream 처리 지연(500ms) + 시스템 오버헤드가 반영된 값으로 해석 가능하다.

---

## 6. 결론
- Task-20260310-19 목표인 C 아키텍처 실측(10/30/50 VU, downstream lag/latency 측정)을 완료했다.
- 다음 단계는 downstream replica 증설 실험(1/2/3)과 B+C 동시 스케일링 조합 비교다.
