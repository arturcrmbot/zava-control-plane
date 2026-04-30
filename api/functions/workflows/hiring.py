# src/functions/workflows/hiring.py
"""
The single Hiring generator orchestration — one POC2 hire end-to-end.

10 phases per [docs/poc2-status.md](../../../docs/poc2-status.md) §2:
  Budget -> Job Design -> Sourcing -> Triage -> Screening -> Voice ->
  Interview -> Compliance -> Offer -> Onboarding

HITL gates (mirror POC1's expense-claim pattern — `wait_for_external_event`
raced against `create_timer`, suspend/resume checkpoints either side):
  - Phase 1 (Budget) waits for the `budget_approval` external event
    (Finance BP £10k delegation per spec §4.6 multi-surface convergence)
  - Phase 9 (Offer) waits for the `offer_approval` external event
    (HR BP final approval; gates the non-revocable offer-letter send)

Reject path: an `offer_approval.decision == "reject"` short-circuits to
status=rejected, mirroring the expense-claim Arbitrate reject branch.

Skipped phases: §4.6 Voice runs only when the screening verdict is
"borderline" (flowchart in poc2-status.md). For the spine we simulate this
by checking `screening.verdict`; downstream tracks fill in the real verdict.
"""
from __future__ import annotations
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df

from api.shared.constants import (
    DECISION_REJECTED,
    BUDGET_APPROVAL_TIMEOUT,
    OFFER_APPROVAL_TIMEOUT,
)


def hiring_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the 10 hiring phases for one req-to-hire."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started", "payload": {"poc": "poc2-hiring"}
    })

    # Phase 1: Budget — Finance BP HITL on £10k+ delegation
    budget_result = yield context.call_activity("hiring_budget_activity_trigger", enriched)
    enriched = {**enriched, "budget": budget_result}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {"reason": "awaiting_budget_approval", "phase": "Budget"},
    })

    approval_event = context.wait_for_external_event("budget_approval")
    timeout_event = context.create_timer(context.current_utc_datetime + BUDGET_APPROVAL_TIMEOUT)
    winner = yield context.task_any([approval_event, timeout_event])

    if winner == timeout_event:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed", "payload": {"status": "timeout", "phase": "Budget"}
        })
        return {"status": "timeout", "phase": "Budget"}
    timeout_event.cancel()

    budget_decision = approval_event.result
    enriched["budget_approval"] = budget_decision

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed", "payload": {"phase": "Budget", "decision": budget_decision}
    })

    # Phase 2: Job Design
    job_design_result = yield context.call_activity("hiring_job_design_activity_trigger", enriched)
    enriched = {**enriched, "job_design": job_design_result}

    # Phase 3: Sourcing
    sourcing_result = yield context.call_activity("hiring_sourcing_activity_trigger", enriched)
    enriched = {**enriched, "sourcing": sourcing_result}

    # Phase 4: Triage (CV crystallisation — multimodal)
    triage_result = yield context.call_activity("hiring_triage_activity_trigger", enriched)
    enriched = {**enriched, "triage": triage_result}

    # Phase 5: Screening (R/A/G-style verdict drives Voice gating)
    screening_result = yield context.call_activity("hiring_screening_activity_trigger", enriched)
    enriched = {**enriched, "screening": screening_result}

    screening_verdict = (screening_result or {}).get("verdict", "borderline")

    # Phase 6: Voice — only on borderline / strong; auto-drop short-circuits.
    if screening_verdict in {"low", "auto-drop"}:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "auto_dropped", "phase": "Screening"}
        })
        return {"status": "auto_dropped", "phase": "Screening", "screening": screening_result}

    voice_result = yield context.call_activity("hiring_voice_activity_trigger", enriched)
    enriched = {**enriched, "voice": voice_result}

    # Phase 7: Interview
    interview_result = yield context.call_activity("hiring_interview_activity_trigger", enriched)
    enriched = {**enriched, "interview": interview_result}

    # Phase 8: Compliance (jurisdiction-aware — USA / DE BetrVG)
    compliance_result = yield context.call_activity("hiring_compliance_activity_trigger", enriched)
    enriched = {**enriched, "compliance": compliance_result}

    # Phase 9: Offer — HR BP HITL on the non-revocable offer-letter send.
    offer_result = yield context.call_activity("hiring_offer_activity_trigger", enriched)
    enriched = {**enriched, "offer": offer_result}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {"reason": "awaiting_offer_approval", "phase": "Offer"},
    })

    offer_event = context.wait_for_external_event("offer_approval")
    timeout_event = context.create_timer(context.current_utc_datetime + OFFER_APPROVAL_TIMEOUT)
    winner = yield context.task_any([offer_event, timeout_event])

    if winner == timeout_event:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed", "payload": {"status": "timeout", "phase": "Offer"}
        })
        return {"status": "timeout", "phase": "Offer"}
    timeout_event.cancel()

    offer_decision = offer_event.result
    decision_type = (
        (offer_decision.get("decision") or "") if isinstance(offer_decision, dict) else ""
    ).lower()

    if decision_type in DECISION_REJECTED:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.rejected",
            "payload": {
                "by": offer_decision.get("resolved_by") if isinstance(offer_decision, dict) else None,
                "reason": "HR BP rejected offer",
                "phase": "Offer",
            },
        })
        return {"status": "rejected", "phase": "Offer", "decision": offer_decision}

    enriched["offer_approval"] = offer_decision

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed", "payload": {"phase": "Offer", "decision": offer_decision}
    })

    # Phase 10: Onboarding (ServiceNow JML, HeyGen avatar, Graph invite)
    onboarding_result = yield context.call_activity("hiring_onboarding_activity_trigger", enriched)
    enriched = {**enriched, "onboarding": onboarding_result}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed", "payload": {}
    })

    return {
        "status": "completed",
        "screening_verdict": screening_verdict,
        "budget": budget_result,
        "job_design": job_design_result,
        "sourcing": sourcing_result,
        "triage": triage_result,
        "screening": screening_result,
        "voice": voice_result,
        "interview": interview_result,
        "compliance": compliance_result,
        "offer": offer_result,
        "onboarding": onboarding_result,
    }
