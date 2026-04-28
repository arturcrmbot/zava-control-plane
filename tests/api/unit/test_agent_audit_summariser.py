"""agent_audit_summariser tests — mocks the SDK session wrapper."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.executors.agents import agent_audit_summariser


@pytest.mark.asyncio
async def test_returns_audit_payload():
    fake = {
        "summary": "EMP-0001 submitted CLM-0042 (GBP 89.50 meals) at 10:00 on 2026-04-01. The classifier returned amber per §3.1; the workflow auto-routed to the SSC reviewer queue and was accepted at 12:32 by reviewer-1.",
        "claim_id": "CLM-0042",
        "workflow_id": "EXP-0001",
    }
    with patch.object(agent_audit_summariser, "run_agent_session", AsyncMock(return_value=fake)) as mock_run:
        with patch.object(agent_audit_summariser, "_emit_audit_event") as mock_emit:
            result = await agent_audit_summariser.execute({
                "workflow_id": "EXP-0001",
                "claim": {"claim_id": "CLM-0042"},
            })

    assert result["audit"] == fake
    mock_run.assert_awaited_once()
    _, kwargs = mock_run.call_args
    assert "EXP-0001" in kwargs["prompt"]
    assert "CLM-0042" in kwargs["prompt"]
    assert kwargs["skill_label"] == "audit-summariser"
    tool_names = {t.name for t in kwargs["tools"]}
    assert tool_names == {"claim_summary", "audit_query"}
    mock_emit.assert_called_once()


@pytest.mark.asyncio
async def test_handles_missing_claim_block_gracefully():
    """If the orchestrator passes only workflow_id (no claim block), the
    agent still composes — the model is responsible for falling back via
    the tools."""
    fake = {"summary": "x", "claim_id": None, "workflow_id": "EXP-Z"}
    with patch.object(agent_audit_summariser, "run_agent_session", AsyncMock(return_value=fake)):
        with patch.object(agent_audit_summariser, "_emit_audit_event"):
            result = await agent_audit_summariser.execute({"workflow_id": "EXP-Z"})
    assert result["audit"]["workflow_id"] == "EXP-Z"
