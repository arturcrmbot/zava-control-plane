"""AC #11 — `simulate_region_failure` simulator command.

Marks a wall-clock window in the audit trail during which the operator
stops the Durable Functions host. Helper itself doesn't stop anything;
it just emits `region.failure.simulated` and snapshots in-flight counts.
"""
from __future__ import annotations
from unittest.mock import patch

import pytest

from api.server.services import simulator_orchestrator
from api.shared.events import FleetEvent


@pytest.mark.asyncio
async def test_simulate_region_failure_emits_event_with_snapshot():
    captured: list[FleetEvent] = []
    with patch.object(
        simulator_orchestrator.app_state.bus, "emit",
        side_effect=lambda e: captured.append(e),
    ):
        result = await simulator_orchestrator.simulate_region_failure(stop_seconds=0)

    assert result["stop_seconds"] == 0
    assert "in_flight" in result
    assert "paused_at_hitl" in result

    assert len(captured) == 1
    ev = captured[0]
    assert ev.type == "region.failure.simulated"
    assert ev.workflow_id == "*"
    extra = ev.model_dump()
    assert extra["stop_seconds"] == 0
    assert extra["in_flight_count"] == result["in_flight"]
    assert extra["paused_at_hitl"] == result["paused_at_hitl"]


@pytest.mark.asyncio
async def test_simulate_region_failure_default_stop_seconds():
    """Defaults to 10s window; we patch sleep so the test stays fast."""
    with patch.object(simulator_orchestrator.app_state.bus, "emit"), \
         patch("api.server.services.simulator_orchestrator.asyncio.sleep") as mock_sleep:
        result = await simulator_orchestrator.simulate_region_failure()

    assert result["stop_seconds"] == 10
    mock_sleep.assert_awaited_once_with(10)
