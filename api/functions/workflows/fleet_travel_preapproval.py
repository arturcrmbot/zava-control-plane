"""
The single Travel pre-approval generator orchestration — one workflow end-to-end.

3 phases per docs/superpowers/specs/fleet-travel-preapproval-brief.yaml:
  Employee Lookup -> Policy Fit Check -> Manager Approval

HITL gates:
  - Phase 3 (Manager Approval) waits for the `manager_approval_decision`
    external event.

Sync generator per the Azure Durable Functions Python convention. Phase
activities are registered in `function_app.py` (see GRADUATION.md for the
diff).
"""
from __future__ import annotations
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df

from api.shared.constants import MANAGER_APPROVAL_TIMEOUT


def fleet_travel_preapproval_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the 3 Travel pre-approval phases for one workflow."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started", "payload": {"domain": "fleet-travel-preapproval"}
    })

    # Phase 1: Employee Lookup (deterministic)
    employee_lookup_result = yield context.call_activity(
        "fleet_travel_preapproval_employee_lookup_activity_trigger", enriched
    )
    enriched = {**enriched, "employee_lookup": employee_lookup_result}

    # Phase 2: Policy Fit Check (agent + validator)
    policy_fit_check_result = yield context.call_activity(
        "fleet_travel_preapproval_policy_fit_check_activity_trigger", enriched
    )
    enriched = {**enriched, "policy_fit_check": policy_fit_check_result}

    # Phase 3: Manager Approval (HITL — line_manager persona)
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {"reason": "awaiting_manager_approval", "phase": "manager_approval",
                    "wait_kind": "operator_review"},
    })

    decision_event = context.wait_for_external_event("manager_approval_decision")
    timeout_event = context.create_timer(context.current_utc_datetime + MANAGER_APPROVAL_TIMEOUT)
    winner = yield context.task_any([decision_event, timeout_event])

    if winner == timeout_event:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "manager_approval"}
        })
        return {"status": "timeout", "phase": "manager_approval"}
    timeout_event.cancel()

    enriched["manager_approval_decision"] = decision_event.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed", "payload": {"phase": "manager_approval"}
    })

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed", "payload": {}
    })

    return {
        "status": "completed",
        "employee_lookup": employee_lookup_result,
        "policy_fit_check": policy_fit_check_result,
        "manager_approval_decision": enriched["manager_approval_decision"],
    }
