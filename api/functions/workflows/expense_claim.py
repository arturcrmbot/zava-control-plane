# src/functions/workflows/expense_claim.py
"""
The single ExpenseClaim generator orchestration — one POC1 expense claim end-to-end.

7 phases per spec §4.1:
  Intake -> Classify -> Validate Receipt -> Route -> Notify -> Arbitrate -> Audit

HITL gates:
  - Phase 5 (Notify, Red path only) waits for the `justification` external event
  - Phase 6 (Arbitrate) waits for the `reviewer_decision` external event

Sync generator per the Azure Durable Functions Python convention. Phases 3-7
call activity triggers that exist registered in function_app.py; the activity
bodies for Phases 3-7 will be wired progressively over Days 7-10 / Week 3.
"""
from __future__ import annotations
from datetime import timedelta
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df

from api.shared.constants import DECISION_REJECTED


def expense_claim_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the 7 expense-compliance phases for one claim."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started", "payload": {}
    })

    # Phase 1: Intake & Normalise
    intake_result = yield context.call_activity("intake_activity_trigger", enriched)
    enriched = {**enriched, "intake": intake_result}

    # Phase 2: Classify (R/A/G)
    classify_result = yield context.call_activity("classify_activity_trigger", enriched)
    enriched = {**enriched, "classify": classify_result}

    # Phase 3: Validate Receipt — wired in Day 7
    receipt_result = yield context.call_activity("receipt_activity_trigger", enriched)
    enriched = {**enriched, "receipt": receipt_result}

    # Phase 4: Route by Verdict — wired in Day 9
    route_result = yield context.call_activity("route_activity_trigger", enriched)
    enriched = {**enriched, "route": route_result}

    verdict = (classify_result or {}).get("verdict", "amber")

    # Phase 5: Notify (Red path only) + Phase 6: Arbitrate — wired in Day 10 / Week 3
    if verdict == "red":
        notify_result = yield context.call_activity("notify_activity_trigger", enriched)
        enriched = {**enriched, "notify": notify_result}

        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "suspended",
            "payload": {"reason": "awaiting_justification"},
        })

        justification_event = context.wait_for_external_event("justification")
        timeout_event = context.create_timer(context.current_utc_datetime + timedelta(hours=72))
        winner = yield context.task_any([justification_event, timeout_event])

        if winner == timeout_event:
            yield context.call_activity("checkpoint_activity_trigger", {
                "workflow_id": workflow_id, "instance_id": context.instance_id,
                "kind": "workflow.completed", "payload": {"status": "timeout"}
            })
            return {"status": "timeout", "phase": "Notify"}
        timeout_event.cancel()

        justification = justification_event.result
        enriched["justification"] = justification

        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "resumed", "payload": {"justification": justification}
        })

        arbitrate_result = yield context.call_activity("arbitrate_activity_trigger", enriched)
        enriched = {**enriched, "arbitrate": arbitrate_result}

        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "suspended", "payload": {"reason": "awaiting_reviewer"},
        })

        decision_event = context.wait_for_external_event("reviewer_decision")
        timeout_event = context.create_timer(context.current_utc_datetime + timedelta(hours=72))
        winner = yield context.task_any([decision_event, timeout_event])

        if winner == timeout_event:
            yield context.call_activity("checkpoint_activity_trigger", {
                "workflow_id": workflow_id, "instance_id": context.instance_id,
                "kind": "workflow.completed", "payload": {"status": "timeout"}
            })
            return {"status": "timeout", "phase": "Arbitrate"}
        timeout_event.cancel()

        decision = decision_event.result
        decision_type = (
            (decision.get("decision") or "") if isinstance(decision, dict) else ""
        ).lower()

        if decision_type in DECISION_REJECTED:
            yield context.call_activity("checkpoint_activity_trigger", {
                "workflow_id": workflow_id, "instance_id": context.instance_id,
                "kind": "workflow.rejected",
                "payload": {
                    "by": decision.get("resolved_by") if isinstance(decision, dict) else None,
                    "reason": "reviewer rejected",
                },
            })
            return {"status": "rejected", "phase": "Arbitrate", "decision": decision}

        enriched["reviewer_decision"] = decision

        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "resumed", "payload": {"decision": decision}
        })

    # Phase 7: Audit — wired in Week 3
    audit_result = yield context.call_activity("audit_activity_trigger", enriched)
    enriched = {**enriched, "audit": audit_result}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed", "payload": {}
    })

    return {
        "status": "completed",
        "verdict": verdict,
        "intake": intake_result,
        "classify": classify_result,
        "receipt": receipt_result,
        "route": route_result,
        "audit": audit_result,
    }
