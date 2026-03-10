from __future__ import annotations

from collections import Counter

import pytest

from app.adapters.db.repositories import SqlAlchemyJobEventRepository
from app.adapters.processing.downstream_dummy import DownstreamDummyProcessor
from app.application.job_service import JobService
from app.application.pipeline_services import DownstreamPipelineService, InferencePipelineService
from app.domain.models import JobStatus


class InferenceSuccessProcessor:
    async def process(self, payload: dict) -> dict:
        return {"mode": "simulated-gpu", "echo": payload.get("input", {}).get("content", "")}


@pytest.mark.asyncio
async def test_c_pipeline_inference_to_downstream_to_success(session_factory, idempotency_store, publisher) -> None:
    job_service = JobService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        publisher=publisher,
        topic="inference-topic",
    )
    inference_service = InferencePipelineService(
        session_factory=session_factory,
        idempotency_store=idempotency_store,
        processor=InferenceSuccessProcessor(),
        publisher=publisher,
        downstream_topic="downstream-topic",
    )
    downstream_service = DownstreamPipelineService(
        session_factory=session_factory,
        processor=DownstreamDummyProcessor(base_latency_ms=1),
    )

    created = await job_service.create_job(
        payload={"input": {"type": "text", "content": "c-path"}, "options": {}},
        idempotency_key="c-path-key",
    )
    inference_event = publisher.published[-1][1]

    inference_ok, inference_error = await inference_service.handle_event(inference_event)
    assert inference_ok is True
    assert inference_error is None
    assert publisher.published[-1][0] == "downstream-topic"

    mid_state = await job_service.get_job(created.id)
    assert mid_state is not None
    assert mid_state.status == JobStatus.PROCESSING

    downstream_event = publisher.published[-1][1]
    downstream_ok, downstream_error = await downstream_service.handle_event(downstream_event)
    assert downstream_ok is True
    assert downstream_error is None

    final_state = await job_service.get_job(created.id)
    assert final_state is not None
    assert final_state.status == JobStatus.SUCCESS
    assert final_state.result is not None
    assert "downstream" in final_state.result

    # Duplicate downstream consume should be ignored once SUCCESS is persisted.
    second_ok, second_error = await downstream_service.handle_event(downstream_event)
    assert second_ok is True
    assert second_error is None

    async with session_factory() as session:
        events = await SqlAlchemyJobEventRepository(session).list_for_job(created.id)
    counts = Counter(item.event_type for item in events)
    assert counts["INFERENCE_COMPLETED"] == 1
    assert counts["DOWNSTREAM_COMPLETED"] == 1
