"""Drain worker calls each evaluator and writes scores to the store."""
from __future__ import annotations
from unittest.mock import MagicMock

import pytest

from api.server.eval import online_subscriber as subscriber_mod
from api.server.eval.store import EvalStore, EvalRow


def _make_row(store):
    row = EvalRow(
        id="ev-1", kind="online", agent_label="rag-classifier",
        workflow_id="wf-1", agent_run_id="ar-1", ts=1000.0,
        prompt="q", response_text="r", context="ctx",
        tool_calls=[],
    )
    store.put_pending(row)
    return row


@pytest.mark.asyncio
async def test_drain_worker_completes_row_with_merged_scores(tmp_path, monkeypatch):
    store = EvalStore(db_path=str(tmp_path / "d.sqlite"))
    monkeypatch.setattr(subscriber_mod, "_store", store)

    fake_evals = {
        "groundedness": MagicMock(return_value={"groundedness": 0.9, "groundedness_reason": "ok"}),
        "tool_call_validity": MagicMock(return_value={"tool_calls_valid": 1.0, "invalid_calls": []}),
    }
    monkeypatch.setattr(
        "api.server.eval.evaluator_set.evaluators_for",
        lambda label: fake_evals,
    )
    monkeypatch.setattr(
        subscriber_mod, "_declared_tools_for", lambda label: ["policy_search"],
    )

    row = _make_row(store)
    await subscriber_mod._score_row(row)

    refreshed = store.by_id("ev-1")
    assert refreshed.status == "completed"
    assert refreshed.scores_json["groundedness"] == 0.9
    assert refreshed.scores_json["tool_calls_valid"] == 1.0


@pytest.mark.asyncio
async def test_drain_worker_marks_error_after_retry_failure(tmp_path, monkeypatch):
    store = EvalStore(db_path=str(tmp_path / "d.sqlite"))
    monkeypatch.setattr(subscriber_mod, "_store", store)

    boom = MagicMock(side_effect=RuntimeError("foundry exploded"))
    monkeypatch.setattr(
        "api.server.eval.evaluator_set.evaluators_for",
        lambda label: {"groundedness": boom},
    )
    monkeypatch.setattr(subscriber_mod, "_declared_tools_for", lambda label: [])
    monkeypatch.setattr(subscriber_mod, "_RETRY_BACKOFF_S", 0.0)

    row = _make_row(store)
    await subscriber_mod._score_row(row)

    refreshed = store.by_id("ev-1")
    assert refreshed.status == "error"
    assert "foundry exploded" in refreshed.error_text
