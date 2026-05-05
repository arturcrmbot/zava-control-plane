"""
Privacy DPIA generator orchestration.

4 phases:
  DPIA Intake -> Risk Classify -> Authority Resolve (matrix-driven) ->
  Approver Signoff (HITL, dynamic persona — dpo for low-risk, gc on
  high-risk in non-EMEA, dpo+gc for EMEA per Art. 35).
"""
from __future__ import annotations
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df
from api.shared.constants import DPIA_SIGNOFF_TIMEOUT


def fleet_privacy_dpia_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    workflow_type = input_dict.get("type", "privacy-dpia")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {"domain": "fleet-privacy-dpia", "workflow_type": workflow_type},
    })

    dpia_intake_result = yield context.call_activity(
        "fleet_privacy_dpia_dpia_intake_activity_trigger", enriched
    )
    enriched = {**enriched, "dpia_intake": dpia_intake_result}

    risk_classify_result = yield context.call_activity(
        "fleet_privacy_dpia_risk_classify_activity_trigger", enriched
    )
    enriched = {**enriched, "risk_classify": risk_classify_result}

    authority_resolve_result = yield context.call_activity(
        "fleet_privacy_dpia_authority_resolve_activity_trigger", enriched
    )
    enriched = {**enriched, "authority_resolve": authority_resolve_result}

    approver = (authority_resolve_result or {}).get("approver_role") or "dpo"

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": f"awaiting_{approver}",
            "phase": "approver_signoff",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            "persona": approver,
            "external_event": "dpia_signoff_decision",
            "context": {
                "dpia": enriched.get("dpia"),
                "dpia_intake": enriched.get("dpia_intake"),
                "risk_classify": enriched.get("risk_classify"),
                "authority_resolve": enriched.get("authority_resolve"),
                "action": "privacy_dpia_signoff",
            },
        },
    })

    decision_event = context.wait_for_external_event("dpia_signoff_decision")
    timeout_event = context.create_timer(context.current_utc_datetime + DPIA_SIGNOFF_TIMEOUT)
    winner = yield context.task_any([decision_event, timeout_event])

    if winner == timeout_event:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "approver_signoff",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "approver_signoff"}
    timeout_event.cancel()

    enriched["approver_signoff"] = decision_event.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "approver_signoff", "workflow_type": workflow_type},
    })
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed", "payload": {"workflow_type": workflow_type},
    })
    return {
        "status": "completed",
        "dpia_intake": dpia_intake_result,
        "risk_classify": risk_classify_result,
        "authority_resolve": authority_resolve_result,
        "approver_signoff": enriched["approver_signoff"],
    }
