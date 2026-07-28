from __future__ import annotations

import copy
import dataclasses
from typing import Any

import pytest

from api.server.world.model import SimulationCommand
from api.server.world.runtime import SimulationRuntime
from verticals.airline.actions import commands as recovery_commands
from verticals.airline.constraints import (
    FeasibilityResult,
    RecoveryAction,
    RecoveryOption,
    admit_recovery_options,
)
from verticals.airline.worlds.model import RecoveryCommand, RecoveryEvaluation
from verticals.airline.worlds.scenario import AirlineWorld


def _active_world() -> tuple[SimulationRuntime, AirlineWorld]:
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario("synthetic-hub-cascade")
    return runtime, world


def _observation(world: AirlineWorld) -> dict[str, Any]:
    sensor = next(
        event
        for event in world.runtime.journal
        if event.type == "sensor.tripped" and event.actor_id == "sensor:integrated_hub_disruption"
    )
    return world.build_observation(sensor.to_dict())


def _tail_result(observation: dict[str, Any]) -> FeasibilityResult:
    return next(
        result
        for result in admit_recovery_options(observation)
        if result.option.option_id == "SYN-OPTION-TAIL-CREW-STAND"
    )


def _tampered_command(
    command: SimulationCommand,
    *,
    command_id: str,
    **payload_changes: Any,
) -> SimulationCommand:
    payload = copy.deepcopy(command.payload)
    payload.update(payload_changes)
    return dataclasses.replace(command, command_id=command_id, payload=payload)


def test_admission_is_pure_deterministic_and_returns_the_specified_set() -> None:
    _, world = _active_world()
    observation = _observation(world)
    before = copy.deepcopy(observation)

    first = admit_recovery_options(observation)
    second = admit_recovery_options(copy.deepcopy(observation))

    assert first == second
    assert observation == before
    assert [result.option.option_id for result in first] == [
        "SYN-OPTION-TAIL-CREW-STAND",
        "SYN-OPTION-CANCEL",
        "SYN-OPTION-RETIME-ONLY",
    ]
    assert [result.feasible for result in first] == [True, True, False]
    assert first[1].option.impact == "high"
    assert {"crew", "slot"} <= set(first[2].reasons)
    assert dataclasses.is_dataclass(RecoveryAction)
    assert dataclasses.is_dataclass(RecoveryOption)
    with pytest.raises(dataclasses.FrozenInstanceError):
        first[0].feasible = False  # type: ignore[misc]


@pytest.mark.parametrize(
    ("invalid_case", "expected_reason"),
    [
        ("aircraft_status", "aircraft availability"),
        ("aircraft_configuration", "aircraft configuration"),
        ("aircraft_overlap", "aircraft overlap"),
        ("crew_qualification", "crew qualification"),
        ("crew_margin", "crew duty margin"),
        ("slot_window", "slot window"),
        ("stand_compatibility", "stand compatibility"),
        ("evidence_version", "evidence versions"),
        ("bounded_value", "bounded value"),
    ],
)
def test_tail_option_admission_checks_actual_world_invariants(
    invalid_case: str,
    expected_reason: str,
) -> None:
    _, world = _active_world()
    observation = _observation(world)

    if invalid_case == "aircraft_status":
        observation["candidate_aircraft"]["status"] = "unavailable"
    elif invalid_case == "aircraft_configuration":
        observation["candidate_aircraft"]["configuration"] = "A321"
    elif invalid_case == "aircraft_overlap":
        observation["sectors"][2]["aircraft_id"] = "SYN-TAIL-005"
    elif invalid_case == "crew_qualification":
        observation["candidate_crew_duty"]["qualification"] = "A321"
    elif invalid_case == "crew_margin":
        observation["candidate_crew_duty"]["remaining_duty_minutes"] = 20
    elif invalid_case == "slot_window":
        observation["outbound_slot"]["scheduled_time"] = 100.0
    elif invalid_case == "stand_compatibility":
        observation["candidate_stand"]["compatible_configurations"] = ["A321"]
    elif invalid_case == "evidence_version":
        observation["evidence_versions"]["SYN-TAIL-005"] += 1
    else:
        observation["maximum_value_gbp"] = 50_000.0

    result = _tail_result(observation)

    assert result.feasible is False
    assert expected_reason in result.reasons


def test_recovery_command_is_atomic_and_idempotent() -> None:
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario("synthetic-hub-cascade")
    command = world.command_for_option(
        option_id="SYN-OPTION-TAIL-CREW-STAND",
        workflow_id="AIRHUB-0001",
        decision_id="SYN-DECISION-001",
        persona="duty_operations_manager",
    )
    first = world.apply_command(command)
    journal_size = len(runtime.journal)
    second = world.apply_command(command)
    assert first.type == "command.accepted"
    assert second.event_id == first.event_id
    assert len(runtime.journal) == journal_size
    assert world.sectors["SYN-SECTOR-OUT-001"].aircraft_id == "SYN-TAIL-005"
    assert world.sectors["SYN-SECTOR-OUT-001"].crew_duty_id == "SYN-DUTY-006"
    assert world.sectors["SYN-SECTOR-OUT-001"].stand_id == "SYN-STAND-05"


def test_accepted_command_applies_coherent_versioned_mutation_and_evidence() -> None:
    runtime, world = _active_world()
    sector = world.sectors["SYN-SECTOR-OUT-001"]
    rotation = world.rotations["SYN-ROTATION-01"]
    old_crew = world.crew_duties["SYN-CREW-DUTY-01"]
    reserve_crew = world.crew_duties["SYN-DUTY-006"]
    tail = world.aircraft["SYN-TAIL-005"]
    stand = world.stands["SYN-STAND-05"]
    versions = {
        record.id: record.version for record in (sector, rotation, old_crew, reserve_crew, tail, stand)
    }
    command = world.command_for_option(
        option_id="SYN-OPTION-TAIL-CREW-STAND",
        workflow_id="AIRHUB-0001",
        decision_id="SYN-DECISION-001",
        persona="duty_operations_manager",
    )

    result = world.apply_command(command)

    assert result.type == "command.accepted"
    business_event = next(
        event
        for event in runtime.journal
        if event.type == "airline.recovery.applied" and event.payload["command_id"] == command.command_id
    )
    sensor_event = next(
        event
        for event in runtime.journal
        if event.type == "sensor.tripped"
        and event.actor_id == "sensor:integrated_hub_disruption"
    )
    assert command.trace_id == sensor_event.trace_id
    assert business_event.cause_event_id == sensor_event.event_id
    assert result.cause_event_id == business_event.event_id
    assert result.trace_id == business_event.trace_id
    assert rotation.aircraft_id == tail.id
    assert tail.status == "assigned"
    assert reserve_crew.status == "active"
    assert sector.id in reserve_crew.sector_ids
    assert sector.id not in old_crew.sector_ids
    assert stand.status == "assigned"
    assert world.disruption_status["SYN-STORY-HUB-001"] == "resolved"
    for record in (sector, rotation, old_crew, reserve_crew, tail, stand):
        assert record.version == versions[record.id] + 1
        assert record.last_event_id == business_event.event_id

    assert list(world.recovery_commands) == [command.command_id]
    assert list(world.recovery_evaluations) == ["AIRHUB-0001"]
    recovery_command = world.recovery_commands[command.command_id]
    evaluation = world.recovery_evaluations["AIRHUB-0001"]
    assert isinstance(recovery_command, RecoveryCommand)
    assert isinstance(evaluation, RecoveryEvaluation)
    assert recovery_command.option_id == "SYN-OPTION-TAIL-CREW-STAND"
    assert evaluation.status == "pass"
    assert recovery_command.last_event_id == business_event.event_id
    assert evaluation.last_event_id == business_event.event_id
    assert len(world.render_state()["recovery_commands"]) == 1
    assert len(world.render_state()["recovery_evaluations"]) == 1


def test_accepted_cancel_is_coherent_causal_and_idempotent_end_to_end() -> None:
    runtime, world = _active_world()
    sector = world.sectors["SYN-SECTOR-OUT-001"]
    rotation = world.rotations["SYN-ROTATION-01"]
    crew = world.crew_duties[sector.crew_duty_id]
    records = (sector, rotation, crew)
    versions = {record.id: record.version for record in records}
    original_crew_sectors = crew.sector_ids
    command = world.command_for_option(
        option_id="SYN-OPTION-CANCEL",
        workflow_id="AIRHUB-0001",
        decision_id="SYN-DECISION-001",
        persona="duty_operations_manager",
    )

    accepted = world.apply_command(command)

    business_event = next(
        event
        for event in runtime.journal
        if event.type == "airline.recovery.applied"
        and event.payload["command_id"] == command.command_id
    )
    sensor_event = next(
        event
        for event in runtime.journal
        if event.type == "sensor.tripped"
        and event.actor_id == "sensor:integrated_hub_disruption"
    )
    assert accepted.type == "command.accepted"
    assert sector.status == "cancelled"
    assert rotation.status == "recovered"
    assert crew.sector_ids == tuple(
        sector_id for sector_id in original_crew_sectors if sector_id != sector.id
    )
    assert world.disruption_status["SYN-STORY-HUB-001"] == "resolved"
    for record in records:
        assert record.version == versions[record.id] + 1
        assert record.last_event_id == business_event.event_id

    assert list(world.recovery_commands) == [command.command_id]
    assert list(world.recovery_evaluations) == ["AIRHUB-0001"]
    recovery_command = world.recovery_commands[command.command_id]
    evaluation = world.recovery_evaluations["AIRHUB-0001"]
    assert isinstance(recovery_command, RecoveryCommand)
    assert isinstance(evaluation, RecoveryEvaluation)
    assert recovery_command.option_id == "SYN-OPTION-CANCEL"
    assert recovery_command.version == 1
    assert recovery_command.last_event_id == business_event.event_id
    assert evaluation.option_id == "SYN-OPTION-CANCEL"
    assert evaluation.status == "pass"
    assert evaluation.version == 1
    assert evaluation.last_event_id == business_event.event_id

    assert business_event.cause_event_id == sensor_event.event_id
    assert business_event.trace_id == sensor_event.trace_id
    assert business_event.payload["affected_actor_ids"] == [
        sector.id,
        rotation.id,
        crew.id,
    ]
    assert business_event.payload["measurements"]["evaluation_status"] == "pass"
    assert accepted.cause_event_id == business_event.event_id
    assert accepted.trace_id == business_event.trace_id
    assert accepted.payload == {
        "command": command.to_dict(),
        "business_event_id": business_event.event_id,
        "evaluation_id": evaluation.id,
    }

    state_after_acceptance = world.render_state()
    journal_size = len(runtime.journal)
    replayed = world.apply_command(command)

    assert replayed.event_id == accepted.event_id
    assert world.render_state() == state_after_acceptance
    assert len(runtime.journal) == journal_size
    assert list(world.recovery_commands) == [command.command_id]
    assert list(world.recovery_evaluations) == ["AIRHUB-0001"]


def test_infeasible_action_rejects_without_partial_mutation() -> None:
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    before = world.render_state()
    command = SimulationCommand(
        command_id="SYN-CMD-BAD",
        trace_id="SYN-STORY-HUB-001",
        issued_by="operations-control",
        type="airline.commit_recovery_plan",
        payload={
            "workflow_id": "AIRHUB-0002",
            "decision_id": "SYN-DECISION-002",
            "persona": "duty_operations_manager",
            "option_id": "SYN-OPTION-ILLEGAL-CREW",
            "evidence_versions": {},
            "value_gbp": 75_000.0,
        },
    )
    result = world.apply_command(command)
    assert result.type == "command.rejected"
    assert world.render_state() == before


def test_feasible_option_without_registered_handler_rejects_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, world = _active_world()
    admitted = tuple(
        dataclasses.replace(result, feasible=True, reasons=())
        if result.option.option_id == "SYN-OPTION-RETIME-ONLY"
        else result
        for result in admit_recovery_options(_observation(world))
    )
    monkeypatch.setattr(
        recovery_commands,
        "admit_recovery_options",
        lambda _observation: admitted,
    )
    command = world.command_for_option(
        option_id="SYN-OPTION-RETIME-ONLY",
        workflow_id="AIRHUB-0001",
        decision_id="SYN-DECISION-001",
        persona="duty_operations_manager",
    )
    before = world.render_state()
    disruption_status = dict(world.disruption_status)
    journal_size = len(runtime.journal)

    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert "no registered mutator/evaluator" in result.payload["reason"]
    assert world.render_state() == before
    assert world.disruption_status == disruption_status
    assert len(runtime.journal) == journal_size + 1


@pytest.mark.parametrize(
    ("case", "expected_reason"),
    [
        ("stale_evidence", "evidence versions"),
        ("persona", "persona"),
        ("value", "bounded value"),
        ("actions", "actions"),
    ],
)
def test_invalid_authority_or_option_evidence_rejects_without_partial_mutation(
    case: str,
    expected_reason: str,
) -> None:
    runtime, world = _active_world()
    valid = world.command_for_option(
        option_id="SYN-OPTION-TAIL-CREW-STAND",
        workflow_id="AIRHUB-0001",
        decision_id="SYN-DECISION-001",
        persona="duty_operations_manager",
    )
    if case == "stale_evidence":
        evidence_versions = dict(valid.payload["evidence_versions"])
        evidence_versions["SYN-TAIL-005"] -= 1
        command = _tampered_command(
            valid,
            command_id="SYN-CMD-STALE",
            evidence_versions=evidence_versions,
        )
    elif case == "persona":
        command = _tampered_command(
            valid,
            command_id="SYN-CMD-PERSONA",
            persona="hub_operations_officer",
        )
    elif case == "value":
        command = _tampered_command(
            valid,
            command_id="SYN-CMD-VALUE",
            value_gbp=150_000.01,
        )
    else:
        command = _tampered_command(
            valid,
            command_id="SYN-CMD-ACTIONS",
            actions=[],
        )
    before = world.render_state()
    journal_size = len(runtime.journal)

    first = world.apply_command(command)
    second = world.apply_command(command)

    assert first.type == "command.rejected"
    assert expected_reason in first.payload["reason"]
    assert second.event_id == first.event_id
    assert len(runtime.journal) == journal_size + 1
    assert world.render_state() == before


def test_command_for_option_rejects_unknown_and_non_admitted_options() -> None:
    _, world = _active_world()

    with pytest.raises(ValueError, match="unknown recovery option"):
        world.command_for_option(
            option_id="SYN-OPTION-UNKNOWN",
            workflow_id="AIRHUB-0001",
            decision_id="SYN-DECISION-001",
            persona="duty_operations_manager",
        )
    with pytest.raises(ValueError, match="not admitted.*crew.*slot"):
        world.command_for_option(
            option_id="SYN-OPTION-RETIME-ONLY",
            workflow_id="AIRHUB-0001",
            decision_id="SYN-DECISION-001",
            persona="duty_operations_manager",
        )


def test_reused_command_id_with_different_payload_fails_closed() -> None:
    runtime, world = _active_world()
    command = world.command_for_option(
        option_id="SYN-OPTION-TAIL-CREW-STAND",
        workflow_id="AIRHUB-0001",
        decision_id="SYN-DECISION-001",
        persona="duty_operations_manager",
    )
    accepted = world.apply_command(command)
    conflicting = dataclasses.replace(
        command,
        payload={**command.payload, "decision_id": "SYN-DECISION-TAMPERED"},
    )
    before = world.render_state()
    journal_size = len(runtime.journal)

    first = world.apply_command(conflicting)
    second = world.apply_command(conflicting)

    assert accepted.type == "command.accepted"
    assert first.type == "command.rejected"
    assert "idempotency" in first.payload["reason"]
    assert second.event_id == first.event_id
    assert len(runtime.journal) == journal_size + 1
    assert world.render_state() == before


def test_idempotency_cache_keeps_an_immutable_command_snapshot() -> None:
    runtime, world = _active_world()
    command = world.command_for_option(
        option_id="SYN-OPTION-TAIL-CREW-STAND",
        workflow_id="AIRHUB-0001",
        decision_id="SYN-DECISION-001",
        persona="duty_operations_manager",
    )
    accepted = world.apply_command(command)
    command.payload["value_gbp"] = 0.0
    before = world.render_state()
    journal_size = len(runtime.journal)

    rejected = world.apply_command(command)

    assert accepted.type == "command.accepted"
    assert rejected.type == "command.rejected"
    assert "idempotency" in rejected.payload["reason"]
    assert len(runtime.journal) == journal_size + 1
    assert world.render_state() == before
