"""
The single Performance review generator orchestration — one workflow end-to-end.

5 phases per docs/superpowers/specs/fleet-perf-review-brief.yaml:
  Employee Lookup -> Peer Feedback Aggregator -> Calibration Drafter ->
  HR Calibration -> Line Manager Delivery

HITL gates:
  - Phase 4 (HR Calibration) waits for the `hr_calibration_decision`
    external event.
  - Phase 5 (Line Manager Delivery) waits for the
    `line_manager_delivery_decision` external event.

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
    HR_CALIBRATION_TIMEOUT,
    LINE_MANAGER_DELIVERY_TIMEOUT,
)


def fleet_perf_review_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the 5 Performance review phases for one workflow."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    # Stamped on every checkpoint payload so the FastAPI bus knows which
    # domain the event belongs to. Without this, /api/blueprint/stream events
    # arrive with domain=null and the mind-map can't pick a ring to light up.
    workflow_type = input_dict.get("type", "perf-review")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {"domain": "fleet-perf-review", "workflow_type": workflow_type},
    })

    # Phase 1: Employee Lookup (deterministic)
    employee_lookup_result = yield context.call_activity(
        "fleet_perf_review_employee_lookup_activity_trigger", enriched
    )
    enriched = {**enriched, "employee_lookup": employee_lookup_result}

    # Phase 2: Peer Feedback Aggregator (agent + validator)
    peer_feedback_aggregator_result = yield context.call_activity(
        "fleet_perf_review_peer_feedback_aggregator_activity_trigger", enriched
    )
    enriched = {**enriched, "peer_feedback_aggregator": peer_feedback_aggregator_result}

    # Phase 3: Calibration Drafter (agent + validator)
    calibration_drafter_result = yield context.call_activity(
        "fleet_perf_review_calibration_drafter_activity_trigger", enriched
    )
    enriched = {**enriched, "calibration_drafter": calibration_drafter_result}

    # Phase 4: HR Calibration (HITL — perf_review_hr_bp persona)
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_hr_calibration",
            "phase": "hr_calibration",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            # Persona-responder contract: tell the responder which persona
            # owns this gate, which event resumes it, and the prior-phase
            # context the persona needs to apply its decision policy.
            "persona": "perf_review_hr_bp",
            "external_event": "hr_calibration_decision",
            "context": {
                "calibration_drafter": enriched.get("calibration_drafter"),
                "peer_feedback_aggregator": enriched.get("peer_feedback_aggregator"),
                "employee_lookup": enriched.get("employee_lookup"),
            },
        },
    })

    decision_event_hr = context.wait_for_external_event("hr_calibration_decision")
    timeout_event_hr = context.create_timer(context.current_utc_datetime + HR_CALIBRATION_TIMEOUT)
    winner_hr = yield context.task_any([decision_event_hr, timeout_event_hr])

    if winner_hr == timeout_event_hr:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "hr_calibration",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "hr_calibration"}
    timeout_event_hr.cancel()

    enriched["hr_calibration"] = decision_event_hr.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "hr_calibration", "workflow_type": workflow_type},
    })

    # Phase 5: Line Manager Delivery (HITL — perf_review_line_manager persona)
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_line_manager_delivery",
            "phase": "line_manager_delivery",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            "persona": "perf_review_line_manager",
            "external_event": "line_manager_delivery_decision",
            "context": {
                "hr_calibration": enriched.get("hr_calibration"),
                "calibration_drafter": enriched.get("calibration_drafter"),
            },
        },
    })

    decision_event_lm = context.wait_for_external_event("line_manager_delivery_decision")
    timeout_event_lm = context.create_timer(context.current_utc_datetime + LINE_MANAGER_DELIVERY_TIMEOUT)
    winner_lm = yield context.task_any([decision_event_lm, timeout_event_lm])

    if winner_lm == timeout_event_lm:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "line_manager_delivery",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "line_manager_delivery"}
    timeout_event_lm.cancel()

    enriched["line_manager_delivery"] = decision_event_lm.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "line_manager_delivery", "workflow_type": workflow_type},
    })

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed", "payload": {"workflow_type": workflow_type},
    })

    return {
        "status": "completed",
        "employee_lookup": employee_lookup_result,
        "peer_feedback_aggregator": peer_feedback_aggregator_result,
        "calibration_drafter": calibration_drafter_result,
        "hr_calibration": enriched["hr_calibration"],
        "line_manager_delivery": enriched["line_manager_delivery"],
    }
