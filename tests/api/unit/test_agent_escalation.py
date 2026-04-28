"""agent_escalation tests — mocks the SDK session wrapper."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.executors.agents import agent_escalation


@pytest.mark.asyncio
async def test_skips_escalation_on_green_verdict():
    """Green verdicts have nothing to enforce; the agent short-circuits and
    does not spin up a session."""
    with patch.object(agent_escalation, "run_agent_session", AsyncMock()) as mock_run:
        result = await agent_escalation.execute({
            "claim_id": "CLM-G", "employee_id": "EMP-1",
            "verdict": "green", "category": "meals",
        })
    mock_run.assert_not_called()
    assert result["escalation"] is None


@pytest.mark.asyncio
async def test_returns_recommendation_payload():
    fake = {
        "tier": "escalation",
        "prior_breach_count": 1,
        "same_category_priors": 0,
        "rationale": "1 prior breach in 90 days, different category — second-strike escalation.",
        "confidence": 0.85,
    }
    with patch.object(agent_escalation, "run_agent_session", AsyncMock(return_value=fake)) as mock_run:
        result = await agent_escalation.execute({
            "claim_id": "CLM-0007",
            "employee_id": "EMP-0001",
            "verdict": "amber",
            "category": "accommodation",
        })

    assert result["escalation"] == fake
    mock_run.assert_awaited_once()
    _, kwargs = mock_run.call_args
    assert "CLM-0007" in kwargs["prompt"]
    assert "EMP-0001" in kwargs["prompt"]
    assert "amber" in kwargs["prompt"]
    assert kwargs["skill_label"] == "escalation-advisor"
    tool_names = {t.name for t in kwargs["tools"]}
    assert tool_names == {"employee_history"}
