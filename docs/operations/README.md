# 운영 안내

운영 환경의 배포, 관측, 장애 대응, 반복 가능한 복구 절차를 관리합니다.

## 문서 구성

- [배포 및 되돌리기](deployment.md)
- [모니터링](monitoring.md)
- [장애 대응](incident-response.md)
- `runbooks/`: 경보 또는 증상별 실행 절차

운영 문서에는 명령 실행 전 조건, 기대 결과, 중단 기준, 에스컬레이션 경로를 포함합니다. 실제 비밀 값은 기록하지 않습니다.

## 런북 목록

| 증상 | 런북 | 심각도 |
|---|---|---|
| Kafka 적체 급증 | [RUNBOOK-queue-001](runbooks/RUNBOOK-kafka-consumer-lag.md) | 높음 |
| 워커 처리 지연 | [RUNBOOK-worker-001](runbooks/RUNBOOK-worker-processing-delay.md) | 보통 |
| 배치 처리 튜닝·롤백 | [RUNBOOK-worker-002](runbooks/RUNBOOK-batch-tuning-rollback.md) | 낮음 |
| 데이터베이스 지연 | [RUNBOOK-storage-001](runbooks/RUNBOOK-database-latency.md) | 높음 |
| Redis 장애 | [RUNBOOK-cache-001](runbooks/RUNBOOK-redis-outage.md) | 보통 |
| 재시도·DLQ 급증 | [RUNBOOK-reliability-001](runbooks/RUNBOOK-retry-dlq-surge.md) | 높음 |
| 후단 처리 병목 | [RUNBOOK-downstream-001](runbooks/RUNBOOK-downstream-bottleneck.md) | 보통 |
