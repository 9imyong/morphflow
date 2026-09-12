---
status: 현재
owners: [김용준]
last_reviewed: 2026-09-13
---

# 구성 요소

## 문서 목적

시스템을 이루는 주요 실행 단위와 선택적으로 그 내부 구성 요소의 책임, 경계, 의존 방향을 설명합니다.

## 언제 수정하는가

- 실행 또는 배포 단위를 추가·분리·통합할 때
- 구성 요소의 책임이나 소유 데이터가 달라질 때
- 허용되는 의존 방향이나 내부 경계가 바뀔 때

## 실행 단위

| 구성 요소 | 책임 | 소유 데이터 | 의존 대상 |
|---|---|---|---|
| `api` | 요청 검증, Job 생성, 상태 조회, 상태 확인 엔드포인트 노출 | 없음 | PostgreSQL, Redis, Kafka |
| `worker` | 진입 토픽 소비, 추론 수행, 재시도·DLQ 판정 | 없음 | PostgreSQL, Redis, Kafka |
| `downstream-worker` | 후단 처리 수행과 Job 최종 완료 (C·BC 모드 전용) | 없음 | PostgreSQL, Kafka |
| `migrate` | Alembic 마이그레이션 적용 | 스키마 | PostgreSQL |
| PostgreSQL | 작업 상태와 이벤트 이력의 기준 저장소 | `jobs`, `job_events` | 없음 |
| Redis | 멱등성 예약과 처리 잠금 | `idem:req:*`, `idem:job:*` | 없음 |
| Kafka | 단계 간 이벤트 전달과 완충 | 토픽별 로그 | 없음 |

`worker`와 `downstream-worker`는 **같은 이미지와 같은 진입점**(`python -m app.workers.runner`)이며 `WORKER_ROLE`로만 구분됩니다.

정식 시각화는 [C4 Container](diagrams/c4/container.md)에, 애플리케이션 내부 구조는 [C4 Component](diagrams/c4/component.md)에 있습니다.

## 애플리케이션 내부 구조

| 계층 | 위치 | 책임 |
|---|---|---|
| `api` | `app/api/` | HTTP 라우팅, 요청·응답 스키마 변환 |
| `workers` | `app/workers/` | Kafka 소비 루프, 역할 조립, 재시도·DLQ 판정 |
| `application` | `app/application/` | 업무 흐름 조립. `JobService`, `WorkerService`, `InferencePipelineService`, `DownstreamPipelineService` |
| `domain` | `app/domain/` | `Job`, `JobStatus`, 이벤트 Envelope 생성 |
| `ports` | `app/ports/` | 저장소, 발행자, 멱등성, 처리기, 워커 역할 인터페이스 |
| `adapters` | `app/adapters/` | PostgreSQL, Redis, Kafka, 처리기 구현 |
| `core` | `app/core/` | 설정, 컨테이너, 수명 주기, 지표, 추적, 토픽 준비 |

## 역할별 서비스 조립

`build_worker_role()`이 `WORKER_ROLE`과 `ARCHITECTURE_MODE`를 함께 보고 서비스를 선택합니다.

| WORKER_ROLE | ARCHITECTURE_MODE | 사용하는 서비스 | 소비 토픽 | 컨슈머 그룹 |
|---|---|---|---|---|
| `unified` | 전체 | `WorkerService` | `request-topic`, `retry-topic` | `architecture-main-worker` |
| `inference` | A, B | `WorkerService` | `request-topic`, `retry-topic` | `architecture-main-worker` |
| `inference` | C, BC | `InferencePipelineService` | `request-topic`, `retry-topic` | `architecture-main-worker` |
| `downstream` | C, BC | `DownstreamPipelineService` | `downstream-topic`, `retry-downstream-topic` | `architecture-main-worker-downstream` |

## 의존성 규칙

- `domain`은 다른 어떤 계층도 참조하지 않습니다.
- `application`은 `ports`의 인터페이스에만 의존하고 `adapters`를 직접 참조하지 않습니다.
- `adapters`는 `ports`를 구현하며, 조립은 `core/container.py`와 `workers/roles.py`에서만 수행합니다.
- `api`와 `workers`는 진입점이며 업무 규칙을 직접 구현하지 않습니다.

구성 요소 사이의 계약은 [기술 명세](../specs/README.md)를 기준으로 합니다.

## 관련 문서

- [해결 전략](solution-strategy.md)
- [C4 Container](diagrams/c4/container.md)
- [C4 Component](diagrams/c4/component.md)
- [실행 흐름](runtime.md)
- [배포 구조](deployment.md)
