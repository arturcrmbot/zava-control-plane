"""agent_rag_classifier executor tests — mocks the SDK session wrapper."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.executors.agents import agent_rag_classifier


@pytest.mark.asyncio
async def test_returns_classifier_payload():
    fake = {
        "verdict": "amber",
        "policy_clause": "§3.1 Meals — UK per-attendee cap GBP 75",
        "reasoning": "Within 110% of cap with named attendees; reviewer should confirm.",
        "confidence": 0.7,
        "competing_interpretations": [],
    }
    with patch.object(agent_rag_classifier, "run_agent_session", AsyncMock(return_value=fake)) as mock_run:
        result = await agent_rag_classifier.execute({"claim_id": "CLM-0007"})

    assert result["classification"] == fake
    mock_run.assert_awaited_once()
    _, kwargs = mock_run.call_args
    assert "CLM-0007" in kwargs["prompt"]
    assert kwargs["skill_label"] == "rag-classifier"
    tool_names = {t.name for t in kwargs["tools"]}
    assert tool_names == {"policy_search", "claim_get_structured"}


@pytest.mark.asyncio
async def test_passes_through_parse_error():
    parse_err = {"raw": "model talked instead of JSON", "parse_error": True}
    with patch.object(agent_rag_classifier, "run_agent_session", AsyncMock(return_value=parse_err)):
        result = await agent_rag_classifier.execute({"claim_id": "CLM-0001"})
    assert result["classification"]["parse_error"] is True
