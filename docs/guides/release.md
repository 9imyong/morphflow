# 릴리스 안내

현재 이 저장소는 버전 태그 기반 릴리스를 운영하지 않습니다. 릴리스는 **이미지 빌드와 배포**를 의미하며, 절차의 기준은 [운영 배포 문서](../operations/deployment.md)입니다.

## 릴리스 전

- [ ] 릴리스 범위를 확정합니다.
- [ ] `pytest -q`와 CI의 네 개 작업을 모두 통과합니다.
- [ ] 스키마 변경이 있으면 마이그레이션과 `alembic check`를 확인합니다.
- [ ] 하위 호환성을 확인합니다. API 응답 필드 제거, 상태값 추가, 이벤트 Envelope 변경은 파괴적 변경입니다.
- [ ] 영향을 받는 문서를 갱신합니다. 판단 기준은 [문서 운영 정책](../DOCS_GOVERNANCE.md)입니다.
- [ ] 되돌릴 이미지 또는 매니페스트를 확인합니다.

## 릴리스

```bash
# 이미지 빌드와 kind 로드
make kind-rebuild

# 배포
scripts/k8s-deploy-kind.sh local-dev base

# 스키마 변경이 포함된 경우
scripts/k8s-deploy-kind.sh local-dev base --with-migrate
```

현재 이미지 태그는 `morphflow-app:kind` 고정입니다. 되돌릴 지점을 남기려면 배포 전 태그를 분리해야 합니다.

## 릴리스 후

- [ ] `/health/live`와 `/health/ready`를 확인합니다.
- [ ] `POST /jobs` → `GET /jobs/{job_id}`가 `SUCCESS`에 도달하는지 확인합니다.
- [ ] 오류율, 처리 지연, 적체, `dlq_messages_total`을 관찰합니다.
- [ ] 문제가 있으면 [운영 배포 문서](../operations/deployment.md)의 되돌리기 절차를 실행합니다.
- [ ] 완료된 작업 문서를 `tasks/completed/`로 이동하고 기준 문서 반영을 확인합니다.

## 관련 문서

- [운영 배포 문서](../operations/deployment.md)
- [테스트 안내](testing.md)
- [문서 운영 정책](../DOCS_GOVERNANCE.md)
