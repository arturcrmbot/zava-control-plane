"""Subscriber respects EVAL_SAMPLE_RATE — random.random() < rate keeps."""
from __future__ import annotations

import pytest

from api.server.eval import online_subscriber as subscriber_mod


@pytest.fixture
def captured(monkeypatch, tmp_path):
    """Subscriber pieces wired with a fresh in-memory queue + temp store."""
    from api.server.eval.store import EvalStore
    store = EvalStore(db_path=str(tmp_path / "s.sqlite"))
    monkeypatch.setattr(subscriber_mod, "_store", store)
    queue: list = []
    monkeypatch.setattr(subscriber_mod, "_enqueue_for_drain", lambda row: queue.append(row))
    return {"store": store, "queue": queue}


def _make_event(workflow_id="wf-1"):
    from api.shared.events import FleetEvent
    return FleetEvent(
        type="agent.completed",
        workflow_id=workflow_id,
        agent_label="rag-classifier",
        agent_run_id="ar-1",
        prompt="...",
        response_text="...",
        extracted_json={},
        tool_calls=[],
        context="",
        usage={"input_tokens": 1, "output_tokens": 1},
        latency_ms=1,
    )


def test_sample_rate_1_always_keeps(monkeypatch, captured):
    monkeypatch.setenv("EVAL_SAMPLE_RATE", "1.0")
    monkeypatch.setattr(subscriber_mod.random, "random", lambda: 0.999)
    subscriber_mod.on_bus_event(_make_event())
    assert len(captured["queue"]) == 1


def test_sample_rate_0_always_drops(monkeypatch, captured):
    monkeypatch.setenv("EVAL_SAMPLE_RATE", "0.0")
    monkeypatch.setattr(subscriber_mod.random, "random", lambda: 0.0)
    subscriber_mod.on_bus_event(_make_event())
    assert captured["queue"] == []


def test_sample_rate_0_5_keeps_only_when_random_below_0_5(monkeypatch, captured):
    monkeypatch.setenv("EVAL_SAMPLE_RATE", "0.5")
    monkeypatch.setattr(subscriber_mod.random, "random", lambda: 0.4)
    subscriber_mod.on_bus_event(_make_event())
    monkeypatch.setattr(subscriber_mod.random, "random", lambda: 0.6)
    subscriber_mod.on_bus_event(_make_event())
    assert len(captured["queue"]) == 1


def test_filters_non_agent_completed_events(monkeypatch, captured):
    monkeypatch.setenv("EVAL_SAMPLE_RATE", "1.0")
    monkeypatch.setattr(subscriber_mod.random, "random", lambda: 0.0)
    from api.shared.events import FleetEvent
    subscriber_mod.on_bus_event(FleetEvent(type="fleet.tick", workflow_id=None))
    assert captured["queue"] == []
