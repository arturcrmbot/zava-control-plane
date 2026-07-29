from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from api.server.world.model import SimulationCommand, SimulationEvent
from verticals.airline.authority import AIRLINE_AUTHORITY
from verticals.airline.constraints import (
    FeasibilityResult,
    RecoveryOption,
    admit_recovery_options,
)
from verticals.airline.process_profiles import (
    COMMAND_TYPE,
    HITL_PERSONA,
    SCENARIO_ID,
    STORY_ID,
    SUCCESS_EVENT,
)
from verticals.airline.worlds.model import RecoveryCommand, RecoveryEvaluation

if TYPE_CHECKING:
    from verticals.airline.worlds.scenario import AirlineWorld

_ISSUER = "operations-control"
_DISRUPTION_ID = "SYN-DISRUPTION-HUB-001"
_TARGET_SECTOR_ID = "SYN-SECTOR-OUT-001"
_TAIL_OPTION_ID = "SYN-OPTION-TAIL-CREW-STAND"
_CANCEL_OPTION_ID = "SYN-OPTION-CANCEL"
_KNOWN_OPTION_IDS = {
    _TAIL_OPTION_ID,
    _CANCEL_OPTION_ID,
    "SYN-OPTION-RETIME-ONLY",
}


def recovery_command_id(
    *,
    workflow_id: str,
    decision_id: str,
    option_id: str,
) -> str:
    return f"SYN-CMD-{workflow_id}-{decision_id}-{option_id}"


def _result_for(
    observation: dict[str, Any],
    option_id: str,
) -> FeasibilityResult | None:
    return next(
        (result for result in admit_recovery_options(observation) if result.option.option_id == option_id),
        None,
    )


def command_for_option(
    world: AirlineWorld,
    *,
    option_id: str,
    workflow_id: str,
    decision_id: str,
    persona: str,
) -> SimulationCommand:
    observation = world.current_recovery_observation()
    result = _result_for(observation, option_id)
    if result is None:
        raise ValueError(f"unknown recovery option: {option_id!r}")
    if not result.feasible:
        reasons = ", ".join(result.reasons)
        raise ValueError(f"recovery option {option_id!r} is not admitted: {reasons}")
    option = result.option
    return SimulationCommand(
        command_id=recovery_command_id(
            workflow_id=workflow_id,
            decision_id=decision_id,
            option_id=option_id,
        ),
        trace_id=str(observation["trace_id"]),
        issued_by=_ISSUER,
        type=COMMAND_TYPE,
        payload={
            "workflow_id": workflow_id,
            "objective_id": f"SYN-OBJECTIVE-{workflow_id}",
            "decision_id": decision_id,
            "disruption_id": _DISRUPTION_ID,
            "scenario_id": SCENARIO_ID,
            "story_id": STORY_ID,
            "persona": persona,
            "option_id": option.option_id,
            "action_category": "integrated_hub_recovery",
            "actions": [action.to_dict() for action in option.actions],
            "evidence_versions": dict(option.evidence_versions),
            "value_gbp": option.value_gbp,
            "expected_event_type": SUCCESS_EVENT,
            "expected_evaluation_type": "airline.recovery.evaluation",
        },
    )


def reject(
    world: AirlineWorld,
    command: SimulationCommand,
    reason: str,
) -> SimulationEvent:
    source = world._scenario_events.get(SCENARIO_ID)
    return world.runtime.emit(
        "command.rejected",
        actor_id=command.issued_by,
        target_id=_TARGET_SECTOR_ID,
        cause_event_id=source.event_id if source is not None else None,
        trace_id=command.trace_id,
        payload={"command": command.to_dict(), "reason": reason},
    )


def _validated_option(
    world: AirlineWorld,
    command: SimulationCommand,
) -> tuple[RecoveryOption | None, dict[str, Any] | None, str | None]:
    if command.type != COMMAND_TYPE:
        return None, None, f"unsupported command type {command.type!r}"
    payload = command.payload
    option_id = payload.get("option_id")
    if option_id not in _KNOWN_OPTION_IDS:
        return None, None, f"unknown or non-admitted recovery option {option_id!r}"
    if world.disruption_status.get(STORY_ID) != "active":
        return None, None, f"disruption {STORY_ID!r} is not active"

    observation = world.current_recovery_observation()
    result = _result_for(observation, str(option_id))
    if result is None:
        return None, observation, f"unknown recovery option {option_id!r}"
    if not result.feasible:
        return (
            None,
            observation,
            f"option {option_id!r} is not admitted: {', '.join(result.reasons)}",
        )
    option = result.option

    workflow_id = payload.get("workflow_id")
    decision_id = payload.get("decision_id")
    if not isinstance(workflow_id, str) or not workflow_id.startswith("AIRHUB-"):
        return None, observation, "workflow_id is not a canonical AIRHUB id"
    if not isinstance(decision_id, str) or not decision_id.startswith("SYN-DECISION-"):
        return None, observation, "decision_id is not a canonical synthetic id"
    if payload.get("objective_id") != f"SYN-OBJECTIVE-{workflow_id}":
        return None, observation, "objective identity does not match workflow"
    if (
        payload.get("disruption_id") != _DISRUPTION_ID
        or payload.get("scenario_id") != SCENARIO_ID
        or payload.get("story_id") != STORY_ID
    ):
        return None, observation, "scenario or disruption identity is invalid"
    if command.trace_id != observation.get("trace_id"):
        return None, observation, "command trace does not match source sensor trace"
    if command.issued_by != _ISSUER:
        return None, observation, f"issuer {command.issued_by!r} is not authorised"

    persona = payload.get("persona")
    if persona != HITL_PERSONA:
        return None, observation, f"persona {persona!r} cannot approve recovery"
    authority = AIRLINE_AUTHORITY.get(persona)
    if authority is None or COMMAND_TYPE not in authority.approval_actions:
        return None, observation, f"persona {persona!r} lacks action authority"

    value = payload.get("value_gbp")
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) != option.value_gbp
        or float(value) < 0
        or float(value) > authority.spend_limit_gbp
    ):
        return (
            None,
            observation,
            f"bounded value must equal GBP {option.value_gbp:,.2f} and not exceed "
            f"GBP {authority.spend_limit_gbp:,.2f}",
        )

    if payload.get("evidence_versions") != dict(option.evidence_versions):
        return None, observation, "evidence versions are stale or incomplete"
    expected_actions = [action.to_dict() for action in option.actions]
    if payload.get("actions") != expected_actions:
        return None, observation, "actions do not match the admitted option"
    if (
        payload.get("action_category") != "integrated_hub_recovery"
        or payload.get("expected_event_type") != SUCCESS_EVENT
        or payload.get("expected_evaluation_type") != "airline.recovery.evaluation"
    ):
        return None, observation, "command contract metadata is invalid"
    return option, observation, None


def _mutate_tail_plan(world: AirlineWorld) -> list[Any]:
    sector = world.sectors[_TARGET_SECTOR_ID]
    rotation = next(item for item in world.rotations.values() if sector.id in item.sector_ids)
    old_crew = world.crew_duties[sector.crew_duty_id]
    tail = world.aircraft["SYN-TAIL-005"]
    reserve_crew = world.crew_duties["SYN-DUTY-006"]
    stand = world.stands["SYN-STAND-05"]

    sector.aircraft_id = tail.id
    sector.crew_duty_id = reserve_crew.id
    sector.stand_id = stand.id
    rotation.aircraft_id = tail.id
    old_crew.sector_ids = tuple(sector_id for sector_id in old_crew.sector_ids if sector_id != sector.id)
    reserve_crew.sector_ids = (*reserve_crew.sector_ids, sector.id)
    reserve_crew.status = "active"
    tail.status = "assigned"
    stand.status = "assigned"
    return [sector, rotation, old_crew, reserve_crew, tail, stand]


def _mutate_cancel_plan(world: AirlineWorld) -> list[Any]:
    sector = world.sectors[_TARGET_SECTOR_ID]
    rotation = next(item for item in world.rotations.values() if sector.id in item.sector_ids)
    crew = world.crew_duties[sector.crew_duty_id]
    sector.status = "cancelled"
    rotation.status = "recovered"
    crew.sector_ids = tuple(sector_id for sector_id in crew.sector_ids if sector_id != sector.id)
    return [sector, rotation, crew]


def _evaluation_results(
    world: AirlineWorld,
    option: RecoveryOption,
) -> tuple[str, tuple[str, ...]]:
    sector = world.sectors[_TARGET_SECTOR_ID]
    if option.option_id == _TAIL_OPTION_ID:
        tail = world.aircraft["SYN-TAIL-005"]
        crew = world.crew_duties["SYN-DUTY-006"]
        stand = world.stands["SYN-STAND-05"]
        checks = (
            (
                "aircraft_assigned",
                sector.aircraft_id == tail.id
                and tail.status == "assigned"
                and sum(
                    item.aircraft_id == tail.id and item.status not in {"cancelled", "completed"}
                    for item in world.sectors.values()
                )
                == 1,
            ),
            (
                "crew_assigned",
                sector.crew_duty_id == crew.id
                and crew.status == "active"
                and crew.sector_ids == (sector.id,),
            ),
            (
                "stand_assigned",
                sector.stand_id == stand.id and stand.status == "assigned",
            ),
            (
                "slot_preserved",
                sector.slot_id == "SYN-SLOT-05" and world.slots[sector.slot_id].status == "allocated",
            ),
            (
                "disruption_resolved",
                world.disruption_status.get(STORY_ID) == "resolved",
            ),
        )
    elif option.option_id == _CANCEL_OPTION_ID:
        checks = (
            ("sector_cancelled", sector.status == "cancelled"),
            (
                "disruption_resolved",
                world.disruption_status.get(STORY_ID) == "resolved",
            ),
        )
    else:
        raise ValueError(f"recovery option {option.option_id!r} has no registered evaluator")
    results = tuple(f"{name}:{'pass' if passed else 'fail'}" for name, passed in checks)
    return ("pass" if all(passed for _, passed in checks) else "fail"), results


def _accept(
    world: AirlineWorld,
    command: SimulationCommand,
    option: RecoveryOption,
    observation: dict[str, Any],
) -> SimulationEvent:
    if option.option_id == _TAIL_OPTION_ID:
        mutated = _mutate_tail_plan(world)
    elif option.option_id == _CANCEL_OPTION_ID:
        mutated = _mutate_cancel_plan(world)
    else:
        return reject(
            world,
            command,
            f"recovery option {option.option_id!r} has no registered mutator/evaluator",
        )
    for record in mutated:
        record.version += 1
    world.disruption_status[STORY_ID] = "resolved"

    payload = command.payload
    workflow_id = str(payload["workflow_id"])
    recovery_command = RecoveryCommand(
        id=command.command_id,
        workflow_id=workflow_id,
        decision_id=str(payload["decision_id"]),
        option_id=option.option_id,
        persona=str(payload["persona"]),
        value_gbp=option.value_gbp,
        action_types=tuple(action.action_type for action in option.actions),
        evidence_versions=option.evidence_versions,
    )
    evaluation_status, invariant_results = _evaluation_results(world, option)
    evaluation = RecoveryEvaluation(
        id=f"SYN-EVAL-{workflow_id}",
        workflow_id=workflow_id,
        command_id=command.command_id,
        option_id=option.option_id,
        status=evaluation_status,
        invariant_results=invariant_results,
    )
    business = world.runtime.emit(
        SUCCESS_EVENT,
        actor_id=command.issued_by,
        target_id=_TARGET_SECTOR_ID,
        cause_event_id=str(observation["sensor_event_id"]),
        trace_id=command.trace_id,
        payload={
            "command_id": command.command_id,
            "workflow_id": workflow_id,
            "decision_id": payload["decision_id"],
            "option_id": option.option_id,
            "actions": [action.to_dict() for action in option.actions],
            "affected_actor_ids": [record.id for record in mutated],
            "evidence_event_ids": observation["evidence_event_ids"],
            "measurements": {
                "evaluation_status": evaluation.status,
                "disruption_status": "resolved",
                "value_gbp": option.value_gbp,
            },
        },
    )
    for record in mutated:
        record.last_event_id = business.event_id
    recovery_command.last_event_id = business.event_id
    evaluation.last_event_id = business.event_id
    world.recovery_commands[recovery_command.id] = recovery_command
    world.recovery_evaluations[workflow_id] = evaluation
    return world.runtime.emit(
        "command.accepted",
        actor_id=command.issued_by,
        target_id=_TARGET_SECTOR_ID,
        cause_event_id=business.event_id,
        trace_id=command.trace_id,
        payload={
            "command": command.to_dict(),
            "business_event_id": business.event_id,
            "evaluation_id": evaluation.id,
        },
    )


def apply_recovery_command(
    world: AirlineWorld,
    command: SimulationCommand,
) -> SimulationEvent:
    option, observation, reason = _validated_option(world, command)
    if reason is not None or option is None or observation is None:
        return reject(world, command, reason or "recovery command is invalid")
    return _accept(world, command, option, observation)
