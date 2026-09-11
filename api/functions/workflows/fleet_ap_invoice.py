"""
The single AP invoice generator orchestration — one workflow end-to-end.

4 phases:
  Invoice Lookup -> Three-Way Match -> AP Clerk Signoff (HITL) ->
  Controller Signoff (HITL escalation, only when AP clerk escalates)

HITL gates:
  - Phase 3 (AP Clerk Signoff) waits for the `ap_invoice_processing_decision`
    external event. Persona `ap_clerk` reads the matrix at AP-001..AP-002:
      - matched + ≤£25k → approve
      - matched + >£25k → escalate (controller band)
      - not matched     → escalate (always)
  - Phase 4 (Controller Signoff) only fires when AP clerk escalated. Persona
    `controller` reads the matrix at AP-003..AP-004 and decides
    approve/escalate (CFO band).

Sync generator per the Azure Durable Functions Python convention. Phase
activities are registered in `function_app.py`.
"""
from __future__ import annotations
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df
from api.shared.constants import (
    AP_CLERK_SIGNOFF_TIMEOUT,
    CONTROLLER_SIGNOFF_TIMEOUT,
)


def fleet_ap_invoice_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the 4 AP invoice phases for one workflow."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    workflow_type = input_dict.get("type", "ap-invoice")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {
            "domain": "fleet-ap-invoice",
            "workflow_type": workflow_type,
            "workflow": {
                "current_phase": "Invoice Lookup",
                "jurisdiction": "London-Zava",
                "agency": "Zava",
                "payload": {
                    "parent_workflow_id": input_dict.get("parent_workflow_id"),
                    "invoice": input_dict.get("invoice") or {},
                    "scenario": input_dict.get("scenario"),
                },
            },
        },
    })

    # Phase 1: Invoice Lookup (deterministic)
    invoice_lookup_result = yield context.call_activity(
        "fleet_ap_invoice_invoice_lookup_activity_trigger", enriched
    )
    enriched = {**enriched, "invoice_lookup": invoice_lookup_result}
    invoice_context = {
        **(input_dict.get("invoice") or {}),
        **(invoice_lookup_result or {}),
    }

    # Phase 2: Three-Way Match (deterministic + validator)
    three_way_match_result = yield context.call_activity(
        "fleet_ap_invoice_three_way_match_activity_trigger", enriched
    )
    enriched = {**enriched, "three_way_match": three_way_match_result}

    # Phase 3: AP Clerk Signoff (HITL — ap_clerk persona)
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_ap_clerk",
            "phase": "ap_clerk_signoff",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            "persona": "ap_clerk",
            "external_event": "ap_invoice_processing_decision",
            "context": {
                "invoice": invoice_context,
                "invoice_lookup": enriched.get("invoice_lookup"),
                "three_way_match": enriched.get("three_way_match"),
                "action": "ap_invoice_approval",
                "escalation_chain": ["controller", "cfo"],
                "workflow_type": workflow_type,
            },
        },
    })

    decision_event_clerk = context.wait_for_external_event("ap_invoice_processing_decision")
    timeout_event_clerk = context.create_timer(context.current_utc_datetime + AP_CLERK_SIGNOFF_TIMEOUT)
    winner_clerk = yield context.task_any([decision_event_clerk, timeout_event_clerk])

    if winner_clerk == timeout_event_clerk:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.failed",
            "payload": {"outcome": "timeout", "phase": "ap_clerk_signoff",
                        "reason": "AP clerk decision timed out",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "ap_clerk_signoff"}
    timeout_event_clerk.cancel()

    enriched["ap_clerk_signoff"] = decision_event_clerk.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "ap_clerk_signoff", "workflow_type": workflow_type},
    })

    # Phase 4 only fires when AP clerk escalated (or rejected — controller still
    # gets to see it). When ap_clerk approved, the workflow is done.
    clerk_decision = (enriched["ap_clerk_signoff"] or {}).get("decision")
    if clerk_decision == "approve":
        outcome = {
            "status": "completed",
            "invoice_id": invoice_context.get("invoice_id"),
            "invoice_lookup": invoice_lookup_result,
            "three_way_match": three_way_match_result,
            "ap_clerk_signoff": enriched["ap_clerk_signoff"],
        }
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.output",
            "payload": {"slot": "outcome", "data": outcome,
                        "workflow_type": workflow_type},
        })
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed", "payload": {"workflow_type": workflow_type},
        })
        return outcome
    if clerk_decision == "reject":
        outcome = {
            "status": "rejected",
            "phase": "ap_clerk_signoff",
            "invoice_id": invoice_context.get("invoice_id"),
            "ap_clerk_signoff": enriched["ap_clerk_signoff"],
        }
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.output",
            "payload": {"slot": "outcome", "data": outcome,
                        "workflow_type": workflow_type},
        })
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.rejected",
            "payload": {
                "phase": "ap_clerk_signoff",
                "reason": (
                    enriched["ap_clerk_signoff"].get("reason")
                    or "AP clerk rejected invoice"
                ),
                "decision_id": enriched["ap_clerk_signoff"].get("decision_id"),
                "workflow_type": workflow_type,
            },
        })
        return outcome
    if clerk_decision != "escalate":
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.failed",
            "payload": {
                "outcome": "invalid_ap_clerk_decision",
                "reason": f"Unsupported AP clerk decision {clerk_decision!r}",
                "workflow_type": workflow_type,
            },
        })
        return {"status": "failed", "outcome": "invalid_ap_clerk_decision"}

    # Phase 4: Controller Signoff (HITL — controller persona)
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_controller",
            "phase": "controller_signoff",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            "persona": "controller",
            "external_event": "controller_signoff_decision",
            "context": {
                "invoice": invoice_context,
                "invoice_lookup": enriched.get("invoice_lookup"),
                "three_way_match": enriched.get("three_way_match"),
                "ap_clerk_signoff": enriched.get("ap_clerk_signoff"),
                "action": "ap_invoice_approval",
                "escalation_chain": ["cfo"],
                "workflow_type": workflow_type,
            },
        },
    })

    decision_event_ctrl = context.wait_for_external_event("controller_signoff_decision")
    timeout_event_ctrl = context.create_timer(context.current_utc_datetime + CONTROLLER_SIGNOFF_TIMEOUT)
    winner_ctrl = yield context.task_any([decision_event_ctrl, timeout_event_ctrl])

    if winner_ctrl == timeout_event_ctrl:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.failed",
            "payload": {"outcome": "timeout", "phase": "controller_signoff",
                        "reason": "Controller decision timed out",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "controller_signoff"}
    timeout_event_ctrl.cancel()

    enriched["controller_signoff"] = decision_event_ctrl.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "controller_signoff", "workflow_type": workflow_type},
    })

    controller_decision = (enriched["controller_signoff"] or {}).get("decision")
    outcome = {
        "status": "completed" if controller_decision == "approve" else (
            "rejected" if controller_decision == "reject" else "failed"
        ),
        "invoice_id": invoice_context.get("invoice_id"),
        "invoice_lookup": invoice_lookup_result,
        "three_way_match": three_way_match_result,
        "ap_clerk_signoff": enriched["ap_clerk_signoff"],
        "controller_signoff": enriched["controller_signoff"],
    }
    if controller_decision == "escalate":
        outcome["outcome"] = "unresolved_escalation"
    elif controller_decision not in {"approve", "reject"}:
        outcome["outcome"] = "invalid_controller_decision"
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.output",
        "payload": {"slot": "outcome", "data": outcome,
                    "workflow_type": workflow_type},
    })
    if controller_decision == "approve":
        terminal_kind = "workflow.completed"
        terminal_payload = {"workflow_type": workflow_type}
    elif controller_decision == "reject":
        terminal_kind = "workflow.rejected"
        terminal_payload = {
            "phase": "controller_signoff",
            "reason": (
                enriched["controller_signoff"].get("reason")
                or "Controller rejected invoice"
            ),
            "decision_id": enriched["controller_signoff"].get("decision_id"),
            "workflow_type": workflow_type,
        }
    else:
        terminal_kind = "workflow.failed"
        terminal_payload = {
            "outcome": outcome["outcome"],
            "reason": (
                "Controller escalation remains unresolved"
                if controller_decision == "escalate"
                else f"Unsupported controller decision {controller_decision!r}"
            ),
            "workflow_type": workflow_type,
        }
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": terminal_kind, "payload": terminal_payload,
    })
    return outcome
