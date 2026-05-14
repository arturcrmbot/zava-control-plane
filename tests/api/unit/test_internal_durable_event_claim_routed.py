"""POST `kind=claim_routed` to /internal/durable-event and assert the bus
fires a `claim.routed.<verdict>` FleetEvent. This is the bridge that lets
the Fleet Manager wake on red routes before any HITL gate trips.
"""
from __future__ import annotations
from fastapi.testclient import TestClient
from tests.api._helpers.durable_event import signed_post

import api.server.main  # noqa: F401  side-effect: wires bus → SSE topics
from api.server.main import app
from api.server.state import app_state
from api.shared.events import FleetEvent


def _capture_fleet_events() -> tuple[list[FleetEvent], callable]:
    captured: list[FleetEvent] = []
    unsub = app_state.bus.on_any(captured.append)
    return captured, unsub


def test_claim_routed_red_emits_claim_routed_red_on_bus():
    captured, unsub = _capture_fleet_events()
    try:
        client = TestClient(app)
        r = signed_post(client, {
            "workflow_id": "CLM-R-1",
            "instance_id": "I-R-1",
            "kind": "claim_routed",
            "payload": {
                "verdict": "red",
                "routed_to": "notify",
                "escalation_tier": "major-violation",
            },
        })
        assert r.status_code == 200
    finally:
        unsub()

    routed = [e for e in captured if e.type == "claim.routed.red"]
    assert len(routed) == 1
    ev = routed[0]
    assert ev.workflow_id == "CLM-R-1"
    assert getattr(ev, "routed_to") == "notify"
    assert getattr(ev, "escalation_tier") == "major-violation"


def test_claim_routed_amber_emits_amber_not_red():
    captured, unsub = _capture_fleet_events()
    try:
        client = TestClient(app)
        r = signed_post(client, {
            "workflow_id": "CLM-A-1",
            "instance_id": "I-A-1",
            "kind": "claim_routed",
            "payload": {
                "verdict": "amber",
                "routed_to": "reviewer-queue",
                "escalation_tier": "warning",
            },
        })
        assert r.status_code == 200
    finally:
        unsub()

    types = [e.type for e in captured]
    assert "claim.routed.amber" in types
    assert "claim.routed.red" not in types


def test_claim_routed_unknown_verdict_emits_nothing():
    captured, unsub = _capture_fleet_events()
    try:
        client = TestClient(app)
        r = signed_post(client, {
            "workflow_id": "CLM-X-1",
            "instance_id": "I-X-1",
            "kind": "claim_routed",
            "payload": {"verdict": "unknown"},
        })
        assert r.status_code == 200
    finally:
        unsub()

    routed_types = [e.type for e in captured if e.type.startswith("claim.routed.")]
    assert routed_types == []
