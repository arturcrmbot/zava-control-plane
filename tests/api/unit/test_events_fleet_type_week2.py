"""Week 2 expense-domain event vocabulary on FleetEventType.

Verifies the new types round-trip via FleetEvent and that they auto-broadcast
to the `fleet` SSE topic via the bus.on_any → hub.broadcast wiring in
api.server.main (same pathway accuracy.* uses).
"""
from __future__ import annotations
import asyncio
import json
from typing import get_args

import pytest

# Side-effect import: wires app_state.bus.on_any → hub.broadcast("fleet", ...)
import api.server.main  # noqa: F401
from api.server.state import app_state
from api.shared.events import FleetEvent, FleetEventType


WEEK2_TYPES = [
    "claim.routed.green",
    "claim.routed.amber",
    "claim.routed.red",
    "receipt.mismatch.detected",
    "escalation.tier.assigned",
    "notification.sent",
    "justification.received",
]


def test_week2_event_types_present_on_literal():
    types = set(get_args(FleetEventType))
    missing = set(WEEK2_TYPES) - types
    assert not missing, f"FleetEventType missing Week 2 types: {missing}"


@pytest.mark.parametrize("event_type", WEEK2_TYPES)
def test_week2_event_type_round_trips_through_fleet_event(event_type):
    ev = FleetEvent(type=event_type, workflow_id="W-test")
    assert ev.type == event_type
    assert ev.workflow_id == "W-test"


@pytest.mark.asyncio
async def test_receipt_mismatch_event_broadcasts_to_fleet_topic():
    q = app_state.hub.subscribe("fleet")
    try:
        ev = FleetEvent(
            type="receipt.mismatch.detected",
            workflow_id="CLM-0042",
            flavour="wrong-amount",
        )
        app_state.bus.emit(ev)
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        data = json.loads(msg)
        assert data["type"] == "receipt.mismatch.detected"
        assert data["workflow_id"] == "CLM-0042"
        assert data["flavour"] == "wrong-amount"
    finally:
        app_state.hub.unsubscribe("fleet", q)


@pytest.mark.asyncio
async def test_claim_routed_red_event_broadcasts_to_fleet_topic():
    q = app_state.hub.subscribe("fleet")
    try:
        ev = FleetEvent(
            type="claim.routed.red",
            workflow_id="CLM-0099",
            tier="director",
        )
        app_state.bus.emit(ev)
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        data = json.loads(msg)
        assert data["type"] == "claim.routed.red"
        assert data["tier"] == "director"
    finally:
        app_state.hub.unsubscribe("fleet", q)


def test_week2_types_not_in_wake_types():
    """Week 2 events are routine workflow signal — must not wake the Fleet Manager."""
    from api.shared.events import WAKE_TYPES
    overlap = set(WEEK2_TYPES) & WAKE_TYPES
    assert not overlap, f"Week 2 types must not wake fleet manager: {overlap}"
