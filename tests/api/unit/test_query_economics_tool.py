"""Tests for the query_economics MCP tool."""
from __future__ import annotations
import json
import time

import pytest

from api.server.mcp_tools.query_economics import query, query_economics_tool
from api.server.state import app_state
from api.shared.types import ClaimData, Workflow


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


def _make_workflow(
    wid: str,
    *,
    created_at: float | None = None,
    verdict: str | None = "amber",
    tokens_spent: int = 0,
    cost_usd: float = 0.0,
) -> Workflow:
    now = time.time() if created_at is None else created_at
    return Workflow(
        id=wid,
        type="expense-claim",
        status="completed",
        current_phase="Audit",
        created_at=now,
        sla_due_at=now + 3600,
        claim=_make_claim(claim_id=wid),
        verdict=verdict,  # type: ignore[arg-type]
        jurisdiction="UK",
        agency="Test Agency",
        tokens_spent=tokens_spent,
        cost_usd=cost_usd,
    )


def test_empty_store_returns_zero_aggregates():
    out = query()
    assert out["n"] == 0
    assert out["total_cost_usd"] == 0
    assert out["avg_cost_per_task_usd"] == 0
    assert out["by_verdict"] == {}
    assert out["items"] == []
    assert out["window_hours"] == 168


def test_window_excludes_workflows_older_than_window():
    now = time.time()
    inside = _make_workflow(
        "EXP-IN", created_at=now, verdict="green",
        tokens_spent=100, cost_usd=0.05,
    )
    outside = _make_workflow(
        "EXP-OUT", created_at=now - (200 * 3600), verdict="green",
        tokens_spent=200, cost_usd=0.10,
    )
    app_state.store.upsert_workflow(inside)
    app_state.store.upsert_workflow(outside)

    out = query(window_hours=168)
    assert out["n"] == 1
    assert out["items"][0]["workflow_id"] == "EXP-IN"
    assert out["total_cost_usd"] == round(0.05, 4)


def test_by_verdict_three_buckets():
    now = time.time()
    app_state.store.upsert_workflow(_make_workflow(
        "EXP-G", created_at=now, verdict="green",
        tokens_spent=100, cost_usd=0.10,
    ))
    app_state.store.upsert_workflow(_make_workflow(
        "EXP-A", created_at=now, verdict="amber",
        tokens_spent=200, cost_usd=0.20,
    ))
    app_state.store.upsert_workflow(_make_workflow(
        "EXP-R", created_at=now, verdict="red",
        tokens_spent=300, cost_usd=0.30,
    ))

    out = query()
    assert out["n"] == 3
    assert set(out["by_verdict"].keys()) == {"green", "amber", "red"}
    assert out["by_verdict"]["green"]["n"] == 1
    assert out["by_verdict"]["green"]["total_cost_usd"] == round(0.10, 4)
    assert out["by_verdict"]["amber"]["total_cost_usd"] == round(0.20, 4)
    assert out["by_verdict"]["red"]["total_cost_usd"] == round(0.30, 4)
    assert out["total_cost_usd"] == round(0.60, 4)
    # avg = 0.60 / 3 = 0.20
    assert out["avg_cost_per_task_usd"] == round(0.20, 6)


def test_unknown_verdict_clusters_as_unknown():
    now = time.time()
    app_state.store.upsert_workflow(_make_workflow(
        "EXP-U", created_at=now, verdict=None,
        tokens_spent=50, cost_usd=0.025,
    ))

    out = query()
    assert out["n"] == 1
    assert "unknown" in out["by_verdict"]
    assert out["by_verdict"]["unknown"]["n"] == 1


def test_items_truncated_to_50_when_more_stored():
    now = time.time()
    for i in range(60):
        app_state.store.upsert_workflow(_make_workflow(
            f"EXP-{i:03d}", created_at=now, verdict="green",
            tokens_spent=10, cost_usd=0.01,
        ))

    out = query()
    assert out["n"] == 60
    assert len(out["items"]) == 50
    assert out["total_cost_usd"] == round(0.60, 4)


def test_tool_wrapper_returns_success_json():
    from copilot.tools import ToolInvocation
    import asyncio

    now = time.time()
    app_state.store.upsert_workflow(_make_workflow(
        "EXP-W", created_at=now, verdict="green",
        tokens_spent=100, cost_usd=0.05,
    ))

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="query_economics",
        arguments={"window_hours": 168},
    )
    result = asyncio.run(query_economics_tool.handler(inv))
    assert result.result_type == "success"
    payload = json.loads(result.text_result_for_llm)
    assert payload["n"] == 1
    assert payload["total_cost_usd"] == round(0.05, 4)
    assert "green" in payload["by_verdict"]
