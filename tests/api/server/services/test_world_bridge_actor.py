"""Behavioural proof for WorldBridge: sensor trace -> Durable command -> actor world.

Uses a fake ``ActorWorldService`` (build_observation/record_external/apply_command)
and monkeypatches the Durable scheduler + status poller, so no real func host is
required.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from api.server.services.event_bus import EventBus
from api.server.services.world_bridge import WorldBridge
from api.shared.events import FleetEvent


class FakeWorld:
    def __init__(self):
        self.applied = []
        self.recorded = []

    def build_observation(self, event):
        return {
            "trace_id": event["trace_id"],
            "queued_tickets": [{"id": "TKT-1", "required_skill": "technical"}],
            "reserve_workers": [{"id": "WRK-31", "skills": ["technical"]}],
        }

    def record_external(self, event_type, **kwargs):
        event = SimpleNamespace(
            event_id=f"evt-{len(self.recorded)+1}",
            trace_id=kwargs["trace_id"],
            type=event_type,
        )
        self.recorded.append((event_type, kwargs))
        return event

    def apply_command(self, command):
        self.applied.append(command)
        return SimpleNamespace(event_id="evt-command", type="command.accepted")


def app_state():
    return SimpleNamespace(
        bus=EventBus(), world_service=FakeWorld(), world_last_response=None
    )


def sensor(trace="trace-1"):
    return FleetEvent(
        type="world.sensor.tripped",
        simulation_event={
            "event_id": "evt-sensor",
            "trace_id": trace,
            "type": "sensor.tripped",
            "payload": {"actor_ids": ["TKT-1"]},
        },
    )


@pytest.mark.asyncio
async def test_sensor_schedules_actor_observation_and_applies_typed_command(monkeypatch):
    state = app_state()
    bridge = WorldBridge(state)
    schedule = AsyncMock(
        return_value={"id": "durable-1", "statusQueryGetUri": "status://1"}
    )
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration", schedule
    )
    bridge._await_output = AsyncMock(return_value={
        "command": {
            "command_id": "cmd-1",
            "trace_id": "trace-1",
            "issued_by": "surge_staffing",
            "type": "reallocate_workers",
            "payload": {
                "worker_ids": ["WRK-31"],
                "from_team_id": "TEAM-RESERVE",
                "to_team_id": "TEAM-SUPPORT",
                "duration_minutes": 60,
            },
        },
        "reasoning": "move technical worker",
    })
    bridge.start()
    state.bus.emit(sensor())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert schedule.await_count == 1
    assert schedule.await_args.args[0]["observation"]["queued_tickets"][0]["id"] == "TKT-1"
    assert state.world_service.applied[0].command_id == "cmd-1"
    assert [kind for kind, _ in state.world_service.recorded] == [
        "responder.requested", "responder.decided"
    ]
    assert state.world_last_response["command"]["command_id"] == "cmd-1"
    assert state.world_last_response["result_event_id"] == "evt-command"


@pytest.mark.asyncio
async def test_no_command_records_deferred_without_mutation(monkeypatch):
    state = app_state()
    bridge = WorldBridge(state)
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration",
        AsyncMock(return_value={"id": "durable-1", "statusQueryGetUri": "status://1"}),
    )
    bridge._await_output = AsyncMock(
        return_value={"command": None, "reasoning": "no reserve workers"}
    )
    bridge.start()
    state.bus.emit(sensor())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert state.world_service.applied == []
    assert state.world_service.recorded[-1][0] == "responder.deferred"
    assert state.world_last_response is None


@pytest.mark.asyncio
async def test_duplicate_trace_is_scheduled_once_while_in_flight(monkeypatch):
    state = app_state()
    bridge = WorldBridge(state)
    gate = asyncio.Event()

    async def schedule(*args):
        await gate.wait()
        return {"id": "durable-1", "statusQueryGetUri": "status://1"}

    scheduled = AsyncMock(side_effect=schedule)
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration", scheduled
    )
    bridge.start()
    state.bus.emit(sensor())
    state.bus.emit(sensor())
    await asyncio.sleep(0)
    assert scheduled.await_count == 1
    gate.set()


@pytest.mark.asyncio
async def test_schedule_failure_records_failed_and_clears_in_flight_trace(monkeypatch):
    state = app_state()
    bridge = WorldBridge(state)
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration",
        AsyncMock(side_effect=RuntimeError("func host unreachable")),
    )
    bridge.start()
    state.bus.emit(sensor())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert state.world_service.applied == []
    assert state.world_service.recorded[-1][0] == "responder.failed"
    assert "trace-1" not in bridge._in_flight_traces

    # Same trace can be retried now that it is no longer in flight.
    retry_schedule = AsyncMock(
        return_value={"id": "durable-2", "statusQueryGetUri": "status://2"}
    )
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration", retry_schedule
    )
    bridge._await_output = AsyncMock(
        return_value={"command": None, "reasoning": "no reserve workers"}
    )
    state.bus.emit(sensor())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert retry_schedule.await_count == 1
