from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest

# This unit test only needs the in-memory workflow store.
os.environ.setdefault("ENTITY_PLANE_ENABLED", "0")

from api.server.services import simulator_orchestrator
from api.server.state import app_state
from api.shared.domains import DOMAINS


@pytest.fixture(autouse=True)
def _isolate_network_incident_spawns():
    previous_seq = simulator_orchestrator._nir_seq
    previous_care_seq = getattr(simulator_orchestrator, "_care_seq", 0)
    previous_workflows = dict(app_state.store._workflows)
    simulator_orchestrator._nir_seq = 0
    simulator_orchestrator._care_seq = 0
    app_state.store._workflows.clear()
    yield
    simulator_orchestrator._nir_seq = previous_seq
    simulator_orchestrator._care_seq = previous_care_seq
    app_state.store._workflows.clear()
    app_state.store._workflows.update(previous_workflows)


@pytest.mark.asyncio
async def test_network_incident_spawner_uses_single_nested_observation(monkeypatch):
    schedule = AsyncMock(return_value={"id": "iid-network-incident"})
    monkeypatch.setattr(
        simulator_orchestrator,
        "schedule_new_orchestration",
        schedule,
    )

    workflow_id = await simulator_orchestrator.spawn_network_incident_workflow(
        scenario="regional-outage",
    )

    observation = {
        "incident_site": {"id": "SITE-01", "status": "failed"},
        "neighbor_sites": [],
        "affected_sessions": [],
        "scenario": "regional-outage",
    }
    workflow = app_state.store.get_workflow(workflow_id)
    assert workflow is not None
    assert workflow.payload == {
        "incident": observation,
        "scenario": "regional-outage",
    }
    assert "incident" not in workflow.payload["incident"]
    schedule.assert_awaited_once_with(
        {
            "workflow_id": workflow_id,
            "type": "network-incident",
            "trace_id": workflow_id,
            "observation": observation,
            "scenario": "regional-outage",
        },
        function_name="NetworkIncidentOrchestrator",
    )


@pytest.mark.asyncio
async def test_proactive_care_spawner_uses_registered_payload_shape(monkeypatch):
    schedule = AsyncMock(return_value={"id": "iid-care"})
    monkeypatch.setattr(
        simulator_orchestrator,
        "schedule_new_orchestration",
        schedule,
    )

    workflow_id = (
        await simulator_orchestrator.spawn_proactive_customer_care_workflow(
            scenario="vulnerable-customer"
        )
    )

    workflow = app_state.store.get_workflow(workflow_id)
    assert workflow is not None
    assert workflow.type == "proactive-customer-care"
    impact = workflow.payload["customer_impact"]
    assert impact["impacted_accounts"][0]["id"] == "ACC-00002"
    schedule.assert_awaited_once_with(
        {
            "workflow_id": workflow_id,
            "type": "proactive-customer-care",
            "trace_id": workflow_id,
            "observation": impact,
            "scenario": "vulnerable-customer",
        },
        function_name="ProactiveCustomerCareOrchestrator",
    )


def test_default_ramp_excludes_registered_domains_without_spawners():
    selected = simulator_orchestrator._select_ramp_domains(
        list(DOMAINS),
        DOMAINS,
    )

    assert selected
    assert all(domain.spawn_fn for domain in selected)
    assert "order-to-activate" not in {domain.workflow_type for domain in selected}
    selected_types = {domain.workflow_type for domain in selected}
    assert "network-incident" not in selected_types
    assert "proactive-customer-care" not in selected_types
