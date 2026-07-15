"""Objective lifecycle proof for WorldBridge over a REAL ActorWorldService.

Complements ``test_world_bridge_actor.py`` (which uses a fake world for the
command-application happy path). Here the bridge drives a real
``ActorWorldService`` so the objective lifecycle is asserted against the actual
simulation journal: ``objective.opened → claimed → acting`` land on the sensor's
anchored trace, the responder is resolved from the objective *type* (not a
scenario branch), and a second sensor for the same target while one objective is
active schedules no second orchestration.

The Durable scheduler and status poller are monkeypatched, so no func host runs.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.server.services.world_bridge import WorldBridge
from api.server.world.service import ActorWorldService
from api.shared.events import FleetEvent


def _state():
    service = ActorWorldService.for_world("support", seed=7, bus=EventBus())
    state = SimpleNamespace(
        bus=service.bus, world_service=service, world_last_response=None,
        store=StateStore(), hub=MagicMock(), audit=MagicMock(),
        orchestration_history={},
    )
    state.workflow_event_ingestor = WorkflowEventIngestor(state)
    return state


def _sensor(event_id: str, trace: str, target: str = "queue:support") -> FleetEvent:
    return FleetEvent(
        type="world.sensor.tripped",
        simulation_event={
            "event_id": event_id,
            "trace_id": trace,
            "target_id": target,
            "actor_id": "sensor:support_pressure",
            "type": "sensor.tripped",
            "payload": {"actor_ids": []},
        },
    )


def _trace_types(service, trace: str) -> list[str]:
    return [event.type for event in service.runtime.journal if event.trace_id == trace]


@pytest.mark.asyncio
async def test_objective_lifecycle_on_anchored_trace(monkeypatch):
    state = _state()
    bridge = WorldBridge(state)
    schedule = AsyncMock(return_value={"id": "durable-1", "statusQueryGetUri": "status://1"})
    monkeypatch.setattr("api.server.services.world_bridge.schedule_new_orchestration", schedule)
    # Deferred path keeps the test independent of a valid typed command while
    # still driving opened → claimed → acting before the deferral fails it.
    bridge._await_output = AsyncMock(return_value={"command": None, "reasoning": "no reserve"})
    bridge.start()

    state.bus.emit(_sensor("evt-s1", "support-pressure-5"))
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    types = _trace_types(state.world_service, "support-pressure-5")
    assert "objective.opened" in types
    assert "objective.claimed" in types
    assert "objective.acting" in types
    assert "responder.requested" in types
    assert "responder.deferred" in types
    # Responder resolved from the objective type, not a scenario branch.
    assert schedule.await_count == 1
    assert schedule.await_args.args[1] == "SurgeStaffingOrchestrator"
    objective = state.world_service.objectives.get("obj-evt-s1")
    assert objective.claimed_by == "surge_staffing"
    assert objective.status == "failed"  # deferred → failed


@pytest.mark.asyncio
async def test_duplicate_target_opens_one_objective_and_schedules_once(monkeypatch):
    state = _state()
    bridge = WorldBridge(state)
    gate = asyncio.Event()

    async def schedule(*args):
        await gate.wait()
        return {"id": "durable-1", "statusQueryGetUri": "status://1"}

    scheduled = AsyncMock(side_effect=schedule)
    monkeypatch.setattr("api.server.services.world_bridge.schedule_new_orchestration", scheduled)
    bridge._await_output = AsyncMock(return_value={"command": None, "reasoning": "no reserve"})
    bridge.start()

    # Two different sensor traces for the SAME target while the first is still
    # in flight (held on the schedule gate).
    state.bus.emit(_sensor("evt-a", "support-pressure-5"))
    state.bus.emit(_sensor("evt-b", "support-pressure-6"))
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    opened = [
        event for event in state.world_service.runtime.journal
        if event.type == "objective.opened" and event.target_id == "queue:support"
    ]
    assert len(opened) == 1
    assert scheduled.await_count == 1
    # The second trace was deduplicated to the first objective: it opened no
    # objective and requested no responder of its own.
    assert _trace_types(state.world_service, "support-pressure-6") == []

    gate.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
