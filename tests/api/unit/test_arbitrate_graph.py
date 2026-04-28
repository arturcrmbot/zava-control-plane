"""Phase 6 (Arbitrate) graph: agent_arbitration + schema validator."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.arbitrate import build_arbitrate_workflow


@pytest.mark.asyncio
async def test_well_formed_arbitration_passes():
    fake = {
        "recommendation": "accept-justification",
        "rationale": "Named senior client; PREC-0017 supports.",
        "cited_precedent_id": "PREC-0017",
        "policy_clause": "§3.1 Meals — UK per-attendee cap GBP 75",
        "confidence": 0.86,
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_arbitration.execute",
        AsyncMock(return_value={"arbitration": fake}),
    ):
        wf = build_arbitrate_workflow()
        events = await wf.run({"workflow_id": "CLM-R", "claim_id": "CLM-R"})
    out = events.get_outputs()[0]
    assert out["ok"] is True
    assert out["recommendation"] == "accept-justification"


@pytest.mark.asyncio
async def test_invalid_recommendation_blocks():
    bad = {
        "recommendation": "buy-pizza",
        "rationale": "x", "cited_precedent_id": None,
        "policy_clause": "§1", "confidence": 0.5,
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_arbitration.execute",
        AsyncMock(return_value={"arbitration": bad}),
    ):
        wf = build_arbitrate_workflow()
        events = await wf.run({"workflow_id": "CLM-X", "claim_id": "CLM-X"})
    out = events.get_outputs()[0]
    assert out["ok"] is False
    assert "recommendation" in (out["blocked_reason"] or "")


@pytest.mark.asyncio
async def test_parse_error_blocks():
    bad = {"raw": "model went off-script", "parse_error": True}
    with patch(
        "api.functions.graphs.executors.agents.agent_arbitration.execute",
        AsyncMock(return_value={"arbitration": bad}),
    ):
        wf = build_arbitrate_workflow()
        events = await wf.run({"workflow_id": "CLM-Y", "claim_id": "CLM-Y"})
    out = events.get_outputs()[0]
    assert out["ok"] is False
    assert "parse_error" in (out["blocked_reason"] or "")
