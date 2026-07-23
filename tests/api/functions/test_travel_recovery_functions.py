"""TDD contract tests for the Travel vertical's flight-disruption recovery
capability (Task 6): the pack-owned pure recovery planner
(`verticals.travel.recovery.planner`) and the real Azure Durable Functions
module (`verticals.travel.durable.functions`) it feeds.

This file intentionally never calls `world_bridge`/the world/objective
pipeline -- that end-to-end wiring is covered separately by
`tests/api/server/services/test_world_bridge_travel_recovery_integration.py`.
Here, every test either:

* drives `TravelWorld` directly (a pure Python call -- no
  `/processes/*/run` HTTP route, no objective, no workflow) to build a real
  `sensor:flight_cancellation_impact` observation, then calls the pure
  planner on it, or
* imports the real `verticals.travel.durable.functions` module and drives
  its Durable orchestrator generator function directly with a hand-built
  fake `DurableOrchestrationContext`, asserting the exact phase/activity
  sequence, the conditional HITL race (`wait_for_external_event` raced
  against `create_timer` via `task_any`, with the loser cancelled), and
  replay-safety (re-driving the same recorded sequence of sent-back values
  yields the identical sequence of activity calls and the identical final
  output), or
* spawns a `ZAVA_VERTICAL=travel` subprocess and calls
  `function_app.app.get_functions()` to prove the orchestrator and its
  activities are actually registered on the selected pack's own
  `azure.durable_functions.DFApp` -- the same technique
  `tests/api/functions/test_vertical_function_registration.py` already
  uses for the agency/telco packs.

Before this task's generator changes exist, every test below fails at
collection with `ModuleNotFoundError: No module named 'verticals.travel.recovery'`
(and, for the Durable-module tests, `'verticals.travel.durable.functions'`) --
a missing capability, never a syntax error.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

import pytest

from verticals.travel.worlds.scenario import TravelWorld

# --- golden scenario: FLT-ZV204 cancelled at minute 180 (Task 5) -----------

_GOLDEN_FLIGHT_ID = "FLT-ZV204"
_GOLDEN_BOOKING_ID = "BKG-4"
_GOLDEN_PARTY_ID = "PTY-4"
_GOLDEN_MEMBER_CUSTOMER_IDS = ("CUS-8", "CUS-9")
_GOLDEN_HOTEL_ID = "HTL-SUN-PMI"
_GOLDEN_ALLOTMENT_ID = "ALT-SUN-PMI"
_GOLDEN_OLD_TRANSFER_ID = "TRF-2"
_GOLDEN_DISRUPTION_ID = f"DIS-flight_cancellation-{_GOLDEN_FLIGHT_ID}"
_DISRUPTION_MINUTE = 180.0

# The 4 real, seeded candidate replacement flights for the golden case (all
# DST-PMI, all real snapshot actors with real capacities) -- see the exact
# numbers this test pins in `verticals/travel/generator/world_templates.py`.
_GOLDEN_RANKED_FLIGHT_IDS = ("FLT-ZV205", "FLT-CA160", "FLT-ZV206")
_GOLDEN_EXCLUDED_FLIGHT_ID = "FLT-CA161"  # 4th candidate: bounded out by <=3

# All 4 real DST-PMI candidate flights (and their 1:1 paired transfers) --
# the *entire* real feasible replacement set for the golden FLT-ZV204 case,
# per `verticals/travel/generator/world_templates.py`.
_GOLDEN_CANDIDATE_FLIGHT_AND_TRANSFER_IDS = (
    ("FLT-ZV205", "TRF-5"),
    ("FLT-CA160", "TRF-6"),
    ("FLT-ZV206", "TRF-7"),
    ("FLT-CA161", "TRF-8"),
)

# Low-cost/non-material scenario: a second, independent flight_cancellation
# disruption (constructed directly in this test, not autonomously) against
# FLT-ZV102/BKG-2/PTY-2, whose one real replacement (FLT-ZV103) is both
# <=750 GBP incremental and non-material -- must auto-approve, no HITL.
_LOW_COST_FLIGHT_ID = "FLT-ZV102"
_LOW_COST_BOOKING_ID = "BKG-2"
_LOW_COST_DISRUPTION_ID = f"DIS-flight_cancellation-{_LOW_COST_FLIGHT_ID}"
_LOW_COST_REPLACEMENT_FLIGHT_ID = "FLT-ZV103"

_AUTO_APPROVE_BOUND_GBP = 750.0


def _golden_world(until: float = _DISRUPTION_MINUTE) -> TravelWorld:
    world = TravelWorld(seed=42)
    world.run(until)
    return world


def _golden_observation(world: TravelWorld) -> dict[str, Any]:
    """The world's own minute-180 autonomous flight cancellation already
    ran the real detector once inside `_operations_flight_cancellation`
    (Task 5); re-invoking the detector here would be a legitimate, safe
    no-op (rising-edge only) and so would return nothing new -- read the
    one real `sensor.tripped` event it already journalled instead."""
    sensor_event = next(
        event for event in world.runtime.journal
        if event.type == "sensor.tripped" and event.target_id == _GOLDEN_FLIGHT_ID
    )
    return world.build_observation(sensor_event.to_dict(), now=world.runtime.now)


def _low_cost_world_and_observation() -> tuple[TravelWorld, dict[str, Any]]:
    """A second, independent flight_cancellation case against FLT-ZV102.

    Mirrors the exact mechanics of `TravelWorld._operations_flight_cancellation`
    (Task 5's own autonomous mutation) by hand, against a different flight,
    entirely as a pure Python call: no world-process HTTP run route, no
    objective, no workflow.
    """
    from verticals.travel.worlds import processes as travel_processes

    world = TravelWorld(seed=42)
    world.run(90.0)  # strictly after FLT-ZV102's own ordinary booking activity
    flight = world.flights[_LOW_COST_FLIGHT_ID]
    assert flight.status == "scheduled"
    cancelled_event = world._apply(
        "flight.cancelled", flight, {"status": "cancelled"},
        extra_payload={"reason": "supplier_operational_cancellation"},
    )
    world.report_disruption(
        kind="flight_cancellation", resource_id=flight.id,
        cause_event_id=cancelled_event.event_id, trace_id=cancelled_event.trace_id,
    )
    events = travel_processes.detect_flight_cancellation_impact(world)
    sensor_event = next(e for e in events if e.target_id == _LOW_COST_FLIGHT_ID)
    observation = world.build_observation(sensor_event.to_dict(), now=world.runtime.now)
    return world, observation


def _golden_world_with_no_feasible_alternatives() -> TravelWorld:
    """The real golden minute-180 FLT-ZV204 cancellation, but with every
    one of its 4 real DST-PMI candidate replacement flights (FLT-ZV205/
    CA160/ZV206/CA161) and their 1:1 paired transfers (TRF-5/6/7/8)
    already at full capacity via the same generic `world._apply(...)`
    mutation primitive every other command handler in this vertical uses
    -- a real, legitimate world state (capacity moved on for other
    parties between the disruption and this recovery attempt), never a
    synthetic/invented gap -- so the real planner's own capacity filter
    genuinely returns zero feasible `RecoveryOption`s for this booking.
    """
    world = _golden_world()
    for flight_id, transfer_id in _GOLDEN_CANDIDATE_FLIGHT_AND_TRANSFER_IDS:
        flight = world.flights[flight_id]
        world._apply("flight.capacity_reserved", flight, {"reserved": flight.capacity})
        transfer = world.transfers[transfer_id]
        world._apply("transfer.capacity_reserved", transfer, {"reserved": transfer.capacity})
    return world


# ---------------------------------------------------------------------------
# A. Pure recovery planner
# ---------------------------------------------------------------------------


def test_build_observation_names_the_exact_affected_golden_actors():
    """Requirement A: build_observation must expose the exact affected
    BKG-4/PTY-4/CUS-8/CUS-9/FLT-ZV204 actors and retained hotel/transfer
    relationships from the real sensor observation -- read live from world
    state, never synthesised.
    """
    world = _golden_world()
    observation = _golden_observation(world)

    assert observation["disruption_id"] == _GOLDEN_DISRUPTION_ID
    assert observation["flight_id"] == _GOLDEN_FLIGHT_ID
    assert observation["booking_id"] == _GOLDEN_BOOKING_ID
    assert observation["party_id"] == _GOLDEN_PARTY_ID
    assert observation["party_size"] == 2
    assert tuple(sorted(observation["member_customer_ids"])) == _GOLDEN_MEMBER_CUSTOMER_IDS
    assert observation["hotel_id"] == _GOLDEN_HOTEL_ID
    assert observation["allotment_id"] == _GOLDEN_ALLOTMENT_ID
    assert observation["old_transfer_id"] == _GOLDEN_OLD_TRANSFER_ID
    assert observation["destination_id"] == "DST-PMI"
    assert observation["old_flight"]["flight_id"] == _GOLDEN_FLIGHT_ID
    assert observation["evidence_event_ids"], "must carry at least the tripping sensor event id"


def test_build_observation_preserves_the_sensor_trace_id():
    """The Durable input must retain the sensor's single causal trace."""
    world = _golden_world()
    sensor_event = next(
        event for event in world.runtime.journal
        if event.type == "sensor.tripped" and event.target_id == _GOLDEN_FLIGHT_ID
    )

    observation = world.build_observation(sensor_event.to_dict(), now=world.runtime.now)

    assert observation["trace_id"] == sensor_event.trace_id


def test_plan_recovery_options_bounds_to_three_and_ranks_deterministically():
    """Requirement A: at most 3 `RecoveryOption`s, sorted deterministically
    by (material-change severity, incremental GBP cost, arrival delay,
    option_id), from a real snapshot of 4 capacity-feasible candidates --
    the 4th (most expensive, longest-delay) candidate must be bounded out.
    """
    from verticals.travel.recovery.planner import plan_recovery_options

    world = _golden_world()
    observation = _golden_observation(world)

    options = plan_recovery_options(observation)

    assert len(options) == 3
    ranked_new_flight_ids = [option.new_flight_id for option in options]
    assert ranked_new_flight_ids == list(_GOLDEN_RANKED_FLIGHT_IDS)
    assert _GOLDEN_EXCLUDED_FLIGHT_ID not in ranked_new_flight_ids

    # every option is sorted strictly non-decreasing on the documented key
    keys = [
        (len(option.material_changes), option.incremental_cost_gbp, option.arrival_delay_minutes, option.option_id)
        for option in options
    ]
    assert keys == sorted(keys)


def test_golden_option_records_full_evidence_and_requires_approval():
    """Requirement A: the golden (top-ranked) option must be feasible and
    require approval because its incremental cost exceeds GBP 750, and it
    must record option_id, old/new flight, hotel, transfer, supplier
    linkage, capacity evidence, arrival delay, incremental cost, material
    changes, affected actor ids and evidence event ids.

    Issue 3: the observation already carries each flight's own real
    `supplier_id` (see `TravelWorld.build_observation`'s `old_flight`/
    `candidate_flights`); the option must carry both the disrupted
    flight's `old_supplier_id` and the replacement's `new_supplier_id`
    through as first-class evidence -- read directly from the
    observation, never dropped -- and both must also show up among the
    option's own `affected_actor_ids` (suppliers are real, first-class
    actors in this world, per `Supplier`/`world.supplier_seeded`).
    """
    from verticals.travel.recovery.planner import AUTO_APPROVE_BOUND_GBP, plan_recovery_options

    assert AUTO_APPROVE_BOUND_GBP == _AUTO_APPROVE_BOUND_GBP

    world = _golden_world()
    observation = _golden_observation(world)
    options = plan_recovery_options(observation)
    golden = options[0]

    assert golden.new_flight_id == "FLT-ZV205"
    assert golden.old_flight_id == _GOLDEN_FLIGHT_ID
    assert golden.booking_id == _GOLDEN_BOOKING_ID
    assert golden.party_id == _GOLDEN_PARTY_ID
    assert golden.old_transfer_id == _GOLDEN_OLD_TRANSFER_ID
    assert golden.new_transfer_id and golden.new_transfer_id != _GOLDEN_OLD_TRANSFER_ID
    assert golden.hotel_id == _GOLDEN_HOTEL_ID
    assert golden.destination_id == "DST-PMI"
    assert golden.incremental_cost_gbp == pytest.approx(900.0)
    assert golden.incremental_cost_gbp > AUTO_APPROVE_BOUND_GBP
    assert golden.requires_approval is True
    assert golden.option_id == f"OPT-{_GOLDEN_DISRUPTION_ID}-FLT-ZV205"
    assert golden.old_supplier_id == "SUP-ZVA"
    assert golden.new_supplier_id == "SUP-ZVA"
    assert golden.old_supplier_id == observation["old_flight"]["supplier_id"]
    new_flight_observed = next(
        candidate for candidate in observation["candidate_flights"] if candidate["flight_id"] == golden.new_flight_id
    )
    assert golden.new_supplier_id == new_flight_observed["supplier_id"]

    for actor_id in (
        _GOLDEN_BOOKING_ID, _GOLDEN_PARTY_ID, *_GOLDEN_MEMBER_CUSTOMER_IDS, _GOLDEN_FLIGHT_ID, golden.new_flight_id,
        golden.old_supplier_id, golden.new_supplier_id,
    ):
        assert actor_id in golden.affected_actor_ids

    evidence = golden.capacity_evidence
    assert evidence["new_flight_capacity"] >= evidence["new_flight_reserved"] + 2
    assert evidence["new_transfer_capacity"] >= evidence["new_transfer_reserved"] + 2
    assert golden.evidence_event_ids

    # to_dict() (the exact shape TravelRecoveryPlanOptions/BuildCommand
    # carry onward as the typed command's own payload) must include both
    # supplier ids too -- never only on the dataclass, never silently
    # dropped on the JSON boundary a real Durable activity crosses.
    golden_dict = golden.to_dict()
    assert golden_dict["old_supplier_id"] == "SUP-ZVA"
    assert golden_dict["new_supplier_id"] == "SUP-ZVA"


def test_material_but_cheaper_option_still_requires_approval_via_material_change():
    """Requirement A: the OR in "cost > GBP 750 OR materially changes the
    holiday" -- FLT-CA160 costs only GBP 650 (<=750) but has a materially
    longer arrival delay, so it must still require approval purely on the
    material-change branch.

    Issue 3: FLT-CA160 is operated by a genuinely different real supplier
    ("SUP-CRA") than the disrupted FLT-ZV204 ("SUP-ZVA") -- proving
    `old_supplier_id`/`new_supplier_id` are two independent, correctly
    distinct fields read from their own real flight records, never one
    value accidentally copied onto the other.
    """
    from verticals.travel.recovery.planner import AUTO_APPROVE_BOUND_GBP, plan_recovery_options

    world = _golden_world()
    observation = _golden_observation(world)
    options = plan_recovery_options(observation)
    material_cheap = next(option for option in options if option.new_flight_id == "FLT-CA160")

    assert material_cheap.incremental_cost_gbp <= AUTO_APPROVE_BOUND_GBP
    assert len(material_cheap.material_changes) > 0
    assert material_cheap.requires_approval is True
    assert material_cheap.old_supplier_id == "SUP-ZVA"
    assert material_cheap.new_supplier_id == "SUP-CRA"
    assert material_cheap.new_supplier_id != material_cheap.old_supplier_id


def test_low_cost_non_material_option_bypasses_approval():
    """Requirement A: a <=750 GBP, non-material replacement (FLT-ZV103 for
    the independent FLT-ZV102 case) must proceed without HITL."""
    from verticals.travel.recovery.planner import plan_recovery_options

    _world, observation = _low_cost_world_and_observation()
    options = plan_recovery_options(observation)

    assert len(options) >= 1
    top = options[0]
    assert top.new_flight_id == _LOW_COST_REPLACEMENT_FLIGHT_ID
    assert top.incremental_cost_gbp <= _AUTO_APPROVE_BOUND_GBP
    assert top.material_changes == ()
    assert top.requires_approval is False


def test_plan_recovery_options_is_pure_and_replay_safe():
    """Requirement E: calling the planner twice on an identical observation
    (a plain, JSON-round-tripped dict -- never a live TravelWorld
    reference) produces byte-identical results; the function never reads
    real time, randomness or any other hidden/ambient state."""
    from verticals.travel.recovery.planner import plan_recovery_options

    world = _golden_world()
    observation = json.loads(json.dumps(_golden_observation(world)))

    first = plan_recovery_options(observation)
    second = plan_recovery_options(json.loads(json.dumps(observation)))

    assert [option.to_dict() for option in first] == [option.to_dict() for option in second]


# ---------------------------------------------------------------------------
# B. Real Durable Functions module: registration
# ---------------------------------------------------------------------------

_EXPECTED_ORCHESTRATOR_NAME = "TravelFlightDisruptionRecoveryOrchestrator"
_EXPECTED_ACTIVITY_NAMES = {
    "TravelRecoveryDetect",
    "TravelRecoveryAssessImpact",
    "TravelRecoveryPlanOptions",
    "TravelRecoveryAutoApprove",
    "TravelRecoveryBuildCommand",
    "TravelRecoveryNotify",
    "TravelRecoveryEvaluateIntent",
}
_EXPECTED_EXTERNAL_EVENT_NAME = "TravelRecoveryApproval"
_EXPECTED_STARTER_NAME = "http_start"


def test_real_durable_module_exposes_a_dfapp_with_orchestrator_and_activities():
    """Requirement B: `verticals.travel.durable.functions` builds its own
    real `azure.durable_functions.DFApp` and registers the real
    `TravelFlightDisruptionRecoveryOrchestrator` plus its activities on it
    -- indexed directly, never through the shared/global
    `api.functions.kernel_registration` app.
    """
    import azure.durable_functions as df

    from verticals.travel.durable import functions as travel_durable_functions

    assert isinstance(travel_durable_functions.app, df.DFApp)
    registered = {f.get_function_name() for f in travel_durable_functions.app.get_functions()}
    assert _EXPECTED_ORCHESTRATOR_NAME in registered
    assert _EXPECTED_ACTIVITY_NAMES <= registered


def test_durable_init_package_re_exports_the_real_app():
    """Requirement B: `verticals.travel.durable.load_module()` (as wired
    through `VerticalPack.durable_functions.load_module` and root
    `function_app.py`) resolves to `verticals.travel.durable` itself, so
    that package's `__init__` must expose the real `app`.
    """
    from verticals.travel import durable as travel_durable

    assert hasattr(travel_durable, "app")
    assert travel_durable.app is not None


def test_function_app_indexes_the_real_travel_orchestrator_when_selected():
    """Requirement B: a `ZAVA_VERTICAL=travel` process's real root
    `function_app.py` indexes the real orchestrator and activities on its
    own selected-pack `app` -- proving the dynamic selected-pack mechanism
    (never a hand-patched global registry), mirroring the exact technique
    `test_vertical_function_registration.py` already uses for other packs.
    """
    script = (
        "import json\n"
        "import function_app\n"
        "functions = function_app.app.get_functions()\n"
        "print(json.dumps(sorted(f.get_function_name() for f in functions)))\n"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "AZURE_STORAGE_CONNECTION_STRING": "",
            "ENTITY_PLANE_ENABLED": "0",
            "ZAVA_VERTICAL": "travel",
        }
    )
    environment.pop("ZAVA_WORLD", None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment, check=True, capture_output=True, text=True, cwd=os.getcwd(),
    )
    indexed = set(json.loads(result.stdout.splitlines()[-1]))

    assert _EXPECTED_ORCHESTRATOR_NAME in indexed
    assert _EXPECTED_ACTIVITY_NAMES <= indexed


def test_function_app_indexes_the_standard_durable_http_starter_when_travel_is_selected():
    """The selected pack must expose the normal Durable client starter too.

    WorldBridge schedules the real Travel orchestration through the standard
    ``/api/orchestrators/{functionName}`` route.  Exporting only activities and
    an orchestrator leaves a real Functions host with no route to start it.
    """
    script = (
        "import json\n"
        "import function_app\n"
        "functions = function_app.app.get_functions()\n"
        "print(json.dumps(sorted(f.get_function_name() for f in functions)))\n"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "AZURE_STORAGE_CONNECTION_STRING": "",
            "ENTITY_PLANE_ENABLED": "0",
            "ZAVA_VERTICAL": "travel",
        }
    )
    environment.pop("ZAVA_WORLD", None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        cwd=os.getcwd(),
    )
    indexed = set(json.loads(result.stdout.splitlines()[-1]))

    assert _EXPECTED_STARTER_NAME in indexed


# ---------------------------------------------------------------------------
# C. Real orchestrator generator: replay-safe phase/HITL flow
# ---------------------------------------------------------------------------


class _FakeTask:
    """A minimal stand-in for `azure.durable_functions.models.Task`.

    Only implements what `TravelFlightDisruptionRecoveryOrchestrator` reads:
    `.result` (for the winning `wait_for_external_event` task) and
    `.is_completed`/`.cancel()` (for the losing `create_timer` task) -- the
    exact surface the Microsoft Learn human-interaction pattern uses.
    """

    def __init__(self, label: str) -> None:
        self.label = label
        self.is_completed = False
        self.result: Any = None
        self.cancel_called = False

    def cancel(self) -> None:
        self.cancel_called = True


class _FakeContext:
    """A faithful, hand-built stand-in for `DurableOrchestrationContext`.

    Drives the real orchestrator generator function step by step: every
    `call_activity` call is recorded (for replay-safety assertions) and
    its result is supplied by the test via `.send(...)`, exactly as the
    real Durable Task Python SDK replays a generator by re-sending
    already-completed results on each replay pass. Never performs any
    actual I/O -- every value crossing the fake boundary is plain,
    JSON-shaped data the test controls completely.
    """

    def __init__(self, input_data: dict[str, Any], *, utc_now: datetime) -> None:
        self._input = input_data
        self.instance_id = input_data["workflow_id"]
        self.current_utc_datetime = utc_now
        self.activity_calls: list[tuple[str, Any]] = []
        self.created_timers: list[_FakeTask] = []
        self.external_event_waits: list[_FakeTask] = []
        self.custom_status: Any = None

    def get_input(self) -> dict[str, Any]:
        return self._input

    def set_custom_status(self, status: Any) -> None:
        """Mirror the real `DurableOrchestrationContext.set_custom_status`:
        remembers the latest value so a test can assert the orchestrator
        made the HITL wait observable via the standard Durable
        custom-status channel (surfaced through the status-query
        endpoint's `customStatus` field) before it actually suspends."""
        self.custom_status = status

    def call_activity(self, name: str, input_: Any = None) -> _FakeTask:
        self.activity_calls.append((name, input_))
        return _FakeTask(f"activity:{name}")

    def create_timer(self, fire_at: datetime) -> _FakeTask:
        task = _FakeTask("timer")
        self.created_timers.append(task)
        return task

    def wait_for_external_event(self, name: str) -> _FakeTask:
        assert name == _EXPECTED_EXTERNAL_EVENT_NAME
        task = _FakeTask(f"event:{name}")
        self.external_event_waits.append(task)
        return task

    def task_any(self, tasks: list[_FakeTask]) -> list[_FakeTask]:
        """Mirror the real `WhenAnyTask`: yielding this resolves to whichever
        original task object completed first (`winner == wait_task`), so
        pass the same task list straight through rather than wrapping it in
        a new synthetic task -- the driver below recognises the list shape
        and sends back whichever pre-marked-complete task is in it."""
        return tasks


def _drive_with_real_activities(
    orchestrator,
    context: _FakeContext,
    *,
    hitl_response: tuple[str, Any] | None = None,
) -> dict[str, Any]:
    """Step a real Durable orchestrator generator to completion, calling
    the real, imported activity functions for every
    `yield context.call_activity(name, input_)` -- exactly mirroring what
    the real Durable Task runtime does: execute the activity, then send
    its real result back into the generator. Never feeds a blind
    placeholder: every activity receives the exact input the orchestrator
    itself passed, so a structurally-wrong orchestrator fails loudly here
    instead of silently coasting to a fabricated final output.

    `hitl_response` resolves at most one `task_any([wait, timer])` race:
    `("timeout", None)` marks the timer complete; any other `(kind,
    payload)` marks the external-event wait complete with `.result =
    payload`. `None` means no race is expected -- if one is yielded
    anyway, this raises (used to prove the low-cost path never waits).
    """
    from verticals.travel.durable import functions as travel_durable_functions

    gen = orchestrator(context)
    sent: Any = None
    while True:
        try:
            yielded = gen.send(sent)
        except StopIteration as stop:
            return stop.value
        if isinstance(yielded, _FakeTask):
            name = yielded.label.split(":", 1)[1]
            activity = getattr(travel_durable_functions, name)
            sent = activity(context.activity_calls[-1][1])
            continue
        if isinstance(yielded, list):
            assert hitl_response is not None, "unexpected HITL task_any race"
            kind, payload = hitl_response
            approval_task, timer_task = yielded
            if kind == "timeout":
                timer_task.is_completed = True
                sent = timer_task
            else:
                approval_task.is_completed = True
                approval_task.result = payload
                sent = approval_task
            continue
        raise AssertionError(f"unexpected yielded value: {yielded!r}")


def _base_input(world: TravelWorld, *, workflow_id: str = "wf-travel-fdr-golden") -> dict[str, Any]:
    observation = _golden_observation(world)
    return {
        "workflow_id": workflow_id,
        "type": "flight-disruption-recovery",
        "trace_id": "trace-golden-1",
        "objective_id": "OBJ-golden-1",
        "observation": observation,
    }


def test_orchestrator_high_cost_option_races_hitl_event_against_timer_and_cancels_timer_on_approval():
    """Requirement B/D: for the golden, requires-approval option, the
    orchestrator must race `wait_for_external_event` against
    `create_timer` via `task_any`, and cancel the still-pending timer once
    the approval event wins -- never mutating the world itself, returning
    only a typed command payload.

    Issue 3: the real typed command's own payload (built by
    `TravelRecoveryBuildCommand` from `dict(option)`) must still carry
    the option's `old_supplier_id`/`new_supplier_id` all the way through
    to the orchestrator's final output -- the one thing a later command
    handler needs to validate supplier identity before ever mutating the
    world.
    """
    from verticals.travel.durable.functions import (
        TravelFlightDisruptionRecoveryOrchestrator,
        TravelRecoveryAssessImpact,
        TravelRecoveryBuildCommand,
        TravelRecoveryDetect,
        TravelRecoveryEvaluateIntent,
        TravelRecoveryNotify,
        TravelRecoveryPlanOptions,
    )

    world = _golden_world()
    input_data = _base_input(world)
    context = _FakeContext(input_data, utc_now=datetime(2024, 1, 1, tzinfo=timezone.utc))

    gen = TravelFlightDisruptionRecoveryOrchestrator(context)
    next(gen)  # yields call_activity(TravelRecoveryDetect, observation)
    assert context.activity_calls[-1][0] == "TravelRecoveryDetect"
    gen.send(TravelRecoveryDetect(input_data["observation"]))
    assert context.activity_calls[-1][0] == "TravelRecoveryAssessImpact"
    gen.send(TravelRecoveryAssessImpact(TravelRecoveryDetect(input_data["observation"])))
    assert context.activity_calls[-1][0] == "TravelRecoveryPlanOptions"

    plan_input = TravelRecoveryAssessImpact(TravelRecoveryDetect(input_data["observation"]))
    options = TravelRecoveryPlanOptions(plan_input)
    assert options[0]["requires_approval"] is True

    task_any_yield = gen.send(options)
    # Requirement D: racing the HITL wait must have already made the
    # suspension observable via the standard Durable custom-status channel
    # (`context.set_custom_status`), naming the exact phase and the exact
    # external event name a generic caller (the shared world_bridge's status
    # poller, and ultimately the existing `/api/exceptions` operator queue)
    # would need to raise the approval -- never a Travel-only side channel.
    assert context.custom_status is not None
    assert context.custom_status["phase"] == "approve_material_change"
    assert context.custom_status["external_event"] == _EXPECTED_EXTERNAL_EVENT_NAME
    assert context.custom_status["wait_seconds"] == 1800.0
    assert isinstance(task_any_yield, list) and len(task_any_yield) == 2
    approval_task, timer_task = task_any_yield
    assert approval_task.label == f"event:{_EXPECTED_EXTERNAL_EVENT_NAME}"
    assert timer_task.label == "timer"
    assert timer_task.cancel_called is False

    approval_task.result = {"decision": "approve", "resolved_by": "head_of_operations"}
    approval_task.is_completed = True
    gen.send(approval_task)
    assert timer_task.cancel_called is True
    assert context.activity_calls[-1][0] == "TravelRecoveryBuildCommand"

    command_payload = TravelRecoveryBuildCommand(
        {"workflow_id": input_data["workflow_id"], "trace_id": input_data["trace_id"], "option": options[0],
         "decision": {"outcome": "approved", "decided_by": "head_of_operations"}}
    )
    gen.send(command_payload)
    assert context.activity_calls[-1][0] == "TravelRecoveryNotify"
    notification = TravelRecoveryNotify(command_payload)
    gen.send(notification)
    assert context.activity_calls[-1][0] == "TravelRecoveryEvaluateIntent"
    evaluation_intent = TravelRecoveryEvaluateIntent(command_payload)

    try:
        gen.send(evaluation_intent)
        raise AssertionError("orchestrator must terminate after Evaluate phase")
    except StopIteration as stop:
        output = stop.value

    assert output["command"] is not None
    assert output["command"]["type"] == "reaccommodate_travellers"
    assert output["command"]["issued_by"] == "operations-control"
    assert output["command"]["payload"]["option_id"] == options[0]["option_id"]
    assert output["command"]["payload"]["old_supplier_id"] == "SUP-ZVA"
    assert output["command"]["payload"]["new_supplier_id"] == "SUP-ZVA"
    assert output["command"]["payload"]["old_supplier_id"] == options[0]["old_supplier_id"]
    assert output["command"]["payload"]["new_supplier_id"] == options[0]["new_supplier_id"]
    assert output["phases"] == [
        "detect", "assess_impact", "search_alternatives", "bound_options",
        "approve_material_change", "reaccommodate", "notify", "evaluate",
    ]
    assert output["hitl_audit"]["required"] is True
    assert output["hitl_audit"]["outcome"] == "approved"
    assert output["decision"]["decided_by"] == "head_of_operations"
    assert output["evaluation_intent"] == evaluation_intent


def test_orchestrator_decline_timeout_and_malformed_all_return_no_command():
    """Requirement A/E: decline, timeout and malformed/wrong-role approval
    responses must all return an explicit terminal failure -- `command`
    is `None`, `TravelRecoveryBuildCommand` is never called -- never a
    silent fallback or a fabricated success."""
    from verticals.travel.durable.functions import TravelFlightDisruptionRecoveryOrchestrator

    world = _golden_world()
    input_data = _base_input(world)

    cases: list[tuple[str, str, Any, str]] = [
        ("declined", "event", {"decision": "reject", "resolved_by": "head_of_operations"}, "declined"),
        ("wrong_actor", "event", {"decision": "approve", "resolved_by": "operations_controller"}, "wrong_actor"),
        ("malformed_not_dict", "event", "approve", "malformed"),
        ("malformed_missing_fields", "event", {"decision": "approve"}, "malformed"),
        ("timeout", "timeout", None, "timeout"),
    ]

    for label, winner_kind, event_payload, expected_outcome in cases:
        context = _FakeContext(input_data, utc_now=datetime(2024, 1, 1, tzinfo=timezone.utc))
        output = _drive_with_real_activities(
            TravelFlightDisruptionRecoveryOrchestrator, context, hitl_response=(winner_kind, event_payload),
        )

        called_names = [name for name, _ in context.activity_calls]
        assert "TravelRecoveryBuildCommand" not in called_names, f"{label}: must not build a command"
        assert output["command"] is None, f"{label}: expected no command"
        assert output["hitl_audit"]["required"] is True
        assert output["hitl_audit"]["outcome"] == expected_outcome, label


def test_orchestrator_with_no_feasible_alternatives_returns_deterministic_no_alternative_terminal_output():
    """Issue 1: when the real planner's own candidate-flight/transfer
    capacity filter genuinely leaves zero feasible `RecoveryOption`s for
    this booking (every one of the 4 real DST-PMI candidate replacement
    flights and their paired transfers is already fully booked -- a real,
    legitimate world state, not a synthetic gap), the real Durable
    orchestrator generator must never raise an unguarded `IndexError` on
    `options[0]`. It must instead route through an explicit,
    deterministic no-command terminal branch: `command` is `None`, the
    decision/HITL-audit outcome is the truthful, distinct `"no_alternative"`
    reason (never misclassified as a HITL decline/timeout/malformed
    response, since no HITL gate was ever reached), no
    `TravelRecoveryBuildCommand` or `TravelRecoveryAutoApprove` activity is
    ever called (there is no option to build a command from or
    auto-approve), no timer/external-event wait is ever created (there is
    nothing left to approve), and yet `TravelRecoveryNotify` /
    `TravelRecoveryEvaluateIntent` still run truthfully against this
    no-command context -- so this real "no feasible alternative" outcome
    is always surfaced, never silently swallowed or crashed as an
    infrastructure fault.
    """
    from verticals.travel.durable.functions import TravelFlightDisruptionRecoveryOrchestrator

    world = _golden_world_with_no_feasible_alternatives()
    input_data = _base_input(world, workflow_id="wf-travel-fdr-no-alt")
    context = _FakeContext(input_data, utc_now=datetime(2024, 1, 1, tzinfo=timezone.utc))

    output = _drive_with_real_activities(
        TravelFlightDisruptionRecoveryOrchestrator, context, hitl_response=None,
    )

    called_names = [name for name, _ in context.activity_calls]
    assert called_names[:3] == [
        "TravelRecoveryDetect", "TravelRecoveryAssessImpact", "TravelRecoveryPlanOptions",
    ]
    assert "TravelRecoveryBuildCommand" not in called_names
    assert "TravelRecoveryAutoApprove" not in called_names
    assert "TravelRecoveryNotify" in called_names
    assert "TravelRecoveryEvaluateIntent" in called_names

    # No HITL gate was ever reached: nothing to wait on, nothing to time out.
    assert context.created_timers == []
    assert context.external_event_waits == []
    assert context.custom_status is None

    assert output["command"] is None
    assert output["option_id"] is None
    assert output["hitl_audit"]["required"] is False
    assert output["hitl_audit"]["outcome"] == "no_alternative"
    assert output["decision"]["outcome"] == "no_alternative"
    assert output["decision"]["decided_by"] is None
    assert output["evaluation_intent"]["will_resolve_objective"] is False
    assert output["booking_id"] == _GOLDEN_BOOKING_ID
    assert output["party_id"] == _GOLDEN_PARTY_ID


def test_orchestrator_low_cost_option_auto_approves_without_any_hitl_wait():
    """Requirement A/B: a <=750 GBP, non-material option must never call
    `wait_for_external_event`/`create_timer` at all -- it auto-approves
    through the deterministic `TravelRecoveryAutoApprove` activity and
    still returns a valid typed command."""
    from verticals.travel.durable.functions import TravelFlightDisruptionRecoveryOrchestrator

    _world, observation = _low_cost_world_and_observation()
    input_data = {
        "workflow_id": "wf-travel-fdr-lowcost", "type": "flight-disruption-recovery",
        "trace_id": "trace-lowcost-1", "objective_id": "OBJ-lowcost-1", "observation": observation,
    }
    context = _FakeContext(input_data, utc_now=datetime(2024, 1, 1, tzinfo=timezone.utc))

    output = _drive_with_real_activities(TravelFlightDisruptionRecoveryOrchestrator, context, hitl_response=None)

    assert context.created_timers == []
    assert context.external_event_waits == []
    # Requirement D: the low-cost/auto-approved branch never suspends, so it
    # must truthfully omit the custom-status HITL gate entirely -- never a
    # fabricated "N/A" gate that could be mistaken for a real wait.
    assert context.custom_status is None
    assert output["command"] is not None
    assert output["command"]["type"] == "reaccommodate_travellers"
    assert output["hitl_audit"]["required"] is False


def test_orchestrator_is_replay_safe():
    """Official Azure Durable constraint: replaying the orchestrator with
    the exact same recorded sequence of real activity results must yield
    the identical sequence of activity-call names and the identical final
    output -- the orchestrator reads no direct I/O, network, environment,
    randomness or wall-clock time of its own."""
    from verticals.travel.durable.functions import TravelFlightDisruptionRecoveryOrchestrator

    _world, observation = _low_cost_world_and_observation()
    input_data = {
        "workflow_id": "wf-travel-fdr-replay", "type": "flight-disruption-recovery",
        "trace_id": "trace-replay-1", "objective_id": "OBJ-replay-1", "observation": observation,
    }

    def run_once() -> tuple[list[str], Any]:
        context = _FakeContext(input_data, utc_now=datetime(2024, 1, 1, tzinfo=timezone.utc))
        output = _drive_with_real_activities(TravelFlightDisruptionRecoveryOrchestrator, context, hitl_response=None)
        return [name for name, _ in context.activity_calls], output

    first_calls, first_output = run_once()
    second_calls, second_output = run_once()
    assert first_calls == second_calls
    assert first_output == second_output


# ---------------------------------------------------------------------------
# D. Authority: one registry-backed source of truth across every surface
# ---------------------------------------------------------------------------


def test_operations_controller_authority_matches_production_auto_approve_bound():
    """Issue 2: `TRAVEL_AUTHORITY['operations_controller'].spend_limit_gbp`
    (the fourteen-row bounded GBP authority matrix -- generated from
    `verticals.travel.generator.portfolio.AUTHORITY_SPECS`) and the
    production recovery planner's own `AUTO_APPROVE_BOUND_GBP` must be the
    exact same GBP 750 number by contract, never two independently
    hardcoded magic constants that can silently drift apart. Both feed
    the identical real-world question -- "can `operations_controller`
    auto-approve this reaccommodation, or does it need `head_of_operations`
    escalation?" -- so every surface that answers it (the production
    planner, the Task 4 diagnostic orchestrator's HITL gate, the command
    handler's own authority guard, and the generated
    `profiles/flight-disruption-recovery.json`) must agree. Escalation
    still exists: `head_of_operations`'s own bound must stay strictly
    higher, never collapsed to the same number.
    """
    from verticals.travel.authority import TRAVEL_AUTHORITY
    from verticals.travel.recovery.planner import AUTO_APPROVE_BOUND_GBP

    operations_controller_bound = TRAVEL_AUTHORITY["operations_controller"].spend_limit_gbp
    assert operations_controller_bound == AUTO_APPROVE_BOUND_GBP == 750.0
    assert TRAVEL_AUTHORITY["head_of_operations"].spend_limit_gbp > operations_controller_bound


def test_diagnostic_orchestrator_hitl_gate_agrees_with_production_planner_at_golden_cost():
    """Issue 2: the Task 4 diagnostic `FlightDisruptionRecoveryOrchestrator`'s
    own `escalate` phase runs exactly `_hitl_step('operations_controller')`
    (see `verticals.travel.durable.orchestrators`'s own
    `PhaseStep('escalate', 'hitl', _hitl_step('operations_controller'))`
    wiring), reading `TRAVEL_AUTHORITY['operations_controller'].spend_limit_gbp`
    fresh -- never a separately-hardcoded duplicate. Driving that exact
    closure at the same GBP 900 golden incremental cost the real
    production planner already ranked as `requires_approval=True` must
    agree: `wait` must also be `True` here. Exercised directly against
    the closure itself (rather than the full orchestrator) so this
    contract is proven without ever proceeding into the `reaccommodate`
    phase's real command handler -- irrelevant to, and unsafe to reach
    for, a pure authority-bound cross-check.
    """
    from verticals.travel.durable.orchestrators import _hitl_step
    from verticals.travel.recovery.planner import AUTO_APPROVE_BOUND_GBP, plan_recovery_options

    world = _golden_world()
    observation = _golden_observation(world)
    golden = plan_recovery_options(observation)[0]
    assert golden.incremental_cost_gbp == pytest.approx(900.0)
    assert golden.requires_approval is True  # production planner's own verdict at GBP 900

    escalate = _hitl_step("operations_controller")
    result = escalate(world, {"command_payload": {"estimated_cost_gbp": golden.incremental_cost_gbp}})

    assert result["cost_gbp"] == pytest.approx(golden.incremental_cost_gbp)
    assert result["authority_bound_gbp"] == AUTO_APPROVE_BOUND_GBP == 750.0
    # `run_phase_plan` halts a "hitl" step's plan immediately whenever its
    # result dict reports `wait=True` (see `verticals.travel.durable.
    # orchestrators.run_phase_plan`), so this exact `wait=True` here is
    # what would halt the real diagnostic orchestrator for head_of_operations
    # approval rather than silently proceeding into `reaccommodate`.
    assert result["wait"] is True  # agrees with the production planner: requires approval
