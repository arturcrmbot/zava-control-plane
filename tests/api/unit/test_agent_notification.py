"""agent_notification tests — mocks the SDK session wrapper."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.executors.agents import agent_notification


@pytest.mark.asyncio
async def test_skips_notification_when_verdict_not_red():
    with patch.object(agent_notification, "run_agent_session", AsyncMock()) as mock_run:
        result = await agent_notification.execute({
            "claim_id": "CLM-A", "verdict": "amber",
            "policy_clause": "§3.1", "escalation": {"tier": "warning"},
        })
    mock_run.assert_not_called()
    assert result["notification"] is None
    assert result["skip_reason"] == "verdict=amber"


@pytest.mark.asyncio
async def test_composes_notification_for_red_with_correct_tools():
    fake = {
        "subject": "Action required: claim CLM-R flagged (escalation)",
        "adaptive_card": {"type": "AdaptiveCard", "version": "1.5", "body": []},
        "email_body": "Your claim CLM-R was flagged...",
        "policy_clause": "§3.1 Meals — UK per-attendee cap GBP 75",
        "tier": "escalation",
    }
    with patch.object(agent_notification, "run_agent_session", AsyncMock(return_value=fake)) as mock_run:
        with patch.object(agent_notification, "_emit_notification_event") as mock_emit:
            result = await agent_notification.execute({
                "claim_id": "CLM-R", "verdict": "red",
                "policy_clause": "§3.1 Meals — UK per-attendee cap GBP 75",
                "escalation": {"tier": "escalation"},
            })

    assert result["notification"] == fake
    mock_run.assert_awaited_once()
    _, kwargs = mock_run.call_args
    assert "CLM-R" in kwargs["prompt"]
    assert "escalation" in kwargs["prompt"]
    assert kwargs["skill_label"] == "notification-composer"
    tool_names = {t.name for t in kwargs["tools"]}
    assert tool_names == {"claim_summary", "policy_cite"}
    # The notification.sent event is fired with the composed payload.
    mock_emit.assert_called_once_with("CLM-R", fake)


@pytest.mark.asyncio
async def test_default_tier_when_escalation_missing():
    fake = {"subject": "x", "adaptive_card": {"type": "AdaptiveCard", "body": []},
            "email_body": "x", "policy_clause": "§3.1", "tier": "warning"}
    with patch.object(agent_notification, "run_agent_session", AsyncMock(return_value=fake)):
        with patch.object(agent_notification, "_emit_notification_event"):
            result = await agent_notification.execute({
                "claim_id": "CLM-R", "verdict": "red",
                "policy_clause": "§3.1",
            })
    assert result["notification"] == fake
