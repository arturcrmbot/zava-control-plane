"""
The single Employee onboarding generator orchestration — one workflow end-to-end.

4 phases per docs/superpowers/specs/fleet-employee-onboarding-brief.yaml:
  Employee Lookup -> Access Drafter -> IT Admin Approval -> Induction Planner

HITL gates:
  - Phase 3 (IT Admin Approval) waits for the `it_admin_approval_decision`
    external event.

Sync generator per the Azure Durable Functions Python convention. Phase
activities are registered in `function_app.py` (see GRADUATION.md for the
diff). Per-phase HITL timeouts are defined locally pre-graduation;
graduate.sh lifts them into api/shared/constants.py and rewrites this
file's import.
"""
from __future__ import annotations
from collections.abc import Generator
from datetime import timedelta
from typing import Any

import azure.durable_functions as df
from api.shared.constants import IT_ADMIN_APPROVAL_TIMEOUT


def fleet_employee_onboarding_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the 4 Employee onboarding phases for one workflow."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    # Stamped on every checkpoint payload so the FastAPI bus knows which
    # domain the event belongs to. Without this, /api/blueprint/stream events
    # arrive with domain=null and the mind-map can't pick a ring to light up.
    workflow_type = input_dict.get("type", "employee-onboarding")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {"domain": "fleet-employee-onboarding", "workflow_type": workflow_type},
    })

    # Phase 1: Employee Lookup (deterministic)
    employee_lookup_result = yield context.call_activity(
        "fleet_employee_onboarding_employee_lookup_activity_trigger", enriched
    )
    enriched = {**enriched, "employee_lookup": employee_lookup_result}

    # Phase 2: Access Drafter (agent + validator)
    access_drafter_result = yield context.call_activity(
        "fleet_employee_onboarding_access_drafter_activity_trigger", enriched
    )
    enriched = {**enriched, "access_drafter": access_drafter_result}

    # Phase 3: IT Admin Approval (HITL — onboarding_it_admin persona)
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_it_admin_approval",
            "phase": "it_admin_approval",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            # Persona-responder contract: tell the responder which persona
            # owns this gate, which event resumes it, and the prior-phase
            # context the persona needs to apply its decision policy.
            "persona": "onboarding_it_admin",
            "external_event": "it_admin_approval_decision",
            "context": {
                "access_drafter": enriched.get("access_drafter"),
            },
        },
    })

    decision_event = context.wait_for_external_event("it_admin_approval_decision")
    timeout_event = context.create_timer(context.current_utc_datetime + IT_ADMIN_APPROVAL_TIMEOUT)
    winner = yield context.task_any([decision_event, timeout_event])

    if winner == timeout_event:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "it_admin_approval",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "it_admin_approval"}
    timeout_event.cancel()

    enriched["it_admin_approval_decision"] = decision_event.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "it_admin_approval", "workflow_type": workflow_type},
    })

    # Phase 4: Induction Planner (agent + validator)
    induction_planner_result = yield context.call_activity(
        "fleet_employee_onboarding_induction_planner_activity_trigger", enriched
    )
    enriched = {**enriched, "induction_planner": induction_planner_result}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed", "payload": {"workflow_type": workflow_type},
    })

    return {
        "status": "completed",
        "employee_lookup": employee_lookup_result,
        "access_drafter": access_drafter_result,
        "it_admin_approval_decision": enriched["it_admin_approval_decision"],
        "induction_planner": induction_planner_result,
    }
