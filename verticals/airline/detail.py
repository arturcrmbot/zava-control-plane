from __future__ import annotations

import dataclasses
from typing import Any, Mapping

from api.shared.types import Workflow
from verticals.airline.process_profiles import (
    COMMAND_TYPE,
    HITL_PERSONA,
    SCENARIO_ID,
    STORY_ID,
    WORKFLOW_TYPE,
)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _observation(
    payload: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> Mapping[str, Any]:
    direct = payload.get("observation")
    if isinstance(direct, Mapping):
        return direct
    workflow_evidence = _mapping(evidence.get("workflow_evidence"))
    nested = workflow_evidence.get("observation")
    return nested if isinstance(nested, Mapping) else {}


def _context(
    payload: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> Mapping[str, Any]:
    terminal = evidence.get("hitl_context")
    if isinstance(terminal, Mapping):
        return terminal
    pending = payload.get("hitl_context")
    return pending if isinstance(pending, Mapping) else {}


def _baseline(observation: Mapping[str, Any]) -> dict[str, Any]:
    sector = _mapping(observation.get("sector"))
    outbound = _mapping(observation.get("outbound_sector"))
    crew = _mapping(observation.get("outbound_crew_duty"))
    slot = _mapping(observation.get("outbound_slot"))
    stand = _mapping(observation.get("stand"))
    cohorts = [
        cohort for cohort in observation.get("connection_cohorts") or [] if isinstance(cohort, Mapping)
    ]
    no_action = _mapping(observation.get("no_action_baseline"))
    return {
        "inbound_sector_id": sector.get("id"),
        "inbound_delay_minutes": sector.get("delay_minutes"),
        "outbound_sector_id": outbound.get("id"),
        "outbound_aircraft_id": outbound.get("aircraft_id"),
        "outbound_crew_duty_id": outbound.get("crew_duty_id"),
        "remaining_crew_duty_minutes": crew.get("remaining_duty_minutes"),
        "outbound_slot_id": slot.get("id"),
        "constrained_stand_id": stand.get("id"),
        "constrained_stand_status": stand.get("status"),
        "connection_cohort_ids": [cohort.get("id") for cohort in cohorts],
        "no_action": dict(no_action),
    }


def _reasoning(
    evidence: Mapping[str, Any],
) -> Mapping[str, Any]:
    value = evidence.get("reasoning")
    return value if isinstance(value, Mapping) else {}


def _admission(
    evidence: Mapping[str, Any],
    context: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    admission = _mapping(_reasoning(evidence).get("admission"))
    admitted = admission.get("admitted_options")
    rejected = admission.get("rejected_options")
    if not isinstance(admitted, list):
        admitted = context.get("admitted_options")
    if not isinstance(rejected, list):
        rejected = context.get("rejected_options")
    return (
        [dict(item) for item in admitted or [] if isinstance(item, Mapping)],
        [dict(item) for item in rejected or [] if isinstance(item, Mapping)],
    )


def _chosen_option(
    evidence: Mapping[str, Any],
    context: Mapping[str, Any],
    admitted: list[dict[str, Any]],
) -> dict[str, Any] | None:
    selected = context.get("selected_option")
    if isinstance(selected, Mapping):
        result = dict(selected)
        result.setdefault("admitted", True)
        return result
    approval = _mapping(evidence.get("approval"))
    option_id = context.get("selected_option_id") or approval.get("selected_option_id")
    return next(
        (option for option in admitted if option.get("option_id") == option_id),
        None,
    )


def _governance(
    workflow: Workflow,
    evidence: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    approval = _mapping(evidence.get("approval"))
    authority = _mapping(_reasoning(evidence).get("authority") or context.get("authority"))
    is_pending = workflow.status == "awaiting_hitl"
    return {
        "status": "pending"
        if is_pending
        else approval.get(
            "decision",
            "unknown",
        ),
        "persona": (approval.get("persona") or context.get("persona") or HITL_PERSONA),
        "decision_id": (approval.get("decision_id") or context.get("decision_id")),
        "rationale": approval.get("rationale"),
        "authority": dict(authority),
        "governing_rule_id": authority.get("governing_rule_id"),
    }


def _world(workflow: Workflow, app_state: Any) -> Any | None:
    service = getattr(app_state, "world_service", None)
    scenario = getattr(service, "scenario", None)
    if scenario is None:
        return None
    evaluations = getattr(scenario, "recovery_evaluations", {})
    evaluation = evaluations.get(workflow.id)
    return scenario if evaluation is not None else None


def _mutations(
    workflow: Workflow,
    evidence: Mapping[str, Any],
    app_state: Any,
) -> dict[str, Any] | None:
    command = evidence.get("command")
    if not isinstance(command, Mapping):
        return None
    command_payload = _mapping(command.get("payload"))
    gateway = _mapping(evidence.get("gateway_event"))
    world = _world(workflow, app_state)
    business_event = None
    if world is not None:
        business_event = next(
            (
                event
                for event in reversed(world.runtime.journal)
                if event.type == "airline.recovery.applied"
                and event.payload.get("workflow_id") == workflow.id
            ),
            None,
        )
    business_payload = business_event.payload if business_event is not None else {}
    return {
        "command_id": command.get("command_id"),
        "command_type": command.get("type"),
        "workflow_id": command_payload.get("workflow_id"),
        "decision_id": command_payload.get("decision_id"),
        "option_id": command_payload.get("option_id"),
        "actions": list(command_payload.get("actions") or []),
        "affected_actor_ids": list(business_payload.get("affected_actor_ids") or []),
        "business_event_id": gateway.get("payload", {}).get("business_event_id")
        if isinstance(gateway.get("payload"), Mapping)
        else None,
        "gateway_event_type": gateway.get("type"),
    }


def _evaluation(
    workflow: Workflow,
    evidence: Mapping[str, Any],
    app_state: Any,
) -> dict[str, Any] | None:
    world = _world(workflow, app_state)
    if world is None:
        return None
    record = world.recovery_evaluations.get(workflow.id)
    if record is None:
        return None
    result = dataclasses.asdict(record)
    result["invariant_results"] = list(record.invariant_results)
    return result


def _timeline(
    observation: Mapping[str, Any],
    evidence: Mapping[str, Any],
    governance: Mapping[str, Any],
    evaluation: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    reasoning = _reasoning(evidence)
    return [
        {
            "phase": "Detect Hub Disruption",
            "kind": "deterministic",
            "status": "completed" if observation else "pending",
            "evidence": {
                "source_event_id": observation.get("source_event_id"),
                "sensor_event_id": observation.get("sensor_event_id"),
            },
        },
        {
            "phase": "Assess Network Impact",
            "kind": "agent",
            "status": ("completed" if isinstance(reasoning.get("impact"), Mapping) else "pending"),
            "evidence": reasoning.get("impact"),
        },
        {
            "phase": "Synthesize Recovery Options",
            "kind": "agent",
            "status": ("completed" if isinstance(reasoning.get("ranking"), Mapping) else "pending"),
            "evidence": reasoning.get("ranking"),
        },
        {
            "phase": "Approve Recovery Plan",
            "kind": "hitl",
            "status": governance.get("status"),
            "evidence": dict(governance),
        },
        {
            "phase": "Commit Recovery Actions",
            "kind": "deterministic",
            "status": ("completed" if isinstance(evidence.get("command"), Mapping) else "pending"),
            "evidence": evidence.get("command"),
        },
        {
            "phase": "Verify Recovery Outcome",
            "kind": "deterministic",
            "status": (evaluation.get("status") if evaluation is not None else "pending"),
            "evidence": evaluation,
        },
    ]


def workflow_detail(
    workflow: Workflow,
    app_state: Any,
) -> Mapping[str, Any] | None:
    if workflow.type != WORKFLOW_TYPE:
        return None
    payload = workflow.payload if isinstance(workflow.payload, dict) else {}
    evidence = _mapping(payload.get("evidence"))
    observation = _observation(payload, evidence)
    context = _context(payload, evidence)
    if not observation:
        return None
    admitted, rejected = _admission(evidence, context)
    chosen = _chosen_option(evidence, context, admitted)
    governance = _governance(workflow, evidence, context)
    evaluation = _evaluation(workflow, evidence, app_state)
    workflow_evidence = _mapping(evidence.get("workflow_evidence"))
    story = {
        "story_id": observation.get("story_id", STORY_ID),
        "scenario_id": observation.get("scenario_id", SCENARIO_ID),
        "source_mode": workflow_evidence.get(
            "source_mode",
            "simulated",
        ),
        "source_event_id": observation.get("source_event_id"),
        "sensor_event_id": observation.get("sensor_event_id"),
    }
    return {
        "workflow_id": workflow.id,
        "story": story,
        "baseline": _baseline(observation),
        "chosen_admitted_option": chosen,
        "rejected_options": rejected,
        "governance": governance,
        "mutations": _mutations(workflow, evidence, app_state),
        "evaluation": evaluation,
        "timeline": _timeline(
            observation,
            evidence,
            governance,
            evaluation,
        ),
        "tools": [
            "airline_read_disruption_evidence",
            "airline_rank_feasible_recovery_options",
        ],
        "command_contract": COMMAND_TYPE,
    }
