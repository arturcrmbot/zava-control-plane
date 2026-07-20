from __future__ import annotations

import hashlib
from collections.abc import Generator
from datetime import timedelta
from typing import Any

import azure.durable_functions as df

from api.functions.kernel_registration import create_app
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES


def _case(payload: dict[str, Any]) -> dict[str, Any]:
    observation = payload.get("observation")
    if not isinstance(observation, dict):
        raise ValueError("observation must be an object")
    case = observation.get("case")
    if not isinstance(case, dict):
        raise ValueError("observation.case must be an object")
    return case


def fashion_skill_activity(payload: dict[str, Any]) -> dict[str, Any]:
    profile = FASHION_PROCESS_PROFILES[str(payload["type"])]
    skill = str(payload.get("skill") or "")
    if skill not in profile.skills:
        raise ValueError(
            f"{skill!r} is not declared for {profile.workflow_type}"
        )
    case = _case(payload)
    facts = case.get("facts") if isinstance(case.get("facts"), dict) else {}
    digest = hashlib.sha256(
        repr(sorted(facts.items())).encode("utf-8")
    ).hexdigest()
    return {
        "skill": skill,
        "recommendation": case.get("recommended_action"),
        "evidence_digest": digest,
        "subject_ids": list(case.get("subject_ids") or ()),
        "reasoning": (
            f"{skill} evaluated only the supplied deterministic Fashion "
            "case evidence."
        ),
    }


def fashion_command_activity(payload: dict[str, Any]) -> dict[str, Any]:
    profile = FASHION_PROCESS_PROFILES[str(payload["type"])]
    _case(payload)
    observation = payload["observation"]
    command_payload = observation.get("command_payload")
    if not isinstance(command_payload, dict):
        raise ValueError("observation.command_payload must be an object")
    if profile.command_type not in observation.get("allowed_commands", ()):
        raise ValueError(
            f"command {profile.command_type!r} is not allowed by observation"
        )
    requires_approval = bool(payload.get("requires_approval"))
    approval = payload.get("approval") or {"decision": "not_required"}
    if requires_approval and approval.get("decision") != "approve":
        raise ValueError(f"{profile.hitl_event} approval is required")
    if requires_approval and not approval.get("approval_reference"):
        raise ValueError("approval_reference is required")
    merged_payload = {
        **command_payload,
        "workflow_id": str(payload["workflow_id"]),
        "skill_outputs": dict(payload.get("skill_outputs") or {}),
        "approval_decision": (
            approval.get("decision", "not_required")
            if requires_approval
            else "approve"
        ),
    }
    if profile.workflow_type == "inventory-rebalancing":
        merged_payload.update(
            {
                "policy_decision": (
                    "approval_required"
                    if requires_approval
                    else "auto_approved"
                ),
                "approval_reference": approval.get("approval_reference"),
            }
        )
    trace_id = str(payload["trace_id"])
    return {
        "command": {
            "command_id": f"cmd-{trace_id}-{profile.command_type}",
            "trace_id": trace_id,
            "issued_by": profile.function.replace("-", "_"),
            "type": profile.command_type,
            "payload": merged_payload,
        },
        "reasoning": f"Prepared {profile.display_name} typed command.",
    }


def fashion_orchestration(
    context: df.DurableOrchestrationContext,
    expected_workflow_type: str,
) -> Generator[Any, Any, dict[str, Any]]:
    input_dict = context.get_input() or {}
    workflow_type = str(input_dict["type"])
    if workflow_type != expected_workflow_type:
        raise ValueError(
            f"expected {expected_workflow_type}, got {workflow_type}"
        )
    profile = FASHION_PROCESS_PROFILES[workflow_type]
    workflow_id = str(input_dict.get("workflow_id") or "?")
    instance_id = context.instance_id
    requires_approval = bool(input_dict.get("requires_approval"))

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
    skill_iterator = iter(profile.skills)

    for phase in profile.phases:
        if phase.kind == "hitl":
            if not requires_approval:
                yield checkpoint(
                    "step.completed",
                    {"step": phase.name, "status": "not_required"},
                )
                continue
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
                profile.hitl_event
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
            skill = next(skill_iterator)
            result = yield context.call_activity(
                "fashion_skill_activity_trigger",
                {
                    **input_dict,
                    "instance_id": instance_id,
                    "skill": skill,
                    "prior_outputs": skill_outputs,
                },
            )
            skill_outputs[skill] = result
        yield checkpoint("step.completed", {"step": phase.name})

    decision = yield context.call_activity(
        "fashion_command_activity_trigger",
        {
            **input_dict,
            "instance_id": instance_id,
            "skill_outputs": skill_outputs,
            "approval": approval,
        },
    )
    return {
        "status": "decision_ready",
        "command": decision["command"],
        "reasoning": decision["reasoning"],
        "observation": input_dict.get("observation"),
    }


app = create_app()


@app.orchestration_trigger(context_name="context")
def InventoryRebalancingOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return fashion_orchestration(context, "inventory-rebalancing")


@app.orchestration_trigger(context_name="context")
def DemandSpikeResponseOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return fashion_orchestration(context, "demand-spike-response")


@app.orchestration_trigger(context_name="context")
def PromotionReadinessOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return fashion_orchestration(context, "promotion-readiness")


@app.orchestration_trigger(context_name="context")
def MarkdownGovernanceOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return fashion_orchestration(context, "markdown-governance")


@app.orchestration_trigger(context_name="context")
def SupplierDelayRecoveryOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return fashion_orchestration(context, "supplier-delay-recovery")


@app.orchestration_trigger(context_name="context")
def FulfilmentExceptionResolutionOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return fashion_orchestration(
        context,
        "fulfilment-exception-resolution",
    )


@app.orchestration_trigger(context_name="context")
def MarketplaceSellerExceptionOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return fashion_orchestration(context, "marketplace-seller-exception")


@app.orchestration_trigger(context_name="context")
def ReturnsDispositionOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return fashion_orchestration(context, "returns-disposition")


@app.activity_trigger(input_name="payload")
def fashion_skill_activity_trigger(payload: dict) -> dict:
    return fashion_skill_activity(payload)


@app.activity_trigger(input_name="payload")
def fashion_command_activity_trigger(
    payload: dict,
) -> dict:
    return fashion_command_activity(payload)
