"""Behavioural proof for WorldBridge: sensor trace -> Durable command -> actor world.

Uses a fake ``ActorWorldService`` (build_observation/record_external/apply_command)
and monkeypatches the Durable scheduler + status poller, so no real func host is
required.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx

from api.server.services import pending_gates
from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.server.services.world_bridge import WorldBridge, _hitl_gate, _sensor_id
from api.server.services.world_responders import (
    resolve_responder as _real_resolve_responder,
)
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
    assert state.world_service.objective_events == [
        ("opened", "obj-evt-sensor"),
        ("claimed", "obj-evt-sensor"),
        ("acting", "obj-evt-sensor"),
    ]
    assert state.world_last_response["command"]["command_id"] == "cmd-1"
    assert state.world_last_response["result_event_id"] == "evt-command"


@pytest.mark.asyncio
async def test_duplicate_sensor_delivery_after_scheduling_does_not_reschedule(monkeypatch):
    """A sensor event redelivered (e.g. at-least-once transport replay) AFTER
    its workflow has already been scheduled must never trigger a second
    Durable orchestration -- regardless of the objective's own current
    status in between.

    This is a stronger, transport-level guarantee than the existing
    ``objective.id != objective_id(...)`` "already active" check just above
    ``_adapter.start`` in ``_drive``: that check only stops a *different*,
    overlapping sensor event while a prior objective for the same (type,
    target) is still live. It does nothing for a literal redelivery of the
    exact same sensor event once the world's own objective bookkeeping has
    moved on (resolved/failed/superseded) or a permissive world implementation
    simply hands back a fresh-looking objective for the identical id -- in
    both cases ``objective.id`` still equals ``objective_id(event_id)``, so
    that check alone never fires. The workflow id is deterministic in the
    sensor event id alone (``WorldWorkflowAdapter.start``), so once a
    workflow already carries a Durable ``orchestration_instance_id`` for that
    id, redelivery of the same event must be a pure no-op.
    """
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

    event = sensor()
    state.bus.emit(event)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert schedule.await_count == 1
    w = state.store.get_workflow("surge-evt-sensor")
    assert w is not None and w.orchestration_instance_id == "durable-1"
    # Sanity: the in-flight guard has already cleared for this event_id, so a
    # second emit below genuinely exercises the *post-scheduling* duplicate
    # path rather than being silently absorbed by the earlier, simpler
    # still-in-flight guard.
    assert "evt-sensor" not in bridge._in_flight_event_ids

    # Redeliver the identical sensor event (same event_id/trace_id) -- e.g.
    # an at-least-once bus replaying a message it never saw acked, arriving
    # strictly after the first delivery's workflow already scheduled.
    state.bus.emit(event)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert schedule.await_count == 1, (
        "duplicate sensor delivery must not schedule a second Durable orchestration"
    )


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
async def test_canonical_workflow_is_created_only_after_scheduling_is_accepted(monkeypatch):
    state = app_state()
    bridge = WorldBridge(state)
    gate = asyncio.Event()
    seen_while_scheduling = {}

    async def schedule(*args):
        seen_while_scheduling["w"] = state.store.get_workflow("surge-evt-sensor")
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

    assert seen_while_scheduling.get("w") is None
    assert state.store.get_workflow("surge-evt-sensor") is None
    gate.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    w = state.store.get_workflow("surge-evt-sensor")
    assert w is not None, "workflow must be upserted after Durable accepts scheduling"
    assert w.id == "surge-evt-sensor"
    assert w.type == "surge-staffing"
    assert w.payload["objective_id"] == "obj-evt-sensor"
    assert w.payload["trace_id"] == "trace-1"


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
async def test_sensor_routes_via_payload_sensor_id_when_it_differs_from_actor_id(
    monkeypatch,
):
    """A detector may need ``actor_id`` for its own causal-chain identity
    (e.g. "which disruption record tripped this") while the registered
    ``ObjectiveRoute.sensor_id`` lives in ``payload["sensor_id"]`` instead.
    Routing must prefer the payload value when present, so such a detector
    still reaches the registered objective route -- not "unroutable"."""
    state = app_state()
    bridge = WorldBridge(state)
    schedule = AsyncMock(
        return_value={"id": "durable-1", "statusQueryGetUri": "status://1"}
    )
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration", schedule
    )
    bridge._await_output = AsyncMock(
        return_value={"command": None, "reasoning": "no reserve workers"}
    )
    bridge.start()
    event = sensor()
    event.simulation_event["actor_id"] = "DIS-some-disruption-record"
    event.simulation_event["payload"] = {
        "sensor_id": "sensor:support_pressure",
        "actor_ids": ["TKT-1"],
    }

    state.bus.emit(event)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    schedule.assert_awaited_once()
    assert "objective.unroutable" not in [
        kind for kind, _ in state.world_service.recorded
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


# --- _hitl_gate: pure extraction of a Durable customStatus HITL declaration.
#
# Any generated-vertical orchestrator may call the standard Durable
# ``context.set_custom_status(...)`` right before racing a HITL wait. This
# helper is the ONE place the bridge decides whether a status-query response
# is declaring an active wait worth surfacing to the operator queue — no
# vertical vocabulary, no HTTP, no async: plain dict in, plain dict or
# ``None`` out.

def test_hitl_gate_is_none_when_custom_status_is_absent():
    assert _hitl_gate({"runtimeStatus": "Running"}) is None


def test_hitl_gate_is_none_when_custom_status_is_not_a_dict():
    assert _hitl_gate({"runtimeStatus": "Running", "customStatus": "waiting"}) is None


def test_hitl_gate_is_none_when_phase_is_missing():
    assert _hitl_gate({
        "runtimeStatus": "Running",
        "customStatus": {"external_event": "SurgeApproval"},
    }) is None


def test_hitl_gate_is_none_when_external_event_is_missing():
    assert _hitl_gate({
        "runtimeStatus": "Running",
        "customStatus": {"phase": "approve_material_change"},
    }) is None


def test_hitl_gate_is_none_when_data_itself_is_not_a_dict():
    assert _hitl_gate(None) is None


def test_hitl_gate_returns_the_custom_status_when_phase_and_external_event_present():
    custom_status = {
        "phase": "approve_material_change",
        "external_event": "SurgeApproval",
        "reason": "cost exceeds bound",
        "wait_kind": "operator_review",
    }
    assert _hitl_gate({"runtimeStatus": "Running", "customStatus": custom_status}) == custom_status


# --- _sensor_id: some detectors need ``actor_id`` to carry a *different*
# identity of their own (e.g. which disruption/resource record tripped the
# condition, for causal-chain purposes) and instead publish the id of the
# ObjectiveRoute they intend to trip inside ``payload["sensor_id"]``. Routing
# must resolve the registered route from whichever one actually carries it --
# preferring the payload value, falling back to ``actor_id`` so every
# existing detector that has no such payload key keeps working unchanged.

def test_sensor_id_prefers_payload_sensor_id_over_actor_id():
    event = {
        "actor_id": "DIS-some-disruption-record",
        "payload": {"sensor_id": "sensor:support_pressure"},
    }
    assert _sensor_id(event) == "sensor:support_pressure"


def test_sensor_id_falls_back_to_actor_id_when_payload_has_no_sensor_id():
    event = {"actor_id": "sensor:support_pressure", "payload": {"actor_ids": ["TKT-1"]}}
    assert _sensor_id(event) == "sensor:support_pressure"


def test_sensor_id_falls_back_to_actor_id_when_payload_is_not_a_dict():
    event = {"actor_id": "sensor:support_pressure", "payload": None}
    assert _sensor_id(event) == "sensor:support_pressure"


def test_sensor_id_falls_back_to_actor_id_when_payload_key_missing():
    event = {"actor_id": "sensor:support_pressure"}
    assert _sensor_id(event) == "sensor:support_pressure"


def test_sensor_id_is_none_when_neither_payload_sensor_id_nor_actor_id_present():
    assert _sensor_id({"payload": {}}) is None


# --- _await_output: the ONE place a `customStatus` HITL gate becomes visible
# (StateStore workflow status + pending_gates cache) via the ALREADY generic,
# already-tested `workflow_event_ingestor.ingest(..., "suspended"/"resumed")`
# path -- reusing exactly the same channel the operator-facing
# `/api/exceptions/{id}/resolve` route already reads. No vertical branches:
# this is driven entirely by the generic "support" fixture used throughout
# this file.

@respx.mock
@pytest.mark.asyncio
async def test_await_output_makes_a_custom_status_gate_visible_then_clears_it_on_completion(
    monkeypatch,
):
    pending_gates.reset()
    state = app_state()
    bridge = WorldBridge(state)
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration",
        AsyncMock(return_value={
            "id": "durable-1",
            "statusQueryGetUri": "http://fake-durable.test/status/1",
        }),
    )

    poll_count = {"n": 0}
    mid_flight_snapshot: dict = {}

    def _status_handler(request: httpx.Request) -> httpx.Response:
        poll_count["n"] += 1
        if poll_count["n"] == 1:
            return httpx.Response(200, json={
                "runtimeStatus": "Running",
                "customStatus": {
                    "phase": "approve_material_change",
                    "external_event": "SurgeApproval",
                    "reason": "cost exceeds bound",
                    "wait_kind": "operator_review",
                },
            })
        # Second poll: prove the FIRST poll's gate was already made visible
        # through the exact same generic channels the admin UI and the
        # `/api/exceptions` operator-resolve route read -- BEFORE the
        # orchestration has resolved, not after the fact.
        w = state.store.get_workflow("surge-evt-sensor")
        mid_flight_snapshot["status"] = w.status if w else None
        mid_flight_snapshot["gate"] = pending_gates.get("surge-evt-sensor")
        return httpx.Response(200, json={"runtimeStatus": "Completed", "output": {
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
        }})

    respx.get("http://fake-durable.test/status/1").mock(side_effect=_status_handler)

    await bridge._drive(sensor().simulation_event)

    assert poll_count["n"] == 2
    assert mid_flight_snapshot["status"] == "awaiting_hitl"
    assert mid_flight_snapshot["gate"] == {
        "phase": "approve_material_change",
        "external_event": "SurgeApproval",
    }
    # Terminal poll must have ingested "resumed" before returning, clearing
    # both the workflow status and the pending-gate cache -- never leaving a
    # stale gate behind once the orchestration actually resolved.
    w = state.store.get_workflow("surge-evt-sensor")
    assert w is not None
    assert w.status == "in_progress"
    assert pending_gates.get("surge-evt-sensor") is None
    assert state.world_service.applied[0].command_id == "cmd-1"


@respx.mock
@pytest.mark.asyncio
async def test_drive_keeps_polling_through_a_declared_hitl_wait_then_applies_once(
    monkeypatch,
):
    """A generic gate's declared wait, not the responder's normal activity
    timeout, owns the poll deadline while the gate remains open.

    The fake clock jumps from the initial gate poll to a five-minute-later
    approval/completion response without a wall-clock wait. The gate declares
    a thirty-minute wait, while the responder's ordinary activity timeout is
    only three minutes. A duplicate sensor delivery after completion must
    still not apply the command a second time.
    """
    pending_gates.reset()
    state = app_state()
    bridge = WorldBridge(state)
    schedule = AsyncMock(return_value={
        "id": "durable-delayed-hitl",
        "statusQueryGetUri": "http://fake-durable.test/status/delayed-hitl",
    })
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration", schedule
    )

    def _three_minute_responder(runtime, objective_type):
        responder = _real_resolve_responder(runtime, objective_type)
        return replace(responder, timeout_seconds=180.0)

    monkeypatch.setattr(
        "api.server.services.world_bridge.resolve_responder",
        _three_minute_responder,
    )

    clock = SimpleNamespace(now=0.0)
    real_get_event_loop = asyncio.get_event_loop
    real_sleep = asyncio.sleep
    monkeypatch.setattr(
        "api.server.services.world_bridge.asyncio.get_event_loop",
        lambda: SimpleNamespace(time=lambda: clock.now),
    )

    async def _advance_to_delayed_approval(_seconds):
        clock.now = 300.0

    monkeypatch.setattr(
        "api.server.services.world_bridge.asyncio.sleep",
        _advance_to_delayed_approval,
    )

    poll_count = {"n": 0}

    def _status_handler(request: httpx.Request) -> httpx.Response:
        poll_count["n"] += 1
        if poll_count["n"] == 1:
            return httpx.Response(200, json={
                "runtimeStatus": "Running",
                "customStatus": {
                    "phase": "approval",
                    "external_event": "ApproveRecovery",
                    "wait_kind": "operator_review",
                    "wait_seconds": 1800.0,
                },
            })
        return httpx.Response(200, json={"runtimeStatus": "Completed", "output": {
            "command": {
                "command_id": "cmd-delayed-hitl",
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
            "reasoning": "operator approved after five minutes",
        }})

    respx.get("http://fake-durable.test/status/delayed-hitl").mock(
        side_effect=_status_handler
    )

    event = sensor().simulation_event
    try:
        await bridge._drive(event)
    finally:
        monkeypatch.setattr(
            "api.server.services.world_bridge.asyncio.get_event_loop",
            real_get_event_loop,
        )
        monkeypatch.setattr(
            "api.server.services.world_bridge.asyncio.sleep",
            real_sleep,
        )

    assert poll_count["n"] == 2
    assert [command.command_id for command in state.world_service.applied] == [
        "cmd-delayed-hitl"
    ]
    assert "responder.failed" not in [
        event_type for event_type, _kwargs in state.world_service.recorded
    ]
    assert state.store.get_workflow("surge-evt-sensor").status == "in_progress"

    await bridge._drive(event)
    assert schedule.await_count == 1
    assert [command.command_id for command in state.world_service.applied] == [
        "cmd-delayed-hitl"
    ]


# ---------------------------------------------------------------------------
# Task 7 quality issue #1: `_await_output`'s HTTP-poll try/except must never
# also swallow the state-mutating `workflow_event_ingestor.ingest(...)` calls
# it makes for "suspended"/"resumed". Those ingests touch the real
# StateStore/pending-gates/ledger/audit trail, so a genuine bug in one of them
# must raise and surface immediately -- never be silently retried until the
# poll deadline and then misreported as "no orchestration output" (a real,
# completed Durable output existed the whole time). Both tests below call
# `_await_output` directly (never `_drive`) so the assertions are unambiguous
# about which method actually raises.
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_await_output_propagates_a_failing_suspended_ingest_instead_of_swallowing_it(
    monkeypatch,
):
    """A genuinely broken 'suspended' ingest (a state-mutating StateStore /
    pending-gates / ledger / audit call) must raise all the way out of
    `_await_output` on the very first poll that observes the HITL gate --
    never be silently swallowed and retried, which would leave the real
    ingest bug invisible while the poll loop spins pointlessly toward its
    deadline."""
    pending_gates.reset()
    state = app_state()
    bridge = WorldBridge(state)
    workflow_id = "surge-evt-suspend-fail"
    instance_id = "durable-suspend-fail"
    bridge._workflow_by_objective["obj-suspend-fail"] = (workflow_id, instance_id)

    poll_count = {"n": 0}

    def _status_handler(request: httpx.Request) -> httpx.Response:
        poll_count["n"] += 1
        return httpx.Response(200, json={
            "runtimeStatus": "Running",
            "customStatus": {
                "phase": "approve_material_change",
                "external_event": "SurgeApproval",
                "reason": "cost exceeds bound",
                "wait_kind": "operator_review",
            },
        })

    respx.get("http://fake-durable.test/status/suspend-fail").mock(side_effect=_status_handler)

    boom = RuntimeError("suspended ingest exploded")

    async def _raising_ingest(wid, iid, kind, payload):
        assert kind == "suspended"
        raise boom

    monkeypatch.setattr(state.workflow_event_ingestor, "ingest", _raising_ingest)

    with pytest.raises(RuntimeError, match="suspended ingest exploded"):
        await bridge._await_output(
            instance_id, "http://fake-durable.test/status/suspend-fail", timeout=3,
        )

    assert poll_count["n"] == 1, "must raise on the very first poll -- never swallowed and retried"


@respx.mock
@pytest.mark.asyncio
async def test_await_output_propagates_a_failing_resumed_ingest_after_completed_instead_of_swallowing_it(
    monkeypatch,
):
    """A genuinely broken 'resumed' ingest that fires right after Durable
    already reports Completed (with a real, usable `output`) must raise
    immediately -- never be silently swallowed, repolled toward the
    deadline, and only THEN returned as `None`, which would misrepresent a
    real, successful recovery as though nothing had come back at all."""
    pending_gates.reset()
    state = app_state()
    bridge = WorldBridge(state)
    workflow_id = "surge-evt-resume-fail"
    instance_id = "durable-resume-fail"
    bridge._workflow_by_objective["obj-resume-fail"] = (workflow_id, instance_id)

    poll_count = {"n": 0}

    def _status_handler(request: httpx.Request) -> httpx.Response:
        poll_count["n"] += 1
        if poll_count["n"] == 1:
            return httpx.Response(200, json={
                "runtimeStatus": "Running",
                "customStatus": {
                    "phase": "approve_material_change",
                    "external_event": "SurgeApproval",
                    "reason": "cost exceeds bound",
                    "wait_kind": "operator_review",
                },
            })
        return httpx.Response(200, json={
            "runtimeStatus": "Completed",
            "output": {"command": {"command_id": "cmd-resume-fail"}, "reasoning": "done"},
        })

    respx.get("http://fake-durable.test/status/resume-fail").mock(side_effect=_status_handler)

    real_ingest = state.workflow_event_ingestor.ingest
    boom = RuntimeError("resumed ingest exploded")

    async def _selective_ingest(wid, iid, kind, payload):
        if kind == "resumed":
            raise boom
        return await real_ingest(wid, iid, kind, payload)

    monkeypatch.setattr(state.workflow_event_ingestor, "ingest", _selective_ingest)

    with pytest.raises(RuntimeError, match="resumed ingest exploded"):
        await bridge._await_output(
            instance_id, "http://fake-durable.test/status/resume-fail", timeout=3,
        )

    assert poll_count["n"] == 2, (
        "must raise as soon as Completed is observed -- never repoll toward timeout"
    )


@respx.mock
@pytest.mark.asyncio
async def test_drive_surfaces_the_true_resumed_ingest_error_not_a_fabricated_no_output_narrative(
    monkeypatch,
):
    """End-to-end through `_drive`: a Completed Durable output already
    existed when the terminal 'resumed' ingest genuinely failed. `_drive`'s
    outer handler must record the TRUE ingest error -- never the unrelated,
    specific "no orchestration output" narrative that would misrepresent a
    real, successful recovery as if Durable had produced nothing at all
    (issue #1's "falsely fail a real recovery" bug). No false
    `responder.failed`/objective failure is fabricated: the ONE
    `responder.failed` recorded here must carry the real ingest error, and
    the command must never have been (mis)applied."""
    pending_gates.reset()
    state = app_state()
    bridge = WorldBridge(state)
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration",
        AsyncMock(return_value={
            "id": "durable-drive-resume-fail",
            "statusQueryGetUri": "http://fake-durable.test/status/drive-resume-fail",
        }),
    )

    # Keep this test fast regardless of the registered 90s responder
    # timeout: the fix must surface the ingest failure on the very next
    # poll, never by exhausting a real timeout window.
    def _short_timeout_resolve_responder(runtime, objective_type):
        responder = _real_resolve_responder(runtime, objective_type)
        return replace(responder, timeout_seconds=3.0)

    monkeypatch.setattr(
        "api.server.services.world_bridge.resolve_responder",
        _short_timeout_resolve_responder,
    )

    poll_count = {"n": 0}

    def _status_handler(request: httpx.Request) -> httpx.Response:
        poll_count["n"] += 1
        if poll_count["n"] == 1:
            return httpx.Response(200, json={
                "runtimeStatus": "Running",
                "customStatus": {
                    "phase": "approve_material_change",
                    "external_event": "SurgeApproval",
                    "reason": "cost exceeds bound",
                    "wait_kind": "operator_review",
                },
            })
        return httpx.Response(200, json={"runtimeStatus": "Completed", "output": {
            "command": {
                "command_id": "cmd-drive-resume-fail",
                "trace_id": "trace-drive-resume-fail",
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
        }})

    respx.get("http://fake-durable.test/status/drive-resume-fail").mock(side_effect=_status_handler)

    real_ingest = state.workflow_event_ingestor.ingest
    boom = RuntimeError("resumed ingest exploded")

    async def _selective_ingest(wid, iid, kind, payload):
        if kind == "resumed":
            raise boom
        return await real_ingest(wid, iid, kind, payload)

    monkeypatch.setattr(state.workflow_event_ingestor, "ingest", _selective_ingest)

    await bridge._drive(sensor(trace="trace-drive-resume-fail").simulation_event)

    assert poll_count["n"] == 2, (
        "must surface the resumed-ingest failure right after Completed -- "
        "never repoll toward the timeout"
    )
    failed_events = [
        kwargs for etype, kwargs in state.world_service.recorded
        if etype == "responder.failed"
    ]
    assert len(failed_events) == 1, "exactly one true failure must be recorded, never a fabricated one"
    assert failed_events[0]["payload"]["error"] == "resumed ingest exploded"
    assert failed_events[0]["payload"].get("error") != "no orchestration output"
    # The real Completed output was never even reached by `_drive` (the
    # exception unwound from inside `_await_output`), so nothing was
    # fabricated as decided/applied either.
    assert state.world_service.applied == []
