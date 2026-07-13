"""Behavioural proof for ActorWorldService: the live async adapter that paces
SimulationRuntime/SupportScenario, publishes journal events to EventBus and
subscribers, and exposes snapshot/observation/control/command surfaces.
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


def test_apply_command_publishes_command_and_worker_events():
    world = service()
    queue = world.subscribe()
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
    published = [queue.get_nowait(), queue.get_nowait()]
    assert [e["type"] for e in published] == ["command.accepted", "worker.reallocated"]


@pytest.mark.asyncio
async def test_pause_step_resume_control_authoritative_runtime():
    world = service()
    world.pause()
    before = world.runtime.now
    await world.step_once()
    assert world.runtime.now >= before
    world.resume()
    task = asyncio.create_task(world.run())
    await asyncio.sleep(0.02)
    world.stop()
    await task
    assert world.runtime.now > before


# --- Focused tests beyond the authoritative set -----------------------------


def test_installation_backlog_is_not_published_on_startup():
    world = service()
    queue = world.subscribe()
    assert queue.qsize() == 0
    assert world._published_seq == len(world.runtime.journal)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_set_speed_rejects_non_positive_or_non_finite(value):
    world = service()
    with pytest.raises(ValueError):
        world.set_speed(value)


def test_set_speed_accepts_positive_finite_value():
    world = service()
    world.set_speed(42.5)
    assert world.minutes_per_second == 42.5


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


def test_restart_rejects_while_not_paused():
    world = service()
    with pytest.raises(RuntimeError):
        world.restart()


def test_restart_resets_actors_and_journal_deterministically_when_paused():
    world = service()
    world.runtime.run_until(5)
    world.pause()
    world.restart(seed=42)

    fresh = service()
    assert world.runtime.canonical_journal() == fresh.runtime.canonical_journal()
    assert len(world.scenario.customers) == 1_000
    assert len(world.scenario.workers) == 40
    assert world._published_seq == len(world.runtime.journal)


def test_subscriber_queue_drops_oldest_when_full():
    world = service()
    queue = world.subscribe(maxsize=2)
    world.record_external("test.one", trace_id="t1")
    world.record_external("test.two", trace_id="t2")
    world.record_external("test.three", trace_id="t3")
    assert queue.qsize() == 2
    first = queue.get_nowait()
    second = queue.get_nowait()
    assert [first["type"], second["type"]] == ["test.two", "test.three"]


def test_unsubscribe_stops_future_delivery():
    world = service()
    queue = world.subscribe()
    world.unsubscribe(queue)
    world.record_external("test.after.unsubscribe", trace_id="t1")
    assert queue.qsize() == 0


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
