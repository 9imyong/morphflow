# 아키텍처 안내

이 디렉터리는 시스템의 **현재 구조와 주요 설계**를 설명하는 기준 문서입니다. arc42의 주요 관점을 참고하지만 12개 장을 기계적으로 복제하지 않으며, 프로젝트 규모에 필요한 문서만 사용합니다. 결정의 역사와 근거는 [ADR](../decisions/README.md), 구현이 따라야 하는 정확한 계약은 [기술 명세](../specs/README.md)에 기록합니다.

## 문서 목적

Architecture 문서의 책임, 탐색 순서와 프로젝트 규모별 적용 방법을 안내합니다.

## 언제 수정하는가

- Architecture 문서를 추가·통합하거나 책임을 변경할 때
- C4 사용 범위 또는 프로젝트의 문서 적용 수준을 바꿀 때

## 작성할 내용

현재 사용하는 Architecture 문서와 소유 방식, C4 연결, 갱신 원칙을 유지합니다. 개별 시스템 설계 내용은 해당 관점 문서에 작성합니다.

## 최소 예제

소규모 서비스라면 `ARCHITECTURE_TEMPLATE.md` 하나와 C4 Context/Container만 사용하고, 복잡도가 증가할 때 필요한 개별 관점 문서를 활성화합니다.

## 문서 구성

- `context.md`: 시스템 경계, 사용자, 외부 시스템
- `constraints.md`: 기술·조직·보안·규제 제약
- `solution-strategy.md`: 품질 목표와 제약을 해결하는 상위 전략
- `building-blocks.md`: 주요 구성 요소와 책임
- `runtime.md`: 중요한 실행 흐름
- `deployment.md`: 실행 환경과 배포 단위
- `data.md`: 데이터 소유권, 흐름, 불변 조건
- `crosscutting-concepts.md`: 인증, 오류, 관측성 등 공통 설계
- `quality.md`: 품질 목표와 측정 가능한 시나리오
- `risks-technical-debt.md`: 현재 위험과 기술 부채
- `diagrams/c4/`: Context, Container, 선택적 Component 시각화

작은 프로젝트는 위 내용을 [통합 아키텍처 템플릿](ARCHITECTURE_TEMPLATE.md) 하나로 관리해도 됩니다.

## C4 Model

C4는 별도의 아키텍처 체계가 아니라 현재 구조를 시각화하는 방법입니다. 설명은 Architecture 본문에 한 번만 작성하고 C4 문서에는 요소, 관계, 범례와 다이어그램을 둡니다.

- [System Context](diagrams/c4/context.md)는 [시스템 맥락](context.md)을 시각화합니다.
- [Container](diagrams/c4/container.md)는 [구성 요소](building-blocks.md)의 실행 단위를 시각화합니다.
- [Component](diagrams/c4/component.md)는 복잡한 Container에만 선택적으로 사용합니다.
- Code Level은 기본 템플릿에 포함하지 않습니다.

## 적용과 갱신 원칙

- 코드나 배포 상태가 달라져 현재 구조 설명이 바뀌면 같은 변경에서 관련 문서를 갱신합니다.
- 해당하지 않는 관점은 내용을 억지로 만들지 않고 `해당 없음`과 사유를 기록합니다.
- 결정의 이유를 Architecture에 복제하지 않고 관련 ADR을 링크합니다.
- 실제 배포 명령과 장애 대응 절차는 [운영 문서](../operations/README.md)에 둡니다.

`ARCHITECTURE_TEMPLATE.md`는 새 프로젝트가 복사해 사용하는 통합 템플릿이고, 나머지 관점 문서는 현재 시스템 상태를 계속 갱신하는 실제 문서입니다. 통합 템플릿과 개별 문서를 동시에 사용할 때 같은 설명을 복사하지 않고 기준 문서를 링크합니다.

## 관련 문서

- [문서 운영 정책](../DOCS_GOVERNANCE.md)
- [요구사항](../requirements/README.md)
- [ADR](../decisions/README.md)
- [기술 명세](../specs/README.md)
- [C4 안내](diagrams/c4/README.md)
