from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.executors.agents import agent_arbitration


@pytest.mark.asyncio
async def test_returns_recommendation_payload():
    fake = {
        "recommendation": "accept-justification",
        "rationale": "Named senior client at Zava NA; PREC-0017 supports.",
        "cited_precedent_id": "PREC-0017",
        "policy_clause": "§3.1 Meals — UK per-attendee cap GBP 75",
        "confidence": 0.86,
    }
    with patch.object(agent_arbitration, "run_agent_session", AsyncMock(return_value=fake)) as mock_run:
        result = await agent_arbitration.execute({
            "claim_id": "CLM-0042",
            "policy_clause": "§3.1 Meals — UK per-attendee cap GBP 75",
            "escalation_tier": "warning",
            "justification": {"text": "Client dinner with VP."},
        })
    assert result["arbitration"] == fake
    mock_run.assert_awaited_once()
    _, kwargs = mock_run.call_args
    assert kwargs["skill_label"] == "arbitration"
    assert {"precedents_search", "policy_search"} == {t.name for t in kwargs["tools"]}
    assert "CLM-0042" in kwargs["prompt"]


@pytest.mark.asyncio
async def test_default_recommendation_when_justification_missing():
    """If the prompt has no justification text, the executor still proceeds —
    the model is responsible for deciding from the absent context."""
    with patch.object(agent_arbitration, "run_agent_session", AsyncMock(return_value={
        "recommendation": "require-repayment", "rationale": "x",
        "cited_precedent_id": None, "policy_clause": "§1", "confidence": 0.5,
    })):
        result = await agent_arbitration.execute({
            "claim_id": "CLM-X", "policy_clause": "§1", "escalation_tier": "warning",
        })
    assert result["arbitration"]["recommendation"] == "require-repayment"
