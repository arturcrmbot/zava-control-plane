"""Tests for the query_reviewer_decisions MCP tool."""
from __future__ import annotations
import json
import time

import pytest

from api.server.mcp_tools.query_reviewer_decisions import (
    query, query_reviewer_decisions_tool,
)
from api.server.state import app_state
from api.shared.types import (
    ActionLedgerEntry, ClaimData, Workflow,
)


@pytest.fixture(autouse=True)
def _isolate_app_state_store():
    """Reset app_state.store after each test so the global store doesn't
    leak between tests."""
    pre = {w.id for w in app_state.store.list_workflows()}
    yield
    for w in list(app_state.store.list_workflows()):
        if w.id not in pre:
            app_state.store._workflows.pop(w.id, None)


def _make_claim(claim_id: str = "CLM-1", category: str = "meals") -> ClaimData:
    return ClaimData(
        claim_id=claim_id,
        employee_id="EMP-0001",
        submitted_at="2026-04-01T12:00:00Z",
        market="UK",
        currency="GBP",
        category=category,  # type: ignore[arg-type]
        vendor="Test Vendor",
        amount=100.0,
        attendees=1,
        receipt_filename=None,
        ems_source="workday",
    )


def _make_workflow(
    wid: str,
    *,
    category: str = "meals",
    verdict: str | None = "amber",
    ledger: list[ActionLedgerEntry] | None = None,
) -> Workflow:
    now = time.time()
    w = Workflow(
        id=wid,
        type="expense-claim",
        status="completed",
        current_phase="Audit",
        created_at=now,
        sla_due_at=now + 3600,
        claim=_make_claim(claim_id=wid, category=category),
        verdict=verdict,  # type: ignore[arg-type]
        jurisdiction="UK",
        agency="Test Agency",
        action_ledger=ledger or [],
    )
    return w


def _make_reviewer_entry(
    wid: str,
    *,
    decision: str = "accept-justification",
    policy_clause: str = "§3.1 Meals — UK per-attendee cap GBP 75",
    category: str = "meals",
    actor_id: str = "reviewer@wpp.com",
    timestamp: float | None = None,
) -> ActionLedgerEntry:
    return ActionLedgerEntry(
        workflow_id=wid,
        timestamp=timestamp if timestamp is not None else time.time(),
        actor_kind="human",
        actor_id=actor_id,
        action="reviewer.decision",
        revocable=False,
        details={
            "recommendation": decision,
            "policy_clause": policy_clause,
            "category": category,
        },
    )


def test_empty_store_returns_empty_payload():
    out = query()
    assert out == {"decisions": [], "clusters": [], "n": 0}


def test_single_workflow_with_reviewer_decision_appears():
    w = _make_workflow("EXP-A")
    entry = _make_reviewer_entry("EXP-A")
    w.action_ledger.append(entry)
    app_state.store.upsert_workflow(w)

    out = query()
    assert out["n"] == 1
    assert len(out["decisions"]) == 1
    d = out["decisions"][0]
    assert d["workflow_id"] == "EXP-A"
    assert d["decision"] == "accept-justification"
    assert d["policy_clause"] == "§3.1 Meals — UK per-attendee cap GBP 75"
    assert d["category"] == "meals"
    assert d["verdict"] == "amber"


def test_multiple_workflows_cluster_on_same_clause_and_decision():
    for i in range(3):
        w = _make_workflow(f"EXP-C{i}")
        w.action_ledger.append(_make_reviewer_entry(f"EXP-C{i}"))
        app_state.store.upsert_workflow(w)

    # Add an unrelated workflow with a different decision so it clusters separately.
    w_other = _make_workflow("EXP-D")
    w_other.action_ledger.append(_make_reviewer_entry(
        "EXP-D", decision="require-repayment",
    ))
    app_state.store.upsert_workflow(w_other)

    out = query()
    assert out["n"] == 4
    # Top cluster has the 3 accept-justification entries.
    top = out["clusters"][0]
    assert top["count"] >= 2
    assert top["policy_clause"] == "§3.1 Meals — UK per-attendee cap GBP 75"
    assert top["decision"] == "accept-justification"


def test_category_filter_excludes_other_categories():
    w_meals = _make_workflow("EXP-M", category="meals")
    w_meals.action_ledger.append(_make_reviewer_entry("EXP-M", category="meals"))
    app_state.store.upsert_workflow(w_meals)

    w_travel = _make_workflow("EXP-T", category="travel")
    w_travel.action_ledger.append(_make_reviewer_entry("EXP-T", category="travel"))
    app_state.store.upsert_workflow(w_travel)

    out = query(category="meals")
    assert out["n"] == 1
    assert out["decisions"][0]["workflow_id"] == "EXP-M"
    assert out["decisions"][0]["category"] == "meals"


def test_tool_wrapper_returns_success_json():
    from copilot.tools import ToolInvocation
    import asyncio

    w = _make_workflow("EXP-W")
    w.action_ledger.append(_make_reviewer_entry("EXP-W"))
    app_state.store.upsert_workflow(w)

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="query_reviewer_decisions",
        arguments={"limit": 10},
    )
    result = asyncio.run(query_reviewer_decisions_tool.handler(inv))
    assert result.result_type == "success"
    payload = json.loads(result.text_result_for_llm)
    assert payload["n"] == 1
    assert payload["decisions"][0]["workflow_id"] == "EXP-W"
    assert isinstance(payload["clusters"], list)
