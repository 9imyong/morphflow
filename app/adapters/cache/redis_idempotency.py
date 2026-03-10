from __future__ import annotations

import json

from redis.asyncio import Redis

from app.ports.idempotency import IdempotencyPort, IdempotencyRecord


class RedisIdempotencyStore(IdempotencyPort):
    def __init__(self, *, redis: Redis, ttl_seconds: int, processing_ttl_seconds: int) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds
        self.processing_ttl_seconds = processing_ttl_seconds

    async def get_request_record(self, key: str) -> IdempotencyRecord | None:
        raw = await self.redis.get(self._request_key(key))
        if raw is None:
            return None
        data = json.loads(raw)
        return IdempotencyRecord(key=key, job_id=data.get("job_id"), status=data["status"])

    async def reserve_request(self, key: str, job_id: str) -> bool:
        value = json.dumps({"status": "PROCESSING", "job_id": job_id})
        return bool(
            await self.redis.set(self._request_key(key), value, nx=True, ex=self.processing_ttl_seconds)
        )

    async def complete_request(self, key: str, job_id: str) -> None:
        value = json.dumps({"status": "COMPLETED", "job_id": job_id})
        await self.redis.set(self._request_key(key), value, ex=self.ttl_seconds)

    async def reserve_job_processing(self, job_id: str) -> bool:
        value = json.dumps({"status": "PROCESSING", "job_id": job_id})
        return bool(
            await self.redis.set(self._job_key(job_id), value, nx=True, ex=self.processing_ttl_seconds)
        )

    async def complete_job_processing(self, job_id: str, success: bool) -> None:
        status = "COMPLETED" if success else "FAILED"
        value = json.dumps({"status": status, "job_id": job_id})
        await self.redis.set(self._job_key(job_id), value, ex=self.ttl_seconds)

    @staticmethod
    def _request_key(key: str) -> str:
        return f"idem:req:{key}"

    @staticmethod
    def _job_key(job_id: str) -> str:
        return f"idem:job:{job_id}"
