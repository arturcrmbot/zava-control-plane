"""Phase 3 (Validate Receipt) graph: agent_receipt_validator + schema validator."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.receipt import build_receipt_workflow


@pytest.mark.asyncio
async def test_receipt_graph_passes_well_formed_match():
    fake = {
        "verdict": "match", "flavour": "correct",
        "evidence": "Receipt totals match within rounding.",
        "confidence": 0.93,
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_receipt_validator.execute",
        AsyncMock(return_value={"receipt_validation": fake}),
    ):
        wf = build_receipt_workflow()
        events = await wf.run({"workflow_id": "CLM-0000", "claim_id": "CLM-0000"})
    out = events.get_outputs()[0]
    assert out["ok"] is True
    assert out["flavour"] == "correct"
    assert out["verdict"] == "match"


@pytest.mark.asyncio
async def test_receipt_graph_passes_well_formed_mismatch():
    fake = {
        "verdict": "mismatch", "flavour": "wrong-amount",
        "evidence": "Receipt total USD 234.50, claim asserts USD 156.33.",
        "confidence": 0.87,
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_receipt_validator.execute",
        AsyncMock(return_value={"receipt_validation": fake}),
    ):
        wf = build_receipt_workflow()
        events = await wf.run({"workflow_id": "CLM-X", "claim_id": "CLM-X"})
    out = events.get_outputs()[0]
    assert out["ok"] is True
    assert out["flavour"] == "wrong-amount"
    assert out["verdict"] == "mismatch"


@pytest.mark.asyncio
async def test_receipt_graph_blocks_parse_error():
    bad = {"raw": "model went off-script", "parse_error": True}
    with patch(
        "api.functions.graphs.executors.agents.agent_receipt_validator.execute",
        AsyncMock(return_value={"receipt_validation": bad}),
    ):
        wf = build_receipt_workflow()
        events = await wf.run({"workflow_id": "CLM-broken", "claim_id": "CLM-broken"})
    out = events.get_outputs()[0]
    assert out["ok"] is False
    assert "parse_error" in out["blocked_reason"]


@pytest.mark.asyncio
async def test_receipt_graph_blocks_verdict_flavour_disagreement():
    """A 'match' verdict with a non-correct flavour is contradictory — block it."""
    bad = {
        "verdict": "match", "flavour": "wrong-amount",
        "evidence": "x", "confidence": 0.5,
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_receipt_validator.execute",
        AsyncMock(return_value={"receipt_validation": bad}),
    ):
        wf = build_receipt_workflow()
        events = await wf.run({"workflow_id": "CLM-bad", "claim_id": "CLM-bad"})
    out = events.get_outputs()[0]
    assert out["ok"] is False
    assert "verdict/flavour" in out["blocked_reason"]


@pytest.mark.asyncio
async def test_receipt_graph_blocks_unknown_flavour():
    bad = {
        "verdict": "mismatch", "flavour": "purple-unicorn",
        "evidence": "x", "confidence": 0.5,
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_receipt_validator.execute",
        AsyncMock(return_value={"receipt_validation": bad}),
    ):
        wf = build_receipt_workflow()
        events = await wf.run({"workflow_id": "CLM-y", "claim_id": "CLM-y"})
    out = events.get_outputs()[0]
    assert out["ok"] is False
    assert "flavour" in out["blocked_reason"]
