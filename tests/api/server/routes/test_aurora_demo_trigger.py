from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.server.state import app_state


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("INSIGHT_LOOP_ENABLED", "0")
    app_state.store._workflows.clear()
    from api.server.main import app
    yield TestClient(app)
    app_state.store._workflows.clear()


def test_full_aurora_arc_is_async_idempotent_starter(client, monkeypatch):
    scheduled = []

    async def _schedule(payload, function_name, instance_id=None):
        scheduled.append((payload, function_name, instance_id))
        return {
            "id": instance_id,
            "statusQueryGetUri": f"http://functions/status/{instance_id}?code=management-secret",
            "_started": True,
        }

    monkeypatch.setattr(
        "api.server.services.durable_client.schedule_new_orchestration",
        _schedule,
    )

    response = client.post(
        "/api/demo/trigger/full-aurora-arc?count=2",
        headers={
            "x-actor-role": "executive",
            "Idempotency-Key": "sales-demo-001",
        },
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body == {
        "workflow_id": body["workflow_id"],
        "instance_id": body["instance_id"],
        "request_id": "sales-demo-001",
        "status_url": f"/api/workflows/{body['workflow_id']}",
        "events_url": f"/api/workflows/{body['workflow_id']}/orchestration",
        "duplicate": False,
    }
    assert "management-secret" not in response.text
    assert "durable_status_url" not in body
    assert body["workflow_id"].startswith("AUR-")
    assert scheduled[0][1] == "AuroraBudgetResponseOrchestrator"
    assert scheduled[0][2] == body["instance_id"]
    assert scheduled[0][0]["workflow_id"] == body["workflow_id"]
    assert scheduled[0][0]["count"] == 2
    workflow = app_state.store.get_workflow(body["workflow_id"])
    assert workflow is not None
    assert workflow.type == "aurora-budget-response"
    assert workflow.orchestration_instance_id == body["instance_id"]

    duplicate = client.post(
        "/api/demo/trigger/full-aurora-arc?count=9",
        headers={
            "x-actor-role": "executive",
            "Idempotency-Key": "sales-demo-001",
        },
    )
    assert duplicate.status_code == 202
    assert duplicate.json()["workflow_id"] == body["workflow_id"]
    assert duplicate.json()["instance_id"] == body["instance_id"]
    assert duplicate.json()["duplicate"] is True


def test_missing_aurora_workflow_is_not_synthesised_from_its_prefix(client):
    response = client.get("/api/workflows/AUR-NOT-STARTED")
    assert response.status_code == 404


def test_full_aurora_arc_does_not_create_workflow_when_functions_unavailable(
    client, monkeypatch,
):
    async def _fail(*args, **kwargs):
        raise RuntimeError("functions unavailable")

    monkeypatch.setattr(
        "api.server.services.durable_client.schedule_new_orchestration",
        _fail,
    )

    response = client.post(
        "/api/demo/trigger/full-aurora-arc",
        headers={
            "x-actor-role": "executive",
            "Idempotency-Key": "sales-demo-unavailable",
        },
    )

    assert response.status_code == 503
    assert not any(
        workflow.type == "aurora-budget-response"
        for workflow in app_state.store.list_workflows()
    )


def test_existing_terminal_durable_instance_is_not_recreated_as_running(
    client, monkeypatch,
):
    async def _existing(payload, function_name, instance_id=None):
        return {
            "id": instance_id,
            "statusQueryGetUri": f"http://functions/status/{instance_id}",
            "_started": False,
            "_runtime_status": "Completed",
        }

    monkeypatch.setattr(
        "api.server.services.durable_client.schedule_new_orchestration",
        _existing,
    )

    response = client.post(
        "/api/demo/trigger/full-aurora-arc",
        headers={
            "x-actor-role": "executive",
            "Idempotency-Key": "sales-demo-completed",
        },
    )

    assert response.status_code == 202
    workflow = app_state.store.get_workflow(response.json()["workflow_id"])
    assert workflow.status == "completed"
    assert workflow.metadata["recovered_from_durable_status"] == "Completed"
