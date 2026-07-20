"""Per-domain operator-resolve route exercises the pending_gates cache +
registry fallback for every domain's HITL gate.

Per TASK-017 of plan/feature-fleet-domain-substrate-1.md.
"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.routes.exceptions import router as exceptions_router
from api.server.services import pending_gates
from api.server.services.exception_factory import compose_hitl_exception
from api.server.state import app_state
from api.shared import domains as registry
from api.shared.types import Workflow


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(exceptions_router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_state():
    pending_gates.reset()
    # Wipe the in-memory store between tests so workflow ids don't collide.
    app_state.store._workflows.clear()
    app_state.store._exceptions.clear()
    yield
    pending_gates.reset()


def _seed_suspended_workflow(workflow_type: str, gate) -> tuple[str, str]:
    """Create a workflow record for `workflow_type`, mark it awaiting_hitl,
    populate pending_gates as if /internal/durable-event suspend handler
    had fired, and compose a HITL exception. Returns (workflow_id, exception_id).
    """
    domain = registry.DOMAINS[workflow_type]
    wid = f"{domain.workflow_id_prefix}-TEST"
    now = time.time()
    w = Workflow(
        id=wid, type=workflow_type, status="awaiting_hitl",
        current_phase=gate.gate_phase, created_at=now, sla_due_at=now + 86400,
        jurisdiction="London-Zava", agency="Zava",
        orchestration_instance_id=f"INST-{wid}",
    )
    app_state.store.upsert_workflow(w)
    pending_gates.record(wid, phase=gate.gate_phase, external_event=gate.external_event)
    exc = compose_hitl_exception(app_state.store, wid, "test gate")
    return wid, exc.id


def test_resolve_route_raises_per_domain_event_via_cache(client, monkeypatch):
    """For every domain × gate, the resolve route should raise the gate's
    canonical external_event when the cache is warm."""
    raised: list[tuple[str, str, dict]] = []

    async def _fake_raise(instance_id, event_name, payload):
        raised.append((instance_id, event_name, payload))

    import api.server.routes.exceptions as ex_module
    # The function imports lazily inside _resolve_one; patch the module.
    import api.server.services.durable_client as dc_module
    monkeypatch.setattr(dc_module, "raise_orchestration_event", _fake_raise)

    for wt, domain in registry.DOMAINS.items():
        for gate in domain.hitl_gates:
            raised.clear()
            pending_gates.reset()
            app_state.store._workflows.clear()
            app_state.store._exceptions.clear()
            wid, exc_id = _seed_suspended_workflow(wt, gate)
            resp = client.post(
                f"/api/exceptions/{exc_id}/resolve",
                json={"resolution": "approve", "resolvedBy": "test@zava"},
            )
            assert resp.status_code == 200, f"{wt}/{gate.gate_phase}: {resp.text}"
            assert raised, f"{wt}/{gate.gate_phase}: no event raised"
            inst, event_name, payload = raised[0]
            assert inst == f"INST-{wid}"
            assert event_name == gate.external_event, (
                f"{wt}/{gate.gate_phase}: raised {event_name!r}, expected "
                f"{gate.external_event!r}"
            )
            assert payload["decision"] == "approve"


def test_resolve_route_falls_back_to_registry_when_cache_cold(client, monkeypatch):
    """If pending_gates is cold (e.g. FastAPI restart between suspend and
    operator click), the route should still resolve via the registry."""
    raised: list[tuple[str, str, dict]] = []

    async def _fake_raise(instance_id, event_name, payload):
        raised.append((instance_id, event_name, payload))

    import api.server.services.durable_client as dc_module
    monkeypatch.setattr(dc_module, "raise_orchestration_event", _fake_raise)

    domain = registry.DOMAINS["vendor-kyc"]
    gate = domain.hitl_gates[0]
    wid, exc_id = _seed_suspended_workflow("vendor-kyc", gate)
    # Simulate cold cache.
    pending_gates.reset()

    resp = client.post(
        f"/api/exceptions/{exc_id}/resolve",
        json={"resolution": "approve", "resolvedBy": "test@zava"},
    )
    assert resp.status_code == 200, resp.text
    assert raised
    assert raised[0][1] == gate.external_event


def test_resolve_route_keeps_gate_open_when_durable_delivery_fails(
    client, monkeypatch
):
    async def _fail_raise(instance_id, event_name, payload):
        raise TimeoutError("durable host busy")

    import api.server.services.durable_client as dc_module

    monkeypatch.setattr(dc_module, "raise_orchestration_event", _fail_raise)
    gate = registry.DOMAINS["vendor-kyc"].hitl_gates[0]
    wid, exc_id = _seed_suspended_workflow("vendor-kyc", gate)

    resp = client.post(
        f"/api/exceptions/{exc_id}/resolve",
        json={"resolution": "approve", "resolvedBy": "test@zava"},
    )

    assert resp.status_code == 503
    assert app_state.store.get_exception(exc_id).resolved_at is None
    workflow = app_state.store.get_workflow(wid)
    assert workflow.status == "awaiting_hitl"
    assert workflow.action_ledger == []
