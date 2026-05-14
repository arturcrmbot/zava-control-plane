"""apply_verdict_routing tests — deterministic Phase 4 router."""
from __future__ import annotations

import pytest

from api.functions.graphs.executors.deterministic import apply_verdict_routing


@pytest.mark.asyncio
async def test_green_routes_to_auto_approve():
    out = await apply_verdict_routing.execute({"verdict": "green"})
    assert out["routed_to"] == "auto-approve"
    assert out["verdict"] == "green"
    assert out["escalation_tier"] is None


@pytest.mark.asyncio
async def test_amber_routes_to_reviewer_queue_with_tier():
    out = await apply_verdict_routing.execute({
        "verdict": "amber",
        "escalation": {"tier": "warning"},
    })
    assert out["routed_to"] == "reviewer-queue"
    assert out["escalation_tier"] == "warning"


@pytest.mark.asyncio
async def test_red_routes_to_notify_with_tier():
    out = await apply_verdict_routing.execute({
        "verdict": "red",
        "escalation": {"tier": "major-violation"},
    })
    assert out["routed_to"] == "notify"
    assert out["escalation_tier"] == "major-violation"


@pytest.mark.asyncio
async def test_route_override_short_circuits_verdict():
    """The policy page can force-route everything (e.g. all amber to
    auto-approve while clearing a backlog). Override wins."""
    out = await apply_verdict_routing.execute({
        "verdict": "amber",
        "escalation": {"tier": "warning"},
        "route_override": "auto-approve",
    })
    assert out["routed_to"] == "auto-approve"
    assert out["override_applied"] is True
    # Original verdict is preserved on output for audit.
    assert out["verdict"] == "amber"


@pytest.mark.asyncio
async def test_invalid_override_falls_back_to_matrix():
    out = await apply_verdict_routing.execute({
        "verdict": "amber",
        "route_override": "send-to-mars",
    })
    assert out["routed_to"] == "reviewer-queue"
    assert "override_applied" not in out
