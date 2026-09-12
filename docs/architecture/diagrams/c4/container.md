# C4 Container Diagram

## 문서 목적

시스템 내부의 주요 실행·배포 단위와 데이터 저장소, 외부 관계를 보여줍니다. 각 단위의 책임은 [구성 요소](../../building-blocks.md)에 기록합니다.

## 언제 수정하는가

Container를 추가·분리·통합하거나 주요 통신 관계 또는 기술 경계가 바뀔 때 수정합니다.

## 다이어그램

```mermaid
flowchart TB
    client["API 클라이언트"]

    subgraph sys["Morphflow"]
        api["Container: api<br/>FastAPI · uvicorn"]
        worker["Container: worker<br/>Python · aiokafka<br/>역할: unified 또는 inference"]
        dworker["Container: downstream-worker<br/>Python · aiokafka<br/>C·BC 모드에서만 실행"]
        migrate["Container: migrate<br/>Alembic Job"]
        kafka[("Container: Kafka<br/>KRaft")]
        db[("Container: PostgreSQL")]
        redis[("Container: Redis")]
    end

    client -->|"HTTP"| api
    api -->|"Job 생성과 조회"| db
    api -->|"요청 멱등성 예약"| redis
    api -->|"request-topic 발행"| kafka
    kafka -->|"request-topic · retry-topic 소비"| worker
    worker -->|"상태 전이와 이벤트 기록"| db
    worker -->|"처리 잠금"| redis
    worker -->|"downstream-topic 발행 (C·BC)"| kafka
    worker -->|"retry-topic · dlq-topic 발행"| kafka
    kafka -->|"downstream-topic 소비 (C·BC)"| dworker
    dworker -->|"최종 완료 기록"| db
    migrate -->|"스키마 적용"| db
```

## 구성 요소 요약

| Container | 기술 | 책임 |
|---|---|---|
| `api` | FastAPI, uvicorn | 요청 검증, Job 생성, 상태 조회, 상태 확인 |
| `worker` | Python, aiokafka | 진입 토픽 소비, 추론, 재시도·DLQ 판정 |
| `downstream-worker` | Python, aiokafka | 후단 처리와 최종 완료 |
| `migrate` | Alembic | 스키마 적용 |
| Kafka | KRaft 단일 노드 | 단계 간 이벤트 전달과 완충 |
| PostgreSQL | 16 | 기준 상태 저장 |
| Redis | 7 | 멱등성 예약과 처리 잠금 |

`worker`와 `downstream-worker`는 같은 이미지이며 `WORKER_ROLE`로 구분됩니다.

## 관련 문서

- [구성 요소](../../building-blocks.md)
- [배포 구조](../../deployment.md)
- [C4 안내](README.md)
