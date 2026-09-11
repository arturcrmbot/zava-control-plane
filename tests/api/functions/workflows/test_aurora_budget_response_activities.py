from __future__ import annotations

import asyncio
import json

import pytest


@pytest.mark.parametrize("with_tool_evidence", [False, True])
def test_recommendation_uses_canonical_agent_session_and_preserves_invoice_values(
    monkeypatch, with_tool_evidence,
):
    calls = []

    async def _run(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return {
            "recommendation": "Freeze Aurora POs for 14 days.",
            "rationale": "The synthetic signal reached the annual budget.",
            "proposed_action": {
                "id": "freeze-brand-aurora",
                "kind": "policy_set",
                "verdict": "freeze",
                "decided_on": ["BRAND-aurora"],
                "attributes": {"scope": "po", "expiry_days": 14},
                "reason": "Budget threshold exceeded.",
            },
            "selected_invoice_ids": ["INV-AUR-TESTMODEL-01"],
            **({"_raw_tool_calls": [{"tool": "skill", "success": True}]} if with_tool_evidence else {}),
        }

    monkeypatch.setattr(
        "api.functions.graphs.executors.agents._wrapper.run_agent_session",
        _run,
    )
    from api.functions.workflows.aurora_budget_response_activities import (
        AuroraRecommendation,
        aurora_recommendation_activity,
    )

    result = asyncio.run(aurora_recommendation_activity({
        "workflow_id": "AUR-TESTMODEL",
        "instance_id": "aurora-test-model",
        "brand_id": "BRAND-aurora",
        "count": 1,
        "observation": {"after_pct": 1.0},
    }))

    assert calls[0][1]["skill_label"] == "aurora-budget-recommender"
    assert calls[0][1]["phase"] == "Recommend response"
    prompt = json.loads(calls[0][0])
    assert prompt["output_schema"] == AuroraRecommendation.model_json_schema()
    assert prompt["required_action"]["attributes"]["expiry_days"] == 14
    selected = result["selected_invoices"][0]
    assert selected["invoice_id"] == "INV-AUR-TESTMODEL-01"
    assert selected["brand_id"] == "BRAND-aurora"
    assert selected["amount_gbp"] >= 500
    assert selected["vendor"]
    assert selected["gl_code"]
    assert "_raw_tool_calls" not in result


@pytest.mark.parametrize(
    ("invoice_id", "extra_fields", "error"),
    [
        ("INV-NOT-SUPPLIED", {}, "outside the supplied candidates"),
        ("INV-AUR-TESTMODEL-01", {"unexpected": True}, "extra_forbidden"),
    ],
)
def test_recommendation_rejects_invalid_model_output(
    monkeypatch, invoice_id, extra_fields, error,
):
    async def _run(*args, **kwargs):
        return {
            "recommendation": "Freeze.",
            "rationale": "Over budget.",
            "proposed_action": {
                "id": "freeze-brand-aurora",
                "kind": "policy_set",
                "verdict": "freeze",
                "decided_on": ["BRAND-aurora"],
                "attributes": {"scope": "po", "expiry_days": 14},
            },
            "selected_invoice_ids": [invoice_id],
            **extra_fields,
        }

    monkeypatch.setattr(
        "api.functions.graphs.executors.agents._wrapper.run_agent_session",
        _run,
    )
    from api.functions.workflows.aurora_budget_response_activities import (
        aurora_recommendation_activity,
    )

    with pytest.raises(ValueError, match=error):
        asyncio.run(aurora_recommendation_activity({
            "workflow_id": "AUR-TESTMODEL",
            "brand_id": "BRAND-aurora",
            "count": 1,
            "observation": {"after_pct": 1.0},
        }))
