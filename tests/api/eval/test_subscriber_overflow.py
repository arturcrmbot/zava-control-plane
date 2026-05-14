"""Queue overflow drops the oldest pending row from the store."""
from __future__ import annotations

import pytest

from api.server.eval import online_subscriber as subscriber_mod


@pytest.fixture
def store_only(monkeypatch, tmp_path):
    from api.server.eval.store import EvalStore
    store = EvalStore(db_path=str(tmp_path / "s.sqlite"))
    monkeypatch.setattr(subscriber_mod, "_store", store)
    monkeypatch.setenv("EVAL_QUEUE_MAX", "2")
    monkeypatch.setenv("EVAL_SAMPLE_RATE", "1.0")
    monkeypatch.setattr(subscriber_mod.random, "random", lambda: 0.0)
    subscriber_mod._reset_queue_for_test(maxsize=2)
    yield store
    subscriber_mod._reset_queue_for_test(maxsize=int(subscriber_mod._DEFAULT_QUEUE_MAX))


def _ev(wid):
    from api.shared.events import FleetEvent
    return FleetEvent(
        type="agent.completed", workflow_id=wid, agent_label="rag-classifier",
        agent_run_id=f"ar-{wid}", prompt="...", response_text="...", extracted_json={},
        tool_calls=[], context="", usage={}, latency_ms=1,
    )


def test_queue_overflow_drops_oldest_pending(monkeypatch, store_only):
    """Push 3 events into a queue of size 2. The oldest pending row in the
    store must be removed and the third row must end up enqueued."""
    subscriber_mod.on_bus_event(_ev("wf-1"))
    subscriber_mod.on_bus_event(_ev("wf-2"))
    subscriber_mod.on_bus_event(_ev("wf-3"))

    rows = store_only.recent(10)
    workflow_ids = {r.workflow_id for r in rows}
    assert workflow_ids == {"wf-2", "wf-3"}
    assert subscriber_mod._metrics["dropped"] >= 1
