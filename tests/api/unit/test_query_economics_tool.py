"""Tests for the query_economics MCP tool.

Post-2026-05-05 (plan/feature-foundry-credibility-friday-1.md TASK-013):
the tool computes cost from real OTEL spans via
`services.economics.compute()`, not from the per-workflow `tokens_spent` /
`cost_usd` fields (which were never written to in the lab build). These
tests plumb fake `gen_ai.usage.*` spans into `app_state.store` per workflow
so the contract is exercised end-to-end.
"""
from __future__ import annotations
import json
import time

import pytest

from api.server.mcp_tools.query_economics import query, query_economics_tool
from api.server.services import model_pricing
from api.server.state import app_state
from api.shared.types import ClaimData, OtelSpan, Workflow


@pytest.fixture(autouse=True)
def _isolate_app_state_store():
    """Save, clear, and restore app_state.store for full isolation."""
    saved_workflows = dict(app_state.store._workflows)
    saved_spans = {k: list(v) for k, v in app_state.store._spans.items()}
    app_state.store._workflows.clear()
    app_state.store._spans.clear()
    yield
    app_state.store._workflows.clear()
    app_state.store._workflows.update(saved_workflows)
    app_state.store._spans.clear()
    app_state.store._spans.update(saved_spans)


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
    )


def _seed_spans(wid: str, *, in_tok: int, out_tok: int, model: str = "gpt-4.1") -> None:
    """Seed one agent span carrying gen_ai.usage.* attributes for the workflow.

    Goes through `app_state.store.append_span(...)` which keys on
    `attributes["workflow.id"]`, matching production paths.
    """
    span = OtelSpan(
        trace_id="t",
        span_id=f"s-{wid}",
        name="gen_ai.generate_content",
        start_ms=0.0,
        end_ms=100.0,
        attributes={
            "workflow.id": wid,
            "gen_ai.system": "github_copilot",
            "gen_ai.request.model": model,
            "gen_ai.usage.input_tokens": in_tok,
            "gen_ai.usage.output_tokens": out_tok,
        },
    )
    app_state.store.append_span(span)


def _expected_cost(in_tok: int, out_tok: int, model: str = "gpt-4.1") -> float:
    return round(model_pricing.cost_for(model, in_tok, out_tok), 4)


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
    inside = _make_workflow("EXP-IN", created_at=now, verdict="green")
    outside = _make_workflow("EXP-OUT", created_at=now - (200 * 3600), verdict="green")
    app_state.store.upsert_workflow(inside)
    app_state.store.upsert_workflow(outside)
    _seed_spans("EXP-IN", in_tok=10_000, out_tok=5_000)
    _seed_spans("EXP-OUT", in_tok=20_000, out_tok=10_000)

    out = query(window_hours=168)
    assert out["n"] == 1
    assert out["items"][0]["workflow_id"] == "EXP-IN"
    assert out["total_cost_usd"] == _expected_cost(10_000, 5_000)


def test_by_verdict_three_buckets():
    now = time.time()
    app_state.store.upsert_workflow(_make_workflow("EXP-G", created_at=now, verdict="green"))
    app_state.store.upsert_workflow(_make_workflow("EXP-A", created_at=now, verdict="amber"))
    app_state.store.upsert_workflow(_make_workflow("EXP-R", created_at=now, verdict="red"))
    _seed_spans("EXP-G", in_tok=10_000, out_tok=5_000)
    _seed_spans("EXP-A", in_tok=20_000, out_tok=10_000)
    _seed_spans("EXP-R", in_tok=30_000, out_tok=15_000)

    out = query()
    assert out["n"] == 3
    assert set(out["by_verdict"].keys()) == {"green", "amber", "red"}
    assert out["by_verdict"]["green"]["n"] == 1
    assert out["by_verdict"]["green"]["total_cost_usd"] == _expected_cost(10_000, 5_000)
    assert out["by_verdict"]["amber"]["total_cost_usd"] == _expected_cost(20_000, 10_000)
    assert out["by_verdict"]["red"]["total_cost_usd"] == _expected_cost(30_000, 15_000)
    expected_total = round(
        _expected_cost(10_000, 5_000)
        + _expected_cost(20_000, 10_000)
        + _expected_cost(30_000, 15_000),
        4,
    )
    assert out["total_cost_usd"] == expected_total


def test_unknown_verdict_clusters_as_unknown():
    now = time.time()
    app_state.store.upsert_workflow(_make_workflow("EXP-U", created_at=now, verdict=None))
    _seed_spans("EXP-U", in_tok=5_000, out_tok=2_500)

    out = query()
    assert out["n"] == 1
    assert "unknown" in out["by_verdict"]
    assert out["by_verdict"]["unknown"]["n"] == 1


def test_items_truncated_to_50_when_more_stored():
    now = time.time()
    for i in range(60):
        wid = f"EXP-{i:03d}"
        app_state.store.upsert_workflow(_make_workflow(wid, created_at=now, verdict="green"))
        _seed_spans(wid, in_tok=1_000, out_tok=500)

    out = query()
    assert out["n"] == 60
    assert len(out["items"]) == 50
    expected_total = round(60 * _expected_cost(1_000, 500), 4)
    assert out["total_cost_usd"] == expected_total


def test_tool_wrapper_returns_success_json():
    from copilot.tools import ToolInvocation
    import asyncio

    now = time.time()
    app_state.store.upsert_workflow(_make_workflow("EXP-W", created_at=now, verdict="green"))
    _seed_spans("EXP-W", in_tok=10_000, out_tok=5_000)

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="query_economics",
        arguments={"window_hours": 168},
    )
    result = asyncio.run(query_economics_tool.handler(inv))
    assert result.result_type == "success"
    payload = json.loads(result.text_result_for_llm)
    assert payload["n"] == 1
    assert payload["total_cost_usd"] == _expected_cost(10_000, 5_000)
    assert "green" in payload["by_verdict"]
    assert payload.get("pricing_source", "").startswith("azure-published-")
