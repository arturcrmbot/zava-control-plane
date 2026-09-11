"""Regression tests for the asynchronous Aurora starter contract."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.server.state import app_state


HDRS = {
    "x-actor-role": "executive",
    "Idempotency-Key": "full-arc-regression",
}


@pytest.fixture
def client(monkeypatch):
    app_state.store._workflows.clear()
    scheduled = []

    async def _schedule(payload, function_name, instance_id=None):
        scheduled.append((payload, function_name, instance_id))
        return {
            "id": instance_id,
            "statusQueryGetUri": f"http://functions/status/{instance_id}",
            "_started": True,
        }

    monkeypatch.setattr(
        "api.server.services.durable_client.schedule_new_orchestration",
        _schedule,
    )
    from api.server.main import app
    yield TestClient(app), scheduled
    app_state.store._workflows.clear()


def test_full_arc_returns_async_tracking_contract(client):
    http, scheduled = client

    response = http.post(
        "/api/demo/trigger/full-aurora-arc?count=3",
        headers=HDRS,
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert set(body) == {
        "workflow_id",
        "instance_id",
        "request_id",
        "status_url",
        "events_url",
        "duplicate",
    }
    assert scheduled[0][1] == "AuroraBudgetResponseOrchestrator"
    assert scheduled[0][0]["count"] == 3


def test_full_arc_does_not_apply_policy_or_create_children_in_request_scope(
    client,
):
    http, _scheduled = client

    response = http.post(
        "/api/demo/trigger/full-aurora-arc",
        headers=HDRS,
    )

    assert response.status_code == 202
    root = app_state.store.get_workflow(response.json()["workflow_id"])
    assert root is not None
    assert root.payload.get("outputs") is None
    assert [
        workflow
        for workflow in app_state.store.list_workflows()
        if workflow.type == "ap-invoice"
    ] == []


def test_full_arc_keeps_legacy_delay_parameter_without_synchronous_wait(client):
    http, _scheduled = client

    response = http.post(
        "/api/demo/trigger/full-aurora-arc?delay_seconds=2.0",
        headers=HDRS,
    )

    assert response.status_code == 202
    root = app_state.store.get_workflow(response.json()["workflow_id"])
    assert root.metadata["delay_seconds_ignored"] == 2.0
