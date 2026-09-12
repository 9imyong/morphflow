# 기술 명세 안내

기술 명세는 구현이 반드시 따라야 하는 구체적이고 검증 가능한 계약을 정의합니다. 시스템 구성의 이유와 관계는 [아키텍처 문서](../architecture/README.md)에 기록하고, 이 디렉터리에는 필드·스키마·오류·호환성처럼 구현 간 합의가 필요한 내용을 둡니다.

## 하위 영역

- `api/`: HTTP API 계약과 설명
- `events/`: 비동기 메시지 및 이벤트 계약
- `database/`: 데이터의 업무 의미, 불변 조건, 마이그레이션 정책

## 언제 작성하는가

- 외부 사용자나 다른 구성 요소가 의존하는 계약을 만들거나 변경할 때
- 데이터 형식, 오류 모델, 호환성 또는 보존 정책을 명확히 해야 할 때
- 자동화된 계약 검증의 기준이 필요할 때

구현 내부에만 영향을 주고 외부 계약이 바뀌지 않는 작은 수정에는 별도 명세를 만들지 않아도 됩니다. 작성 여부의 최종 기준은 [문서 운영 정책](../DOCS_GOVERNANCE.md)을 따릅니다.

## 기준 정보

OpenAPI, AsyncAPI, JSON Schema, 마이그레이션처럼 기계가 검증할 수 있는 산출물이 있으면 그것을 계약의 기준으로 사용합니다. Markdown은 배경과 의미를 설명하며 동일한 구조를 다시 복사하지 않습니다.

## 현재 명세

| 영역 | 계약 기준 | 설명 문서 |
|---|---|---|
| HTTP API | [`api/openapi.yaml`](api/openapi.yaml) | [작업 접수와 조회](api/jobs.md) |
| 이벤트 | [`events/asyncapi.yaml`](events/asyncapi.yaml), [`events/schemas/job-event-envelope.json`](events/schemas/job-event-envelope.json) | [작업 이벤트](events/job-events.md) |
| 데이터 | `alembic/versions/` 마이그레이션 | [데이터 구조 개요](database/schema.md), [데이터 사전](database/data-dictionary.md) |
