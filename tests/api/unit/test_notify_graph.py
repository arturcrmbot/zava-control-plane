"""Phase 5 (Notify) graph: agent_notification only, on Red verdicts."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.notify import build_notify_workflow


@pytest.mark.asyncio
async def test_red_path_runs_notification_composer():
    fake = {
        "subject": "Action required: CLM-R",
        "adaptive_card": {"type": "AdaptiveCard", "body": []},
        "email_body": "...",
        "policy_clause": "§3.1",
        "tier": "warning",
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_notification.run_agent_session",
        AsyncMock(return_value=fake),
    ):
        wf = build_notify_workflow()
        events = await wf.run({
            "workflow_id": "CLM-R", "claim_id": "CLM-R",
            "verdict": "red", "policy_clause": "§3.1",
            "escalation": {"tier": "warning"},
        })
    out = events.get_outputs()[0]
    assert out["notification"] == fake


@pytest.mark.asyncio
async def test_non_red_short_circuits():
    """If Phase 5 is reached with a non-red verdict (shouldn't happen via the
    orchestrator, but defensively), the notification agent skips and the
    graph terminates cleanly."""
    with patch(
        "api.functions.graphs.executors.agents.agent_notification.run_agent_session",
        AsyncMock(),
    ) as mock_run:
        wf = build_notify_workflow()
        events = await wf.run({
            "workflow_id": "CLM-A", "claim_id": "CLM-A",
            "verdict": "amber",
        })
    mock_run.assert_not_called()
    out = events.get_outputs()[0]
    assert out["notification"] is None
