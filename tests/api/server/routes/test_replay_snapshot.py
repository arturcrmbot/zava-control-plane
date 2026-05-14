"""GET /api/replay/snapshot — pitch-j4 time-scrub snapshot endpoint."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from api.server.services.audit_logger import AuditLogger
from api.server.state import app_state


@pytest.fixture
def fresh_audit(monkeypatch):
    """Swap a clean in-memory AuditLogger so tests don't see other
    tests' entries (the global one is shared via app_state)."""
    a = AuditLogger()
    monkeypatch.setattr(app_state, "audit", a)
    yield a


@pytest.fixture
def client():
    from api.server.main import app
    return TestClient(app)


def test_snapshot_shape_at_now(fresh_audit, client):
    fresh_audit.log("entity.upserted", {
        "id": "vendor:acme",
        "kind": "vendor",
        "workflow_id": "wf1",
        "source_workflows": ["wf1"],
    })
    r = client.get("/api/replay/snapshot", params={"at": time.time()})
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"at", "entities", "in_flight_workflows",
                         "recent_events", "kpis_at"}
    assert any(e["id"] == "vendor:acme" for e in body["entities"])
    # KPI rows are {label, value, unit}.
    for k in body["kpis_at"]:
        assert {"label", "value", "unit"} <= set(k)


def test_snapshot_very_old_at_is_sparse(fresh_audit, client):
    fresh_audit.log("entity.upserted", {
        "id": "vendor:acme",
        "kind": "vendor",
        "workflow_id": "wf1",
        "source_workflows": ["wf1"],
    })
    r = client.get("/api/replay/snapshot", params={"at": 1000.0})
    assert r.status_code == 200
    body = r.json()
    assert body["entities"] == []
    assert body["in_flight_workflows"] == []
    assert body["recent_events"] == []


def test_snapshot_future_at_is_400(fresh_audit, client):
    r = client.get(
        "/api/replay/snapshot",
        params={"at": time.time() + 3600},
    )
    assert r.status_code == 400


def test_snapshot_terminated_workflow_excluded(fresh_audit, client):
    fresh_audit.log("entity.upserted", {
        "id": "vendor:beta", "kind": "vendor",
        "workflow_id": "wf-done", "source_workflows": ["wf-done"],
    })
    fresh_audit.log("decision.recorded", {
        "decision_id": "d1", "workflow_id": "wf-done",
        "phase": "approve", "persona_role": "x", "verdict": "approve",
    })
    fresh_audit.log("entity.upserted", {
        "id": "vendor:gamma", "kind": "vendor",
        "workflow_id": "wf-live", "source_workflows": ["wf-live"],
    })
    r = client.get("/api/replay/snapshot", params={"at": time.time()})
    assert r.status_code == 200
    body = r.json()
    ids = {w["id"] for w in body["in_flight_workflows"]}
    assert "wf-live" in ids
    assert "wf-done" not in ids


def test_snapshot_recent_events_window(fresh_audit, client):
    # Inject one entry, then probe with at = now + 120s (so the entry
    # is older than the 60s recent window).
    fresh_audit.log("entity.upserted", {
        "id": "vendor:old", "kind": "vendor",
        "workflow_id": "wf-old", "source_workflows": ["wf-old"],
    })
    far_future_within_grace = time.time() + 120
    # 120s is past the 5s future grace so we expect 400 — flip the
    # logic: probe at "now" so the freshly logged entry is in window.
    r = client.get("/api/replay/snapshot", params={"at": time.time()})
    assert r.status_code == 200
    body = r.json()
    assert any(ev["type"] == "entity.upserted" for ev in body["recent_events"])
    # Sanity: the "far future" probe gets rejected.
    assert client.get(
        "/api/replay/snapshot",
        params={"at": far_future_within_grace},
    ).status_code == 400
