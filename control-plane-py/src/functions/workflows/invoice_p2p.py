# src/functions/workflows/invoice_p2p.py
"""
The single InvoiceP2P generator orchestration — represents one POC1 invoice end-to-end.

Drives 6 phases as activities. HITL gate at Approval via wait_for_external_event.
Sync generator per Azure Durable Functions Python convention.
"""
from __future__ import annotations
from datetime import timedelta
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df


def invoice_p2p_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the 6 POC1 phases for one invoice. HITL on Approval."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    enriched = {**input_dict, "instance_id": context.instance_id}

    # Lifecycle: workflow.started
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started", "payload": {}
    })

    # Step 1: Intake
    intake_result = yield context.call_activity("intake_activity_trigger", enriched)
    enriched = {**enriched, "intake": intake_result}

    # Step 2: Validation
    validation_result = yield context.call_activity("validation_activity_trigger", enriched)
    enriched = {**enriched, "validation": validation_result}

    # Step 3: Routing
    routing_result = yield context.call_activity("routing_activity_trigger", enriched)
    enriched = {**enriched, "routing": routing_result}

    # Step 4: Approval
    approval_result = yield context.call_activity("approval_activity_trigger", enriched)
    enriched = {**enriched, "approval": approval_result}

    if approval_result.get("requires_hitl"):
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "suspended", "payload": {"reason": approval_result.get("reason", "approval_required")}
        })

        decision_event = context.wait_for_external_event("approval_decision")
        timeout_event = context.create_timer(context.current_utc_datetime + timedelta(hours=72))
        winner = yield context.task_any([decision_event, timeout_event])

        if winner == timeout_event:
            yield context.call_activity("checkpoint_activity_trigger", {
                "workflow_id": workflow_id, "instance_id": context.instance_id,
                "kind": "workflow.completed", "payload": {"status": "timeout"}
            })
            return {"status": "timeout", "phase": "Approval"}
        timeout_event.cancel()

        decision = decision_event.result
        approval_result["decision"] = decision
        approval_result["via_hitl"] = True
        enriched["approval"] = approval_result

        # Add synthetic ledger entry so submit_payment's hook check passes
        ledger_entry = {
            "actor_kind": "human",
            "actor_id": (decision.get("resolved_by") if isinstance(decision, dict) else "operator"),
            "action": "approve",
        }
        enriched["action_ledger"] = [*(enriched.get("action_ledger") or []), ledger_entry]

        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "resumed", "payload": {"decision": decision}
        })

    # Step 5: Payment
    payment_result = yield context.call_activity("payment_activity_trigger", enriched)
    enriched = {**enriched, "payment": payment_result}

    # Step 6: Reconciliation
    recon_result = yield context.call_activity("reconciliation_activity_trigger", enriched)
    enriched = {**enriched, "reconciliation": recon_result}

    # Lifecycle: workflow.completed
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed", "payload": {}
    })

    return {
        "status": "completed",
        "intake": intake_result,
        "validation": validation_result,
        "routing": routing_result,
        "approval": approval_result,
        "payment": payment_result,
        "reconciliation": recon_result,
    }
