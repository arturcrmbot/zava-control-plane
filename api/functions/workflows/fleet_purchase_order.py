"""
Purchase Order generator orchestration — one workflow end-to-end.

4 phases:
  PO Lookup -> Supplier Check -> Authority Resolve (matrix-driven) ->
  Approver Signoff (HITL with persona dynamically picked from the matrix:
  line_manager / category_manager / sourcing_lead / cpo depending on value).

This is the cleaner pattern that exercises the FULL value-band escalation
chain — different invoices route to different personae automatically.

Sync generator per Azure Durable Functions Python convention.
"""
from __future__ import annotations
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df
from api.shared.constants import PURCHASE_ORDER_SIGNOFF_TIMEOUT


def fleet_purchase_order_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the 4 PO phases for one workflow."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    workflow_type = input_dict.get("type", "purchase-order")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {"domain": "fleet-purchase-order", "workflow_type": workflow_type},
    })

    # Phase 1: PO Lookup (deterministic)
    po_lookup_result = yield context.call_activity(
        "fleet_purchase_order_po_lookup_activity_trigger", enriched
    )
    enriched = {**enriched, "po_lookup": po_lookup_result}

    # Phase 2: Supplier Check (deterministic + validator)
    supplier_check_result = yield context.call_activity(
        "fleet_purchase_order_supplier_check_activity_trigger", enriched
    )
    enriched = {**enriched, "supplier_check": supplier_check_result}

    # Phase 3: Authority Resolve (deterministic — calls matrix MCP)
    authority_resolve_result = yield context.call_activity(
        "fleet_purchase_order_authority_resolve_activity_trigger", enriched
    )
    enriched = {**enriched, "authority_resolve": authority_resolve_result}

    # Phase 4: Approver Signoff (HITL — persona is dynamic, picked from
    # the matrix-resolved approver_role).
    approver = (authority_resolve_result or {}).get("approver_role") or "category_manager"

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": f"awaiting_{approver}",
            "phase": "approver_signoff",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            "persona": approver,
            "external_event": "purchase_order_approval_decision",
            "context": {
                "purchase_order": enriched.get("purchase_order"),
                "po_lookup": enriched.get("po_lookup"),
                "supplier_check": enriched.get("supplier_check"),
                "authority_resolve": enriched.get("authority_resolve"),
                "action": "purchase_order_approval",
            },
        },
    })

    decision_event = context.wait_for_external_event("purchase_order_approval_decision")
    timeout_event = context.create_timer(context.current_utc_datetime + PURCHASE_ORDER_SIGNOFF_TIMEOUT)
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
        "po_lookup": po_lookup_result,
        "supplier_check": supplier_check_result,
        "authority_resolve": authority_resolve_result,
        "approver_signoff": enriched["approver_signoff"],
    }
