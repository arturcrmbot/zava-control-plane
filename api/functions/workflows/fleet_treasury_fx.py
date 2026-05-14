"""
Treasury FX generator orchestration.

4 phases:
  Op Lookup -> Position Check -> Authority Resolve (matrix-driven) ->
  Approver Signoff (HITL — treasurer for ≤£1M, cfo above).
"""
from __future__ import annotations
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df
from api.shared.constants import TREASURY_SIGNOFF_TIMEOUT


def fleet_treasury_fx_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    workflow_type = input_dict.get("type", "treasury-fx")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {"domain": "fleet-treasury-fx", "workflow_type": workflow_type},
    })

    op_lookup_result = yield context.call_activity(
        "fleet_treasury_fx_op_lookup_activity_trigger", enriched
    )
    enriched = {**enriched, "op_lookup": op_lookup_result}

    position_check_result = yield context.call_activity(
        "fleet_treasury_fx_position_check_activity_trigger", enriched
    )
    enriched = {**enriched, "position_check": position_check_result}

    authority_resolve_result = yield context.call_activity(
        "fleet_treasury_fx_authority_resolve_activity_trigger", enriched
    )
    enriched = {**enriched, "authority_resolve": authority_resolve_result}

    approver = (authority_resolve_result or {}).get("approver_role") or "treasurer"

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": f"awaiting_{approver}",
            "phase": "approver_signoff",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            "persona": approver,
            "external_event": "treasury_signoff_decision",
            "context": {
                "treasury_op": enriched.get("treasury_op"),
                "op_lookup": enriched.get("op_lookup"),
                "position_check": enriched.get("position_check"),
                "authority_resolve": enriched.get("authority_resolve"),
                "action": "treasury_fx_hedge",
            },
        },
    })

    decision_event = context.wait_for_external_event("treasury_signoff_decision")
    timeout_event = context.create_timer(context.current_utc_datetime + TREASURY_SIGNOFF_TIMEOUT)
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
        "op_lookup": op_lookup_result,
        "position_check": position_check_result,
        "authority_resolve": authority_resolve_result,
        "approver_signoff": enriched["approver_signoff"],
    }
