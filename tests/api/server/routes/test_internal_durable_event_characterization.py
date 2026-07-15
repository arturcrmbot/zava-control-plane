"""Characterization of the /internal/durable-event ingestion behaviour.

Captures the durable-event ingestion side effects (workflow history, phase
append/update, StateStore status transitions, ledger, and FleetEvent bus
emission) as they behave TODAY, before the ingestion logic is extracted into
``api.server.services.workflow_event_ingestor``. The same assertions run after
the extraction to prove the route delegates without any behaviour change.

These go through the signed HTTP route (the only entry point pre-extraction);
the post-extraction ``test_workflow_event_ingestor`` suite exercises the same
behaviour via the non-HTTP service API directly.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from tests.api._helpers.durable_event import setup_secret, signed_post


@pytest.fixture
def client(monkeypatch):
    setup_secret(monkeypatch)
    from api.server.main import app

    return TestClient(app)


def _capture_bus():
    from api.server.routes.internal_durable_event import app_state

    events: list = []
    off = app_state.bus.on_any(lambda ev: events.append(ev))
    return events, off


def _seed_workflow(wid: str, wtype: str = "network-incident"):
    from api.server.routes.internal_durable_event import app_state
    from api.shared.types import Workflow

    now = time.time()
    w = Workflow(
        id=wid,
        type=wtype,
        current_phase="Telemetry Correlation",
        created_at=now,
        sla_due_at=now + 86400,
        jurisdiction="London-Zava",
        agency="Zava-Test",
        payload={},
    )
    app_state.store.upsert_workflow(w)
    return app_state


def test_workflow_started_emits_durable_event_and_history(client):
    events, off = _capture_bus()
    try:
        _seed_workflow("CHAR-START")
        r = signed_post(client, {
            "workflow_id": "CHAR-START",
            "instance_id": "I-1",
            "kind": "workflow.started",
            "payload": {"workflow_type": "network-incident"},
        })
    finally:
        off()
    assert r.status_code == 200
    from api.server.routes.internal_durable_event import app_state

    types = [e.type for e in events]
    assert "workflow.started" in types
    assert "durable.workflow.started" in types
    # workflow_type cache forwards onto emitted events.
    started = next(e for e in events if e.type == "durable.workflow.started")
    assert getattr(started, "workflow_type", None) == "network-incident"
    hist = app_state.orchestration_history.get("CHAR-START")
    assert hist and hist[-1]["kind"] == "workflow.started"


def test_step_started_then_completed_tracks_phases(client):
    events, off = _capture_bus()
    try:
        state = _seed_workflow("CHAR-STEP")
        signed_post(client, {
            "workflow_id": "CHAR-STEP", "instance_id": "I-1",
            "kind": "step.started", "payload": {"step": "Impact Diagnosis"},
        })
        phases_after_start = [(p.name, p.status) for p in state.store.get_phases("CHAR-STEP")]
        w_mid = state.store.get_workflow("CHAR-STEP")
        signed_post(client, {
            "workflow_id": "CHAR-STEP", "instance_id": "I-1",
            "kind": "step.completed",
            "payload": {"step": "Impact Diagnosis", "duration_ms": 5},
        })
    finally:
        off()
    assert ("Impact Diagnosis", "in_progress") in phases_after_start
    assert w_mid.current_phase == "Impact Diagnosis"
    final = [(p.name, p.status) for p in state.store.get_phases("CHAR-STEP")]
    assert ("Impact Diagnosis", "completed") in final
    types = [e.type for e in events]
    assert "workflow.phase.started" in types
    assert "durable.step.started" in types
    assert "workflow.phase.completed" in types
    assert "durable.step.completed" in types


def test_step_started_is_idempotent_on_replay(client):
    _seed_workflow("CHAR-IDEMP")
    for _ in range(3):
        signed_post(client, {
            "workflow_id": "CHAR-IDEMP", "instance_id": "I-1",
            "kind": "step.started", "payload": {"step": "Reroute Planning"},
        })
    from api.server.routes.internal_durable_event import app_state

    phases = [p for p in app_state.store.get_phases("CHAR-IDEMP") if p.name == "Reroute Planning"]
    assert len(phases) == 1


def test_mcp_call_appends_call(client):
    _seed_workflow("CHAR-MCP")
    r = signed_post(client, {
        "workflow_id": "CHAR-MCP", "instance_id": "I-1",
        "kind": "mcp.call",
        "payload": {
            "tool": "getSite", "url": "http://x/mcp/getSite", "method": "POST",
            "request": {"id": "S-1"}, "response": {"ok": True},
            "status_code": 200, "duration_ms": 3,
        },
    })
    assert r.status_code == 200
    from api.server.routes.internal_durable_event import app_state

    calls = app_state.store.get_mcp_calls("CHAR-MCP")
    assert calls and calls[-1].tool == "getSite"


def test_workflow_completed_sets_status_and_resolves(client):
    events, off = _capture_bus()
    try:
        state = _seed_workflow("CHAR-DONE")
        signed_post(client, {
            "workflow_id": "CHAR-DONE", "instance_id": "I-1",
            "kind": "workflow.completed", "payload": {},
        })
    finally:
        off()
    assert state.store.get_workflow("CHAR-DONE").status == "completed"
    types = [e.type for e in events]
    assert "durable.workflow.completed" in types
    assert "workflow.resolved" in types


def test_workflow_rejected_sets_failed_and_emits_workflow_failed(client):
    events, off = _capture_bus()
    try:
        state = _seed_workflow("CHAR-REJ")
        signed_post(client, {
            "workflow_id": "CHAR-REJ", "instance_id": "I-1",
            "kind": "workflow.rejected",
            "payload": {"by": "operator", "reason": "no"},
        })
    finally:
        off()
    assert state.store.get_workflow("CHAR-REJ").status == "failed"
    types = [e.type for e in events]
    assert "workflow.resolved" in types
    assert "workflow.failed" in types
