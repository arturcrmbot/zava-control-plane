"""Behavioural proof for WorldBridge: sensor trace -> Durable command -> actor world.

Uses a fake ``ActorWorldService`` (build_observation/record_external/apply_command)
and monkeypatches the Durable scheduler + status poller, so no real func host is
required.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.server.services.world_bridge import WorldBridge
from api.server.world.registry import ObjectiveRoute
from api.shared.events import FleetEvent
from api.shared.vertical_loader import build_runtime


_AGENCY_RUNTIME = build_runtime({}, data_root=Path("/tmp"))


class FakeObjective:
    def __init__(self, oid, trace_id):
        self.id = oid
        self.trace_id = trace_id
        self.status = "open"


class FakeWorld:
    def __init__(self):
        self.applied = []
        self.recorded = []
        self.objective_events = []
        self._objectives = {}
        self.registration = SimpleNamespace(
            name="support",
            objective_routes=(
                ObjectiveRoute(
                    sensor_id="sensor:support_pressure",
                    objective_type="support_capacity",
                    allowed_command_types=frozenset({"reallocate_workers"}),
                    success_event_types=frozenset({"worker.reallocated"}),
                    failure_event_types=frozenset({"ticket.abandoned"}),
                    evaluation_timeout_minutes=30,
                ),
            ),
        )
        self.objectives = self
        self.evaluator = SimpleNamespace(for_objective=lambda _objective_id: None)

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

    def open_objective(self, sensor_event, route, *, owner_function, **kwargs):
        oid = f"obj-{sensor_event['event_id']}"
        objective = self._objectives.get(oid)
        if objective is None:
            objective = FakeObjective(oid, sensor_event["trace_id"])
            self._objectives[oid] = objective
            self.objective_events.append(("opened", oid))
        return objective

    def transition_objective(self, objective_id, to_status, **kwargs):
        objective = self._objectives[objective_id]
        objective.status = to_status
        self.objective_events.append((to_status, objective_id))
        return objective

    def get(self, objective_id):
        return self._objectives.get(objective_id)

    def fail_objective(self, objective_id, **kwargs):
        objective = self._objectives.get(objective_id)
        if objective is None or objective.status in {"resolved", "failed", "superseded"}:
            return objective
        return self.transition_objective(objective_id, "failed", **kwargs)

    def apply_typed_command(self, objective, command):
        self.applied.append(command)
        return SimpleNamespace(event_id="evt-command", type="command.accepted")


def app_state():
    state = SimpleNamespace(
        bus=EventBus(), world_service=FakeWorld(), world_last_response=None,
        store=StateStore(), hub=MagicMock(), audit=MagicMock(),
        orchestration_history={}, runtime=_AGENCY_RUNTIME,
    )
    state.workflow_event_ingestor = WorkflowEventIngestor(state)
    return state


def sensor(trace="trace-1"):
    return FleetEvent(
        type="world.sensor.tripped",
        simulation_event={
            "event_id": "evt-sensor",
            "trace_id": trace,
            "actor_id": "sensor:support_pressure",
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
    # Canonical Workflow created BEFORE scheduling, with a deterministic
    # sensor-event-based id and objective_id in the Durable payload (no
    # prefix-trace id reconstruction).
    assert schedule.await_args.args[0]["workflow_id"] == "surge-evt-sensor"
    assert schedule.await_args.args[0]["objective_id"] == "obj-evt-sensor"
    assert schedule.await_args.args[0]["trace_id"] == "trace-1"
    w = state.store.get_workflow("surge-evt-sensor")
    assert w is not None
    # Command applied, but the workflow stays NONTERMINAL pending Phase 3
    # world-recovery evaluation — never completed/resolved here.
    assert w.status == "in_progress"
    assert w.payload["decision"]["command"]["command_id"] == "cmd-1"
    assert state.world_service.applied[0].command_id == "cmd-1"
    assert [kind for kind, _ in state.world_service.recorded] == [
        "responder.requested", "responder.decided"
    ]
    for _, recorded in state.world_service.recorded:
        assert recorded["payload"]["workflow_id"] == "surge-evt-sensor"
        assert recorded["payload"]["workflow_type"] == "surge-staffing"
    assert state.world_service.objective_events == [
        ("opened", "obj-evt-sensor"),
        ("claimed", "obj-evt-sensor"),
        ("acting", "obj-evt-sensor"),
    ]
    assert state.world_last_response["command"]["command_id"] == "cmd-1"
    assert state.world_last_response["result_event_id"] == "evt-command"


@pytest.mark.asyncio
async def test_stop_cancels_in_flight_responses_before_world_reset(monkeypatch):
    state = app_state()
    bridge = WorldBridge(state)
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration",
        AsyncMock(
            return_value={
                "id": "durable-reset",
                "statusQueryGetUri": "status://reset",
            }
        ),
    )

    async def never_complete(*_args, **_kwargs):
        await asyncio.Future()

    bridge._await_output = never_complete
    bridge.start()
    state.bus.emit(sensor("trace-reset"))
    await asyncio.sleep(0)
    tasks = tuple(bridge._tasks)
    assert tasks

    bridge.stop()
    await asyncio.sleep(0)

    assert all(task.cancelled() for task in tasks)
    assert state.world_service.applied == []
    assert bridge._in_flight_event_ids == set()


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
    assert state.world_service._objectives["obj-evt-sensor"].status == "failed"
    assert state.world_last_response is None
    # Canonical workflow reflects the genuine failure (nothing applied) — but
    # is NOT completed/resolved.
    w = state.store.get_workflow("surge-evt-sensor")
    assert w is not None and w.status == "failed"


@pytest.mark.asyncio
async def test_command_rejected_routes_workflow_failure_without_decision_ready(monkeypatch):
    state = app_state()
    bridge = WorldBridge(state)
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration",
        AsyncMock(return_value={"id": "durable-1", "statusQueryGetUri": "status://1"}),
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

    rejection_reason = "worker WRK-31 is no longer available"
    rejection_payload = {
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
        "reason": rejection_reason,
    }

    def reject_command(objective, command):
        state.world_service.applied.append(command)
        state.world_service.transition_objective(objective.id, "failed")
        return SimpleNamespace(
            event_id="evt-command-rejected",
            type="command.rejected",
            payload=rejection_payload,
        )

    state.world_service.apply_typed_command = reject_command
    decided = AsyncMock(wraps=bridge._adapter.decided)
    failed = AsyncMock(wraps=bridge._adapter.failed)
    bridge._adapter.decided = decided
    bridge._adapter.failed = failed

    bridge.start()
    state.bus.emit(sensor())
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    decided.assert_not_awaited()
    failed.assert_awaited_once()
    assert failed.await_args.args == ("surge-evt-sensor", "durable-1", rejection_reason)

    w = state.store.get_workflow("surge-evt-sensor")
    assert w is not None
    assert w.status == "failed"
    assert w.metadata["world_lifecycle"] == "failed"
    assert w.metadata["failure_reason"] == rejection_reason
    assert "decision" not in (w.payload or {})
    assert state.world_service._objectives["obj-evt-sensor"].status == "failed"
    assert state.world_service.objective_events == [
        ("opened", "obj-evt-sensor"),
        ("claimed", "obj-evt-sensor"),
        ("acting", "obj-evt-sensor"),
        ("failed", "obj-evt-sensor"),
    ]
    assert state.world_last_response == {
        "instance_id": "durable-1",
        "observation": {
            "trace_id": "trace-1",
            "queued_tickets": [{"id": "TKT-1", "required_skill": "technical"}],
            "reserve_workers": [{"id": "WRK-31", "skills": ["technical"]}],
        },
        "output": {
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
        },
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
        "result_event_id": "evt-command-rejected",
        "result_type": "command.rejected",
        "result_payload": rejection_payload,
        "objective_id": "obj-evt-sensor",
        "workflow_id": "surge-evt-sensor",
    }


@pytest.mark.asyncio
async def test_delayed_evaluation_event_completes_the_canonical_workflow():
    state = app_state()
    bridge = WorldBridge(state)
    bridge._workflow_by_objective["obj-delayed"] = (
        "incident-evt-delayed",
        "durable-delayed",
    )
    bridge._decision_ready.add("obj-delayed")
    bridge._adapter.resolved = AsyncMock()
    bridge.start()

    state.bus.emit(
        FleetEvent(
            type="world.evaluation.resolved",
            simulation_event={
                "type": "evaluation.resolved",
                "payload": {
                    "objective_id": "obj-delayed",
                    "status": "resolved",
                    "evidence_event_ids": ["evt-site-recovered"],
                },
            },
        )
    )
    await asyncio.sleep(0)

    bridge._adapter.resolved.assert_awaited_once_with(
        "incident-evt-delayed",
        "durable-delayed",
        {
            "objective_id": "obj-delayed",
            "status": "resolved",
            "evidence_event_ids": ["evt-site-recovered"],
        },
    )
    assert "obj-delayed" not in bridge._workflow_by_objective


@pytest.mark.asyncio
async def test_canonical_workflow_is_created_before_scheduling(monkeypatch):
    state = app_state()
    bridge = WorldBridge(state)
    gate = asyncio.Event()
    seen_before_schedule = {}

    async def schedule(*args):
        # The canonical Workflow MUST exist in the store before we schedule.
        seen_before_schedule["w"] = state.store.get_workflow("surge-evt-sensor")
        await gate.wait()
        return {"id": "durable-1", "statusQueryGetUri": "status://1"}

    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration",
        AsyncMock(side_effect=schedule),
    )
    bridge._await_output = AsyncMock(return_value={"command": None, "reasoning": "x"})
    bridge.start()
    state.bus.emit(sensor())
    await asyncio.sleep(0)

    w = seen_before_schedule.get("w")
    assert w is not None, "workflow must be upserted before Durable scheduling"
    assert w.id == "surge-evt-sensor"
    assert w.type == "surge-staffing"
    assert w.payload["objective_id"] == "obj-evt-sensor"
    assert w.payload["trace_id"] == "trace-1"
    gate.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)


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
async def test_unknown_sensor_is_journalled_unroutable_without_scheduling(monkeypatch):
    state = app_state()
    bridge = WorldBridge(state)
    scheduled = AsyncMock()
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration", scheduled
    )
    bridge.start()
    event = sensor()
    event.simulation_event["actor_id"] = "sensor:unknown"

    state.bus.emit(event)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    scheduled.assert_not_awaited()
    assert state.world_service.recorded == [
        (
            "objective.unroutable",
            {
                "trace_id": "trace-1",
                "cause_event_id": "evt-sensor",
                "payload": {
                    "sensor_id": "sensor:unknown",
                    "sensor_event_id": "evt-sensor",
                },
            },
        )
    ]


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
    assert state.world_service._objectives["obj-evt-sensor"].status == "failed"
    assert "evt-sensor" not in bridge._in_flight_event_ids

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
