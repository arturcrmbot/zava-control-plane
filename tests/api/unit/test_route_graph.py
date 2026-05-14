"""Phase 4 (Route by Verdict) graph: agent_escalation + apply_verdict_routing."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.route import build_route_workflow


@pytest.mark.asyncio
async def test_green_routes_to_auto_approve_no_escalation_call():
    """Green verdicts skip the escalation advisor (no model call)."""
    with patch(
        "api.functions.graphs.executors.agents.agent_escalation.run_agent_session",
        AsyncMock(),
    ) as mock_run:
        wf = build_route_workflow()
        events = await wf.run({
            "workflow_id": "CLM-G", "claim_id": "CLM-G",
            "employee_id": "EMP-1", "verdict": "green", "category": "meals",
        })
    out = events.get_outputs()[0]
    mock_run.assert_not_called()
    assert out["routed_to"] == "auto-approve"
    assert out["escalation_tier"] is None


@pytest.mark.asyncio
async def test_amber_routes_to_reviewer_queue_with_tier():
    fake_escalation = {
        "tier": "warning", "prior_breach_count": 0, "same_category_priors": 0,
        "rationale": "First breach.", "confidence": 0.9,
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_escalation.run_agent_session",
        AsyncMock(return_value=fake_escalation),
    ):
        wf = build_route_workflow()
        events = await wf.run({
            "workflow_id": "CLM-A", "claim_id": "CLM-A",
            "employee_id": "EMP-1", "verdict": "amber", "category": "accommodation",
        })
    out = events.get_outputs()[0]
    assert out["routed_to"] == "reviewer-queue"
    assert out["verdict"] == "amber"
    assert out["escalation_tier"] == "warning"


@pytest.mark.asyncio
async def test_red_routes_to_notify_with_major_violation_tier():
    fake_escalation = {
        "tier": "major-violation", "prior_breach_count": 2,
        "same_category_priors": 1,
        "rationale": "Two priors, same-category override.",
        "confidence": 0.92,
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_escalation.run_agent_session",
        AsyncMock(return_value=fake_escalation),
    ):
        wf = build_route_workflow()
        events = await wf.run({
            "workflow_id": "CLM-R", "claim_id": "CLM-R",
            "employee_id": "EMP-0001", "verdict": "red", "category": "meals",
        })
    out = events.get_outputs()[0]
    assert out["routed_to"] == "notify"
    assert out["escalation_tier"] == "major-violation"
