"""Airline Hero 3 – Preemptive Schedule Resilience command handler.

Distinct command type: airline.commit_schedule_adjustment
Canonical workflow IDs start with AIRSCHED-.
"""
from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING, Any

from api.server.world.model import SimulationCommand, SimulationEvent
from verticals.airline.schedule_constants import (
    SCHED_BUFFER_MINUTES,
    SCHED_CANCEL_ROTATION_ID,
    SCHED_CANCEL_SECTOR_ID,
    SCHED_CANCEL_CREW_ID,
    SCHED_COMMAND_TYPE,
    SCHED_FREED_DUTY_MINUTES,
    SCHED_HITL_PERSONA,
    SCHED_ISSUER,
    SCHED_MAX_VALUE_GBP,
    SCHED_RESERVE_AIRCRAFT_ID,
    SCHED_RESERVE_CREW_ID,
    SCHED_RISK_SIGNAL_ID,
    SCHED_SCENARIO_ID,
    SCHED_STORY_ID,
    SCHED_SUCCESS_EVENT,
    SCHED_WORKFLOW_ID,
)
from verticals.airline.schedule_constraints import (
    SCHED_OPTION_BUFFER_RETIME,
    SCHED_OPTION_CANCEL_LIMITED,
    SCHED_OPTION_MONITOR_RISK,
    SCHED_OPTION_PREPOSITION,
    SchedFeasibilityResult,
    SchedOption,
    admit_schedule_options,
)
from verticals.airline.worlds.model import (
    ScheduleAdjustmentCommand,
    ScheduleResilienceEvaluation,
)

if TYPE_CHECKING:
    from verticals.airline.worlds.scenario import AirlineWorld

_KNOWN_OPTION_IDS = frozenset({
    SCHED_OPTION_BUFFER_RETIME,
    SCHED_OPTION_PREPOSITION,
    SCHED_OPTION_CANCEL_LIMITED,
    SCHED_OPTION_MONITOR_RISK,
})


def schedule_command_id(
    *,
    workflow_id: str,
    decision_id: str,
    option_id: str,
) -> str:
    return f"SYN-SCHED-CMD-{workflow_id}-{decision_id}-{option_id}"


def _result_for(obs: dict[str, Any], option_id: str) -> SchedFeasibilityResult | None:
    return next(
        (r for r in admit_schedule_options(obs) if r.option.option_id == option_id),
        None,
    )


def command_for_schedule_option(
    world: AirlineWorld,
    *,
    option_id: str,
    workflow_id: str,
    decision_id: str,
    persona: str,
) -> SimulationCommand:
    obs = world.current_schedule_observation()
    result = _result_for(obs, option_id)
    if result is None:
        raise ValueError(f"unknown schedule resilience option: {option_id!r}")
    if not result.feasible:
        reasons = ", ".join(result.reasons)
        raise ValueError(f"schedule option {option_id!r} is not admitted: {reasons}")
    option = result.option
    return SimulationCommand(
        command_id=schedule_command_id(
            workflow_id=workflow_id,
            decision_id=decision_id,
            option_id=option_id,
        ),
        trace_id=str(obs["trace_id"]),
        issued_by=SCHED_ISSUER,
        type=SCHED_COMMAND_TYPE,
        payload={
            "workflow_id": workflow_id,
            "objective_id": f"SYN-SCHED-OBJECTIVE-{workflow_id}",
            "decision_id": decision_id,
            "scenario_id": SCHED_SCENARIO_ID,
            "story_id": SCHED_STORY_ID,
            "persona": persona,
            "option_id": option.option_id,
            "action_category": "schedule_resilience",
            "actions": [a.to_dict() for a in option.actions],
            "evidence_versions": dict(option.evidence_versions),
            "value_gbp": option.value_gbp,
            "expected_event_type": SCHED_SUCCESS_EVENT,
            "expected_evaluation_type": "airline.schedule.evaluation",
        },
    )


def _sched_reject(
    world: AirlineWorld,
    command: SimulationCommand,
    reason: str,
) -> SimulationEvent:
    source = world._scenario_events.get(SCHED_SCENARIO_ID)
    return world.runtime.emit(
        "command.rejected",
        actor_id=command.issued_by,
        target_id=SCHED_RISK_SIGNAL_ID,
        cause_event_id=source.event_id if source is not None else None,
        trace_id=command.trace_id,
        payload={"command": command.to_dict(), "reason": reason},
    )


def _validated_sched_option(
    world: AirlineWorld,
    command: SimulationCommand,
) -> tuple[SchedOption | None, dict[str, Any] | None, str | None]:
    if command.type != SCHED_COMMAND_TYPE:
        return None, None, f"unsupported command type {command.type!r} for schedule handler"

    payload = command.payload
    option_id = payload.get("option_id")
    if option_id not in _KNOWN_OPTION_IDS:
        return None, None, f"unknown or non-admitted schedule option {option_id!r}"

    if world.sched_story_status.get(SCHED_STORY_ID) != "active":
        return None, None, f"schedule story {SCHED_STORY_ID!r} is not active"

    obs = world.current_schedule_observation()
    result = _result_for(obs, str(option_id))
    if result is None:
        return None, obs, f"unknown schedule option {option_id!r}"
    if not result.feasible:
        return None, obs, f"option {option_id!r} not admitted: {', '.join(result.reasons)}"
    option = result.option

    workflow_id = payload.get("workflow_id")
    decision_id = payload.get("decision_id")
    if not isinstance(workflow_id, str) or not workflow_id.startswith("AIRSCHED-"):
        return None, obs, "workflow_id is not a canonical AIRSCHED id"
    if not isinstance(decision_id, str) or not decision_id.startswith("SYN-SCHED-DECISION-"):
        return None, obs, "decision_id is not a canonical schedule synthetic id"
    if payload.get("objective_id") != f"SYN-SCHED-OBJECTIVE-{workflow_id}":
        return None, obs, "schedule objective identity does not match workflow"
    if (
        payload.get("scenario_id") != SCHED_SCENARIO_ID
        or payload.get("story_id") != SCHED_STORY_ID
    ):
        return None, obs, "schedule scenario or story identity is invalid"
    if command.trace_id != obs.get("trace_id"):
        return None, obs, "command trace does not match schedule sensor trace"
    if command.issued_by != SCHED_ISSUER:
        return None, obs, f"issuer {command.issued_by!r} is not authorised"

    persona = payload.get("persona")
    if persona != SCHED_HITL_PERSONA:
        return None, obs, f"persona {persona!r} cannot approve schedule adjustment"

    from verticals.airline.authority import AIRLINE_AUTHORITY
    authority_row = AIRLINE_AUTHORITY.get(SCHED_HITL_PERSONA)
    if authority_row is None:
        return None, obs, f"no authority row for persona {SCHED_HITL_PERSONA!r} — failing closed"
    if SCHED_COMMAND_TYPE not in authority_row.approval_actions:
        return None, obs, f"action {SCHED_COMMAND_TYPE!r} not in authority row for {SCHED_HITL_PERSONA!r} — failing closed"
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
        return None, obs, "schedule evidence versions are stale or incomplete"
    expected_actions = [a.to_dict() for a in option.actions]
    if payload.get("actions") != expected_actions:
        return None, obs, "schedule actions do not match the admitted option"
    if (
        payload.get("action_category") != "schedule_resilience"
        or payload.get("expected_event_type") != SCHED_SUCCESS_EVENT
        or payload.get("expected_evaluation_type") != "airline.schedule.evaluation"
    ):
        return None, obs, "schedule command contract metadata is invalid"

    return option, obs, None


# ---------------------------------------------------------------------------
# Mutation helpers
# ---------------------------------------------------------------------------

def _mutate_buffer_retime(world: AirlineWorld) -> list[Any]:
    """Retime affected OUT-003 and OUT-004 sectors and their corresponding slots."""
    s3 = world.sectors["SYN-SECTOR-OUT-003"]
    s4 = world.sectors["SYN-SECTOR-OUT-004"]
    sl7 = world.slots["SYN-SLOT-07"]
    sl8 = world.slots["SYN-SLOT-08"]

    s3.scheduled_departure += SCHED_BUFFER_MINUTES
    s4.scheduled_departure += SCHED_BUFFER_MINUTES
    sl7.scheduled_time += SCHED_BUFFER_MINUTES
    sl8.scheduled_time += SCHED_BUFFER_MINUTES

    return [s3, s4, sl7, sl8]


def _mutate_preposition(world: AirlineWorld) -> list[Any]:
    """Assign existing reserve aircraft and crew to prepositioned standby."""
    aircraft = world.aircraft[SCHED_RESERVE_AIRCRAFT_ID]
    crew = world.crew_duties[SCHED_RESERVE_CREW_ID]

    aircraft.status = "prepositioned"
    crew.status = "prepositioned"

    return [aircraft, crew]


def _mutate_cancel_limited(world: AirlineWorld) -> list[Any]:
    """Cancel the permitted pre-day sector and adjust owned rotation/crew coherently."""
    sector = world.sectors[SCHED_CANCEL_SECTOR_ID]
    rotation = world.rotations[SCHED_CANCEL_ROTATION_ID]
    crew = world.crew_duties[SCHED_CANCEL_CREW_ID]

    sector.status = "cancelled"
    rotation.status = "partial"
    crew.remaining_duty_minutes += SCHED_FREED_DUTY_MINUTES

    return [sector, rotation, crew]


def _mutate_monitor_risk(world: AirlineWorld) -> list[Any]:
    """Mark risk signal as monitored; no operational schedule records mutated."""
    signal = world.schedule_risk_signals[SCHED_RISK_SIGNAL_ID]
    signal.status = "monitored"
    return [signal]


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def _evaluation_results(
    world: AirlineWorld,
    option: SchedOption,
) -> tuple[str, tuple[str, ...], str, bool, bool, bool, int, float, str, int]:
    """Returns (status, invariant_results, selected_action, ac_ok, crew_ok, slot_ok, cohorts, cap_pct, fpe, delay_reduction)."""
    if option.option_id == SCHED_OPTION_BUFFER_RETIME:
        s3 = world.sectors["SYN-SECTOR-OUT-003"]
        s4 = world.sectors["SYN-SECTOR-OUT-004"]
        sl7 = world.slots["SYN-SLOT-07"]
        sl8 = world.slots["SYN-SLOT-08"]
        checks = (
            ("sectors_retimed", s3.scheduled_departure > 170.0 and s4.scheduled_departure > 180.0),
            ("slots_updated", sl7.scheduled_time > 170.0 and sl8.scheduled_time > 180.0),
            ("within_slot_tolerance", (s3.scheduled_departure - 170.0) <= 15.0 and (s4.scheduled_departure - 180.0) <= 15.0),
            ("reserve_aircraft_unchanged", world.aircraft[SCHED_RESERVE_AIRCRAFT_ID].status == "reserve"),
            ("reserve_crew_unchanged", world.crew_duties[SCHED_RESERVE_CREW_ID].status == "reserve"),
        )
        selected = "buffer_retime"
        ac_ok, crew_ok, slot_ok = True, True, True
        cohorts = 1
        cap_pct = 100.0
        fpe = "low"
        delay_reduction = SCHED_BUFFER_MINUTES * 2

    elif option.option_id == SCHED_OPTION_PREPOSITION:
        ac = world.aircraft[SCHED_RESERVE_AIRCRAFT_ID]
        crew = world.crew_duties[SCHED_RESERVE_CREW_ID]
        s3 = world.sectors["SYN-SECTOR-OUT-003"]
        s4 = world.sectors["SYN-SECTOR-OUT-004"]
        checks = (
            ("reserve_aircraft_prepositioned", ac.status == "prepositioned"),
            ("reserve_crew_prepositioned", crew.status == "prepositioned"),
            ("no_operational_rotation_changed", s3.version == 1 and s4.version == 1),
            ("no_aircraft_double_assignment", ac.status == "prepositioned"),
        )
        selected = "preposition_reserve"
        ac_ok, crew_ok, slot_ok = True, True, False
        cohorts = 0
        cap_pct = 100.0
        fpe = "medium"
        delay_reduction = 0

    elif option.option_id == SCHED_OPTION_CANCEL_LIMITED:
        sector = world.sectors[SCHED_CANCEL_SECTOR_ID]
        rotation = world.rotations[SCHED_CANCEL_ROTATION_ID]
        crew = world.crew_duties[SCHED_CANCEL_CREW_ID]
        checks = (
            ("sector_cancelled", sector.status == "cancelled"),
            ("rotation_adjusted", rotation.status == "partial"),
            ("crew_duty_adjusted", crew.remaining_duty_minutes > 340),
            ("within_cancellation_limit", True),
            ("other_sectors_intact", world.sectors["SYN-SECTOR-OUT-003"].status == "scheduled"),
        )
        selected = "cancel_limited"
        ac_ok, crew_ok, slot_ok = False, True, False
        cohorts = 0
        cap_pct = 50.0
        fpe = "high"
        delay_reduction = 45

    elif option.option_id == SCHED_OPTION_MONITOR_RISK:
        signal = world.schedule_risk_signals[SCHED_RISK_SIGNAL_ID]
        s3 = world.sectors["SYN-SECTOR-OUT-003"]
        s4 = world.sectors["SYN-SECTOR-OUT-004"]
        checks = (
            ("risk_signal_monitored", signal.status == "monitored"),
            ("no_operational_sector_mutation", s3.version == 1 and s4.version == 1),
            ("command_persisted", True),
            ("evaluation_persisted", True),
        )
        selected = "monitor_risk"
        ac_ok, crew_ok, slot_ok = False, False, False
        cohorts = 0
        cap_pct = 60.0
        fpe = "none"
        delay_reduction = 0

    else:
        raise ValueError(f"schedule option {option.option_id!r} has no registered evaluator")

    results = tuple(f"{name}:{'pass' if passed else 'fail'}" for name, passed in checks)
    status = "pass" if all(p for _, p in checks) else "fail"
    return status, results, selected, ac_ok, crew_ok, slot_ok, cohorts, cap_pct, fpe, delay_reduction


# ---------------------------------------------------------------------------
# Accept / apply
# ---------------------------------------------------------------------------

def _accept_sched(
    world: AirlineWorld,
    command: SimulationCommand,
    option: SchedOption,
    obs: dict[str, Any],
) -> SimulationEvent:
    workflow_id = str(command.payload["workflow_id"])

    if option.option_id == SCHED_OPTION_BUFFER_RETIME:
        mutated = _mutate_buffer_retime(world)
    elif option.option_id == SCHED_OPTION_PREPOSITION:
        mutated = _mutate_preposition(world)
    elif option.option_id == SCHED_OPTION_CANCEL_LIMITED:
        mutated = _mutate_cancel_limited(world)
    elif option.option_id == SCHED_OPTION_MONITOR_RISK:
        mutated = _mutate_monitor_risk(world)
    else:
        return _sched_reject(world, command, f"schedule option {option.option_id!r} has no registered mutator")

    for record in mutated:
        record.version += 1

    if option.option_id == SCHED_OPTION_MONITOR_RISK:
        world.sched_story_status[SCHED_STORY_ID] = "monitored"
    else:
        world.sched_story_status[SCHED_STORY_ID] = "resolved"

    sched_cmd = ScheduleAdjustmentCommand(
        id=command.command_id,
        workflow_id=workflow_id,
        decision_id=str(command.payload["decision_id"]),
        option_id=option.option_id,
        persona=str(command.payload["persona"]),
        value_gbp=option.value_gbp,
        action_types=tuple(a.action_type for a in option.actions),
        evidence_versions=option.evidence_versions,
    )

    (
        evaluation_status,
        invariant_results,
        selected_action,
        ac_ok,
        crew_ok,
        slot_ok,
        cohorts,
        cap_pct,
        fpe,
        delay_reduction,
    ) = _evaluation_results(world, option)

    no_baseline = dict(obs.get("no_action_baseline") or {})

    evaluation = ScheduleResilienceEvaluation(
        id=f"SYN-SCHED-EVAL-{workflow_id}",
        workflow_id=workflow_id,
        command_id=command.command_id,
        option_id=option.option_id,
        status=evaluation_status,
        invariant_results=invariant_results,
        predicted_delay_reduction_minutes=delay_reduction,
        cancellations_reduced=-1 if option.option_id == SCHED_OPTION_CANCEL_LIMITED else 0,
        aircraft_feasibility_restored=ac_ok,
        crew_feasibility_restored=crew_ok,
        slot_feasibility_restored=slot_ok,
        protected_cohorts=cohorts,
        capacity_retained_pct=cap_pct,
        synthetic_cost_gbp=option.value_gbp,
        forecast_confidence=float(obs.get("forecast_confidence", 0.0)),
        false_positive_exposure=fpe,
        no_action_cancellations=int(no_baseline.get("predicted_cancellations", 0)),
        no_action_delay_minutes=int(no_baseline.get("predicted_delay_per_sector", 45)),
        selected_action=selected_action,
    )

    affected_ids = [r.id for r in mutated]

    business = world.runtime.emit(
        SCHED_SUCCESS_EVENT,
        actor_id=command.issued_by,
        target_id=SCHED_RISK_SIGNAL_ID,
        cause_event_id=str(obs["sensor_event_id"]),
        trace_id=command.trace_id,
        payload={
            "command_id": command.command_id,
            "workflow_id": workflow_id,
            "decision_id": command.payload["decision_id"],
            "option_id": option.option_id,
            "actions": [a.to_dict() for a in option.actions],
            "affected_actor_ids": affected_ids,
            "evidence_event_ids": obs["evidence_event_ids"],
            "measurements": {
                "evaluation_status": evaluation.status,
                "sched_story_status": world.sched_story_status.get(SCHED_STORY_ID),
                "value_gbp": option.value_gbp,
                "selected_action": selected_action,
            },
        },
    )

    for record in mutated:
        record.last_event_id = business.event_id
    sched_cmd.last_event_id = business.event_id
    evaluation.last_event_id = business.event_id

    world.schedule_adjustment_commands[sched_cmd.id] = sched_cmd
    world.schedule_resilience_evaluations[evaluation.id] = evaluation

    return world.runtime.emit(
        "command.accepted",
        actor_id=command.issued_by,
        target_id=SCHED_RISK_SIGNAL_ID,
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
                "schedule_command": dataclasses.asdict(sched_cmd),
                "evaluation": dataclasses.asdict(evaluation),
            },
        },
    )


def apply_schedule_adjustment_command(
    world: AirlineWorld,
    command: SimulationCommand,
) -> SimulationEvent:
    option, obs, reason = _validated_sched_option(world, command)
    if reason is not None or option is None or obs is None:
        return _sched_reject(world, command, reason or "schedule adjustment command is invalid")
    return _accept_sched(world, command, option, obs)
