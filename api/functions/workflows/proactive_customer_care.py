from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
from typing import Any

import azure.durable_functions as df


def proactive_customer_care_orchestration(
    context: df.DurableOrchestrationContext,
) -> Generator[Any, Any, dict]:
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    workflow_type = input_dict.get("type", "proactive-customer-care")
    instance_id = context.instance_id
    enriched = {**input_dict, "instance_id": instance_id}

    yield context.call_activity(
        "checkpoint_activity_trigger",
        {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "kind": "workflow.started",
            "payload": {"workflow_type": workflow_type},
        },
    )
    yield context.call_activity(
        "checkpoint_activity_trigger",
        {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "kind": "step.started",
            "payload": {"step": "Impact Assessment", "workflow_type": workflow_type},
        },
    )
    impact = yield context.call_activity(
        "customer_care_impact_activity_trigger", enriched
    )
    yield context.call_activity(
        "checkpoint_activity_trigger",
        {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "kind": "step.completed",
            "payload": {"step": "Impact Assessment", "workflow_type": workflow_type},
        },
    )

    yield context.call_activity(
        "checkpoint_activity_trigger",
        {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "kind": "step.started",
            "payload": {"step": "Entitlement Decision", "workflow_type": workflow_type},
        },
    )
    entitlement = yield context.call_activity(
        "customer_care_entitlement_activity_trigger",
        {**enriched, "impact_assessment": impact},
    )
    yield context.call_activity(
        "checkpoint_activity_trigger",
        {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "kind": "step.completed",
            "payload": {"step": "Entitlement Decision", "workflow_type": workflow_type},
        },
    )
    approval: dict = {"decision": "approve", "source": "policy"}
    requires_approval = any(
        bool(account.get("approval_required"))
        for account in impact.get("accounts", [])
        if isinstance(account, dict)
    )
    if requires_approval:
        yield context.call_activity(
            "checkpoint_activity_trigger",
            {
                "workflow_id": workflow_id,
                "instance_id": instance_id,
                "kind": "suspended",
                "payload": {
                    "reason": "awaiting_credit_approval",
                    "phase": "Credit Approval",
                    "wait_kind": "operator_review",
                    "workflow_type": workflow_type,
                    "persona": "cs_manager",
                    "external_event": "cs_manager_decision",
                    "context": {
                        "action": "cs_manager_decision",
                        "request": {
                            "amount": entitlement.get("aggregate_credit", 0),
                            "category": "service_credit",
                        },
                    },
                },
            },
        )
        decision_event = context.wait_for_external_event("cs_manager_decision")
        timer = context.create_timer(context.current_utc_datetime + timedelta(minutes=5))
        winner = yield context.task_any([decision_event, timer])
        if winner == timer:
            return {"status": "timeout", "command": None, "reasoning": "credit approval timed out"}
        timer.cancel()
        approval = decision_event.result or {}
        yield context.call_activity(
            "checkpoint_activity_trigger",
            {
                "workflow_id": workflow_id,
                "instance_id": instance_id,
                "kind": "resumed",
                "payload": {"phase": "Credit Approval", "workflow_type": workflow_type},
            },
        )
        if approval.get("decision") != "approve":
            return {
                "status": "denied",
                "command": None,
                "reasoning": "credit approval denied",
            }

    yield context.call_activity(
        "checkpoint_activity_trigger",
        {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "kind": "step.started",
            "payload": {"step": "Care Execution", "workflow_type": workflow_type},
        },
    )
    execution = yield context.call_activity(
        "customer_care_execution_activity_trigger",
        {
            **enriched,
            "impact_assessment": impact,
            "entitlement_decision": entitlement,
            "approval": approval,
        },
    )
    yield context.call_activity(
        "checkpoint_activity_trigger",
        {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "kind": "step.completed",
            "payload": {"step": "Care Execution", "workflow_type": workflow_type},
        },
    )
    command = execution.get("command")
    if isinstance(command, dict):
        command = dict(command)
        command["payload"] = {
            **(command.get("payload") or {}),
            "approval_decision": approval.get("decision"),
        }
    return {
        "status": "decision_ready",
        "command": command,
        "reasoning": execution.get("reasoning"),
        "observation": input_dict.get("observation"),
    }
