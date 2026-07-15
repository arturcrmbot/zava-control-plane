from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
from typing import Any

import azure.durable_functions as df


def order_to_activate_orchestration(
    context: df.DurableOrchestrationContext,
) -> Generator[Any, Any, dict]:
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    workflow_type = input_dict.get("type", "order-to-activate")
    instance_id = context.instance_id

    def checkpoint(kind: str, payload: dict) -> Any:
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
    yield checkpoint("step.started", {"step": "Order Intake"})
    yield checkpoint("step.completed", {"step": "Order Intake"})
    yield checkpoint("step.started", {"step": "Feasibility Check"})
    feasibility = yield context.call_activity(
        "order_activation_feasibility_activity_trigger", input_dict
    )
    yield checkpoint("step.completed", {"step": "Feasibility Check"})

    approval: dict = {"decision": "not_required"}
    if feasibility.get("requires_approval"):
        yield checkpoint(
            "suspended",
            {
                "reason": "awaiting_capacity_approval",
                "phase": "Capacity Approval",
                "wait_kind": "operator_review",
                "persona": "delivery_lead",
                "external_event": "capacity_manager_decision",
            },
        )
        decision_event = context.wait_for_external_event(
            "capacity_manager_decision"
        )
        timer = context.create_timer(
            context.current_utc_datetime + timedelta(minutes=5)
        )
        winner = yield context.task_any([decision_event, timer])
        if winner == timer:
            return {
                "status": "timeout",
                "command": None,
                "reasoning": "capacity approval timed out",
            }
        timer.cancel()
        approval = decision_event.result or {}
        yield checkpoint("resumed", {"phase": "Capacity Approval"})

    prepared = yield context.call_activity(
        "order_activation_prepare_activity_trigger",
        {**input_dict, "feasibility": feasibility, "approval": approval},
    )
    return {
        "status": "decision_ready",
        "command": prepared.get("command"),
        "reasoning": prepared.get("reasoning"),
        "observation": input_dict.get("observation"),
    }
