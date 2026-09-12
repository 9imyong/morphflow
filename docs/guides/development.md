# 개발 환경 안내

## 지원 환경

| 항목 | 버전 |
|---|---|
| Python | 3.12 이상 |
| 패키지 관리 | uv (권장) 또는 pip |
| 컨테이너 | Docker, Docker Compose v2 |
| Kubernetes (선택) | kind, kubectl |

## 초기 설정

```bash
# 의존성 설치 (개발 도구 포함)
uv sync --extra dev

# uv 없이 사용할 경우
python -m pip install ".[dev]"
```

## 로컬 실행

전체 스택을 컨테이너로 기동하는 방식이 기본입니다. Kafka·PostgreSQL·Redis가 모두 필요하기 때문입니다.

```bash
docker compose -f docker-compose.dev.yml --env-file env/.env.dev up -d --build
```

기동 확인:

```bash
curl -s http://localhost:8000/health/ready | jq
```

작업 한 건을 넣어 전체 경로를 확인합니다.

```bash
JOB=$(curl -sS -X POST http://localhost:8000/jobs \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: dev-001' \
  -d '{"input": {"type": "text", "content": "hello"}}' | jq -r .job_id)

curl -sS http://localhost:8000/jobs/$JOB | jq
```

`status`가 `PENDING` → `PROCESSING` → `SUCCESS`로 바뀌면 정상입니다.

모드별 실행과 Kubernetes 배포는 [운영 배포 문서](../operations/deployment.md)를 따릅니다.

## 마이그레이션

```bash
alembic upgrade head     # 적용
alembic downgrade -1     # 되돌리기
alembic check            # 모델과 마이그레이션 드리프트 확인
```

ORM 모델만 바꾸고 마이그레이션을 만들지 않으면 CI가 실패합니다.

## 환경 변수

전체 정의는 `app/core/config.py`의 `Settings`에 있습니다. 자주 바꾸는 항목만 정리합니다.

| 이름 | 필수 | 용도 | 기본값 |
|---|---|---|---|
| `DATABASE_URL` | 아니요 | PostgreSQL 접속 문자열 | `postgresql+asyncpg://app:app@localhost:5432/fault_monitoring` |
| `REDIS_URL` | 아니요 | Redis 접속 문자열 | `redis://localhost:6379/0` |
| `KAFKA_BOOTSTRAP_SERVERS` | 아니요 | Kafka 접속 주소 | `localhost:9092` |
| `ARCHITECTURE_MODE` | 아니요 | 아키텍처 모드 (`A`·`B`·`C`·`BC`) | `A` |
| `WORKER_ROLE` | 아니요 | 워커 역할 (`unified`·`inference`·`downstream`) | `unified` |
| `WORKER_PROCESSOR_BACKEND` | 아니요 | 처리기 (`simulator`·`dummy`) | `simulator` |
| `INFERENCE_MAX_CONCURRENCY` | 아니요 | 추론 동시 실행 수 | `2` |
| `INFERENCE_SIMULATED_LATENCY_MS` | 아니요 | 시뮬레이션 처리 지연 | `700` |
| `INFERENCE_SIMULATED_FAILURE_RATE` | 아니요 | 시뮬레이션 실패 확률 | `0.0` |
| `RETRY_MAX_COUNT` | 아니요 | DLQ 이전 최대 재시도 횟수 | `3` |
| `IDEMPOTENCY_TTL_SECONDS` | 아니요 | 완료 멱등성 키 유지 시간 | `3600` |
| `WORKER_PROCESSING_TTL_SECONDS` | 아니요 | 처리 잠금 유지 시간 | `1800` |
| `TRACING_ENABLED` | 아니요 | OpenTelemetry 추적 사용 여부 | `true` |
| `KAFKA_PARTITIONS_WORKER_TOPIC` | 아니요 | 진입 토픽 파티션 수 | `1` (dev 환경은 `8`) |

`env/.env.dev`와 `env/.env.prod`의 값은 **로컬 검증 전용**입니다. 실제 자격증명을 이 파일에 넣지 않습니다.

## 동작을 바꾸는 조합

| 하고 싶은 것 | 설정 |
|---|---|
| 추론을 느리게 만들어 병목 재현 | `INFERENCE_SIMULATED_LATENCY_MS=900`, `INFERENCE_MAX_CONCURRENCY=2` |
| 실패와 재시도 경로 확인 | `INFERENCE_SIMULATED_FAILURE_RATE=0.3` |
| 단일 요청만 느리게 | 요청 본문 `options.simulate_inference_ms` |
| 배치 없이 동작 확인 | `INFERENCE_BATCH_ENABLED=false` |

## 자주 발생하는 문제

| 증상 | 원인 | 해결 방법 |
|---|---|---|
| `/health/ready`가 503 | 의존성 중 하나가 아직 기동 전 | 응답 본문의 `dependencies`에서 실패 항목 확인 후 해당 컨테이너 로그 점검 |
| 작업이 계속 `PENDING` | 워커가 소비하지 못함 | `docker compose logs worker`로 소비 여부 확인. Kafka 연결 실패가 흔한 원인 |
| 워커를 늘려도 처리량이 그대로 | 파티션 수가 상한 | `KAFKA_PARTITIONS_WORKER_TOPIC` 확인. 파티션 수를 넘는 워커는 유휴 상태 |
| 같은 요청이 계속 새 작업 생성 | `Idempotency-Key` 헤더 누락 | 헤더를 보내거나 TTL(`IDEMPOTENCY_TTL_SECONDS`) 경과 여부 확인 |
| CI의 `migration-check` 실패 | 모델과 마이그레이션 불일치 | `alembic revision --autogenerate`로 마이그레이션 생성 후 검토 |

## 관련 문서

- [테스트 안내](testing.md)
- [운영 배포 문서](../operations/deployment.md)
- [구성 요소](../architecture/building-blocks.md)
