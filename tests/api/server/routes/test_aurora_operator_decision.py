from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.routes.exceptions import router
from api.server.services.exception_factory import compose_hitl_exception
from api.server.state import app_state
from api.shared.types import Workflow


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AGT_ENFORCE", "1")
    app_state.store._workflows.clear()
    app_state.store._exceptions.clear()
    workflow = Workflow(
        id="AUR-DECISION-1",
        type="aurora-budget-response",
        status="awaiting_hitl",
        current_phase="Executive approval",
        created_at=time.time(),
        sla_due_at=time.time() + 3600,
        jurisdiction="London-Zava",
        agency="Zava",
        orchestration_instance_id="aurora-decision-instance",
        payload={
            "hitl_context": {
                "operator_only": True,
                "persona": "cfo",
                "external_event": "aurora_budget_response_decision",
                "proposed_action": {
                    "id": "freeze-brand-aurora",
                    "kind": "policy_set",
                    "verdict": "freeze",
                    "decided_on": ["BRAND-aurora"],
                    "attributes": {"scope": "po", "expiry_days": 14},
                },
            }
        },
    )
    app_state.store.upsert_workflow(workflow)
    exception = compose_hitl_exception(
        app_state.store,
        workflow.id,
        "awaiting_explicit_operator_approval",
    )
    app = FastAPI()
    app.include_router(router)
    yield TestClient(app), workflow, exception
    app_state.store._workflows.clear()
    app_state.store._exceptions.clear()


def test_aurora_gate_denies_actor_without_cfo_policy_authority(
    client, monkeypatch,
):
    http, workflow, exception = client
    raised = []

    async def _raise(*args):
        raised.append(args)
        return True

    monkeypatch.setattr(
        "api.server.services.durable_client.raise_orchestration_event",
        _raise,
    )

    response = http.post(
        f"/api/exceptions/{exception.id}/resolve",
        headers={
            "X-Actor-Id": "executive@example.test",
            "X-Actor-Role": "executive",
        },
        json={"resolution": "approve", "resolvedBy": "spoofed@example.test"},
    )

    assert response.status_code == 403
    assert workflow.status == "awaiting_hitl"
    assert raised == []


def test_aurora_gate_rejects_non_terminal_generic_resolution(
    client, monkeypatch,
):
    http, workflow, exception = client
    raised = []

    async def _raise(*args):
        raised.append(args)
        return True

    monkeypatch.setattr(
        "api.server.services.durable_client.raise_orchestration_event",
        _raise,
    )

    response = http.post(
        f"/api/exceptions/{exception.id}/resolve",
        headers={
            "X-Actor-Id": "cfo@example.test",
            "X-Actor-Role": "cfo",
        },
        json={"resolution": "request-info"},
    )

    assert response.status_code == 400
    assert workflow.status == "awaiting_hitl"
    assert raised == []


def test_aurora_gate_uses_authenticated_actor_and_rejects_duplicate_decision(
    client, monkeypatch,
):
    http, workflow, exception = client
    raised = []

    async def _raise(instance_id, event_name, payload):
        raised.append((instance_id, event_name, payload))
        return True

    monkeypatch.setattr(
        "api.server.services.durable_client.raise_orchestration_event",
        _raise,
    )

    response = http.post(
        f"/api/exceptions/{exception.id}/resolve",
        headers={
            "X-Actor-Id": "cfo@example.test",
            "X-Actor-Role": "cfo",
        },
        json={"resolution": "approve", "resolvedBy": "spoofed@example.test"},
    )

    assert response.status_code == 200, response.text
    assert raised[0][1] == "aurora_budget_response_decision"
    assert raised[0][2]["resolved_by"] == "cfo@example.test"
    assert raised[0][2]["actor_role"] == "cfo"
    assert raised[0][2]["decision_id"] == exception.id
    assert workflow.payload["decisions"][-1]["decision_id"] == exception.id

    duplicate = http.post(
        f"/api/exceptions/{exception.id}/resolve",
        headers={
            "X-Actor-Id": "cfo@example.test",
            "X-Actor-Role": "cfo",
        },
        json={"resolution": "approve"},
    )
    assert duplicate.status_code == 409
    assert len(raised) == 1
