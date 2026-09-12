# API 설명: 작업 접수와 조회

## 목적

클라이언트가 추론 작업을 맡기고 결과를 되찾아 갈 수 있게 합니다. 처리 시간이 길거나 시스템이 적체되어 있어도 접수 자체는 빠르게 끝나야 하며, 같은 요청을 여러 번 보내도 작업이 늘어나면 안 됩니다.

## 계약 기준

- OpenAPI 위치: `docs/specs/api/openapi.yaml`
- 계약 관리 방식: 코드 우선. 라우터와 Pydantic 스키마가 실제 동작의 기준이며 OpenAPI는 이를 문서화합니다.
- 확인 명령: 애플리케이션 기동 후 `curl -s http://localhost:8000/openapi.json`으로 실제 생성 스키마와 비교합니다.

## 인증과 권한

현재 인증을 요구하지 않습니다. 신뢰 경계 안에서만 호출된다고 가정하며, 외부 노출 시 인증 방식 결정이 선행되어야 합니다.

## 주요 시나리오

### 작업 접수

```bash
curl -sS -X POST http://localhost:8000/jobs \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: client-req-20260913-0001' \
  -d '{"input": {"type": "text", "content": "hello morphflow"}, "options": {"priority": "normal"}}'
```

```json
{ "job_id": "1f0c5f2e9a7b4c3d8e6f1a2b3c4d5e6f", "status": "PENDING" }
```

응답은 `202 Accepted`입니다. **처리 완료가 아니라 접수 완료를 의미합니다.**

### 상태 조회

```bash
curl -sS http://localhost:8000/jobs/1f0c5f2e9a7b4c3d8e6f1a2b3c4d5e6f
```

```json
{
  "job_id": "1f0c5f2e9a7b4c3d8e6f1a2b3c4d5e6f",
  "status": "SUCCESS",
  "result": { "message": "gpu inference simulator completed", "simulated_batch_size": 4 },
  "error": null
}
```

## 멱등성 규칙

- `Idempotency-Key` 헤더를 보내면 같은 키의 재요청은 **새 작업을 만들지 않고 최초 작업의 식별자**를 반환합니다.
- 헤더를 생략하면 서버가 매 요청마다 새 키를 생성하므로 사실상 멱등성이 적용되지 않습니다. 재시도 가능성이 있는 클라이언트는 반드시 키를 보내야 합니다.
- 키의 유효 기간은 `IDEMPOTENCY_TTL_SECONDS`(기본 3600초)입니다. 이 시간이 지난 뒤 같은 키로 요청하면 새 작업이 생성됩니다.
- 키의 범위는 전역입니다. 클라이언트별로 분리되지 않으므로 충돌하지 않을 값을 사용해야 합니다.

동작 원리는 [ADR-0002](../../decisions/ADR-0002-idempotency-strategy.md)에 있습니다.

## 상태 해석

| status | 의미 | 클라이언트 대응 |
|---|---|---|
| `PENDING` | 접수되었고 아직 워커가 잡지 않음 | 잠시 후 재조회 |
| `PROCESSING` | 처리 중. C·BC 모드에서는 후단 처리 대기도 포함 | 잠시 후 재조회 |
| `SUCCESS` | 완료. `result`에 결과가 있음 | 결과 사용 |
| `FAILED` | 실패. `error`에 사유가 있음 | 재시도가 남아 있으면 이후 `SUCCESS`로 바뀔 수 있으므로 즉시 재요청하지 않음 |

`FAILED`는 최종 상태가 아닐 수 있습니다. 재시도 경로가 살아 있는 동안에는 상태가 다시 `SUCCESS`로 바뀔 수 있습니다.

## 오류 모델

| 상태 코드 | 의미 | 호출자 대응 |
|---|---|---|
| 404 | 해당 식별자의 작업 없음 | 식별자 확인 |
| 422 | 요청 본문이 스키마 불일치 | 입력 수정 |
| 500 | 서버 내부 오류 | 같은 `Idempotency-Key`로 재시도 |
| 503 | `/health/ready`에서 의존성 비정상 | 트래픽 전송 중단 |

## 호환성 정책

- 이 계약은 아키텍처 모드 전환과 무관하게 고정합니다. 모드에 따라 경로·필드·상태값이 달라지지 않습니다.
- 상태값 추가는 파괴적 변경으로 간주합니다. 확장 논의는 [RFC-0001](../../rfcs/RFC-0001-extended-job-status-model.md)에 있습니다.
- 응답 필드 추가는 하위 호환으로 보고, 제거와 의미 변경은 ADR을 통해서만 수행합니다.
