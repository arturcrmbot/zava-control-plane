"""Tests for the audit_query MCP tool."""
from __future__ import annotations
import json
import time

import pytest

from api.server.mcp_tools.audit_query import audit_query_tool, query
from api.server.state import app_state
from api.shared.types import (
    ActionLedgerEntry, ClaimData, Workflow,
)


@pytest.fixture(autouse=True)
def _isolate_app_state_store():
    """Save, clear, and restore app_state.store for full isolation."""
    saved = dict(app_state.store._workflows)
    app_state.store._workflows.clear()
    yield
    app_state.store._workflows.clear()
    app_state.store._workflows.update(saved)


def _make_claim(claim_id: str = "CLM-1") -> ClaimData:
    return ClaimData(
        claim_id=claim_id,
        employee_id="EMP-0001",
        submitted_at="2026-04-01T12:00:00Z",
        market="UK",
        currency="GBP",
        category="meals",
        vendor="Test Vendor",
        amount=100.0,
        attendees=1,
        receipt_filename=None,
        ems_source="workday",
    )


def _make_workflow(wid: str, ledger: list[ActionLedgerEntry] | None = None) -> Workflow:
    now = time.time()
    return Workflow(
        id=wid,
        type="expense-claim",
        status="completed",
        current_phase="Audit",
        created_at=now,
        sla_due_at=now + 3600,
        claim=_make_claim(claim_id=wid),
        verdict="amber",
        jurisdiction="UK",
        agency="Test Agency",
        action_ledger=ledger or [],
    )


def _entry(
    wid: str,
    *,
    timestamp: float,
    actor_kind: str = "agent",
    actor_id: str = "agent-x",
    action: str = "phase.completed",
    details: dict | None = None,
) -> ActionLedgerEntry:
    return ActionLedgerEntry(
        workflow_id=wid,
        timestamp=timestamp,
        actor_kind=actor_kind,  # type: ignore[arg-type]
        actor_id=actor_id,
        action=action,
        revocable=False,
        details=details or {},
    )


def test_empty_store_returns_empty():
    out = query()
    assert out == {"entries": [], "n": 0}


def test_since_excludes_earlier_entries():
    w = _make_workflow("EXP-A")
    w.action_ledger.extend([
        _entry("EXP-A", timestamp=100.0),
        _entry("EXP-A", timestamp=200.0),
        _entry("EXP-A", timestamp=300.0),
    ])
    app_state.store.upsert_workflow(w)

    out = query(since=200.0)
    assert out["n"] == 2
    timestamps = sorted(e["timestamp"] for e in out["entries"])
    assert timestamps == [200.0, 300.0]


def test_until_excludes_later_entries():
    w = _make_workflow("EXP-B")
    w.action_ledger.extend([
        _entry("EXP-B", timestamp=100.0),
        _entry("EXP-B", timestamp=200.0),
        _entry("EXP-B", timestamp=300.0),
    ])
    app_state.store.upsert_workflow(w)

    out = query(until=200.0)
    assert out["n"] == 2
    timestamps = sorted(e["timestamp"] for e in out["entries"])
    assert timestamps == [100.0, 200.0]


def test_actor_kind_filter_only_agent():
    w = _make_workflow("EXP-C")
    w.action_ledger.extend([
        _entry("EXP-C", timestamp=100.0, actor_kind="agent"),
        _entry("EXP-C", timestamp=200.0, actor_kind="human"),
        _entry("EXP-C", timestamp=300.0, actor_kind="agent"),
    ])
    app_state.store.upsert_workflow(w)

    out = query(actor_kind="agent")
    assert out["n"] == 2
    for e in out["entries"]:
        assert e["actor_kind"] == "agent"


def test_workflow_id_filter_isolates_to_single_workflow():
    w1 = _make_workflow("EXP-D1")
    w1.action_ledger.append(_entry("EXP-D1", timestamp=100.0))
    app_state.store.upsert_workflow(w1)

    w2 = _make_workflow("EXP-D2")
    w2.action_ledger.append(_entry("EXP-D2", timestamp=200.0))
    app_state.store.upsert_workflow(w2)

    out = query(workflow_id="EXP-D1")
    assert out["n"] == 1
    assert out["entries"][0]["workflow_id"] == "EXP-D1"


def test_limit_caps_returned_entries():
    w = _make_workflow("EXP-L")
    for i in range(10):
        w.action_ledger.append(_entry("EXP-L", timestamp=float(i)))
    app_state.store.upsert_workflow(w)

    out = query(limit=3)
    assert len(out["entries"]) == 3
    # `n` is the total match count, not capped by limit.
    assert out["n"] == 10
    # Newest-first.
    timestamps = [e["timestamp"] for e in out["entries"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_tool_wrapper_returns_success_json():
    from copilot.tools import ToolInvocation
    import asyncio

    w = _make_workflow("EXP-T")
    w.action_ledger.append(_entry("EXP-T", timestamp=123.0, action="reviewer.decision"))
    app_state.store.upsert_workflow(w)

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="audit_query",
        arguments={"workflow_id": "EXP-T", "limit": 10},
    )
    result = asyncio.run(audit_query_tool.handler(inv))
    assert result.result_type == "success"
    payload = json.loads(result.text_result_for_llm)
    assert payload["n"] == 1
    assert payload["entries"][0]["action"] == "reviewer.decision"
