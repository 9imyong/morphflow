from app.domain.events import EventType, build_event


def test_build_event_contains_required_fields():
    event = build_event(
        job_id="job-1",
        event_type=EventType.REQUESTED,
        source="api",
        trace_id="trace-1",
        payload={"request": {"input": "x"}},
    )

    assert event["job_id"] == "job-1"
    assert event["event_type"] == "REQUESTED"
    assert event["source"] == "api"
    assert event["trace_id"] == "trace-1"
    assert "event_id" in event
