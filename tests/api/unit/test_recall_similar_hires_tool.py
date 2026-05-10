"""Tests for recall_similar_hires MCP tool — episodic memory surface.

The tool walks `app_state.store.list_workflows()` and returns matches whose
`type == "hiring"` and whose metadata carries the queried `role_family` /
`jurisdiction`. We exercise:

- exact match on role_family + jurisdiction (case-insensitive)
- filtering of non-hiring workflows
- filtering by jurisdiction (different jurisdictions excluded)
- the limit parameter (most recent N)
- the empty-result envelope
- the `_RecallParams`-based public Tool wrapper returns serialised JSON
"""
from __future__ import annotations

import json
import time

import pytest

from api.shared.types import Workflow
from api.server.mcp_tools import recall_similar_hires as recall_mod


def _hiring(
    workflow_id: str,
    *,
    role_family: str = "senior-data-engineer",
    jurisdiction: str = "USA",
    status: str = "completed",
    panel_score: float | None = 0.85,
    rejection_reason: str | None = None,
    completed_at: float | None = None,
) -> Workflow:
    now = time.time()
    meta: dict = {"role_family": role_family, "jurisdiction": jurisdiction}
    if panel_score is not None:
        meta["panel_score"] = panel_score
    if rejection_reason is not None:
        meta["rejection_reason"] = rejection_reason
    return Workflow(
        id=workflow_id,
        type="hiring",
        created_at=now,
        sla_due_at=now + 3600,
        jurisdiction=jurisdiction,
        agency="Zava-HR",
        current_phase="Triage",
        status=status,
        completed_at=completed_at,
        metadata=meta,
    )


@pytest.fixture
def fresh_store(monkeypatch):
    """Yield a fresh in-memory StateStore swapped onto app_state.

    The mcp_tool reads ``app_state.store`` at call time, so monkey-patching the
    attribute is enough — no module reloads required.

    Note: we patch ``recall_mod.app_state.store`` (rather than re-importing
    ``app_state`` from ``api.server.state``) because earlier tests in the
    suite may have popped ``api.server.state`` out of ``sys.modules`` and
    rebuilt a fresh AppState — at that point the freshly imported singleton
    is a *different* object from the one ``recall_similar_hires`` captured at
    its own import time.
    """
    from api.server.services.state_store import StateStore

    new_store = StateStore()
    monkeypatch.setattr(recall_mod.app_state, "store", new_store)
    return new_store


def test_returns_empty_envelope_when_no_workflows(fresh_store):
    out = recall_mod.recall_similar_hires(
        role_family="senior-data-engineer", jurisdiction="USA"
    )
    assert out == {
        "role_family": "senior-data-engineer",
        "jurisdiction": "USA",
        "n": 0,
        "hires": [],
    }


def test_returns_matching_hiring_workflows(fresh_store):
    fresh_store.upsert_workflow(_hiring("H-1", panel_score=0.91))
    fresh_store.upsert_workflow(
        _hiring("H-2", status="failed", panel_score=0.42, rejection_reason="culture")
    )
    out = recall_mod.recall_similar_hires(
        role_family="senior-data-engineer", jurisdiction="USA"
    )
    assert out["n"] == 2
    ids = {h["workflow_id"] for h in out["hires"]}
    assert ids == {"H-1", "H-2"}
    by_id = {h["workflow_id"]: h for h in out["hires"]}
    assert by_id["H-1"]["outcome"] == "completed"
    assert by_id["H-1"]["panel_score"] == 0.91
    assert by_id["H-2"]["outcome"] == "failed"
    assert by_id["H-2"]["rejection_reason"] == "culture"


def test_excludes_non_hiring_workflows(fresh_store):
    fresh_store.upsert_workflow(_hiring("HIRE-1"))
    other = _hiring("EXP-1")
    other.type = "expense-claim"
    fresh_store.upsert_workflow(other)
    out = recall_mod.recall_similar_hires(
        role_family="senior-data-engineer", jurisdiction="USA"
    )
    assert {h["workflow_id"] for h in out["hires"]} == {"HIRE-1"}


def test_filters_by_role_family_case_insensitive(fresh_store):
    fresh_store.upsert_workflow(_hiring("SDE-1", role_family="senior-data-engineer"))
    fresh_store.upsert_workflow(_hiring("CD-1", role_family="creative-director"))
    out = recall_mod.recall_similar_hires(
        role_family="SENIOR-DATA-ENGINEER", jurisdiction="USA"
    )
    assert {h["workflow_id"] for h in out["hires"]} == {"SDE-1"}


def test_filters_by_jurisdiction_case_insensitive(fresh_store):
    fresh_store.upsert_workflow(_hiring("US-1", jurisdiction="USA"))
    fresh_store.upsert_workflow(_hiring("DE-1", jurisdiction="DE"))
    out = recall_mod.recall_similar_hires(
        role_family="senior-data-engineer", jurisdiction="usa"
    )
    assert {h["workflow_id"] for h in out["hires"]} == {"US-1"}


def test_respects_limit_returning_last_n(fresh_store):
    for i in range(7):
        fresh_store.upsert_workflow(_hiring(f"H-{i}"))
    out = recall_mod.recall_similar_hires(
        role_family="senior-data-engineer", jurisdiction="USA", limit=3
    )
    assert out["n"] == 3
    # `matches[-limit:]` keeps the LAST three, in insertion order.
    assert [h["workflow_id"] for h in out["hires"]] == ["H-4", "H-5", "H-6"]


def test_default_limit_is_five(fresh_store):
    for i in range(10):
        fresh_store.upsert_workflow(_hiring(f"H-{i}"))
    out = recall_mod.recall_similar_hires(
        role_family="senior-data-engineer", jurisdiction="USA"
    )
    assert out["n"] == 5


def test_tool_wrapper_returns_serialised_json(fresh_store):
    import asyncio
    from copilot.tools import ToolInvocation

    fresh_store.upsert_workflow(_hiring("H-X"))
    inv = ToolInvocation(
        session_id="t",
        tool_call_id="t",
        tool_name="recall_similar_hires",
        arguments={"role_family": "senior-data-engineer", "jurisdiction": "USA"},
    )
    result = asyncio.run(recall_mod.recall_similar_hires_tool.handler(inv))
    decoded = json.loads(result.text_result_for_llm)
    assert decoded["n"] == 1
    assert decoded["hires"][0]["workflow_id"] == "H-X"
