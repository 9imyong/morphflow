# 작업 진행도/작업 단위 기록 문서

## 1. 목적
이 문서는 작업 상태를 빠르게 이해할 수 있도록, 다음 두 가지를 표준 형식으로 기록한다.

1. 작업 진행도(%)와 상태
2. 작업 단위(Work Unit)별 상세 내역

---

## 2. 상태 기준

- `TODO`: 아직 시작하지 않음
- `IN_PROGRESS`: 진행 중
- `BLOCKED`: 외부 이슈로 중단
- `DONE`: 완료

---

## 3. 진행도(%) 기준

- `0%`: 착수 전
- `10~30%`: 요구사항/코드 구조 파악
- `40~70%`: 구현/수정 진행
- `80~90%`: 테스트/검증 진행
- `100%`: 반영 완료 + 검증 완료

진행도는 대략치가 아니라, 실제 완료된 작업 단위 수를 기준으로 업데이트한다.

---

## 4. 작업 단위 정의

작업 단위는 아래 조건을 만족하면 1개로 본다.

- 독립적으로 완료/검증 가능
- 산출물(코드, 문서, 설정) 위치가 명확
- 완료 기준(DoD)이 한 줄로 정의 가능

권장 크기:
- 30분~2시간 내 완료 가능한 크기

---

## 5. 기록 템플릿

아래 형식으로 항목을 추가한다.

```md
### [Task-YYYYMMDD-번호] 작업 제목
- 상태: TODO | IN_PROGRESS | BLOCKED | DONE
- 진행도: 0~100%
- 담당: Codex / 사용자명
- 시작일: YYYY-MM-DD
- 최근 업데이트: YYYY-MM-DD
- 목표(DoD): 한 줄 완료 기준
- 작업 단위:
  - [ ] WU-1: 작업 단위 설명
  - [ ] WU-2: 작업 단위 설명
  - [ ] WU-3: 작업 단위 설명
- 메모/이슈:
  - 이슈 또는 결정사항
```

---

## 6. 현재 작업 기록

### [Task-20260310-01] 작업 진행도/작업 단위 문서화
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): 팀이 공통 포맷으로 진행도와 작업 단위를 이해/추적할 수 있는 문서를 `docs`에 추가한다.
- 작업 단위:
  - [x] WU-1: 기존 `docs` 문서 구조 확인
  - [x] WU-2: 진행도 기준/상태 정의 정리
  - [x] WU-3: 재사용 가능한 기록 템플릿 작성
  - [x] WU-4: 현재 요청 작업을 예시로 첫 기록 추가
- 메모/이슈:
  - 이후 작업부터 본 문서에 동일 포맷으로 누적 기록

### [Task-20260310-02] Kafka KRaft 전환(ZooKeeper 제거, 4.0.0)
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): 개발용 Compose에서 ZooKeeper 의존성을 제거하고 Kafka 이미지를 `apache/kafka:4.0.0`으로 고정한다.
- 작업 단위:
  - [x] WU-1: 기존 Kafka/ZooKeeper compose 설정 확인
  - [x] WU-2: ZooKeeper 서비스 제거 및 Kafka KRaft 환경 변수 적용
  - [x] WU-3: Kafka 이미지 버전 `apache/kafka:4.0.0` 고정
  - [x] WU-4: 변경 사항 문서 로그 반영
- 메모/이슈:
  - 단일 브로커 KRaft 구성으로 로컬 개발 환경 기준

### [Task-20260310-03] 운영용 Compose 기본 구성 추가
- 상태: DONE
- 진행도: 100%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: 2026-03-10
- 목표(DoD): `docker-compose.prod.yml`을 실행 가능한 기본 운영 스택으로 구성한다.
- 작업 단위:
  - [x] WU-1: `env/.env.prod`와 dev compose 기준으로 서비스 요구사항 정리
  - [x] WU-2: `api/worker/postgres/redis/kafka/prometheus` 서비스 정의
  - [x] WU-3: Kafka를 ZooKeeper 없는 `apache/kafka:4.0.0` KRaft로 구성
  - [x] WU-4: `docker compose config`로 유효성 검증
- 메모/이슈:
  - 현재는 단일 노드 운영 기본안이며, HA/replication은 후속 작업 범위

### [Task-20260310-04] A 아키텍처 E2E 실행 검증
- 상태: TODO
- 진행도: 0%
- 담당: Codex
- 시작일: 2026-03-10
- 최근 업데이트: -
- 목표(DoD): docker compose 환경에서 API → Kafka → Worker → DB 파이프라인이 정상 동작하는지 검증한다.
- 작업 단위:
  - [ ] WU-1: docker compose 전체 서비스 기동(api/worker/postgres/redis/kafka)
  - [ ] WU-2: POST /jobs 요청 테스트
  - [ ] WU-3: Kafka request-topic 메시지 발행 확인
  - [ ] WU-4: Worker consume 및 처리 확인
  - [ ] WU-5: Job 상태(PENDING → PROCESSING → SUCCESS) DB 반영 확인
  - [ ] WU-6: GET /jobs/{job_id} 결과 조회 확인
  - [ ] WU-7: Idempotency-Key 중복 요청 테스트
- 메모/이슈:
  - Worker 재시작 시 중복 처리 방지 확인
  - Kafka partition/consumer group 정상 동작 확인
