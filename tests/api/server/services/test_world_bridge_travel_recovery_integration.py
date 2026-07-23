"""End-to-end proof for Task 6's Travel flight-disruption-recovery wiring:
the autonomous minute-180 state-derived sensor -> registered objective ->
real Azure Durable orchestration -> conditional HITL gate -> typed
`reaccommodate_travellers` command -> atomic world mutation -> objective
evaluation chain, all driven through the real, industry-neutral
`WorldBridge`/`WorldWorkflowAdapter` (never a Travel-specific bridge).

This file never calls a `/processes/*/run` route, a direct workflow-start
endpoint, or anything resembling a "Run" button: every scenario below is
triggered purely by publishing a real `sensor.tripped` `FleetEvent` onto the
`EventBus` -- exactly what `ActorWorldService._publish_new()` does once the
real, generated `verticals.travel.worlds.processes.detect_flight_cancellation_impact`
(Task 5's own autonomous minute-180 process) or a hand-built low-cost
disruption (mirroring `tests/api/functions/test_travel_recovery_functions.py`'s
own `_low_cost_world_and_observation` mechanics) reports one. Every HTTP call
observed in these tests targets only the fake Durable host below
(`http://localhost:7071/...`) -- there is no FastAPI app/TestClient/route in
play at all here, so no direct-run route could structurally be exercised.

The real Durable orchestrator generator (`TravelFlightDisruptionRecoveryOrchestrator`,
imported unmodified from `verticals.travel.durable.functions`) is driven to
completion by a small fake Durable HTTP host that intercepts exactly the
`durable_client.py` HTTP surface (`respx.mock`, matching
`schedule_new_orchestration`/`raise_orchestration_event`'s real URL
construction) and dispatches every `call_activity` yield to the real,
imported activity functions -- mirroring
`test_travel_recovery_functions.py`'s own `_drive_with_real_activities`
exactly (`_FakeContext`/`_FakeTask` are imported directly from that module
rather than reimplemented, so the two files can never silently drift). The
one thing genuinely faked here is the Durable *transport*; the orchestrator,
its activities, the recovery planner, the command handler and the world
mutation are all the real, unmodified production modules.

The high-cost golden path's HITL approval/decline is driven through the
REAL, existing, generic `POST /api/exceptions/{id}/resolve` operator route
handler (`api.server.routes.exceptions._resolve_one`, called directly and
monkeypatched onto this test's own lightweight `SimpleNamespace` app_state)
-- never a hand-rolled shortcut that resumes the fake host directly. This is
the "generic existing decision/event API" Part D requires; no new HITL
plumbing was added to reach it. `test_travel_recovery_functions.py` already
exhaustively proves the orchestrator's own internal classification of
declined/timed-out/malformed/wrong-actor/stale-option approvals (all
collapse to an identical `command=None` bridge-visible outcome), so this
file proves only ONE representative terminal-failure path (decline) at the
bridge-integration level -- re-deriving all five sub-cases here would just
duplicate file 1's own, already-passing coverage without adding signal.

Before this file's underlying capability existed, the golden/low-cost paths
below would fail with an `ImportError`/`ModuleNotFoundError` for
`verticals.travel.recovery`/`verticals.travel.durable.functions`, or (once
those existed but the bridge itself had not yet been extended for Travel's
`actor_id`-carries-disruption-id sensor convention) a `ValueError` from
`resolve_objective_route` / an `objective.unroutable` diagnostic instead of
a scheduled orchestration -- a missing capability, never a syntax error.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
import respx

import api.server.routes.exceptions as exceptions_module
import api.server.services.world_bridge as world_bridge_module
import api.server.services.pending_gates as pending_gates
from api.server.routes.exceptions import _resolve_one
from api.server.services.durable_client import FUNCTIONS_HOST as _FUNCTIONS_HOST
from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.server.services.world_bridge import SENSOR_EVENT, WorldBridge
from api.server.world.service import ActorWorldService
from api.shared.vertical_loader import build_runtime
from tests.api.functions.test_travel_recovery_functions import (
    _FakeContext,
    _FakeTask,
    _GOLDEN_CANDIDATE_FLIGHT_AND_TRANSFER_IDS,
    _LOW_COST_BOOKING_ID,
    _LOW_COST_FLIGHT_ID,
    _LOW_COST_REPLACEMENT_FLIGHT_ID,
)
from verticals.travel.durable import functions as travel_durable_functions
from verticals.travel.durable.functions import TravelFlightDisruptionRecoveryOrchestrator
from verticals.travel.worlds import processes as travel_processes

# --- golden scenario: FLT-ZV204 cancelled at minute 180 (same as file 1) ---

_GOLDEN_FLIGHT_ID = "FLT-ZV204"
_GOLDEN_NEW_FLIGHT_ID = "FLT-ZV205"
_GOLDEN_BOOKING_ID = "BKG-4"
_GOLDEN_PARTY_ID = "PTY-4"
_GOLDEN_MEMBER_CUSTOMER_IDS = ("CUS-8", "CUS-9")
_GOLDEN_DISRUPTION_ID = f"DIS-flight_cancellation-{_GOLDEN_FLIGHT_ID}"
_GOLDEN_INCREMENTAL_COST_GBP = 900.0
_DISRUPTION_MINUTE = 180.0
_ORCHESTRATOR_NAME = "TravelFlightDisruptionRecoveryOrchestrator"


# ---------------------------------------------------------------------------
# Fake Durable HTTP host: drives the REAL orchestrator generator, dispatching
# every activity yield to the REAL, imported activity functions. Intercepts
# only the transport (respx against durable_client.py's exact URL shapes);
# everything downstream of that boundary is genuine production code.
# ---------------------------------------------------------------------------


class _HostedInstance:
    """One running orchestration instance: a real generator + fake context."""

    def __init__(self, instance_id: str, input_data: dict) -> None:
        self.instance_id = instance_id
        self.context = _FakeContext(
            input_data, utc_now=datetime(2024, 1, 1, tzinfo=timezone.utc)
        )
        self._gen = TravelFlightDisruptionRecoveryOrchestrator(self.context)
        self.pending_race: tuple[_FakeTask, _FakeTask] | None = None
        self.output: dict | None = None
        self.completed = False
        self._sent = None
        self._advance()

    def _advance(self) -> None:
        """Drive the real generator until it either completes or pauses at
        the `task_any([approval, timer])` HITL race -- calling the real
        imported activity for every `call_activity` yield, exactly mirroring
        `test_travel_recovery_functions.py`'s own `_drive_with_real_activities`."""
        while True:
            try:
                yielded = self._gen.send(self._sent)
            except StopIteration as stop:
                self.output = stop.value
                self.completed = True
                return
            if isinstance(yielded, _FakeTask):
                name = yielded.label.split(":", 1)[1]
                activity = getattr(travel_durable_functions, name)
                self._sent = activity(self.context.activity_calls[-1][1])
                continue
            if isinstance(yielded, list):
                self.pending_race = tuple(yielded)  # (approval_task, timer_task)
                return
            raise AssertionError(f"unexpected yielded value from orchestrator: {yielded!r}")

    def raise_event(self, payload: dict) -> None:
        """Resolve the pending race in favour of the external-event task --
        exactly what a real Durable host does when `raiseEvent` is called."""
        assert self.pending_race is not None, "no pending HITL race to raise an event into"
        approval_task, _timer_task = self.pending_race
        approval_task.result = payload
        approval_task.is_completed = True
        self.pending_race = None
        self._sent = approval_task
        self._advance()

    def status_payload(self) -> dict:
        if self.completed:
            return {"runtimeStatus": "Completed", "output": self.output}
        return {"runtimeStatus": "Running", "customStatus": self.context.custom_status}


class _FakeDurableHTTPHost:
    """Keyed by instance_id; installed behind `respx.mock` HTTP routes below."""

    def __init__(self) -> None:
        self.instances: dict[str, _HostedInstance] = {}
        self._counter = 0
        self.schedule_payloads: list[dict] = []

    def schedule(self, payload: dict) -> dict:
        self._counter += 1
        instance_id = f"fdr-instance-{self._counter}"
        self.schedule_payloads.append(payload)
        self.instances[instance_id] = _HostedInstance(instance_id, payload)
        return {
            "id": instance_id,
            "statusQueryGetUri": f"{_FUNCTIONS_HOST}/status/{instance_id}",
            "sendEventPostUri": f"{_FUNCTIONS_HOST}/raise/{instance_id}/{{eventName}}",
        }

    def raise_event(self, instance_id: str, payload: dict) -> None:
        self.instances[instance_id].raise_event(payload)


def _install_fake_durable_host(host: _FakeDurableHTTPHost, router: respx.MockRouter) -> None:
    """Register routes matching `durable_client.py`'s real URL shapes onto
    the given `respx.MockRouter` instance.

    `router` must be the object returned by `with respx.mock(...) as router:`
    -- a plain call to `respx.mock(...)` used as a context manager (rather
    than as the `@respx.mock` decorator) creates an independent router that
    the bare top-level `respx.post`/`respx.route` helpers do NOT target, so
    routes must be registered on `router` itself. The status route
    deliberately performs no side effects of its own -- approval/decline is
    always driven through the real `_resolve_one` operator route from the
    test body, never smuggled into a mocked poll response.
    """

    def _schedule_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        return httpx.Response(200, json=host.schedule(payload))

    router.post(f"{_FUNCTIONS_HOST}/api/orchestrators/{_ORCHESTRATOR_NAME}").mock(
        side_effect=_schedule_handler
    )

    def _status_handler(request: httpx.Request) -> httpx.Response:
        instance_id = request.url.path.rsplit("/", 1)[-1]
        inst = host.instances[instance_id]
        return httpx.Response(200, json=inst.status_payload())

    router.route(method="GET", url__regex=rf"{_FUNCTIONS_HOST}/status/.*").mock(
        side_effect=_status_handler
    )

    def _raise_handler(request: httpx.Request) -> httpx.Response:
        # sendEventPostUri shape: {_FUNCTIONS_HOST}/raise/{instance_id}/{eventName}
        instance_id = request.url.path.strip("/").split("/")[1]
        host.raise_event(instance_id, json.loads(request.content))
        return httpx.Response(202)

    router.route(method="POST", url__regex=rf"{_FUNCTIONS_HOST}/raise/.*").mock(
        side_effect=_raise_handler
    )


# ---------------------------------------------------------------------------
# Real ActorWorldService + lightweight app_state, mirroring the established
# `test_world_bridge_actor.py` SimpleNamespace idiom -- but with the real
# Travel `ActorWorldService`/`VerticalRuntime` instead of a `FakeWorld`.
# ---------------------------------------------------------------------------


def _travel_state(seed: int = 42) -> SimpleNamespace:
    bus = EventBus()
    runtime = build_runtime({"ZAVA_VERTICAL": "travel"}, data_root=Path("."))
    service = ActorWorldService.for_runtime(runtime, seed=seed, bus=bus)
    state = SimpleNamespace(
        bus=bus,
        world_service=service,
        world_last_response=None,
        store=StateStore(),
        hub=MagicMock(),
        audit=MagicMock(),
        orchestration_history={},
        runtime=runtime,
    )
    state.workflow_event_ingestor = WorkflowEventIngestor(state)
    return state


def _low_cost_disruption(state: SimpleNamespace) -> None:
    """Hand-construct a second, independent flight_cancellation case against
    FLT-ZV102/BKG-2 -- mirroring `test_travel_recovery_functions.py`'s own
    `_low_cost_world_and_observation` mechanics exactly, but applied to the
    SAME `ActorWorldService.scenario`/`.runtime` this test's bridge already
    owns (rather than a standalone `TravelWorld`), so the resulting sensor
    event actually reaches the real `EventBus` via `_publish_new()`.
    """
    service = state.world_service
    service.scenario.run(90.0)  # strictly after FLT-ZV102's own ordinary booking activity
    flight = service.scenario.flights[_LOW_COST_FLIGHT_ID]
    assert flight.status == "scheduled"
    cancelled_event = service.scenario._apply(
        "flight.cancelled", flight, {"status": "cancelled"},
        extra_payload={"reason": "supplier_operational_cancellation"},
    )
    service.scenario.report_disruption(
        kind="flight_cancellation", resource_id=flight.id,
        cause_event_id=cancelled_event.event_id, trace_id=cancelled_event.trace_id,
    )
    travel_processes.detect_flight_cancellation_impact(service.scenario)
    service._publish_new()


async def _run_until(state: SimpleNamespace, workflow_id: str, statuses, *, budget_s: float = 8.0):
    """Poll the canonical `StateStore` Workflow until it reaches one of
    `statuses`, or raise once `budget_s` has elapsed. `_await_output` polls
    the fake Durable host on a genuine 1-second cadence (mirroring
    `_await_output`'s real `asyncio.sleep(1.0)`), so the golden/decline paths
    below genuinely take a couple of real wall-clock seconds -- the same
    accepted pattern already used by
    `test_await_output_makes_a_custom_status_gate_visible_then_clears_it_on_completion`
    in `test_world_bridge_actor.py`.
    """
    deadline = asyncio.get_event_loop().time() + budget_s
    while asyncio.get_event_loop().time() < deadline:
        workflow = state.store.get_workflow(workflow_id)
        if workflow is not None and workflow.status in statuses:
            return workflow
        await asyncio.sleep(0.1)
    raise AssertionError(
        f"workflow {workflow_id} did not reach {statuses} within {budget_s}s "
        f"(last status={getattr(state.store.get_workflow(workflow_id), 'status', None)!r})"
    )


@pytest.mark.asyncio
async def test_unavailable_functions_host_records_world_failure_without_a_phantom_workflow(
    monkeypatch: pytest.MonkeyPatch,
):
    """A failed schedule has no Durable instance, so it cannot leave a workflow."""
    state = _travel_state()
    bridge = WorldBridge(state)
    bridge.start()

    async def unavailable_functions_host(*_args, **_kwargs):
        raise httpx.ConnectError("Functions host is unavailable")

    monkeypatch.setattr(
        world_bridge_module,
        "schedule_new_orchestration",
        unavailable_functions_host,
    )
    try:
        state.world_service.scenario.run(_DISRUPTION_MINUTE)
        state.world_service._publish_new()
        sensor = next(
            event
            for event in state.world_service.runtime.journal
            if event.type == "sensor.tripped" and event.target_id == _GOLDEN_FLIGHT_ID
        )
        workflow_id = f"fdr-{sensor.event_id}"

        for _ in range(20):
            if any(
                event.type == "responder.failed"
                for event in state.world_service.runtime.journal
            ):
                break
            await asyncio.sleep(0)

        assert any(
            event.type == "responder.failed"
            for event in state.world_service.runtime.journal
        )
        assert state.store.get_workflow(workflow_id) is None
    finally:
        bridge.stop()


@pytest.mark.asyncio
async def test_real_travel_schedule_records_one_workflow_started_event_for_agui():
    """Travel's selected host has no webhook starter activity of its own."""
    state = _travel_state()
    bridge = WorldBridge(state)
    bridge.start()
    host = _FakeDurableHTTPHost()
    try:
        with respx.mock(assert_all_called=False) as respx_mock:
            _install_fake_durable_host(host, respx_mock)
            state.world_service.scenario.run(_DISRUPTION_MINUTE)
            state.world_service._publish_new()
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            workflow_id = host.schedule_payloads[0]["workflow_id"]
            await _run_until(state, workflow_id, {"awaiting_hitl"})

            history = state.orchestration_history[workflow_id]
            assert [entry["kind"] for entry in history].count("workflow.started") == 1
    finally:
        bridge.stop()


@pytest.mark.asyncio
async def test_actor_world_disabled_diagnostic_runs_real_durable_to_completion():
    """The explicit diagnostic path has no live actor-world service to mutate."""
    from verticals.travel.worlds.diagnostics import build_diagnostic_input

    state = _travel_state()
    sensor_event, observation = build_diagnostic_input(
        "flight-disruption-recovery"
    )
    responder = state.runtime.pack.worlds["travel"].responders[
        "recover_cancelled_flight"
    ]
    del state.world_service
    bridge = WorldBridge(state)
    host = _FakeDurableHTTPHost()
    original_app_state = exceptions_module.app_state
    exceptions_module.app_state = state
    try:
        with respx.mock(assert_all_called=False) as respx_mock:
            _install_fake_durable_host(host, respx_mock)
            workflow_id = await bridge.start_diagnostic(
                sensor_event=sensor_event,
                responder=responder,
                observation=observation,
            )
            workflow = await _run_until(state, workflow_id, {"awaiting_hitl"})
            exception = next(
                exception
                for exception in state.store.list_exceptions(include_resolved=False)
                if exception.workflow_id == workflow.id
            )
            assert await _resolve_one(
                exception.id, "approve", "head_of_operations"
            )

            workflow = await _run_until(state, workflow_id, {"completed", "failed"})
            assert workflow.status == "completed"
            assert workflow.metadata["diagnostic_only"] is True
            history = state.orchestration_history[workflow_id]
            assert [entry["kind"] for entry in history] == [
                "workflow.started",
                "suspended",
                "resumed",
                "step.started",
                "step.completed",
                "workflow.completed",
            ]
            assert not any(entry["kind"] == "dead_letter" for entry in history)
    finally:
        exceptions_module.app_state = original_app_state
        bridge.stop()


# ---------------------------------------------------------------------------
# A/D/E. Golden high-cost path: sensor -> objective -> Durable -> HITL ->
# real _resolve_one approval -> typed command -> atomic world mutation ->
# evaluation PASS -> objective/workflow resolved.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_golden_high_cost_disruption_requires_hitl_approval_then_completes_recovery():
    state = _travel_state()
    bridge = WorldBridge(state)
    bridge.start()
    host = _FakeDurableHTTPHost()

    original_app_state = exceptions_module.app_state
    exceptions_module.app_state = state
    try:
        with respx.mock(assert_all_called=False) as respx_mock:
            _install_fake_durable_host(host, respx_mock)

            # The ONLY trigger: the real minute-180 autonomous process (Task
            # 5's own deterministic simulation clock -- see
            # `tests/api/world/actor/test_travel_disruption.py`). No
            # `/processes/*/run` route, no direct workflow-start call, no Run
            # button -- just advancing the real simulation clock and letting
            # the world publish whatever it has already journalled.
            state.world_service.scenario.run(_DISRUPTION_MINUTE)
            state.world_service._publish_new()
            # Let the bridge's `asyncio.create_task(self._drive(...))` --
            # spawned synchronously from inside the `bus.emit` call above --
            # actually run up to its first await point before we inspect the
            # fake Durable host (same idiom as `test_world_bridge_actor.py`).
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            assert len(host.schedule_payloads) == 1, "sensor must schedule exactly one orchestration"
            schedule_payload = host.schedule_payloads[0]
            workflow_id = schedule_payload["workflow_id"]
            assert workflow_id.startswith("fdr-")

            # -- becomes visible as awaiting HITL -----------------------------
            workflow = await _run_until(state, workflow_id, {"awaiting_hitl", "completed", "failed"})
            assert workflow.status == "awaiting_hitl", (
                "golden option's incremental cost/material change must require HITL"
            )
            gate = pending_gates.get(workflow_id)
            assert gate is not None
            assert gate["external_event"] == "TravelRecoveryApproval"
            exception = next(
                e for e in state.store.list_exceptions(include_resolved=False)
                if e.workflow_id == workflow_id
            )
            assert exception.category == "threshold-exceeded"

            # -- approve via the REAL generic decision/event API --------------
            approved = await _resolve_one(exception.id, "approve", "head_of_operations")
            assert approved is True

            workflow = await _run_until(state, workflow_id, {"completed", "failed"})
            assert workflow.status == "completed"
            instance = host.instances[workflow.orchestration_instance_id]
            assert instance.completed
            output = instance.output
            assert output["command"] is not None
            assert output["decision"]["outcome"] == "approved"
            assert output["decision"]["decided_by"] == "head_of_operations"

            # -- every httpx call in this test targeted only the fake Durable
            # host; no direct-run/app route of any kind was ever reachable
            # here -------------------------------------------------------------
            for call in respx_mock.calls:
                assert str(call.request.url).startswith(_FUNCTIONS_HOST)
    finally:
        exceptions_module.app_state = original_app_state

    # -- pending gate cleared, no stale awaiting-gate left behind ----------
    assert pending_gates.get(workflow_id) is None

    # -- same workflow id flows through schedule payload, StateStore and the
    # orchestrator's own output -----------------------------------------
    assert output["workflow_id"] == workflow_id
    assert output["booking_id"] == _GOLDEN_BOOKING_ID
    assert output["party_id"] == _GOLDEN_PARTY_ID
    assert output["phases"] == [
        "detect", "assess_impact", "search_alternatives", "bound_options",
        "approve_material_change", "reaccommodate", "notify", "evaluate",
    ]
    assert output["hitl_audit"]["required"] is True
    assert output["hitl_audit"]["outcome"] == "approved"

    # -- typed command exact shape: SimulationCommand-compatible envelope
    # (command_id/trace_id/issued_by/type/payload), the RecoveryOption's own
    # fields plus workflow_id/decision_id/decision_outcome/decided_by nested
    # under `payload` -- exactly what `TravelRecoveryBuildCommand` (Part B,
    # already unit-tested in file 1) actually produces. ---------------------
    command = output["command"]
    assert command["type"] == "reaccommodate_travellers"
    assert command["issued_by"] == "operations-control"
    payload = command["payload"]
    assert payload["option_id"] == output["option_id"]
    assert payload["disruption_id"] == _GOLDEN_DISRUPTION_ID
    assert payload["booking_id"] == _GOLDEN_BOOKING_ID
    assert payload["party_id"] == _GOLDEN_PARTY_ID
    assert payload["old_flight_id"] == _GOLDEN_FLIGHT_ID
    assert payload["new_flight_id"] == _GOLDEN_NEW_FLIGHT_ID
    assert payload["incremental_cost_gbp"] == _GOLDEN_INCREMENTAL_COST_GBP
    assert payload["decision_outcome"] == "approved"
    assert payload["decided_by"] == "head_of_operations"
    assert payload["workflow_id"] == workflow_id

    # -- atomic world mutation: capacity conservation + booking/party/CUS-8/
    # CUS-9 visible status --------------------------------------------------
    service = state.world_service
    booking = service.scenario.bookings[_GOLDEN_BOOKING_ID]
    assert booking.flight_id == _GOLDEN_NEW_FLIGHT_ID
    assert booking.recovery_status == "reaccommodated"
    party = service.scenario.parties[_GOLDEN_PARTY_ID]
    assert party.state == "reaccommodated"
    assert party.member_customer_ids == _GOLDEN_MEMBER_CUSTOMER_IDS
    old_flight = service.scenario.flights[_GOLDEN_FLIGHT_ID]
    new_flight = service.scenario.flights[_GOLDEN_NEW_FLIGHT_ID]
    assert old_flight.reserved >= 0
    assert 0 <= new_flight.reserved <= new_flight.capacity

    # -- Decision/Command/Evaluation actors recorded -------------------------
    decisions = [d for d in service.scenario.recovery_decisions.values() if d.workflow_id == workflow_id]
    assert len(decisions) == 1
    assert decisions[0].outcome == "approved"
    assert decisions[0].decided_by == "head_of_operations"
    commands = [c for c in service.scenario.recovery_commands.values() if c.workflow_id == workflow_id]
    assert len(commands) == 1
    assert commands[0].incremental_cost_gbp == _GOLDEN_INCREMENTAL_COST_GBP
    assert commands[0].id == command["command_id"]
    evaluations = [e for e in service.scenario.recovery_evaluations.values() if e.workflow_id == workflow_id]
    assert len(evaluations) == 1
    assert evaluations[0].status == "pass", "evaluation PASS requires conservation + recovered itinerary"

    # -- objective lifecycle open -> claimed -> acting -> evaluating ->
    # resolved, and evaluation PASS resolves it ------------------------------
    objective_id = schedule_payload["objective_id"]
    objective = service.objectives.get(objective_id)
    assert objective is not None
    assert objective.status == "resolved"
    assert objective.type == "recover_cancelled_flight"


@pytest.mark.asyncio
async def test_delayed_hitl_approval_before_gate_deadline_reaches_terminal_evaluation(
    monkeypatch,
):
    state = _travel_state()
    bridge = WorldBridge(state)
    host = _FakeDurableHTTPHost()
    captured = []
    state.bus.on(SENSOR_EVENT, captured.append)

    original_app_state = exceptions_module.app_state
    exceptions_module.app_state = state
    try:
        with respx.mock(assert_all_called=False) as respx_mock:
            _install_fake_durable_host(host, respx_mock)
            state.world_service.scenario.run(_DISRUPTION_MINUTE)
            state.world_service._publish_new()
            sensor_event = next(
                event.simulation_event
                for event in captured
                if event.simulation_event.get("payload", {}).get("sensor_id")
                == "sensor:flight_cancellation_impact"
            )

            clock = SimpleNamespace(now=0.0)
            approval_count = 0

            async def _advance_past_responder_timeout(_seconds):
                nonlocal approval_count
                clock.now = 300.0
                exception = next(
                    item
                    for item in state.store.list_exceptions(include_resolved=False)
                    if item.workflow_id == host.schedule_payloads[0]["workflow_id"]
                )
                assert await _resolve_one(
                    exception.id, "approve", "head_of_operations"
                )
                approval_count += 1

            monkeypatch.setattr(
                world_bridge_module,
                "asyncio",
                SimpleNamespace(
                    get_event_loop=lambda: SimpleNamespace(time=lambda: clock.now),
                    sleep=_advance_past_responder_timeout,
                ),
            )

            await bridge._drive(sensor_event)

            workflow_id = host.schedule_payloads[0]["workflow_id"]
            assert clock.now == 300.0
            assert approval_count == 1
            assert state.store.get_workflow(workflow_id).status == "completed"
            assert state.world_service.scenario.bookings[
                _GOLDEN_BOOKING_ID
            ].flight_id == _GOLDEN_NEW_FLIGHT_ID
            commands = [
                command
                for command in state.world_service.scenario.recovery_commands.values()
                if command.workflow_id == workflow_id
            ]
            evaluations = [
                evaluation
                for evaluation in state.world_service.scenario.recovery_evaluations.values()
                if evaluation.workflow_id == workflow_id
            ]
            assert len(commands) == 1
            assert len(evaluations) == 1
            assert evaluations[0].status == "pass"

            await bridge._drive(sensor_event)
            assert len(host.schedule_payloads) == 1
            assert len(
                [
                    command
                    for command in state.world_service.scenario.recovery_commands.values()
                    if command.workflow_id == workflow_id
                ]
            ) == 1
    finally:
        exceptions_module.app_state = original_app_state


# ---------------------------------------------------------------------------
# Low-cost / non-material branch: bypasses HITL entirely.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_low_cost_disruption_bypasses_hitl_and_completes_immediately():
    state = _travel_state()
    bridge = WorldBridge(state)
    bridge.start()
    host = _FakeDurableHTTPHost()

    with respx.mock(assert_all_called=False) as respx_mock:
        _install_fake_durable_host(host, respx_mock)

        _low_cost_disruption(state)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert len(host.schedule_payloads) == 1
        workflow_id = host.schedule_payloads[0]["workflow_id"]

        workflow = await _run_until(state, workflow_id, {"completed", "failed"})
        assert workflow.status == "completed"

        # Never suspended: no gate was ever recorded for this workflow.
        assert pending_gates.get(workflow_id) is None
        assert not any(
            e.workflow_id == workflow_id for e in state.store.list_exceptions(include_resolved=True)
        )

        instance = host.instances[workflow.orchestration_instance_id]
        output = instance.output
        assert output["command"] is not None
        assert output["hitl_audit"]["required"] is False
        assert output["decision"]["outcome"] == "auto_approved"
        assert output["decision"]["decided_by"] == "operations_controller"
        assert output["command"]["type"] == "reaccommodate_travellers"
        assert output["command"]["payload"]["decision_outcome"] == "auto_approved"

    booking = state.world_service.scenario.bookings[_LOW_COST_BOOKING_ID]
    assert booking.flight_id == _LOW_COST_REPLACEMENT_FLIGHT_ID
    assert booking.recovery_status == "reaccommodated"

    recovery_commands = [
        c for c in state.world_service.scenario.recovery_commands.values()
        if c.workflow_id == workflow_id
    ]
    assert len(recovery_commands) == 1
    evaluations = [
        e for e in state.world_service.scenario.recovery_evaluations.values()
        if e.workflow_id == workflow_id
    ]
    assert len(evaluations) == 1
    assert evaluations[0].status == "pass"


# ---------------------------------------------------------------------------
# Decline: graceful terminal failure, zero mutation, no phantom completion.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decline_produces_graceful_terminal_failure_with_zero_world_mutation():
    state = _travel_state()
    bridge = WorldBridge(state)
    bridge.start()
    host = _FakeDurableHTTPHost()

    original_app_state = exceptions_module.app_state
    exceptions_module.app_state = state
    try:
        with respx.mock(assert_all_called=False) as respx_mock:
            _install_fake_durable_host(host, respx_mock)

            state.world_service.scenario.run(_DISRUPTION_MINUTE)
            state.world_service._publish_new()
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            workflow_id = host.schedule_payloads[0]["workflow_id"]
            workflow = await _run_until(state, workflow_id, {"awaiting_hitl", "completed", "failed"})
            assert workflow.status == "awaiting_hitl"

            exception = next(
                e for e in state.store.list_exceptions(include_resolved=False)
                if e.workflow_id == workflow_id
            )
            declined = await _resolve_one(exception.id, "reject", "head_of_operations")
            assert declined is True

            workflow = await _run_until(state, workflow_id, {"completed", "failed"})
            assert workflow.status == "failed", "decline must fail the workflow, never complete it"
    finally:
        exceptions_module.app_state = original_app_state

    assert pending_gates.get(workflow_id) is None
    assert state.world_last_response is None, "no command was ever applied to the world"

    booking = state.world_service.scenario.bookings[_GOLDEN_BOOKING_ID]
    assert booking.flight_id == _GOLDEN_FLIGHT_ID, "booking must remain unmutated after a decline"
    assert booking.recovery_status is None
    party = state.world_service.scenario.parties[_GOLDEN_PARTY_ID]
    assert party.state != "reaccommodated"
    assert state.world_service.scenario.recovery_commands == {}, "zero mutation: no command recorded"

    objective_id = host.schedule_payloads[0]["objective_id"]
    objective = state.world_service.objectives.get(objective_id)
    assert objective is not None
    assert objective.status == "failed"


# ---------------------------------------------------------------------------
# Issue 1: zero feasible alternatives -- graceful terminal failure, never an
# infrastructure crash.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_feasible_alternatives_fails_gracefully_with_zero_world_mutation():
    """Issue 1: when every one of the golden disruption's 4 real candidate
    replacement flights/transfers is already at full capacity (a real,
    legitimate world state -- capacity moved on for other parties, never a
    synthetic/invented gap), the real planner returns zero feasible
    `RecoveryOption`s and the real orchestrator's own `no_alternative`
    terminal branch must surface through the exact same generic,
    industry-neutral `command is None` bridge path already proven above
    for a declined decision -- never an unhandled `options[0]` IndexError
    or any other infrastructure crash. The orchestrator never pauses for
    HITL here (there is no option to gate approval on), so this
    orchestration instance completes synchronously, inside the very same
    `schedule_new_orchestration` call, with zero `awaiting_hitl` hop --
    `test_travel_recovery_functions.py`'s own
    `test_orchestrator_with_no_feasible_alternatives_returns_deterministic_no_alternative_terminal_output`
    already exhaustively proves this exact terminal shape at the
    orchestrator level; this test proves only that the neutral bridge
    surfaces it gracefully, with zero world mutation, rather than crashing.
    """
    state = _travel_state()
    bridge = WorldBridge(state)
    bridge.start()
    host = _FakeDurableHTTPHost()

    original_app_state = exceptions_module.app_state
    exceptions_module.app_state = state
    try:
        with respx.mock(assert_all_called=False) as respx_mock:
            _install_fake_durable_host(host, respx_mock)

            state.world_service.scenario.run(_DISRUPTION_MINUTE)
            for flight_id, transfer_id in _GOLDEN_CANDIDATE_FLIGHT_AND_TRANSFER_IDS:
                flight = state.world_service.scenario.flights[flight_id]
                state.world_service.scenario._apply(
                    "flight.capacity_reserved", flight, {"reserved": flight.capacity}
                )
                transfer = state.world_service.scenario.transfers[transfer_id]
                state.world_service.scenario._apply(
                    "transfer.capacity_reserved", transfer, {"reserved": transfer.capacity}
                )
            state.world_service._publish_new()
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            assert len(host.schedule_payloads) == 1, "sensor must schedule exactly one orchestration"
            workflow_id = host.schedule_payloads[0]["workflow_id"]

            workflow = await _run_until(state, workflow_id, {"completed", "failed"})
            assert workflow.status == "failed", (
                "zero feasible alternatives must fail the workflow gracefully, never crash"
            )
            instance = host.instances[workflow.orchestration_instance_id]
            assert instance.completed
            output = instance.output
            assert output["command"] is None
            assert output["option_id"] is None
            assert output["decision"]["outcome"] == "no_alternative"
            assert output["decision"]["decided_by"] is None
            assert output["hitl_audit"]["required"] is False

            # No HITL wait/timer was ever created for this branch: no gate
            # was ever registered and no operator exception was ever opened.
            assert pending_gates.get(workflow_id) is None
            assert not any(
                e.workflow_id == workflow_id for e in state.store.list_exceptions(include_resolved=False)
            )

            for call in respx_mock.calls:
                assert str(call.request.url).startswith(_FUNCTIONS_HOST)
    finally:
        exceptions_module.app_state = original_app_state

    assert pending_gates.get(workflow_id) is None
    assert state.world_last_response is None, "no command was ever applied to the world"

    booking = state.world_service.scenario.bookings[_GOLDEN_BOOKING_ID]
    assert booking.flight_id == _GOLDEN_FLIGHT_ID, "booking must remain unmutated when no alternative exists"
    assert booking.recovery_status is None
    party = state.world_service.scenario.parties[_GOLDEN_PARTY_ID]
    assert party.state != "reaccommodated"
    assert state.world_service.scenario.recovery_commands == {}, "zero mutation: no command recorded"
    assert state.world_service.scenario.recovery_decisions == {}, "zero mutation: no decision recorded"

    objective_id = host.schedule_payloads[0]["objective_id"]
    objective = state.world_service.objectives.get(objective_id)
    assert objective is not None
    assert objective.status == "failed"


# ---------------------------------------------------------------------------
# Duplicate sensor delivery: idempotent, exactly one workflow/command.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_sensor_delivery_schedules_the_same_workflow_exactly_once():
    state = _travel_state()
    bridge = WorldBridge(state)
    bridge.start()
    host = _FakeDurableHTTPHost()

    captured: list = []
    state.bus.on(SENSOR_EVENT, captured.append)

    with respx.mock(assert_all_called=False) as respx_mock:
        _install_fake_durable_host(host, respx_mock)

        _low_cost_disruption(state)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert len(host.schedule_payloads) == 1
        schedule_payload = host.schedule_payloads[0]
        workflow_id = schedule_payload["workflow_id"]
        # `objective_id` is deterministically `f"obj-{sensor_event_id}"`
        # (`api.server.world.objectives.objective_id`); recover the exact
        # sensor FleetEvent this workflow was scheduled from, regardless of
        # how many OTHER, unrelated sensors also happened to trip while
        # advancing the shared simulation clock to build this fixture.
        target_event_id = schedule_payload["objective_id"].removeprefix("obj-")
        sensor_event = next(
            e for e in captured if e.simulation_event.get("event_id") == target_event_id
        )

        workflow = await _run_until(state, workflow_id, {"completed", "failed"})
        assert workflow.status == "completed"
        first_instance_id = workflow.orchestration_instance_id

        # Simulate an at-least-once redelivery of the IDENTICAL sensor event
        # (same event_id), strictly after the first delivery's workflow has
        # already fully completed -- proving the wiring holds for the real
        # Travel golden path specifically (the underlying dedup/idempotency
        # mechanisms themselves are already generically proven in
        # `test_world_bridge_actor.py`).
        state.bus.emit(sensor_event)
        await asyncio.sleep(0.3)

        assert len(host.schedule_payloads) == 1, "duplicate delivery must not schedule a second orchestration"
        workflow_again = state.store.get_workflow(workflow_id)
        assert workflow_again is not None
        assert workflow_again.orchestration_instance_id == first_instance_id

    booking = state.world_service.scenario.bookings[_LOW_COST_BOOKING_ID]
    assert booking.flight_id == _LOW_COST_REPLACEMENT_FLIGHT_ID
    recovery_commands = state.world_service.scenario.recovery_commands
    assert len(recovery_commands) == 1, "duplicate delivery must not produce a second command"
