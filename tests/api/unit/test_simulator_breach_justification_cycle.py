"""Day 10 / Task 23: breach -> notification -> justification round-trip."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.server.services import simulator_orchestrator
from api.shared.types import Workflow, ClaimData


@pytest.fixture(autouse=True)
def _isolate_app_state_store():
    """Each test starts with the workflows the test creates removed at
    teardown — prevents order-dependent failures once a parallel test
    runner reads the process-global app_state.store."""
    store = simulator_orchestrator.app_state.store
    pre_existing = {w.id for w in store.list_workflows()}
    yield
    for w in list(store.list_workflows()):
        if w.id not in pre_existing:
            store._workflows.pop(w.id, None)


def _make_workflow_in_store(workflow_id: str = "EXP-9001") -> Workflow:
    w = Workflow(
        id=workflow_id,
        type="expense-claim",
        current_phase="Notify",
        created_at=0,
        sla_due_at=0,
        jurisdiction="UK-Zava",
        agency="Mindshare",
        orchestration_instance_id=f"durable-{workflow_id}",
        claim=ClaimData(
            claim_id="CLM-0007",
            employee_id="EMP-0001",
            submitted_at="2026-04-01T08:00:00",
            market="UK",
            currency="GBP",
            category="meals",
            vendor="Côte Brasserie",
            amount=89.5,
            attendees=3,
            ems_source="concur",
        ),
    )
    simulator_orchestrator.app_state.store.upsert_workflow(w)
    return w


@pytest.mark.asyncio
async def test_simulate_justification_fires_external_event_and_emits_event():
    w = _make_workflow_in_store("EXP-9001")
    raised: list[tuple[str, str, dict]] = []

    async def fake_raise(instance_id, event_name, event_data):
        raised.append((instance_id, event_name, event_data))

    bus_events: list = []
    with patch.object(simulator_orchestrator, "raise_orchestration_event", AsyncMock(side_effect=fake_raise)):
        sub = simulator_orchestrator.app_state.bus.on_any(lambda e: bus_events.append(e))
        try:
            await simulator_orchestrator.simulate_justification(
                "EXP-9001", text="Client dinner, see attached approval.",
            )
        finally:
            sub()

    assert len(raised) == 1
    instance_id, event_name, event_data = raised[0]
    assert instance_id == w.orchestration_instance_id
    assert event_name == "justification"
    assert event_data["claim_id"] == "CLM-0007"
    assert event_data["submitted_by"] == "EMP-0001"
    assert "Client dinner" in event_data["text"]

    justification_events = [e for e in bus_events if e.type == "justification.received"]
    assert len(justification_events) == 1
    assert justification_events[0].workflow_id == "EXP-9001"


@pytest.mark.asyncio
async def test_simulate_justification_unknown_workflow_raises():
    with pytest.raises(KeyError):
        await simulator_orchestrator.simulate_justification("EXP-NOPE")


@pytest.mark.asyncio
async def test_simulate_justification_missing_orchestration_instance_raises():
    """If the workflow exists but never got a Durable instance id (e.g. the
    Functions host wasn't running when it was spawned), the simulator
    refuses to send the event rather than guessing."""
    w = Workflow(
        id="EXP-NO-DURABLE", type="expense-claim", current_phase="Notify",
        created_at=0, sla_due_at=0, jurisdiction="UK-Zava", agency="x",
        orchestration_instance_id=None,
        claim=ClaimData(
            claim_id="CLM-X", employee_id="EMP-X", submitted_at="2026-04-01T00:00:00",
            market="UK", currency="GBP", category="meals", vendor="V", amount=10.0,
            attendees=1, ems_source="workday",
        ),
    )
    simulator_orchestrator.app_state.store.upsert_workflow(w)
    with pytest.raises(ValueError, match="orchestration_instance_id"):
        await simulator_orchestrator.simulate_justification("EXP-NO-DURABLE")
