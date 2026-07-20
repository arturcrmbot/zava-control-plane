from __future__ import annotations

from typing import Any

from api.server.world.model import SimulationCommand, SimulationEvent
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES


PROFILE_BY_COMMAND = {
    profile.command_type: profile
    for profile in FASHION_PROCESS_PROFILES.values()
    if profile.workflow_type != "inventory-rebalancing"
}


def validate_reference_command(
    scenario: Any,
    command: SimulationCommand,
) -> str | None:
    profile = PROFILE_BY_COMMAND[command.type]
    case = scenario.process_cases.get(command.payload.get("case_id"))
    if case is None:
        return f"unknown process case: {command.payload.get('case_id')!r}"
    if case.workflow_type != profile.workflow_type:
        return f"case {case.id} does not belong to {profile.workflow_type}"
    if case.status != "open":
        return f"case {case.id} is not open"
    if command.payload.get("workflow_id") is None:
        return "workflow_id is required"
    if command.payload.get("action") not in case.allowed_actions:
        return f"action {command.payload.get('action')!r} is not declared"
    if tuple(command.payload.get("subject_ids") or ()) != case.subject_ids:
        return "command subject_ids do not match case subjects"
    outputs = command.payload.get("skill_outputs")
    if not isinstance(outputs, dict) or not set(profile.skills) <= set(outputs):
        return "command is missing declared skill outputs"
    if command.payload.get("approval_decision") != "approve":
        return f"{profile.hitl_event} approval is required"
    return None


def apply_reference_command(
    scenario: Any,
    command: SimulationCommand,
) -> SimulationEvent:
    profile = PROFILE_BY_COMMAND[command.type]
    case = scenario.process_cases[command.payload["case_id"]]
    accepted = scenario._record_command_accepted(command, target_id=case.id)
    action = str(command.payload["action"])
    case.status = "completed"
    case.outcome = {
        "action": action,
        "command_type": profile.command_type,
        "mutation_family": profile.mutation_family,
        "subject_ids": list(case.subject_ids),
        "source_mode": "simulated",
        "evaluation": {"status": "pass"},
    }
    scenario.workflow_state[profile.workflow_type] = {
        "status": "completed",
        "action": action,
        "case_id": case.id,
    }
    scenario.runtime.emit(
        profile.success_event,
        actor_id=case.id,
        target_id=case.subject_ids[0] if case.subject_ids else None,
        cause_event_id=accepted.event_id,
        trace_id=command.trace_id,
        payload={
            "case": scenario.process_case_view(case),
            "command_id": command.command_id,
            "mutation_family": profile.mutation_family,
        },
    )
    scenario.runtime.emit(
        "evaluation.completed",
        actor_id=case.id,
        cause_event_id=accepted.event_id,
        trace_id=command.trace_id,
        payload={
            "workflow_type": profile.workflow_type,
            "status": "pass",
        },
    )
    return accepted

