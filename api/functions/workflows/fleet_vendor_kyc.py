"""
The single Vendor onboarding & KYC generator orchestration — one workflow end-to-end.

4 phases per docs/superpowers/specs/fleet-vendor-kyc-brief.yaml:
  Vendor Intake -> KYC Diligence -> UBO Resolver -> Finance Signoff

HITL gates:
  - Phase 4 (Finance Signoff) waits for the `finance_signoff_decision`
    external event.

Sync generator per the Azure Durable Functions Python convention. Phase
activities are registered in `function_app.py` by graduate.sh.
"""
from __future__ import annotations
from collections.abc import Generator
from datetime import timedelta
from typing import Any

import azure.durable_functions as df
from api.shared.constants import (
    FINANCE_SIGNOFF_TIMEOUT,
)

# Per-phase HITL timeouts. Defined locally pre-graduation; graduate.sh lifts
# them into api/shared/constants.py and rewrites this file's import.
def fleet_vendor_kyc_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the 4 Vendor onboarding & KYC phases for one workflow."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    # v3 substrate-fix contract: stamp workflow_type on every checkpoint
    # payload so internal_durable_event populates its _workflow_types
    # cache and forwards `workflow_type` onto every downstream FleetEvent.
    # Without this, recordings come out tagged unknown-... and SSE events
    # arrive with domain=null.
    workflow_type = input_dict.get("type", "vendor-kyc")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {"domain": "fleet-vendor-kyc", "workflow_type": workflow_type},
    })

    # Phase 1: Vendor Intake (deterministic)
    vendor_intake_result = yield context.call_activity(
        "fleet_vendor_kyc_vendor_intake_activity_trigger", enriched
    )
    enriched = {**enriched, "vendor_intake": vendor_intake_result}

    # Phase 2: KYC Diligence (agent + validator)
    kyc_diligence_result = yield context.call_activity(
        "fleet_vendor_kyc_kyc_diligence_activity_trigger", enriched
    )
    enriched = {**enriched, "kyc_diligence": kyc_diligence_result}

    # Phase 3: UBO Resolver (agent + validator)
    ubo_resolver_result = yield context.call_activity(
        "fleet_vendor_kyc_ubo_resolver_activity_trigger", enriched
    )
    enriched = {**enriched, "ubo_resolver": ubo_resolver_result}

    # Phase 4: Finance Signoff (HITL — vendor_kyc_finance_bp persona)
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_finance_signoff",
            "phase": "finance_signoff",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            # Persona-responder contract: tell the responder which persona
            # owns this gate, which event resumes it, and the prior-phase
            # context the persona needs to apply its decision policy.
            "persona": "vendor_kyc_finance_bp",
            "external_event": "finance_signoff_decision",
            "context": {
                "ubo_resolver": enriched.get("ubo_resolver"),
                "kyc_diligence": enriched.get("kyc_diligence"),
            },
        },
    })

    decision_event = context.wait_for_external_event("finance_signoff_decision")
    timeout_event = context.create_timer(context.current_utc_datetime + FINANCE_SIGNOFF_TIMEOUT)
    winner = yield context.task_any([decision_event, timeout_event])

    if winner == timeout_event:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "finance_signoff",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "finance_signoff"}
    timeout_event.cancel()

    enriched["finance_signoff_decision"] = decision_event.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "finance_signoff", "workflow_type": workflow_type},
    })

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed", "payload": {"workflow_type": workflow_type},
    })

    return {
        "status": "completed",
        "vendor_intake": vendor_intake_result,
        "kyc_diligence": kyc_diligence_result,
        "ubo_resolver": ubo_resolver_result,
        "finance_signoff_decision": enriched["finance_signoff_decision"],
    }
