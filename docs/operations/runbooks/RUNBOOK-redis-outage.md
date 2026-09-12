---
id: RUNBOOK-cache-001
title: Redis 장애
owners: [김용준]
last_validated: 2026-03-18
severity: 보통
---

# 런북: Redis 장애

## 발동 조건과 영향

- 경보: `RedisExporterDown`
- 증상: `/health/ready`의 `redis` 항목 실패, 멱등성 예약 실패

Redis는 **1차 방어선일 뿐 기준 저장소가 아닙니다.** 장애 시에도 중복 완료는 데이터베이스 상태 확인이 막습니다. 실제 영향은 다음과 같습니다.

- 요청 멱등성이 동작하지 않아 같은 키의 재요청이 새 작업을 만들 수 있습니다.
- 처리 잠금이 없어 같은 작업을 두 워커가 동시에 처리할 수 있습니다. 중복 완료는 막히지만 자원이 낭비됩니다.
- `/health/ready`가 `503`을 반환해 트래픽이 차단될 수 있습니다.

## 사전 조건과 안전 수칙

- 필요한 접근: Redis 파드 조회와 재시작 권한
- 실행하면 안 되는 조건: `FLUSHALL`을 실행하지 않습니다. 진행 중인 처리 잠금이 사라져 중복 처리가 늘어납니다.
- 데이터 손실 가능성: Redis 데이터는 모두 TTL 기반 임시 데이터이므로 유실 자체는 허용됩니다.

## 진단

1. 연결과 상태를 확인합니다.

   ```bash
   curl -s http://localhost:18000/health/ready | jq '.dependencies.redis'
   kubectl get pods -l app=redis -n morphflow --context kind-local-dev
   kubectl exec -it deploy/redis -n morphflow --context kind-local-dev -- redis-cli ping
   ```

   정상 응답은 `PONG`입니다.

2. 장애 구간을 특정합니다. 이후 중복 처리 후보를 좁히는 데 사용합니다.

   ```bash
   kubectl logs deploy/redis -n morphflow --context kind-local-dev --tail=100
   ```

## 완화와 복구

1. Redis를 재기동합니다.

   ```bash
   kubectl rollout restart deploy/redis -n morphflow --context kind-local-dev
   ```

2. 연결 복구 후 API와 워커가 정상 동작하는지 확인합니다. 애플리케이션은 재시작 없이 재연결합니다.

3. 장애 구간에 생성된 중복 작업 후보를 확인합니다.

   ```sql
   SELECT request_payload->>'input' AS input_key, count(*), array_agg(id)
   FROM jobs
   WHERE created_at BETWEEN '<장애 시작>' AND '<장애 종료>'
   GROUP BY 1 HAVING count(*) > 1;
   ```

   중복이 확인되면 업무 규칙에 따라 처리합니다. 자동 정리는 하지 않습니다.

중단 조건: 재기동으로 복구되지 않으면 인프라 문제이므로 애플리케이션 조치를 중단합니다.

## 검증

- `redis-cli ping`이 `PONG` 반환
- `/health/ready`가 `200` 복귀
- 같은 `Idempotency-Key` 재요청 시 같은 `job_id` 반환 확인
- 장애 구간 중복 작업 검토 완료

## 에스컬레이션

Redis 장애는 아키텍처 모드 전환의 근거가 아닙니다. 반복된다면 기반 인프라 안정화(HA 구성)를 우선 검토합니다.

## 이력

| 날짜 | 검증 또는 사용 결과 | 수행자 | 후속 조치 |
|---|---|---|---|
| 2026-03-18 | 기존 Runbook 문서에서 이관. 실제 영향 범위를 멱등성 2단계 구조 기준으로 정정 | 김용준 | 없음 |
