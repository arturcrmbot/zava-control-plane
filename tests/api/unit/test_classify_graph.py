"""Phase 2 (Classify R/A/G) graph — agent_rag_classifier + schema validator edge."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.classify import build_classify_workflow


@pytest.mark.asyncio
async def test_classify_graph_passes_well_formed_payload():
    fake = {
        "verdict": "amber",
        "policy_clause": "§3.1 Meals — UK per-attendee cap GBP 75",
        "reasoning": "Within 110% of cap with named attendees.",
        "confidence": 0.7,
        "competing_interpretations": [],
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_rag_classifier.execute",
        AsyncMock(return_value={"classification": fake}),
    ):
        wf = build_classify_workflow()
        events = await wf.run({"workflow_id": "CLM-0007", "claim_id": "CLM-0007"})
    out = events.get_outputs()[0]
    assert out["classification"]["verdict"] == "amber"
    assert out["ok"] is True
    assert out["verdict"] == "amber"


@pytest.mark.asyncio
async def test_classify_graph_blocks_malformed_payload():
    bad = {"raw": "model went off-script", "parse_error": True}
    with patch(
        "api.functions.graphs.executors.agents.agent_rag_classifier.execute",
        AsyncMock(return_value={"classification": bad}),
    ):
        wf = build_classify_workflow()
        events = await wf.run({"workflow_id": "CLM-broken", "claim_id": "CLM-broken"})
    out = events.get_outputs()[0]
    assert out["ok"] is False
    assert "parse_error" in (out.get("blocked_reason") or "")


@pytest.mark.asyncio
async def test_classify_graph_blocks_missing_required_field():
    bad = {
        "verdict": "green",
        "reasoning": "fine",
        "confidence": 0.9,
        "competing_interpretations": [],
        # missing policy_clause
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_rag_classifier.execute",
        AsyncMock(return_value={"classification": bad}),
    ):
        wf = build_classify_workflow()
        events = await wf.run({"workflow_id": "CLM-x", "claim_id": "CLM-x"})
    out = events.get_outputs()[0]
    assert out["ok"] is False
    assert "policy_clause" in (out.get("blocked_reason") or "")


@pytest.mark.asyncio
async def test_classify_graph_blocks_invalid_verdict_value():
    bad = {
        "verdict": "purple",
        "policy_clause": "§3.1",
        "reasoning": "x",
        "confidence": 0.5,
        "competing_interpretations": [],
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_rag_classifier.execute",
        AsyncMock(return_value={"classification": bad}),
    ):
        wf = build_classify_workflow()
        events = await wf.run({"workflow_id": "CLM-y", "claim_id": "CLM-y"})
    out = events.get_outputs()[0]
    assert out["ok"] is False
    assert "verdict" in (out.get("blocked_reason") or "")
