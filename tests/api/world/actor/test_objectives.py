"""Deterministic proof for ObjectiveManager: IDs, dedupe, the strict transition
table, and causal/trace links written into the real simulation journal.
"""
from __future__ import annotations

import pytest

from api.server.world.objectives import ObjectiveManager
from api.server.world.registry import WORLD_PACKS
from api.server.world.runtime import SimulationRuntime

SUPPORT = WORLD_PACKS["support"]


def _runtime() -> SimulationRuntime:
    return SimulationRuntime(seed=42)


def _sensor(runtime: SimulationRuntime, *, target: str = "queue:support", trace: str = "support-pressure-5"):
    event = runtime.emit(
        "sensor.tripped",
        actor_id="sensor:support_pressure",
        target_id=target,
        trace_id=trace,
        payload={"measurements": {"support_backlog": 30}},
    )
    return event.to_dict()


def test_deterministic_objective_id_from_sensor_event():
    runtime = _runtime()
    sensor = _sensor(runtime)
    manager = ObjectiveManager(runtime)
    objective = manager.open(sensor, SUPPORT, owner_function="surge_staffing_responder")
    assert objective.id == f"obj-{sensor['event_id']}"
    assert objective.type == "support_capacity"
    assert objective.status == "open"
    assert objective.allowed_command_types == frozenset({"reallocate_workers"})
    assert objective.evidence_event_ids == (sensor["event_id"],)


def test_open_journals_objective_opened_on_the_sensor_trace():
    runtime = _runtime()
    sensor = _sensor(runtime)
    manager = ObjectiveManager(runtime)
    objective = manager.open(sensor, SUPPORT, owner_function="surge_staffing_responder")
    opened = runtime.journal[-1]
    assert opened.type == "objective.opened"
    assert opened.trace_id == sensor["trace_id"] == objective.trace_id
    assert opened.cause_event_id == sensor["event_id"]
    assert opened.payload["id"] == objective.id
    assert opened.payload["allowed_command_types"] == ["reallocate_workers"]


def test_dedupe_returns_existing_active_objective_without_second_opened():
    runtime = _runtime()
    manager = ObjectiveManager(runtime)
    first = manager.open(_sensor(runtime), SUPPORT, owner_function="r")
    opened_events = sum(e.type == "objective.opened" for e in runtime.journal)
    # A second sensor for the same (type, target) — different event id/trace.
    second = manager.open(
        _sensor(runtime, trace="support-pressure-9"), SUPPORT, owner_function="r"
    )
    assert second is first
    assert sum(e.type == "objective.opened" for e in runtime.journal) == opened_events


def test_distinct_targets_open_distinct_objectives():
    runtime = _runtime()
    manager = ObjectiveManager(runtime)
    a = manager.open(_sensor(runtime, target="SITE-01"), SUPPORT, owner_function="r")
    b = manager.open(_sensor(runtime, target="SITE-02"), SUPPORT, owner_function="r")
    assert a.id != b.id
    assert {o.id for o in manager.active()} == {a.id, b.id}


def test_full_lifecycle_transitions_chain_causally_on_one_trace():
    runtime = _runtime()
    sensor = _sensor(runtime)
    manager = ObjectiveManager(runtime)
    objective = manager.open(sensor, SUPPORT, owner_function="r")
    opened = runtime.journal[-1]

    claimed = manager.transition(objective.id, "claimed", claimed_by="surge-trace")
    assert claimed.status == "claimed"
    assert claimed.claimed_by == "surge-trace"
    claimed_evt = runtime.journal[-1]
    assert claimed_evt.type == "objective.claimed"
    assert claimed_evt.cause_event_id == opened.event_id
    assert claimed_evt.trace_id == sensor["trace_id"]

    acting = manager.transition(objective.id, "acting")
    assert acting.status == "acting"
    assert runtime.journal[-1].type == "objective.acting"
    assert runtime.journal[-1].cause_event_id == claimed_evt.event_id

    evaluating = manager.transition(objective.id, "evaluating")
    assert evaluating.status == "evaluating"
    assert runtime.journal[-1].type == "objective.evaluating"

    resolved = manager.transition(objective.id, "resolved")
    assert resolved.status == "resolved"
    assert runtime.journal[-1].type == "objective.resolved"
    # every lifecycle event stayed on the sensor's trace
    lifecycle = [e for e in runtime.journal if e.type.startswith("objective.")]
    assert {e.trace_id for e in lifecycle} == {sensor["trace_id"]}


def test_invalid_transition_rejected():
    runtime = _runtime()
    manager = ObjectiveManager(runtime)
    objective = manager.open(_sensor(runtime), SUPPORT, owner_function="r")
    with pytest.raises(ValueError, match="cannot transition open → acting"):
        manager.transition(objective.id, "acting")


def test_terminal_objective_cannot_transition_again():
    runtime = _runtime()
    manager = ObjectiveManager(runtime)
    objective = manager.open(_sensor(runtime), SUPPORT, owner_function="r")
    manager.transition(objective.id, "failed")
    with pytest.raises(ValueError, match="cannot transition failed → "):
        manager.transition(objective.id, "claimed")


def test_claimed_transition_requires_claimed_by():
    runtime = _runtime()
    manager = ObjectiveManager(runtime)
    objective = manager.open(_sensor(runtime), SUPPORT, owner_function="r")
    with pytest.raises(ValueError, match="requires claimed_by"):
        manager.transition(objective.id, "claimed")


def test_resolved_objective_frees_key_for_a_fresh_objective():
    runtime = _runtime()
    manager = ObjectiveManager(runtime)
    first = manager.open(_sensor(runtime), SUPPORT, owner_function="r")
    manager.transition(first.id, "superseded")
    assert manager.active() == []
    second = manager.open(
        _sensor(runtime, trace="support-pressure-12"), SUPPORT, owner_function="r"
    )
    assert second is not first
    assert second.id != first.id
    assert [o.id for o in manager.all()] == [first.id, second.id]


def test_unknown_objective_id_raises_keyerror():
    runtime = _runtime()
    manager = ObjectiveManager(runtime)
    with pytest.raises(KeyError):
        manager.transition("obj-missing", "claimed", claimed_by="x")
