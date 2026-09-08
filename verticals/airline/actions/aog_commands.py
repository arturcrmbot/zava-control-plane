"""Airline Hero 2 – AOG Engineering Recovery command handler.

Distinct command type: airline.commit_aog_recovery
Canonical workflow IDs start with AOGA-.
"""
from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING, Any

from api.server.world.model import SimulationCommand, SimulationEvent
from verticals.airline.aog_constants import (
    AOG_AFFECTED_TAIL_ID,
    AOG_COMMAND_TYPE,
    AOG_HITL_PERSONA,
    AOG_ISSUER,
    AOG_PROVIDER_ID,
    AOG_ROTATION_ID,
    AOG_SCENARIO_ID,
    AOG_SPARE_LOCAL_ID,
    AOG_SPARE_REPO_ID,
    AOG_STORY_ID,
    AOG_SUBSTITUTE_TAIL_ID,
    AOG_SUCCESS_EVENT,
    AOG_TASK_ID,
    AOG_TECH_STATUS_ID,
    AOG_THREATENED_SECTOR_ID,
    AOG_WORKFLOW_ID,
)
from verticals.airline.aog_constraints import (
    AOG_OPTION_SUBSTITUTE,
    AOG_OPTION_WORK_LOCAL,
    AOG_OPTION_WORK_REPO,
    AogFeasibilityResult,
    AogOption,
    admit_aog_options,
)
from verticals.airline.worlds.model import (
    AogRecoveryCommand,
    AogRecoveryEvaluation,
    EngineeringWorkOrder,
    SpareMovement,
)
from verticals.airline.worlds.reference_data import HUB_ID

if TYPE_CHECKING:
    from verticals.airline.worlds.scenario import AirlineWorld

_KNOWN_OPTION_IDS = frozenset({
    AOG_OPTION_WORK_LOCAL,
    AOG_OPTION_WORK_REPO,
    AOG_OPTION_SUBSTITUTE,
})


def aog_recovery_command_id(
    *,
    workflow_id: str,
    decision_id: str,
    option_id: str,
) -> str:
    return f"SYN-AOG-CMD-{workflow_id}-{decision_id}-{option_id}"


def _result_for(obs: dict[str, Any], option_id: str) -> AogFeasibilityResult | None:
    return next(
        (r for r in admit_aog_options(obs) if r.option.option_id == option_id),
        None,
    )


def command_for_aog_option(
    world: AirlineWorld,
    *,
    option_id: str,
    workflow_id: str,
    decision_id: str,
    persona: str,
) -> SimulationCommand:
    obs = world.current_aog_observation()
    result = _result_for(obs, option_id)
    if result is None:
        raise ValueError(f"unknown AOG recovery option: {option_id!r}")
    if not result.feasible:
        reasons = ", ".join(result.reasons)
        raise ValueError(f"AOG option {option_id!r} is not admitted: {reasons}")
    option = result.option
    return SimulationCommand(
        command_id=aog_recovery_command_id(
            workflow_id=workflow_id,
            decision_id=decision_id,
            option_id=option_id,
        ),
        trace_id=str(obs["trace_id"]),
        issued_by=AOG_ISSUER,
        type=AOG_COMMAND_TYPE,
        payload={
            "workflow_id": workflow_id,
            "objective_id": f"SYN-AOG-OBJECTIVE-{workflow_id}",
            "decision_id": decision_id,
            "scenario_id": AOG_SCENARIO_ID,
            "story_id": AOG_STORY_ID,
            "persona": persona,
            "option_id": option.option_id,
            "action_category": "aog_engineering_recovery",
            "actions": [a.to_dict() for a in option.actions],
            "evidence_versions": dict(option.evidence_versions),
            "value_gbp": option.value_gbp,
            "expected_event_type": AOG_SUCCESS_EVENT,
            "expected_evaluation_type": "airline.aog.evaluation",
        },
    )


def _aog_reject(
    world: AirlineWorld,
    command: SimulationCommand,
    reason: str,
) -> SimulationEvent:
    source = world._scenario_events.get(AOG_SCENARIO_ID)
    return world.runtime.emit(
        "command.rejected",
        actor_id=command.issued_by,
        target_id=AOG_THREATENED_SECTOR_ID,
        cause_event_id=source.event_id if source is not None else None,
        trace_id=command.trace_id,
        payload={"command": command.to_dict(), "reason": reason},
    )


def _validated_aog_option(
    world: AirlineWorld,
    command: SimulationCommand,
) -> tuple[AogOption | None, dict[str, Any] | None, str | None]:
    if command.type != AOG_COMMAND_TYPE:
        return None, None, f"unsupported command type {command.type!r} for AOG handler"

    payload = command.payload
    option_id = payload.get("option_id")
    if option_id not in _KNOWN_OPTION_IDS:
        return None, None, f"unknown or non-admitted AOG recovery option {option_id!r}"

    if world.aog_story_status.get(AOG_STORY_ID) != "active":
        return None, None, f"AOG story {AOG_STORY_ID!r} is not active"

    obs = world.current_aog_observation()
    result = _result_for(obs, str(option_id))
    if result is None:
        return None, obs, f"unknown AOG recovery option {option_id!r}"
    if not result.feasible:
        return None, obs, f"option {option_id!r} not admitted: {', '.join(result.reasons)}"
    option = result.option

    workflow_id = payload.get("workflow_id")
    decision_id = payload.get("decision_id")
    if not isinstance(workflow_id, str) or not workflow_id.startswith("AOGA-"):
        return None, obs, "workflow_id is not a canonical AOGA id"
    if not isinstance(decision_id, str) or not decision_id.startswith("SYN-AOG-DECISION-"):
        return None, obs, "decision_id is not a canonical AOG synthetic id"
    if payload.get("objective_id") != f"SYN-AOG-OBJECTIVE-{workflow_id}":
        return None, obs, "AOG objective identity does not match workflow"
    if (
        payload.get("scenario_id") != AOG_SCENARIO_ID
        or payload.get("story_id") != AOG_STORY_ID
    ):
        return None, obs, "AOG scenario or story identity is invalid"
    if command.trace_id != obs.get("trace_id"):
        return None, obs, "command trace does not match AOG sensor trace"
    if command.issued_by != AOG_ISSUER:
        return None, obs, f"issuer {command.issued_by!r} is not authorised"

    persona = payload.get("persona")
    if persona != AOG_HITL_PERSONA:
        return None, obs, f"persona {persona!r} cannot approve AOG recovery"

    from verticals.airline.authority import AIRLINE_AUTHORITY
    authority_row = AIRLINE_AUTHORITY.get(AOG_HITL_PERSONA)
    if authority_row is None:
        return None, obs, f"no authority row for persona {AOG_HITL_PERSONA!r} — failing closed"
    if AOG_COMMAND_TYPE not in authority_row.approval_actions:
        return None, obs, f"action {AOG_COMMAND_TYPE!r} not in authority row for {AOG_HITL_PERSONA!r} — failing closed"
    max_value_gbp = authority_row.spend_limit_gbp

    value = payload.get("value_gbp")
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) != option.value_gbp
        or float(value) < 0
        or float(value) > max_value_gbp
    ):
        return (
            None,
            obs,
            f"bounded value must equal GBP {option.value_gbp:,.2f} and not exceed "
            f"GBP {max_value_gbp:,.2f}",
        )

    if payload.get("evidence_versions") != dict(option.evidence_versions):
        return None, obs, "AOG evidence versions are stale or incomplete"
    expected_actions = [a.to_dict() for a in option.actions]
    if payload.get("actions") != expected_actions:
        return None, obs, "AOG actions do not match the admitted option"
    if (
        payload.get("action_category") != "aog_engineering_recovery"
        or payload.get("expected_event_type") != AOG_SUCCESS_EVENT
        or payload.get("expected_evaluation_type") != "airline.aog.evaluation"
    ):
        return None, obs, "AOG command contract metadata is invalid"

    return option, obs, None


# ---------------------------------------------------------------------------
# Mutation helpers
# ---------------------------------------------------------------------------

def _mutate_work_order(
    world: AirlineWorld,
    option: AogOption,
    spare_id: str,
) -> list[Any]:
    tech = world.technical_statuses[AOG_TECH_STATUS_ID]
    task = world.maintenance_tasks[AOG_TASK_ID]
    spare = world.spares[spare_id]
    aircraft = world.aircraft[AOG_AFFECTED_TAIL_ID]

    task.provider_id = AOG_PROVIDER_ID
    task.status = "in_progress"
    tech.status = "work_in_progress"
    spare.status = "reserved"
    # Aircraft stays grounded – do not change to operational/serviceable
    return [tech, task, spare, aircraft]


def _create_work_order_records(
    world: AirlineWorld,
    workflow_id: str,
    spare_id: str,
) -> tuple[EngineeringWorkOrder, SpareMovement]:
    spare = world.spares[spare_id]
    aircraft = world.aircraft[AOG_AFFECTED_TAIL_ID]
    wo = EngineeringWorkOrder(
        id=f"SYN-EWO-{workflow_id}",
        workflow_id=workflow_id,
        technical_status_id=AOG_TECH_STATUS_ID,
        maintenance_task_id=AOG_TASK_ID,
        provider_id=AOG_PROVIDER_ID,
        spare_id=spare_id,
        status="in_progress",
    )
    movement = SpareMovement(
        id=f"SYN-SMOV-{workflow_id}",
        spare_id=spare_id,
        workflow_id=workflow_id,
        from_station_id=spare.station_id,
        to_station_id=aircraft.current_station_id,
        status="reserved",
    )
    return wo, movement


def _mutate_substitute(world: AirlineWorld) -> list[Any]:
    sector = world.sectors[AOG_THREATENED_SECTOR_ID]
    sub = world.aircraft[AOG_SUBSTITUTE_TAIL_ID]

    sector.aircraft_id = sub.id
    sub.status = "assigned"
    return [sector, sub]


def _create_substitute_coordination(
    world: AirlineWorld,
    workflow_id: str,
) -> EngineeringWorkOrder:
    """Engineering coordination record for grounded tail when substituting."""
    return EngineeringWorkOrder(
        id=f"SYN-EWO-{workflow_id}",
        workflow_id=workflow_id,
        technical_status_id=AOG_TECH_STATUS_ID,
        maintenance_task_id=AOG_TASK_ID,
        provider_id=AOG_PROVIDER_ID,
        spare_id=None,
        status="open",
    )


def _evaluation_results(
    world: AirlineWorld,
    option: AogOption,
) -> tuple[str, tuple[str, ...]]:
    if option.option_id in {AOG_OPTION_WORK_LOCAL, AOG_OPTION_WORK_REPO}:
        tech = world.technical_statuses[AOG_TECH_STATUS_ID]
        task = world.maintenance_tasks[AOG_TASK_ID]
        spare_id = AOG_SPARE_LOCAL_ID if option.option_id == AOG_OPTION_WORK_LOCAL else AOG_SPARE_REPO_ID
        spare = world.spares[spare_id]
        aircraft = world.aircraft[AOG_AFFECTED_TAIL_ID]
        checks = (
            (
                "technical_status_work_in_progress",
                tech.status == "work_in_progress" and tech.aircraft_id == AOG_AFFECTED_TAIL_ID,
            ),
            ("task_in_progress", task.status == "in_progress" and task.provider_id == AOG_PROVIDER_ID),
            ("spare_reserved", spare.status == "reserved"),
            ("aircraft_not_released", aircraft.status in {"grounded", "work_in_progress"}),
            ("work_order_created", bool(world.engineering_work_orders)),
            ("spare_movement_created", bool(world.spare_movements)),
        )
    elif option.option_id == AOG_OPTION_SUBSTITUTE:
        sector = world.sectors[AOG_THREATENED_SECTOR_ID]
        sub = world.aircraft[AOG_SUBSTITUTE_TAIL_ID]
        aircraft = world.aircraft[AOG_AFFECTED_TAIL_ID]
        checks = (
            ("substitute_assigned", sector.aircraft_id == sub.id and sub.status == "assigned"),
            ("grounded_tail_unchanged", aircraft.status == "grounded"),
            ("engineering_coordination_created", bool(world.engineering_work_orders)),
        )
    else:
        raise ValueError(f"AOG option {option.option_id!r} has no registered evaluator")

    results = tuple(f"{name}:{'pass' if passed else 'fail'}" for name, passed in checks)
    return ("pass" if all(p for _, p in checks) else "fail"), results


# ---------------------------------------------------------------------------
# Accept / apply
# ---------------------------------------------------------------------------

def _accept_aog(
    world: AirlineWorld,
    command: SimulationCommand,
    option: AogOption,
    obs: dict[str, Any],
) -> SimulationEvent:
    workflow_id = str(command.payload["workflow_id"])

    if option.option_id in {AOG_OPTION_WORK_LOCAL, AOG_OPTION_WORK_REPO}:
        spare_id = AOG_SPARE_LOCAL_ID if option.option_id == AOG_OPTION_WORK_LOCAL else AOG_SPARE_REPO_ID
        mutated = _mutate_work_order(world, option, spare_id)
        wo, movement = _create_work_order_records(world, workflow_id, spare_id)
    elif option.option_id == AOG_OPTION_SUBSTITUTE:
        mutated = _mutate_substitute(world)
        wo = _create_substitute_coordination(world, workflow_id)
        movement = None
    else:
        return _aog_reject(world, command, f"AOG option {option.option_id!r} has no registered mutator")

    for record in mutated:
        record.version += 1

    world.aog_story_status[AOG_STORY_ID] = "resolved"

    # Register work orders before evaluation so invariants can check them
    world.engineering_work_orders[wo.id] = wo
    if movement is not None:
        world.spare_movements[movement.id] = movement

    aog_cmd = AogRecoveryCommand(
        id=command.command_id,
        workflow_id=workflow_id,
        decision_id=str(command.payload["decision_id"]),
        option_id=option.option_id,
        persona=str(command.payload["persona"]),
        value_gbp=option.value_gbp,
        action_types=tuple(a.action_type for a in option.actions),
        evidence_versions=option.evidence_versions,
    )

    evaluation_status, invariant_results = _evaluation_results(world, option)

    spare_lead_time = 0
    if option.option_id in {AOG_OPTION_WORK_LOCAL, AOG_OPTION_WORK_REPO}:
        spare_id = AOG_SPARE_LOCAL_ID if option.option_id == AOG_OPTION_WORK_LOCAL else AOG_SPARE_REPO_ID
        spare_lead_time = world.spares[spare_id].lead_time_minutes

    sectors_protected = int(option.option_id == AOG_OPTION_SUBSTITUTE)
    projected_aog_minutes = spare_lead_time + 240 if option.option_id != AOG_OPTION_SUBSTITUTE else 0

    evaluation = AogRecoveryEvaluation(
        id=f"SYN-AOG-EVAL-{workflow_id}",
        workflow_id=workflow_id,
        command_id=command.command_id,
        option_id=option.option_id,
        status=evaluation_status,
        invariant_results=invariant_results,
        sectors_protected=sectors_protected,
        projected_aog_duration_minutes=projected_aog_minutes,
        spare_lead_time_minutes=spare_lead_time,
        approved_provider_coverage=option.option_id in {AOG_OPTION_WORK_LOCAL, AOG_OPTION_WORK_REPO},
        synthetic_recovery_cost_gbp=option.value_gbp,
        aircraft_released_by_ai=False,
    )

    business = world.runtime.emit(
        AOG_SUCCESS_EVENT,
        actor_id=command.issued_by,
        target_id=AOG_THREATENED_SECTOR_ID,
        cause_event_id=str(obs["sensor_event_id"]),
        trace_id=command.trace_id,
        payload={
            "command_id": command.command_id,
            "workflow_id": workflow_id,
            "decision_id": command.payload["decision_id"],
            "option_id": option.option_id,
            "actions": [a.to_dict() for a in option.actions],
            "affected_actor_ids": [record.id for record in mutated],
            "evidence_event_ids": obs["evidence_event_ids"],
            "measurements": {
                "evaluation_status": evaluation.status,
                "aog_story_status": "resolved",
                "value_gbp": option.value_gbp,
                "aircraft_released_by_ai": False,
            },
        },
    )
    for record in mutated:
        record.last_event_id = business.event_id
    world.engineering_work_orders[wo.id].last_event_id = business.event_id
    if movement is not None:
        world.spare_movements[movement.id].last_event_id = business.event_id
    aog_cmd.last_event_id = business.event_id
    evaluation.last_event_id = business.event_id

    world.aog_recovery_commands[aog_cmd.id] = aog_cmd
    world.aog_recovery_evaluations[evaluation.id] = evaluation

    return world.runtime.emit(
        "command.accepted",
        actor_id=command.issued_by,
        target_id=AOG_THREATENED_SECTOR_ID,
        cause_event_id=business.event_id,
        trace_id=command.trace_id,
        payload={
            "workflow_id": workflow_id,
            "decision_id": command.payload["decision_id"],
            "option_id": option.option_id,
            "command": command.to_dict(),
            "business_event_id": business.event_id,
            "evaluation_id": evaluation.id,
            "mutation_records": {
                "work_order": dataclasses.asdict(wo),
                "spare_movement": (
                    dataclasses.asdict(movement) if movement is not None else None
                ),
                "spare": (
                    dataclasses.asdict(world.spares[wo.spare_id])
                    if wo.spare_id is not None
                    else None
                ),
                "aog_command": dataclasses.asdict(aog_cmd),
                "evaluation": dataclasses.asdict(evaluation),
            },
        },
    )


def apply_aog_recovery_command(
    world: AirlineWorld,
    command: SimulationCommand,
) -> SimulationEvent:
    option, obs, reason = _validated_aog_option(world, command)
    if reason is not None or option is None or obs is None:
        return _aog_reject(world, command, reason or "AOG recovery command is invalid")
    return _accept_aog(world, command, option, obs)
