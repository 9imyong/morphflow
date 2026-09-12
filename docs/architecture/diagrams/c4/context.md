# C4 System Context

## 문서 목적

시스템과 사용자, 외부 시스템의 관계를 한눈에 보여줍니다. 관계의 상세 의미는 [시스템 맥락](../../context.md)에 기록합니다.

## 언제 수정하는가

시스템 경계, 주요 사용자 또는 외부 시스템 관계가 바뀔 때 수정합니다.

## 다이어그램

```mermaid
flowchart TB
    client["사람·시스템: API 클라이언트<br/>추론 작업을 요청하고 결과를 조회"]
    operator["사람: 운영자<br/>상태를 관측하고 장애에 대응"]

    subgraph sys["Morphflow 추론 처리 플랫폼"]
        core["작업 접수 · 비동기 처리 · 상태 관리"]
    end

    obs["시스템: 관측 스택<br/>Prometheus · Grafana · Jaeger · EFK"]

    client -->|"작업 생성과 상태 조회 (HTTP)"| core
    core -->|"job_id와 처리 결과"| client
    core -->|"지표 · 로그 · 추적"| obs
    operator -->|"대시보드와 경보 확인"| obs
    operator -->|"배포와 복구 조치"| sys
```

## 범례

| 표기 | 의미 |
|---|---|
| 사각형 | 사람 또는 외부 시스템 |
| 굵은 경계 영역 | 이 문서가 설명하는 시스템의 경계 |
| 화살표 | 통신 방향과 목적 |

PostgreSQL, Redis, Kafka는 시스템 경계 **안쪽**의 구성 요소이므로 이 수준에서는 표현하지 않습니다. [C4 Container](container.md)를 참조합니다.

## 관련 문서

- [시스템 맥락](../../context.md)
- [C4 Container](container.md)
- [C4 안내](README.md)
