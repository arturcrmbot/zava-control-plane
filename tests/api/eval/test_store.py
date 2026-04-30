"""EvalStore CRUD + summary aggregation behaviour."""
from __future__ import annotations
import time

import pytest

from api.server.eval.store import EvalStore, EvalRow


@pytest.fixture
def store(tmp_path):
    return EvalStore(db_path=str(tmp_path / "eval.sqlite"))


def _make_row(store, **overrides) -> EvalRow:
    base = dict(
        id=f"ev-{time.time_ns()}",
        kind="online",
        agent_label="rag-classifier",
        workflow_id="wf-1",
        agent_run_id="ar-1",
        ts=time.time(),
    )
    base.update(overrides)
    row = EvalRow(**base)
    store.put_pending(row)
    return row


def test_put_pending_and_by_id_round_trips(store):
    row = _make_row(store)
    fetched = store.by_id(row.id)
    assert fetched is not None
    assert fetched.id == row.id
    assert fetched.status == "pending"
    assert fetched.scores_json is None


def test_complete_updates_status_and_scores(store):
    row = _make_row(store)
    store.complete(row.id, scores={"groundedness": 0.9}, foundry_run_url=None)
    fetched = store.by_id(row.id)
    assert fetched.status == "completed"
    assert fetched.scores_json == {"groundedness": 0.9}


def test_error_updates_status_and_text(store):
    row = _make_row(store)
    store.error(row.id, error_text="rate-limited after retry")
    fetched = store.by_id(row.id)
    assert fetched.status == "error"
    assert fetched.error_text == "rate-limited after retry"


def test_recent_returns_completed_rows_newest_first(store):
    r1 = _make_row(store, id="ev-1", ts=1000.0)
    r2 = _make_row(store, id="ev-2", ts=2000.0)
    store.complete(r1.id, scores={"groundedness": 0.8}, foundry_run_url=None)
    store.complete(r2.id, scores={"groundedness": 0.95}, foundry_run_url=None)
    rows = store.recent(10)
    assert [r.id for r in rows] == ["ev-2", "ev-1"]


def test_recent_filters_by_agent_label(store):
    r1 = _make_row(store, id="ev-1", agent_label="rag-classifier")
    r2 = _make_row(store, id="ev-2", agent_label="arbitration")
    store.complete(r1.id, scores={"a": 1}, foundry_run_url=None)
    store.complete(r2.id, scores={"a": 1}, foundry_run_url=None)
    rows = store.recent(10, agent_label="arbitration")
    assert [r.id for r in rows] == ["ev-2"]


def test_summary_excludes_errored_rows_from_averages(store):
    r1 = _make_row(store, id="ev-1")
    r2 = _make_row(store, id="ev-2")
    r3 = _make_row(store, id="ev-3")
    store.complete(r1.id, scores={"groundedness": 0.9, "relevance": 0.8}, foundry_run_url=None)
    store.complete(r2.id, scores={"groundedness": 0.7, "relevance": 0.6}, foundry_run_url=None)
    store.error(r3.id, error_text="boom")

    summary = store.summary(window_minutes=60)
    assert summary["n_completed"] == 2
    assert summary["n_errored"] == 1
    # Mean of {0.9, 0.7} = 0.8 — errored row not counted.
    assert summary["per_agent"]["rag-classifier"]["scores"]["groundedness"] == pytest.approx(0.8)


def test_summary_per_agent_breakdown(store):
    r1 = _make_row(store, id="ev-1", agent_label="rag-classifier")
    r2 = _make_row(store, id="ev-2", agent_label="arbitration")
    store.complete(r1.id, scores={"groundedness": 0.9}, foundry_run_url=None)
    store.complete(r2.id, scores={"groundedness": 0.6}, foundry_run_url=None)

    summary = store.summary(window_minutes=60)
    by_agent = summary["per_agent"]
    assert by_agent["rag-classifier"]["scores"]["groundedness"] == 0.9
    assert by_agent["arbitration"]["scores"]["groundedness"] == 0.6


def test_summary_window_excludes_old_rows(store):
    """Rows older than the window must not affect averages."""
    old = _make_row(store, id="old", ts=time.time() - 7200)  # 2h ago
    new = _make_row(store, id="new", ts=time.time())
    store.complete(old.id, scores={"groundedness": 0.1}, foundry_run_url=None)
    store.complete(new.id, scores={"groundedness": 0.99}, foundry_run_url=None)

    summary = store.summary(window_minutes=60)
    assert summary["per_agent"]["rag-classifier"]["scores"]["groundedness"] == 0.99
    assert summary["n_completed"] == 1


def test_drop_oldest_pending_removes_one_pending_row(store):
    _make_row(store, id="ev-1", ts=1000.0)
    _make_row(store, id="ev-2", ts=2000.0)
    store.drop_oldest_pending()
    assert store.by_id("ev-1") is None
    assert store.by_id("ev-2") is not None


def test_put_batch_and_last_batch_run_round_trip(store):
    report = {
        "run_id": "acc-abc",
        "n": 300,
        "overall_accuracy": 0.96,
        "foundry_run_url": "https://ai.foundry/...",
    }
    store.put_batch("acc-abc", report)
    last = store.last_batch_run()
    assert last["run_id"] == "acc-abc"
    assert last["overall_accuracy"] == 0.96


def test_by_workflow_returns_all_rows_for_a_workflow(store):
    r1 = _make_row(store, id="ev-1", workflow_id="wf-A")
    r2 = _make_row(store, id="ev-2", workflow_id="wf-A")
    r3 = _make_row(store, id="ev-3", workflow_id="wf-B")
    store.complete(r1.id, scores={"a": 1}, foundry_run_url=None)
    store.complete(r2.id, scores={"a": 1}, foundry_run_url=None)
    store.complete(r3.id, scores={"a": 1}, foundry_run_url=None)
    rows = store.by_workflow("wf-A")
    assert {r.id for r in rows} == {"ev-1", "ev-2"}


def test_health_reports_pending_in_flight_dropped_counts(store):
    _make_row(store, id="ev-1")
    r2 = _make_row(store, id="ev-2")
    store.complete(r2.id, scores={"a": 1}, foundry_run_url=None)
    health = store.health()
    assert health["pending"] == 1
    assert health["completed"] == 1
