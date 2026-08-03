"""Behavioural proof for ActorWorldService: the live async adapter that paces
SimulationRuntime/SupportScenario and publishes journal events to EventBus.

Viewer-era controls (pause/resume/step/restart/subscribers) are deferred to
Plan 3 and are intentionally not covered here.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from api.server.services.event_bus import EventBus
from api.server.world.model import SimulationCommand
from api.server.world.packs.support import Ticket
from api.server.world.service import ActorWorldService


def service() -> ActorWorldService:
    return ActorWorldService.support(seed=42, bus=EventBus(), minutes_per_second=1000)


def test_snapshot_contains_actual_actor_state_and_projection():
    world = service()
    snapshot = world.snapshot()
    assert snapshot["scenario"] == "support"
    assert len(snapshot["customers"]) == 1_000
    assert len(snapshot["workers"]) == 40
    assert snapshot["projection"]["tickets_opened"] == 0
    assert snapshot["latest_seq"] == len(world.runtime.journal)
    json.dumps(snapshot)  # must not raise
    assert isinstance(snapshot["customers"][0]["active_ticket_ids"], list)
    assert isinstance(snapshot["workers"][0]["skills"], list)


def test_events_after_returns_causal_journal_tail():
    world = service()
    tail = world.events_after(1_030)
    assert tail
    assert all(event["seq"] > 1_030 for event in tail)


def test_apply_command_publishes_command_and_worker_events_and_moves_worker():
    world = service()
    published: list[str] = []
    world.bus.on_any(lambda event: published.append(event.type))
    command = SimulationCommand(
        command_id="cmd-test",
        trace_id="trace-test",
        issued_by="test",
        type="reallocate_workers",
        payload={
            "worker_ids": ["WRK-0031"],
            "from_team_id": "TEAM-RESERVE",
            "to_team_id": "TEAM-SUPPORT",
            "duration_minutes": 30,
        },
    )
    result = world.apply_command(command)
    assert result.type == "command.accepted"
    assert published == ["world.command.accepted", "world.worker.reallocated"]
    assert world.scenario.workers["WRK-0031"].team_id == "TEAM-SUPPORT"


def test_record_external_publishes_to_event_bus():
    world = service()
    published: list[str] = []
    world.bus.on_any(lambda event: published.append(event.type))
    world.record_external("test.happened", trace_id="t1")
    assert published == ["world.test.happened"]


@pytest.mark.asyncio
async def test_run_advances_authoritative_runtime_and_stop_ends_task(monkeypatch):
    # The step throttle (WORLD_MAX_STEPS_PER_SECOND, default 100) floors every
    # loop iteration at 10ms, which is coarser than this test's 20ms budget and
    # would leave the SimPy clock parked on the events queued at t=0. Lift the
    # ceiling so this asserts clock advance rather than the throttle; the
    # throttle itself is covered by tests/api/server/services/test_world_load_limits.py.
    monkeypatch.setenv("WORLD_MAX_STEPS_PER_SECOND", "100000")
    world = service()
    before = world.runtime.now
    task = asyncio.create_task(world.run())
    await asyncio.sleep(0.02)
    world.stop()
    await task
    assert world.runtime.now > before
    assert task.done()


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_constructor_rejects_non_positive_or_non_finite_speed(value):
    with pytest.raises(ValueError):
        ActorWorldService.support(seed=42, bus=EventBus(), minutes_per_second=value)


@pytest.mark.parametrize("multiplier", [1, 0.5, 0, -2, float("nan"), float("inf")])
def test_inject_demand_surge_rejects_invalid_multiplier(multiplier):
    world = service()
    with pytest.raises(ValueError):
        world.inject_demand_surge(multiplier, 30)


@pytest.mark.parametrize("duration", [0, -10, float("nan"), float("inf")])
def test_inject_demand_surge_rejects_invalid_duration(duration):
    world = service()
    with pytest.raises(ValueError):
        world.inject_demand_surge(4, duration)


def test_inject_demand_surge_schedules_a_real_perturbation_process():
    world = service()
    before = len(world.runtime.journal)
    world.inject_demand_surge(4, 30)
    world.runtime.run_until(1)
    assert any(
        event.type == "perturbation.started" for event in world.runtime.journal[before:]
    )


def test_build_observation_reports_real_reserve_ids_and_ticket_details():
    world = service()
    ticket = Ticket(
        id="TKT-000001",
        customer_id="CUS-00001",
        severity="high",
        required_skill="technical",
        created_at=0.0,
        queued_at=0.0,
        sla_deadline=30.0,
        trace_id="ticket-TKT-000001",
    )
    world.scenario.tickets[ticket.id] = ticket
    world.scenario.queued_ticket_ids[ticket.id] = None

    sensor_event = {
        "event_id": "evt-synthetic-sensor",
        "trace_id": "trace-synthetic",
        "type": "sensor.tripped",
        "payload": {"actor_ids": [ticket.id, "TKT-missing"]},
    }
    observation = world.build_observation(sensor_event)

    assert observation["trace_id"] == "trace-synthetic"
    assert observation["sensor_event_id"] == "evt-synthetic-sensor"
    assert observation["queued_tickets"] == [
        {
            "id": "TKT-000001",
            "customer_id": "CUS-00001",
            "severity": "high",
            "required_skill": "technical",
            "status": "queued",
            "queued_at": 0.0,
            "sla_deadline": 30.0,
            "wait_minutes": world.runtime.now - 0.0,
        }
    ]
    reserve_ids = {f"WRK-{i:04d}" for i in range(31, 41)}
    support_ids = {f"WRK-{i:04d}" for i in range(1, 31)}
    assert {w["id"] for w in observation["reserve_workers"]} == reserve_ids
    assert all(w["status"] == "reserve" for w in observation["reserve_workers"])
    assert {w["id"] for w in observation["support_workers"]} == support_ids
    assert observation["allowed_commands"] == ["reallocate_workers"]
    # exact worker keys
    for w in observation["support_workers"] + observation["reserve_workers"]:
        assert set(w.keys()) == {"id", "skills", "status", "team_id", "current_ticket_id"}
        assert isinstance(w["skills"], list)
    # old keys must be absent from tickets and workers
    qt = observation["queued_tickets"][0]
    assert "customer" not in qt
    assert "skill" not in qt
    assert "team" not in observation["support_workers"][0]
    assert "current_ticket" not in observation["support_workers"][0]
