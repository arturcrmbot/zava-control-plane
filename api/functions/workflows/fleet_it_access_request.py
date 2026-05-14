"""
The single IT access request generator orchestration — one workflow end-to-end.

5 phases per docs/superpowers/specs/fleet-it-access-request-brief.yaml:
  Employee Lookup -> RBAC Resolver -> Risk Assessor ->
  Line Manager Approval -> IT Admin Approval

HITL gates:
  - Phase 4 (Line Manager Approval) waits for the
    `line_manager_approval_decision` external event.
  - Phase 5 (IT Admin Approval) waits for the `it_admin_approval_decision`
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
from api.shared.constants import (
    LINE_MANAGER_APPROVAL_TIMEOUT,
    IT_ADMIN_APPROVAL_TIMEOUT,
)


def fleet_it_access_request_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the 5 IT access request phases for one workflow."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    # Stamped on every checkpoint payload so the FastAPI bus knows which
    # domain the event belongs to. Without this, /api/blueprint/stream events
    # arrive with domain=null and the mind-map can't pick a ring to light up.
    workflow_type = input_dict.get("type", "it-access-request")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {"domain": "fleet-it-access-request", "workflow_type": workflow_type},
    })

    # Phase 1: Employee Lookup (deterministic)
    employee_lookup_result = yield context.call_activity(
        "fleet_it_access_request_employee_lookup_activity_trigger", enriched
    )
    enriched = {**enriched, "employee_lookup": employee_lookup_result}

    # Phase 2: RBAC Resolver (agent + validator)
    rbac_resolver_result = yield context.call_activity(
        "fleet_it_access_request_rbac_resolver_activity_trigger", enriched
    )
    enriched = {**enriched, "rbac_resolver": rbac_resolver_result}

    # Phase 3: Risk Assessor (agent + validator)
    risk_assessor_result = yield context.call_activity(
        "fleet_it_access_request_risk_assessor_activity_trigger", enriched
    )
    enriched = {**enriched, "risk_assessor": risk_assessor_result}

    # Phase 4: Line Manager Approval (HITL — it_access_line_manager persona)
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_line_manager_approval",
            "phase": "line_manager_approval",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            # Persona-responder contract: tell the responder which persona
            # owns this gate, which event resumes it, and the prior-phase
            # context the persona needs to apply its decision policy.
            "persona": "it_access_line_manager",
            "external_event": "line_manager_approval_decision",
            "context": {
                "risk_assessor": enriched.get("risk_assessor"),
                "employee_lookup": enriched.get("employee_lookup"),
                "rbac_resolver": enriched.get("rbac_resolver"),
            },
        },
    })

    decision_event_lm = context.wait_for_external_event("line_manager_approval_decision")
    timeout_event_lm = context.create_timer(context.current_utc_datetime + LINE_MANAGER_APPROVAL_TIMEOUT)
    winner_lm = yield context.task_any([decision_event_lm, timeout_event_lm])

    if winner_lm == timeout_event_lm:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "line_manager_approval",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "line_manager_approval"}
    timeout_event_lm.cancel()

    enriched["line_manager_approval"] = decision_event_lm.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "line_manager_approval", "workflow_type": workflow_type},
    })

    # Phase 5: IT Admin Approval (HITL — it_access_it_admin persona)
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_it_admin_approval",
            "phase": "it_admin_approval",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            "persona": "it_access_it_admin",
            "external_event": "it_admin_approval_decision",
            "context": {
                "line_manager_approval": enriched.get("line_manager_approval"),
                "rbac_resolver": enriched.get("rbac_resolver"),
            },
        },
    })

    decision_event_it = context.wait_for_external_event("it_admin_approval_decision")
    timeout_event_it = context.create_timer(context.current_utc_datetime + IT_ADMIN_APPROVAL_TIMEOUT)
    winner_it = yield context.task_any([decision_event_it, timeout_event_it])

    if winner_it == timeout_event_it:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "it_admin_approval",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "it_admin_approval"}
    timeout_event_it.cancel()

    enriched["it_admin_approval"] = decision_event_it.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "it_admin_approval", "workflow_type": workflow_type},
    })

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed", "payload": {"workflow_type": workflow_type},
    })

    return {
        "status": "completed",
        "employee_lookup": employee_lookup_result,
        "rbac_resolver": rbac_resolver_result,
        "risk_assessor": risk_assessor_result,
        "line_manager_approval": enriched["line_manager_approval"],
        "it_admin_approval": enriched["it_admin_approval"],
    }
