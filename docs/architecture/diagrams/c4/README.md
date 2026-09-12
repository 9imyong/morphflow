# C4 다이어그램 안내

## 문서 목적

C4 Model을 사용해 Architecture 문서의 현재 구조를 서로 다른 추상화 수준으로 시각화합니다. C4는 별도의 Architecture 체계가 아니며 본문 설명을 복제하지 않습니다.

## 언제 수정하는가

- 시스템 경계, 외부 관계, Container 또는 주요 Component가 바뀔 때
- Architecture 본문과 다이어그램이 일치하지 않을 때

## 작성할 내용

- [System Context](context.md): 시스템, 사용자, 외부 시스템
- [Container](container.md): 실행·배포 단위와 주요 관계
- [Component](component.md): 복잡한 Container 내부의 주요 구성 요소

Code Level 다이어그램은 기본 템플릿에 포함하지 않습니다. Component도 구조 설명의 가치가 있을 때만 작성합니다.

## 중복 방지 원칙

- 요소의 책임과 정책은 Architecture 본문에 기록합니다.
- C4 문서에는 다이어그램, 범례, 표시 범위와 본문 링크만 둡니다.
- API 필드와 스키마는 [기술 명세](../../../specs/README.md)를 참조합니다.

## 최소 예제

`context.md`의 범용 Mermaid 예제를 프로젝트 요소로 교체하고, 대응하는 Architecture 본문을 링크합니다.

## 관련 문서

- [아키텍처 안내](../../README.md)
- [시스템 맥락](../../context.md)
- [구성 요소](../../building-blocks.md)
