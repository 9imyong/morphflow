---
status: 현재
owners: [김용준]
last_reviewed: 2026-09-13
---

# 제약 사항

## 문서 목적

설계와 구현이 반드시 따라야 하는 기술적·조직적·보안·규제 제약을 기록합니다. 선택의 이유와 대안은 ADR에 둡니다.

## 언제 수정하는가

- 지원 플랫폼, 표준 기술 또는 조직 정책이 바뀔 때
- 보안·법률·규제 요구가 추가되거나 폐기될 때
- 일정, 예산, 운영 환경이 아키텍처 선택을 제한하게 될 때

## 기술 제약

| 제약 | 내용 | 근거 |
|---|---|---|
| 런타임 | Python 3.12 이상 | `pyproject.toml`의 `requires-python` |
| 의존성 고정 | 모든 런타임 의존성을 정확한 버전으로 고정 | 재현 가능한 빌드. CI가 `pip check`로 무결성 검증 |
| 비동기 일관성 | API·워커·저장소 접근 전 구간 async | FastAPI + aiokafka + asyncpg 조합 |
| 단일 브로커 | Kafka는 KRaft 단일 노드, replication factor 1 | 로컬 검증 환경. 운영 전환 시 재검토 필요 |
| GPU 미사용 | 실제 GPU 없이 추론 특성만 시뮬레이션 | [ADR-0006](../decisions/ADR-0006-gpu-inference-simulator.md) |
| 실행 환경 | Docker Compose와 kind 기반 단일 노드 | 다중 노드 스케줄링·스토리지 가정을 두지 않음 |

## 구조 제약

- A/B/C/BC 모드는 **별도 서비스로 분기하지 않습니다.** 같은 코드베이스와 같은 이미지가 설정만으로 역할을 바꿉니다.
- 아래 요소는 모드 전환과 무관하게 유지합니다. 이를 깨는 변경은 ADR이 필요합니다.
  - HTTP API 계약
  - Job 상태 모델
  - 이벤트 Envelope 형식
  - Redis 멱등성 키 전략
  - 데이터베이스 스키마
  - 지표 이름과 라벨
- 진입 토픽(`request-topic`)과 컨슈머 그룹 ID는 모드 전환 시에도 고정합니다. 근거는 [ADR-0004](../decisions/ADR-0004-fixed-ingress-topic-and-group.md)에 있습니다.

## 운영 제약

- 데이터베이스 스키마 변경은 Alembic 마이그레이션으로만 수행하며, CI의 `alembic check`가 모델과 마이그레이션의 드리프트를 차단합니다.
- 모든 Kubernetes 매니페스트는 CI에서 `kubectl kustomize` 렌더에 성공해야 합니다.
- 비밀 값은 문서에 기록하지 않습니다. 현재 저장소의 `env/`와 `deploy/k8s/base/secret-app.yaml`에 있는 값은 **로컬 검증 전용**이며 운영 자격증명이 아닙니다.

## 알려진 한계

현재 수용 중인 제약은 [위험과 기술 부채](risks-technical-debt.md)에서 추적합니다.

## 관련 문서

- [해결 전략](solution-strategy.md)
- [위험과 기술 부채](risks-technical-debt.md)
- [ADR](../decisions/README.md)
