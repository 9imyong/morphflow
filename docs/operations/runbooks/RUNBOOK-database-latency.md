---
id: RUNBOOK-storage-001
title: 데이터베이스 지연 증가
owners: [김용준]
last_validated: 2026-03-18
severity: 높음
---

# 런북: 데이터베이스 지연 증가

## 발동 조건과 영향

- 경보: `PostgresResponseSlow`, `PostgresExporterDown`
- 증상: 접수 응답 지연, 워커 처리 시간 증가, `/health/ready`의 `database` 항목 실패

PostgreSQL은 **유일한 기준 저장소**입니다. 지연이 커지면 접수와 처리 양쪽이 함께 느려집니다.

## 사전 조건과 안전 수칙

- 필요한 접근: PostgreSQL 조회 권한, Prometheus
- 실행하면 안 되는 조건: 장애 중 스키마 변경이나 대량 삭제를 수행하지 않습니다.
- 데이터 손실 가능성: 세션을 강제 종료하면 진행 중이던 트랜잭션이 롤백됩니다. 작업 상태는 재시도로 복구되지만 종료 대상은 확인 후 선택합니다.

## 진단

1. 준비 상태를 확인합니다.

   ```bash
   curl -s http://localhost:18000/health/ready | jq '.dependencies.database'
   ```

2. 느린 쿼리와 락 대기를 확인합니다.

   ```sql
   SELECT pid, state, wait_event_type, wait_event, now() - query_start AS duration, query
   FROM pg_stat_activity
   WHERE state <> 'idle'
   ORDER BY duration DESC
   LIMIT 20;
   ```

3. 자원과 연결 수를 확인합니다.

   ```bash
   kubectl top pod -l app=postgres -n morphflow --context kind-local-dev
   ```

   ```sql
   SELECT count(*) FROM pg_stat_activity;
   ```

4. 워커 확장이 원인인지 확인합니다. **워커를 늘린 직후 지연이 시작되었다면 커넥션 경합일 수 있습니다.** 각 워커와 API가 독립적인 커넥션 풀을 가지므로 확장은 곧 커넥션 증가입니다.

## 완화와 복구

1. 대량 배치성 작업이나 관리 쿼리가 돌고 있으면 중지합니다.

2. 오래 걸리는 세션을 확인 후 선택적으로 종료합니다.

   ```sql
   SELECT pg_cancel_backend(<pid>);   -- 먼저 취소를 시도
   SELECT pg_terminate_backend(<pid>); -- 취소로 해결되지 않을 때만
   ```

3. 커넥션 경합이면 워커 수를 줄여 부하를 낮춥니다. 적체는 늘지만 데이터베이스가 회복되면 해소됩니다.

4. 회복 후 `PROCESSING` 상태로 장시간 남은 작업을 확인합니다.

   ```sql
   SELECT id, status, updated_at FROM jobs
   WHERE status = 'PROCESSING' AND updated_at < now() - interval '30 minutes'
   ORDER BY updated_at;
   ```

   이 작업들은 Redis 잠금 TTL(`WORKER_PROCESSING_TTL_SECONDS`, 기본 1800초)이 만료되면 재처리 가능해집니다.

중단 조건: 세션 종료로도 지연이 해소되지 않으면 저장소 자원 한계이므로 자원 증설 또는 부하 축소로 전환합니다.

## 검증

- `/health/ready`의 `database` 항목이 `ok`로 복귀
- 워커 처리 시간 p95가 기준치로 복귀
- 장시간 `PROCESSING` 작업이 해소됨
- 적체가 감소 추세

## 에스컬레이션

저장·전달 구간 병목이 지속되면 후단 분리(C 모드)를 검토합니다. 다만 **저장소 자체의 용량 문제는 모드 전환으로 해결되지 않습니다.** 분리는 GPU 처리 경로를 보호할 뿐입니다.

## 이력

| 날짜 | 검증 또는 사용 결과 | 수행자 | 후속 조치 |
|---|---|---|---|
| 2026-03-18 | 기존 Runbook 문서에서 이관. 커넥션 경합 진단과 잠금 TTL 안내 추가 | 김용준 | 없음 |
