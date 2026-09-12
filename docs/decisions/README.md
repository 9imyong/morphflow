# 아키텍처 결정 기록 안내

ADR은 중요한 기술 결정 하나와 당시의 맥락, 검토한 대안, 결과를 보존합니다.

## 파일 이름

`ADR-0001-짧은-제목.md` 형식을 사용하고 번호는 다시 사용하지 않습니다.

## 상태

- 제안됨: 검토 전
- 승인됨: 적용하기로 결정
- 거절됨: 적용하지 않기로 결정
- 대체됨: 더 새로운 ADR이 대신함
- 폐기됨: 더 이상 관련 없음

승인된 ADR의 결론을 소급해 고치지 않습니다. 결정이 바뀌면 새 ADR을 만들고 서로 연결합니다.

새 기록은 [ADR 템플릿](ADR_TEMPLATE.md)을 사용합니다.

## 작성 기준과 연결

ADR은 장기간 영향을 주거나 되돌리기 어렵고 선택 이유를 보존해야 하는 결정에 작성합니다. 일상적인 구현 세부 사항에는 작성하지 않습니다. RFC 검토에서 중요한 결정이 나오면 해당 RFC를 링크하고, 결정 결과를 관련 Architecture와 Spec에 반영합니다.

대안 논의가 이미 끝났다면 RFC 없이 ADR을 작성할 수 있습니다. 전체 흐름과 생략 기준은 [문서 운영 정책](../DOCS_GOVERNANCE.md)을 따릅니다.

## 현재 결정 목록

| ID | 제목 | 상태 | 날짜 |
|---|---|---|---|
| [ADR-0001](ADR-0001-transitional-architecture-modes.md) | 병목 위치에 따라 전환하는 단일 서비스 구조 채택 | 승인됨 | 2026-03-10 |
| [ADR-0002](ADR-0002-idempotency-strategy.md) | Redis 예약과 데이터베이스 상태 확인을 결합한 멱등성 보장 | 승인됨 | 2026-03-10 |
| [ADR-0003](ADR-0003-retry-and-dlq.md) | 헤더 기반 재시도와 DLQ 격리 | 승인됨 | 2026-03-10 |
| [ADR-0004](ADR-0004-fixed-ingress-topic-and-group.md) | 아키텍처 모드 전환 시 진입 토픽과 컨슈머 그룹 고정 | 승인됨 | 2026-03-11 |
| [ADR-0005](ADR-0005-kind-based-local-kubernetes.md) | Compose에서 kind 기반 Kubernetes로 실행 환경 전환 | 승인됨 | 2026-03-17 |
| [ADR-0006](ADR-0006-gpu-inference-simulator.md) | 실제 GPU 대신 추론 시뮬레이터 사용 | 승인됨 | 2026-03-10 |
| [ADR-0007](ADR-0007-kafka-kraft-single-broker.md) | Kafka KRaft 모드 단일 브로커와 토픽 자동 구성 | 승인됨 | 2026-03-10 |
