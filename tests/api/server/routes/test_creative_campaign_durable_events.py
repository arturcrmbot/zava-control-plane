"""POC3 Phase 5 — internal/durable-event handlers for creative-campaign.

Verifies:
  1. `creative.phase.output` checkpoint stashes data onto workflow.payload[slot].
  2. `concept_lock_decision` (and the other three creative HITL events)
     raise the corresponding Durable orchestration event when posted from
     the UI (the manual path used by the "Lock route" button in
     CreativeCampaignArtefacts).
"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.routes.internal_durable_event import router as durable_router
from api.server.services import pending_gates
from api.server.state import app_state
from api.shared.types import Workflow


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(durable_router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    pending_gates.reset()
    app_state.store._workflows.clear()
    app_state.store._exceptions.clear()
    yield
    pending_gates.reset()


def _seed_workflow(wid: str = "CMP-T1", *, awaiting_hitl: bool = False) -> Workflow:
    now = time.time()
    w = Workflow(
        id=wid,
        type="creative-campaign",
        status="awaiting_hitl" if awaiting_hitl else "in_progress",
        current_phase="brief_capture",
        created_at=now,
        sla_due_at=now + 86400,
        jurisdiction="UK-WPP",
        agency="Ogilvy",
        payload={"brief": {"id": "BRF-001", "client_brand": "Solene"}},
        orchestration_instance_id=f"INST-{wid}",
    )
    app_state.store.upsert_workflow(w)
    return w


def test_creative_phase_output_stashes_brief(client):
    _seed_workflow("CMP-P1")
    resp = client.post("/internal/durable-event", json={
        "workflow_id": "CMP-P1",
        "kind": "creative.phase.output",
        "payload": {
            "slot": "brief_synthesis",
            "data": {
                "brief_json": {
                    "audience": "test audience",
                    "mandatory_messages": ["m1"],
                    "kpis": {"awareness": "+10%"},
                },
            },
        },
    })
    assert resp.status_code == 200
    w = app_state.store.get_workflow("CMP-P1")
    assert w is not None
    assert "brief_synthesis" in w.payload
    assert w.payload["brief_synthesis"]["brief_json"]["audience"] == "test audience"


def test_creative_phase_output_stashes_concept_routes(client):
    _seed_workflow("CMP-P2")
    routes = [
        {"route_name": "route-A", "headline": "Origin",
         "stills": ["a/1.svg", "a/2.svg"], "brand_fit": 0.9, "distinctiveness": 0.8},
        {"route_name": "route-B", "headline": "Pulse",
         "stills": ["b/1.svg", "b/2.svg"], "brand_fit": 0.85, "distinctiveness": 0.9},
    ]
    resp = client.post("/internal/durable-event", json={
        "workflow_id": "CMP-P2",
        "kind": "creative.phase.output",
        "payload": {"slot": "concept_fanout", "data": {"routes": routes}},
    })
    assert resp.status_code == 200
    w = app_state.store.get_workflow("CMP-P2")
    assert len(w.payload["concept_fanout"]["routes"]) == 2
    assert w.payload["concept_fanout"]["routes"][1]["route_name"] == "route-B"


def test_creative_phase_output_overwrites_same_slot(client):
    """Re-emitting the same slot replaces the prior value."""
    _seed_workflow("CMP-P3")
    for routes in [
        [{"route_name": "x", "stills": [], "brand_fit": 0.5, "distinctiveness": 0.5}],
        [{"route_name": "y", "stills": [], "brand_fit": 0.7, "distinctiveness": 0.7},
         {"route_name": "z", "stills": [], "brand_fit": 0.8, "distinctiveness": 0.8}],
    ]:
        client.post("/internal/durable-event", json={
            "workflow_id": "CMP-P3",
            "kind": "creative.phase.output",
            "payload": {"slot": "concept_fanout", "data": {"routes": routes}},
        })
    w = app_state.store.get_workflow("CMP-P3")
    assert len(w.payload["concept_fanout"]["routes"]) == 2


def test_concept_lock_decision_raises_orchestration_event(client, monkeypatch):
    """The UI's 'Lock route' button POSTs concept_lock_decision; handler
    raises the matching Durable external event."""
    raised: list[tuple[str, str, dict]] = []

    async def _fake(instance_id, event_name, payload):
        raised.append((instance_id, event_name, payload))

    import api.server.services.durable_client as dc
    monkeypatch.setattr(dc, "raise_orchestration_event", _fake)

    _seed_workflow("CMP-P4", awaiting_hitl=True)
    resp = client.post("/internal/durable-event", json={
        "workflow_id": "CMP-P4",
        "kind": "concept_lock_decision",
        "payload": {
            "decision": "approve",
            "locked_route": "route-B",
            "reason": "operator-locked route-B via Control Plane",
        },
    })
    assert resp.status_code == 200
    assert raised, "no orchestration event raised"
    inst, event_name, payload = raised[0]
    assert inst == "INST-CMP-P4"
    assert event_name == "concept_lock_decision"
    assert payload["locked_route"] == "route-B"


@pytest.mark.parametrize("kind", [
    "brief_approval_decision",
    "storyboard_approval_decision",
    "final_signoff_decision",
])
def test_creative_decision_handlers_raise_for_each_gate(client, monkeypatch, kind):
    raised: list[tuple[str, str, dict]] = []

    async def _fake(instance_id, event_name, payload):
        raised.append((instance_id, event_name, payload))

    import api.server.services.durable_client as dc
    monkeypatch.setattr(dc, "raise_orchestration_event", _fake)

    _seed_workflow("CMP-P5", awaiting_hitl=True)
    resp = client.post("/internal/durable-event", json={
        "workflow_id": "CMP-P5",
        "kind": kind,
        "payload": {"decision": "approve"},
    })
    assert resp.status_code == 200
    assert raised, f"no event raised for {kind}"
    assert raised[0][1] == kind
