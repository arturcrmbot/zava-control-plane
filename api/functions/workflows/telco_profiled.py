from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
from typing import Any

import azure.durable_functions as df

from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES


def telco_profile_orchestration(
    context: df.DurableOrchestrationContext,
    engine_code: str,
) -> Generator[Any, Any, dict]:
    input_dict = context.get_input() or {}
    workflow_type = str(input_dict["type"])
    profile = STANDARD_PROCESS_PROFILES[workflow_type]
    if profile.engine != engine_code:
        raise ValueError(
            f"{workflow_type} uses {profile.engine}, not {engine_code}"
        )
    workflow_id = input_dict.get("workflow_id", "?")
    instance_id = context.instance_id

    def checkpoint(kind: str, payload: dict[str, Any]) -> Any:
        return context.call_activity(
            "checkpoint_activity_trigger",
            {
                "workflow_id": workflow_id,
                "instance_id": instance_id,
                "kind": kind,
                "payload": {**payload, "workflow_type": workflow_type},
            },
        )

    yield checkpoint("workflow.started", {})
    skill_outputs: dict[str, dict[str, Any]] = {}
    approval: dict[str, Any] = {"decision": "not_required"}

    for phase in profile.phases:
        if phase.kind == "hitl":
            yield checkpoint(
                "suspended",
                {
                    "reason": "awaiting_approval",
                    "phase": phase.name,
                    "wait_kind": "operator_review",
                    "persona": profile.hitl_persona,
                    "external_event": profile.hitl_event,
                    "context": {
                        "action": profile.hitl_event,
                        "request": {
                            "amount": 0.0,
                            "category": profile.workflow_type,
                        },
                    },
                },
            )
            decision_event = context.wait_for_external_event(
                str(profile.hitl_event)
            )
            timer = context.create_timer(
                context.current_utc_datetime + timedelta(minutes=5)
            )
            winner = yield context.task_any([decision_event, timer])
            if winner == timer:
                return {
                    "status": "timeout",
                    "command": None,
                    "reasoning": f"{phase.name} timed out",
                }
            timer.cancel()
            approval = decision_event.result or {}
            yield checkpoint("resumed", {"phase": phase.name})
            if approval.get("decision") != "approve":
                return {
                    "status": "denied",
                    "command": None,
                    "reasoning": f"{phase.name} denied",
                }
            continue

        yield checkpoint("step.started", {"step": phase.name})
        if phase.kind == "agent":
            result = yield context.call_activity(
                "telco_profile_skill_activity_trigger",
                {
                    **input_dict,
                    "instance_id": instance_id,
                    "skill": phase.skill,
                    "phase": phase.name,
                    "prior_outputs": skill_outputs,
                },
            )
            skill_outputs[str(phase.skill)] = result
        yield checkpoint("step.completed", {"step": phase.name})

    decision = yield context.call_activity(
        "telco_profile_command_activity_trigger",
        {
            **input_dict,
            "instance_id": instance_id,
            "skill_outputs": skill_outputs,
            "approval": approval,
        },
    )
    return {
        "status": "decision_ready",
        "command": decision.get("command"),
        "reasoning": decision.get("reasoning"),
        "observation": input_dict.get("observation"),
    }


def telco_detect_diagnose_act_orchestration(context):
    return telco_profile_orchestration(context, "DDA")


def telco_forecast_simulate_plan_orchestration(context):
    return telco_profile_orchestration(context, "FSP")


def telco_case_triage_resolve_orchestration(context):
    return telco_profile_orchestration(context, "CTR")


def telco_order_fulfil_verify_orchestration(context):
    return telco_profile_orchestration(context, "OFV")


def telco_risk_investigate_govern_orchestration(context):
    return telco_profile_orchestration(context, "RIG")


def telco_assist_recommend_act_orchestration(context):
    return telco_profile_orchestration(context, "ARA")
