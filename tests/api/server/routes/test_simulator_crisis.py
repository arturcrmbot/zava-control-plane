"""POST /api/simulator/crisis/client-loss — pitch-h7 wow-moment.

Single-call event that drops 4 simultaneous workflows across the org
(contract-review offboarding, talent-redeployment, intercompany-recharge
unwind, board-prep loss entry) plus a single ``crisis.injected`` shockwave
event for the cosmic lens.
"""
from __future__ import annotations

import pytest

from api.server.services.entity_graph import EntityWrite
from api.server.state import app_state
from api.shared.events import FleetEvent

from tests.api.server.routes._entities_fixtures import client, graph  # noqa: F401


_CLIENT_ID = "ORG-client-soylent-group"


@pytest.fixture
def seeded_client(graph):  # noqa: F811
    """Upsert the client Organisation so entities.get() finds it."""
    graph.upsert(EntityWrite(
        kind="Organisation",
        id=_CLIENT_ID,
        attrs={"name": "Soylent Group"},
    ))
    return _CLIENT_ID


@pytest.fixture
def crisis_events():
    """Subscribe to the bus and return a captured-event list.

    Detaches the handler on teardown so the bus doesn't accumulate test
    listeners across runs (the bus is a process-singleton).
    """
    captured: list[FleetEvent] = []
    off = app_state.bus.on_any(captured.append)
    try:
        yield captured
    finally:
        off()


def test_crisis_unknown_client_returns_404(graph, client):  # noqa: F811
    r = client.post(
        "/api/simulator/crisis/client-loss",
        json={"client_id": "ORG-client-does-not-exist", "reason": "demo"},
    )
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_crisis_valid_client_returns_202_with_4_ids(seeded_client, client):
    r = client.post(
        "/api/simulator/crisis/client-loss",
        json={"client_id": seeded_client, "reason": "renegotiated agency RFP"},
    )
    assert r.status_code == 202
    body = r.json()
    ids = body["spawned_workflow_ids"]
    assert isinstance(ids, list)
    assert len(ids) == 4
    # Each id must be unique and use the registry prefixes.
    assert len(set(ids)) == 4
    prefixes = {wid.split("-", 1)[0] for wid in ids}
    assert prefixes == {"CRW", "TLR", "ICR", "BRD"}


def test_crisis_spawned_workflows_are_persisted(seeded_client, client):
    r = client.post(
        "/api/simulator/crisis/client-loss",
        json={"client_id": seeded_client, "reason": "demo"},
    )
    assert r.status_code == 202
    ids = r.json()["spawned_workflow_ids"]
    seen_types: set[str] = set()
    for wid in ids:
        wf = app_state.store.get_workflow(wid)
        assert wf is not None, f"spawned workflow {wid} missing from store"
        seen_types.add(wf.type)
        # Each payload carries the originating client_id so downstream
        # views can join back to the loss event.
        assert wf.payload.get("client_id") == seeded_client
    assert seen_types == {
        "contract-review", "talent-redeployment",
        "intercompany-recharge", "board-prep",
    }


def test_crisis_payload_shapes_match_spec(seeded_client, client):
    r = client.post(
        "/api/simulator/crisis/client-loss",
        json={"client_id": seeded_client, "reason": "RFP loss"},
    )
    assert r.status_code == 202
    by_type = {}
    for wid in r.json()["spawned_workflow_ids"]:
        wf = app_state.store.get_workflow(wid)
        by_type[wf.type] = wf.payload
    assert by_type["contract-review"]["purpose"] == "offboarding"
    assert by_type["intercompany-recharge"]["direction"] == "reverse"
    assert by_type["board-prep"]["kind"] == "client_loss"
    assert "affected_subsidiaries" in by_type["talent-redeployment"]
    assert isinstance(by_type["talent-redeployment"]["affected_subsidiaries"], list)


def test_crisis_emits_shockwave_event_exactly_once(
    seeded_client, client, crisis_events,
):
    r = client.post(
        "/api/simulator/crisis/client-loss",
        json={"client_id": seeded_client, "reason": "demo"},
    )
    assert r.status_code == 202
    ids = r.json()["spawned_workflow_ids"]

    crisis_events_only = [e for e in crisis_events if e.type == "crisis.injected"]
    assert len(crisis_events_only) == 1
    ev = crisis_events_only[0]
    assert getattr(ev, "client_id", None) == seeded_client
    assert getattr(ev, "reason", None) == "demo"
    assert sorted(getattr(ev, "spawned_workflow_ids", [])) == sorted(ids)


def test_crisis_audit_log_entry_shape(seeded_client, client):
    before = len(app_state.audit.list())
    r = client.post(
        "/api/simulator/crisis/client-loss",
        json={"client_id": seeded_client, "reason": "lost the pitch"},
    )
    assert r.status_code == 202
    ids = r.json()["spawned_workflow_ids"]

    new_entries = app_state.audit.list()[before:]
    crisis_entries = [e for e in new_entries if e["action"] == "crisis.injected"]
    assert len(crisis_entries) == 1
    details = crisis_entries[0]["details"]
    assert details["client_id"] == seeded_client
    assert details["reason"] == "lost the pitch"
    assert sorted(details["spawned_workflow_ids"]) == sorted(ids)
