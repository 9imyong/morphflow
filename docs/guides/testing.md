# 테스트 안내

## 테스트 원칙

- 동작에 가장 가까운 낮은 비용의 테스트를 우선합니다.
- 외부 계약은 계약 테스트로 검증합니다.
- 오류, 경계값, 권한, 중복 요청 같은 실패 경로를 포함합니다.
- 불안정한 테스트를 무시하지 않고 원인과 소유자를 기록합니다.

이 저장소에서는 **외부 시스템 없이 실행 가능한 테스트**를 기본으로 합니다. `tests/conftest.py`가 SQLite와 인메모리 구현을 주입하므로 Kafka·Redis·PostgreSQL 없이 전체 처리 흐름을 검증할 수 있습니다. 포트와 어댑터를 분리한 이유가 여기에 있습니다.

## 테스트 종류와 명령

| 종류 | 목적 | 실행 명령 |
|---|---|---|
| 전체 | 기본 검증 | `uv run --extra dev pytest -q` |
| 처리 흐름 | 접수부터 완료까지 | `pytest -q tests/test_api_worker_integration.py` |
| C 경로 | 추론·후단 분리 경로 | `pytest -q tests/test_c_architecture_flow.py` |
| 재시도 | 헤더·백오프·재시도 복구 | `pytest -q tests/test_retry_runtime.py` |
| 멱등성 | 잠금 경합과 복구 | `pytest -q tests/test_lock_recovery_flow.py` |
| 계약 | 이벤트 Envelope 구조 | `pytest -q tests/test_event_envelope.py` |
| 역할 조립 | 모드·역할별 서비스 선택 | `pytest -q tests/test_worker_roles.py` |
| 토픽 구성 | 파티션 목표 계산 | `pytest -q tests/test_kafka_topics.py tests/test_container_topics.py` |
| 처리기 | 동시성과 배치 동작 | `pytest -q tests/test_gpu_simulator.py` |
| 상태 확인 | 의존성 점검 응답 | `pytest -q tests/test_health_readiness.py` |
| 스키마 | 모델·마이그레이션 일치 | `alembic check` |
| 매니페스트 | 렌더 가능 여부 | `kubectl kustomize deploy/k8s/base` |

## 부하 테스트

k6로 실행하며 컨테이너 스택이 기동된 상태를 전제로 합니다.

```bash
docker run --rm -v "$PWD:/work" -w /work grafana/k6 run tests/perf/jobs_load_test.js \
  -e BASE_URL=http://host.docker.internal:8000 \
  -e VUS=50 -e DURATION=1m \
  --summary-export reports/perf/k6_vus50.json
```

k6 결과만으로 판단하지 않습니다. **HTTP 지표가 모두 정상이어도 적체가 쌓이고 있을 수 있습니다.** 부하 시험 중에는 아래를 함께 확인합니다.

```promql
max(kafka_consumergroup_lag)
sum(rate(jobs_created_total[5m]))
sum(rate(jobs_success_total[5m]))        # A·B 모드
sum(rate(downstream_success_total[5m]))  # C·BC 모드
```

측정 기준과 과거 결과는 [품질](../architecture/quality.md)에 있습니다.

## CI에서 실행하는 검증

`.github/workflows/ci.yml`이 네 개 작업으로 분리되어 있습니다.

| 작업 | 내용 |
|---|---|
| `unit-tests` | `pytest -q` |
| `static-checks` | `compileall` 구문 검사, `pip check` 의존성 무결성 |
| `migration-check` | PostgreSQL 기동 후 `alembic upgrade head` + `alembic check` |
| `k8s-manifest-validate` | `deploy/k8s`의 모든 kustomization 렌더 |

## 완료 기준

변경 요청에는 실행한 검증, 결과, 실행하지 못한 항목과 이유를 기록합니다. 특히 다음 변경에는 대응 검증을 포함합니다.

| 변경 | 함께 실행할 검증 |
|---|---|
| 처리 흐름·상태 전이 | 처리 흐름 테스트와 재시도 테스트 |
| 멱등성 관련 | 멱등성 테스트 |
| 이벤트 Envelope | 계약 테스트와 [이벤트 명세](../specs/events/README.md) 갱신 |
| ORM 모델 | `alembic check`와 마이그레이션 추가 |
| 매니페스트 | `kubectl kustomize` 렌더 |
| 성능에 영향을 주는 변경 | k6 재측정과 [품질](../architecture/quality.md) 갱신 |

## 관련 문서

- [개발 환경 안내](development.md)
- [품질](../architecture/quality.md)
- [기술 명세](../specs/README.md)
