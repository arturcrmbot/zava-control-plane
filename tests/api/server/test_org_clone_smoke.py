"""End-to-end smoke for the org-clone observatory (Phase 4 IP9 TASK-041)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.shared.events import FleetEvent
from tests.api.server._p4_fixtures import fresh_entities  # noqa: F401


@pytest.fixture
def client():
    from api.server.main import app
    return TestClient(app)


def test_entity_stats_returns_counts(client, fresh_entities):
    r = client.get("/api/entities/_stats")
    assert r.status_code == 200
    body = r.json()
    assert "counts" in body
    # Bootstrap from fixtures should give at least Person + Organisation.
    assert body["counts"]["Person"] > 0


def test_functions_returns_at_least_ten(client):
    r = client.get("/api/functions")
    assert r.status_code == 200
    body = r.json()
    assert len(body) >= 10
    names = {e["name"] for e in body}
    assert "ceo" in names
    assert "legacy" not in names


def test_cadences_returns_at_least_three(client):
    r = client.get("/api/cadences")
    assert r.status_code == 200
    assert len(r.json()) >= 3


def test_finance_ambient_returns_three(client):
    r = client.get("/api/functions/finance/ambient")
    assert r.status_code == 200
    names = {a["name"] for a in r.json()}
    assert {"budget-variance-watcher", "vendor-risk-watcher", "period-close"} <= names


def test_meta_workflow_reflector_writes_tree(client, fresh_entities):
    """Emitting workflow.sub_spawned populates SUB_WORKFLOW_OF and
    /api/workflows/{parent}/tree shows the child."""
    from api.server.routes.workflows import app_state
    parent_id = "wf-smoke-parent"
    child_id = "wf-smoke-child"
    app_state.bus.emit(FleetEvent(
        type="workflow.sub_spawned",
        workflow_id=parent_id,
        parent_workflow_id=parent_id,
        parent_workflow_type="meta-fy-close",
        child_workflow_id=child_id,
        child_workflow_type="ap-invoice",
    ))
    r = client.get(f"/api/workflows/{parent_id}/tree")
    assert r.status_code == 200
    body = r.json()
    assert body["workflow_id"] == parent_id
    child_ids = [c["workflow_id"] for c in body["children"]]
    assert child_id in child_ids


def test_audit_event_registry_covers_phase4_events():
    from api.server.services.audit_logger import AUDIT_EVENT_REGISTRY
    assert "cadence.tick" in AUDIT_EVENT_REGISTRY
    assert "workflow.sub_spawned" in AUDIT_EVENT_REGISTRY
    assert "ambient.decided" in AUDIT_EVENT_REGISTRY
    assert "decision.recorded" in AUDIT_EVENT_REGISTRY
    assert "entity.write.failed" in AUDIT_EVENT_REGISTRY

