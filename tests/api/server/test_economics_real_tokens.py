"""Tests for api.server.services.economics — real-token cost path."""
from __future__ import annotations

import pytest

from api.server.services import economics, model_pricing
from api.shared.types import OtelSpan, Workflow


def _wf(workflow_id: str = "EXP-TEST-1") -> Workflow:
    return Workflow(
        id=workflow_id,
        type="expense-claim",
        status="in_progress",
        current_phase="Intake",
        created_at=0.0,
        sla_due_at=0.0,
        jurisdiction="London-Zava",
        agency="Zava",
    )


def _agent_span(model: str, in_tok: int, out_tok: int, sid: str = "s1") -> OtelSpan:
    return OtelSpan(
        trace_id="t",
        span_id=sid,
        name="gen_ai.generate_content",
        start_ms=0.0,
        end_ms=10.0,
        attributes={
            "gen_ai.system": "github_copilot",
            "gen_ai.request.model": model,
            "gen_ai.usage.input_tokens": in_tok,
            "gen_ai.usage.output_tokens": out_tok,
        },
    )


def test_compute_zero_when_no_spans():
    eco = economics.compute(_wf(), spans=[], mcp_calls=[])
    assert eco["modelCostUsd"] == 0.0
    assert eco["computeCostUsd"] == 0.0  # back-compat alias
    assert eco["inputTokens"] == 0
    assert eco["outputTokens"] == 0
    assert eco["modelCalls"] == 0
    assert eco["pricingSource"].startswith("azure-published-")


def test_compute_single_gpt41_call():
    spans = [_agent_span("gpt-4.1", 100_000, 50_000)]
    eco = economics.compute(_wf(), spans=spans, mcp_calls=[])
    expected = model_pricing.cost_for("gpt-4.1", 100_000, 50_000)
    assert eco["modelCostUsd"] == pytest.approx(round(expected, 4))
    assert eco["inputTokens"] == 100_000
    assert eco["outputTokens"] == 50_000
    assert eco["modelCalls"] == 1
    assert eco["perModel"][0]["model"] == "gpt-4.1"


def test_compute_two_models_in_one_workflow():
    spans = [
        _agent_span("gpt-4.1", 1_000_000, 0, sid="s1"),
        _agent_span("gpt-4.1-mini", 1_000_000, 0, sid="s2"),
    ]
    eco = economics.compute(_wf(), spans=spans, mcp_calls=[])
    # gpt-4.1 1M in = $2; gpt-4.1-mini 1M in = $0.40; total $2.40
    assert eco["modelCostUsd"] == pytest.approx(2.40)
    assert eco["inputTokens"] == 2_000_000
    assert eco["modelCalls"] == 2
    models = sorted(p["model"] for p in eco["perModel"])
    assert models == ["gpt-4.1", "gpt-4.1-mini"]


def test_compute_legacy_executor_type_agent_counts_calls_but_zero_cost():
    # Older `executor.type=agent` spans (pre-wrapper-otel-bridge) didn't carry
    # gen_ai.usage. They should still count as a call but contribute 0 cost.
    legacy = OtelSpan(
        trace_id="t",
        span_id="s1",
        name="executor.classify",
        start_ms=0.0,
        end_ms=1000.0,
        attributes={"executor.type": "agent"},
    )
    eco = economics.compute(_wf(), spans=[legacy], mcp_calls=[])
    assert eco["modelCalls"] == 1
    assert eco["modelCostUsd"] == 0.0
    assert eco["inputTokens"] == 0


def test_compute_ignores_non_agent_spans():
    deterministic = OtelSpan(
        trace_id="t",
        span_id="s1",
        name="executor.intake",
        start_ms=0.0,
        end_ms=10.0,
        attributes={"executor.type": "deterministic"},
    )
    eco = economics.compute(_wf(), spans=[deterministic], mcp_calls=[])
    assert eco["modelCalls"] == 0
    assert eco["modelCostUsd"] == 0.0


def test_compute_back_compat_keys_present():
    eco = economics.compute(_wf(), spans=[], mcp_calls=[])
    for key in ("computeCostUsd", "modelCostUsd", "modelCalls",
                "toolCalls", "daysElapsed", "slaToken",
                "inputTokens", "outputTokens", "pricingSource", "perModel"):
        assert key in eco, f"missing key {key}"
