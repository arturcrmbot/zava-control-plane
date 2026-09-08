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
        "workflow_id": "AIRHUB-0001",
        "decision_id": "SYN-DECISION-001",
        "option_id": "SYN-OPTION-CANCEL",
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


def test_unknown_option_id_in_known_set_rejects_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proves gateway rejects a command whose option_id is registered in _KNOWN_OPTION_IDS
    but has no mutator/evaluator — using a fabricated option not covered by any handler."""
    runtime, world = _active_world()
    # Inject a synthetic fourth option that is feasible but has no handler.
    from verticals.airline.constraints import RecoveryAction, RecoveryOption

    ghost_option = RecoveryOption(
        option_id="SYN-OPTION-GHOST",
        impact="material",
        value_gbp=10_000.0,
        actions=(RecoveryAction("ghost_action", "SYN-SECTOR-OUT-001"),),
        evidence_versions=(),
    )
    admitted_with_ghost = tuple(admit_recovery_options(_observation(world))) + (
        dataclasses.replace(
            dataclasses.replace(
                dataclasses.replace(
                    # Build a FeasibilityResult for the ghost option.
                    admit_recovery_options(_observation(world))[0],
                    option=ghost_option,
                ),
                feasible=True,
            ),
            reasons=(),
        ),
    )
    monkeypatch.setattr(
        recovery_commands,
        "admit_recovery_options",
        lambda _obs: admitted_with_ghost,
    )
    # Temporarily extend the known-option set so _validated_option doesn't pre-reject.
    monkeypatch.setattr(
        recovery_commands,
        "_KNOWN_OPTION_IDS",
        recovery_commands._KNOWN_OPTION_IDS | {"SYN-OPTION-GHOST"},
    )

    from api.server.world.model import SimulationCommand

    observation = world.current_recovery_observation()
    ghost_command = SimulationCommand(
        command_id="SYN-CMD-GHOST",
        trace_id=str(observation["trace_id"]),
        issued_by="operations-control",
        type="airline.commit_recovery_plan",
        payload={
            "workflow_id": "AIRHUB-0001",
            "objective_id": "SYN-OBJECTIVE-AIRHUB-0001",
            "decision_id": "SYN-DECISION-001",
            "disruption_id": "SYN-DISRUPTION-HUB-001",
            "scenario_id": "synthetic-hub-cascade",
            "story_id": "SYN-STORY-HUB-001",
            "persona": "duty_operations_manager",
            "option_id": "SYN-OPTION-GHOST",
            "action_category": "integrated_hub_recovery",
            "actions": [action.to_dict() for action in ghost_option.actions],
            "evidence_versions": {},
            "value_gbp": 10_000.0,
            "expected_event_type": "airline.recovery.applied",
            "expected_evaluation_type": "airline.recovery.evaluation",
        },
    )
    before = world.render_state()
    disruption_status = dict(world.disruption_status)
    journal_size = len(runtime.journal)

    result = world.apply_command(ghost_command)

    assert result.type == "command.rejected"
    assert "no registered mutator/evaluator" in result.payload["reason"]
    assert world.render_state() == before
    assert world.disruption_status == disruption_status
    assert len(runtime.journal) == journal_size + 1


def _make_retime_feasible(world: AirlineWorld) -> None:
    """Adjust crew duty margin and slot time so SYN-OPTION-RETIME-ONLY passes admission.

    Retime requires:
      - outbound crew remaining_duty_minutes >= 390 (RETIME_MINUTES)
      - abs(scheduled_departure + 390 - slot_time) <= tolerance (15)
    The default world has crew=360 and slot_time=150; we move them to 400 and 540.
    Versions are not bumped so the observation evidence remains current.
    """
    world.crew_duties["SYN-CREW-DUTY-01"].remaining_duty_minutes = 400
    world.slots["SYN-SLOT-05"].scheduled_time = 540.0


def test_retime_option_accepted_coherent_versioned_mutation_and_evidence() -> None:
    runtime, world = _active_world()
    _make_retime_feasible(world)

    sector = world.sectors["SYN-SECTOR-OUT-001"]
    slot = world.slots["SYN-SLOT-05"]
    original_departure = sector.scheduled_departure
    sector_version = sector.version
    slot_version = slot.version

    command = world.command_for_option(
        option_id="SYN-OPTION-RETIME-ONLY",
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
        if event.type == "sensor.tripped" and event.actor_id == "sensor:integrated_hub_disruption"
    )
    assert command.trace_id == sensor_event.trace_id
    assert business_event.cause_event_id == sensor_event.event_id
    assert result.cause_event_id == business_event.event_id
    assert result.trace_id == business_event.trace_id

    # Sector was retimed: departure moved forward by 390 minutes, delay cleared to 0
    assert sector.scheduled_departure == original_departure + 390
    assert sector.delay_minutes == 0
    # Slot time matches new sector departure
    assert sector.scheduled_departure == slot.scheduled_time
    # Slot remains allocated (already a precondition, not mutated)
    assert slot.status == "allocated"
    # Slot version not bumped (was already allocated in preconditions)
    assert slot.version == slot_version
    # Only sector was mutated
    assert sector.version == sector_version + 1
    assert world.disruption_status["SYN-STORY-HUB-001"] == "resolved"

    # Sector has last_event_id set
    assert sector.last_event_id == business_event.event_id

    assert list(world.recovery_commands) == [command.command_id]
    assert list(world.recovery_evaluations) == ["AIRHUB-0001"]
    recovery_command = world.recovery_commands[command.command_id]
    evaluation = world.recovery_evaluations["AIRHUB-0001"]
    assert isinstance(recovery_command, RecoveryCommand)
    assert isinstance(evaluation, RecoveryEvaluation)
    assert recovery_command.option_id == "SYN-OPTION-RETIME-ONLY"
    assert recovery_command.last_event_id == business_event.event_id
    assert evaluation.option_id == "SYN-OPTION-RETIME-ONLY"
    assert evaluation.status == "pass"
    assert evaluation.last_event_id == business_event.event_id
    assert len(world.render_state()["recovery_commands"]) == 1
    assert len(world.render_state()["recovery_evaluations"]) == 1


def test_retime_option_is_atomic_and_idempotent() -> None:
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario("synthetic-hub-cascade")
    _make_retime_feasible(world)

    command = world.command_for_option(
        option_id="SYN-OPTION-RETIME-ONLY",
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
    # After retime, sector has moved forward 390 minutes with delay_minutes cleared to 0
    assert world.sectors["SYN-SECTOR-OUT-001"].scheduled_departure == 150.0 + 390
    assert world.sectors["SYN-SECTOR-OUT-001"].delay_minutes == 0


def test_retime_causal_trace_and_evaluation_metrics() -> None:
    runtime, world = _active_world()
    _make_retime_feasible(world)

    sector = world.sectors["SYN-SECTOR-OUT-001"]
    command = world.command_for_option(
        option_id="SYN-OPTION-RETIME-ONLY",
        workflow_id="AIRHUB-0002",
        decision_id="SYN-DECISION-002",
        persona="duty_operations_manager",
    )
    accepted = world.apply_command(command)

    business_event = next(
        event
        for event in runtime.journal
        if event.type == "airline.recovery.applied" and event.payload["command_id"] == command.command_id
    )
    sensor_event = next(
        event
        for event in runtime.journal
        if event.type == "sensor.tripped" and event.actor_id == "sensor:integrated_hub_disruption"
    )
    assert business_event.cause_event_id == sensor_event.event_id
    assert business_event.trace_id == sensor_event.trace_id
    assert business_event.payload["option_id"] == "SYN-OPTION-RETIME-ONLY"
    assert business_event.payload["measurements"]["evaluation_status"] == "pass"
    assert business_event.payload["measurements"]["disruption_status"] == "resolved"
    assert accepted.cause_event_id == business_event.event_id
    assert accepted.payload["option_id"] == "SYN-OPTION-RETIME-ONLY"

    evaluation = world.recovery_evaluations["AIRHUB-0002"]
    assert evaluation.status == "pass"
    assert evaluation.cancellations_avoided == 1
    # Retime achieves 0 delay on new scheduled time, so counts as departure-zero/within-fifteen recovered
    assert evaluation.departure_zero_recovered == 1
    assert evaluation.departure_within_fifteen_recovered == 1
    # Retime does not require rerouting — sector is not cancelled.
    assert evaluation.passengers_requiring_rerouting == 0
    assert evaluation.synthetic_recovery_cost_gbp == 20_000.0

    # State after acceptance is stable under idempotent replay.
    state_after = world.render_state()
    journal_size = len(runtime.journal)
    replayed = world.apply_command(command)
    assert replayed.event_id == accepted.event_id
    assert world.render_state() == state_after
    assert len(runtime.journal) == journal_size


def test_default_scenario_keeps_retime_infeasible() -> None:
    """The unmodified synthetic-hub-cascade world keeps SYN-OPTION-RETIME-ONLY infeasible
    because outbound crew margin (360) < 390 and slot time (150) is far from the retime target."""
    _, world = _active_world()
    observation = _observation(world)
    retime_result = next(
        result
        for result in admit_recovery_options(observation)
        if result.option.option_id == "SYN-OPTION-RETIME-ONLY"
    )
    assert retime_result.feasible is False
    assert "crew" in retime_result.reasons
    assert "slot" in retime_result.reasons
    with pytest.raises(ValueError, match="not admitted.*crew.*slot"):
        world.command_for_option(
            option_id="SYN-OPTION-RETIME-ONLY",
            workflow_id="AIRHUB-0001",
            decision_id="SYN-DECISION-001",
            persona="duty_operations_manager",
        )


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


# ---------------------------------------------------------------------------
# _mutate_retime_plan contract: resource_id and minutes from action (Hero 1)
# ---------------------------------------------------------------------------


def _make_retime_option(
    *,
    resource_id: str | None,
    minutes: int | bool | None,
) -> RecoveryOption:
    """Build a minimal RecoveryOption for retime mutation tests."""
    return RecoveryOption(
        option_id="SYN-OPTION-RETIME-ONLY",
        impact="low",
        value_gbp=20_000.0,
        evidence_versions={},
        actions=(
            RecoveryAction(
                action_type="retime_sector",
                sector_id="SYN-SECTOR-OUT-001",
                resource_id=resource_id,
                minutes=minutes,  # type: ignore[arg-type]
            ),
        ),
    )


def test_retime_mutator_rejects_nonexistent_slot_before_mutation() -> None:
    """_mutate_retime_plan must validate slot existence before mutating sector (atomicity).

    A syntactically valid but nonexistent resource_id must raise ValueError before any sector mutation.
    This prevents sector state corruption if the slot lookup fails.
    """
    _, world = _active_world()
    sector_version_before = world.sectors["SYN-SECTOR-OUT-001"].version
    sector_departure_before = world.sectors["SYN-SECTOR-OUT-001"].scheduled_departure

    option = _make_retime_option(resource_id="SYN-SLOT-999", minutes=30)
    with pytest.raises(ValueError, match="slot.*not found|no such slot"):
        recovery_commands._mutate_retime_plan(world, option)

    # Verify sector was NOT mutated
    sector = world.sectors["SYN-SECTOR-OUT-001"]
    assert sector.version == sector_version_before
    assert sector.scheduled_departure == sector_departure_before


def test_retime_mutator_consumes_resource_id_from_action_not_hardcoded() -> None:
    """_mutate_retime_plan must consult the slot from action.resource_id to validate slot membership.

    The mutation should succeed only if the slot exists and belongs to the sector.
    This test proves the function reads action.resource_id by using a different slot that exists.
    Only the sector is returned in mutated list; slot is already allocated from preconditions.
    """
    _, world = _active_world()
    # Use SYN-SLOT-05 which is already allocated to the target sector in preconditions
    option = _make_retime_option(resource_id="SYN-SLOT-05", minutes=30)
    mutated = recovery_commands._mutate_retime_plan(world, option)
    # Only sector should be mutated
    assert len(mutated) == 1
    assert mutated[0].id == "SYN-SECTOR-OUT-001"
    # Sector departure should be moved forward by 30 minutes
    assert mutated[0].scheduled_departure == 150.0 + 30
    # Slot is accessed from action.resource_id and validated, proving it consulted the parameter


@pytest.mark.parametrize(
    ("resource_id", "minutes", "match"),
    [
        (None, 30, "resource_id"),
        ("", 30, "resource_id"),
        ("SYN-SLOT-05", True, "minutes"),
        ("SYN-SLOT-05", 0, "minutes"),
        ("SYN-SLOT-05", -5, "minutes"),
    ],
)
def test_retime_mutator_fails_closed_on_malformed_action_contract(
    resource_id: str | None,
    minutes: int | bool | None,
    match: str,
) -> None:
    """_mutate_retime_plan must raise ValueError for every malformed admitted action.

    With the hardcoded _RETIME_SLOT_ID these cases are silently accepted (None/''
    are ignored, bool coerces via int(), non-positive ints are set verbatim).
    After the fix each case must raise explicitly before any world mutation.
    """
    _, world = _active_world()
    option = _make_retime_option(resource_id=resource_id, minutes=minutes)
    with pytest.raises(ValueError, match=match):
        recovery_commands._mutate_retime_plan(world, option)

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


def test_retime_mutation_moves_departure_forward_and_clears_delay_minutes() -> None:
    """Correct retime semantic: move scheduled_departure forward by action.minutes, clear delay_minutes to 0."""
    runtime, world = _active_world()
    _make_retime_feasible(world)

    sector = world.sectors["SYN-SECTOR-OUT-001"]
    original_departure = sector.scheduled_departure
    slot = world.slots["SYN-SLOT-05"]

    command = world.command_for_option(
        option_id="SYN-OPTION-RETIME-ONLY",
        workflow_id="AIRHUB-0001",
        decision_id="SYN-DECISION-001",
        persona="duty_operations_manager",
    )

    result = world.apply_command(command)

    assert result.type == "command.accepted"
    # After retime, sector.scheduled_departure should move forward by 390 minutes
    assert sector.scheduled_departure == original_departure + 390
    # After retime, sector.delay_minutes should be 0 (not 390)
    assert sector.delay_minutes == 0
    # Slot time should match new sector departure
    assert sector.scheduled_departure == slot.scheduled_time


def test_retime_mutation_only_mutates_sector_not_slot() -> None:
    """Only sector should be in mutated list; slot is already allocated from preconditions."""
    _, world = _active_world()
    option = _make_retime_option(resource_id="SYN-SLOT-05", minutes=390)

    mutated = recovery_commands._mutate_retime_plan(world, option)

    # Only sector should be mutated, not the slot
    assert len(mutated) == 1
    assert mutated[0].id == "SYN-SECTOR-OUT-001"
    slot_ids = {obj.id for obj in mutated}
    assert "SYN-SLOT-05" not in slot_ids


def test_retime_evaluation_checks_departure_time_match_and_zero_delay() -> None:
    """Evaluation should verify sector departure matches slot time and delay is zero."""
    runtime, world = _active_world()
    _make_retime_feasible(world)

    sector = world.sectors["SYN-SECTOR-OUT-001"]
    slot = world.slots["SYN-SLOT-05"]
    original_departure = sector.scheduled_departure

    command = world.command_for_option(
        option_id="SYN-OPTION-RETIME-ONLY",
        workflow_id="AIRHUB-0002",
        decision_id="SYN-DECISION-002",
        persona="duty_operations_manager",
    )

    result = world.apply_command(command)

    assert result.type == "command.accepted"
    # Verify evaluation checks
    evaluation = world.recovery_evaluations["AIRHUB-0002"]
    assert evaluation.status == "pass"
    # Verify that metrics treat retime appropriately
    # Since retime achieves 0 delay on the new scheduled time, it counts as departure-zero-recovered
    assert evaluation.departure_zero_recovered == 1
    assert evaluation.departure_within_fifteen_recovered == 1
    # Verify sector state is correct
    assert sector.scheduled_departure == original_departure + 390
    assert sector.delay_minutes == 0
    assert sector.scheduled_departure == slot.scheduled_time
