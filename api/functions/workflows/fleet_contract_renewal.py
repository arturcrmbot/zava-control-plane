"""
The single Contract renewal generator orchestration — one workflow end-to-end.

5 phases per docs/superpowers/specs/fleet-contract-renewal-brief.yaml:
  Contract Lookup -> Market Benchmarker -> Renewal Terms Drafter ->
  Finance Signoff -> Contract Owner Signoff

HITL gates:
  - Phase 4 (Finance Signoff) waits for the `finance_signoff_decision`
    external event.
  - Phase 5 (Contract Owner Signoff) waits for the
    `contract_owner_signoff_decision` external event.

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
    FINANCE_SIGNOFF_TIMEOUT,
    CONTRACT_OWNER_SIGNOFF_TIMEOUT,
)


def fleet_contract_renewal_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the 5 Contract renewal phases for one workflow."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    # Stamped on every checkpoint payload so the FastAPI bus knows which
    # domain the event belongs to. Without this, /api/blueprint/stream events
    # arrive with domain=null and the mind-map can't pick a ring to light up.
    workflow_type = input_dict.get("type", "contract-renewal")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {"domain": "fleet-contract-renewal", "workflow_type": workflow_type},
    })

    # Phase 1: Contract Lookup (deterministic)
    contract_lookup_result = yield context.call_activity(
        "fleet_contract_renewal_contract_lookup_activity_trigger", enriched
    )
    enriched = {**enriched, "contract_lookup": contract_lookup_result}

    # Phase 2: Market Benchmarker (agent + validator)
    market_benchmarker_result = yield context.call_activity(
        "fleet_contract_renewal_market_benchmarker_activity_trigger", enriched
    )
    enriched = {**enriched, "market_benchmarker": market_benchmarker_result}

    # Phase 3: Renewal Terms Drafter (agent + validator)
    renewal_terms_drafter_result = yield context.call_activity(
        "fleet_contract_renewal_renewal_terms_drafter_activity_trigger", enriched
    )
    enriched = {**enriched, "renewal_terms_drafter": renewal_terms_drafter_result}

    # Phase 4: Finance Signoff (HITL — contract_finance_bp persona)
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
            "persona": "contract_finance_bp",
            "external_event": "finance_signoff_decision",
            "context": {
                "renewal_terms_drafter": enriched.get("renewal_terms_drafter"),
                "market_benchmarker": enriched.get("market_benchmarker"),
            },
        },
    })

    decision_event_fin = context.wait_for_external_event("finance_signoff_decision")
    timeout_event_fin = context.create_timer(context.current_utc_datetime + FINANCE_SIGNOFF_TIMEOUT)
    winner_fin = yield context.task_any([decision_event_fin, timeout_event_fin])

    if winner_fin == timeout_event_fin:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "finance_signoff",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "finance_signoff"}
    timeout_event_fin.cancel()

    enriched["finance_signoff"] = decision_event_fin.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "finance_signoff", "workflow_type": workflow_type},
    })

    # Phase 5: Contract Owner Signoff (HITL — contract_line_manager persona)
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_contract_owner_signoff",
            "phase": "contract_owner_signoff",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            "persona": "contract_line_manager",
            "external_event": "contract_owner_signoff_decision",
            "context": {
                "finance_signoff": enriched.get("finance_signoff"),
                "renewal_terms_drafter": enriched.get("renewal_terms_drafter"),
            },
        },
    })

    decision_event_co = context.wait_for_external_event("contract_owner_signoff_decision")
    timeout_event_co = context.create_timer(context.current_utc_datetime + CONTRACT_OWNER_SIGNOFF_TIMEOUT)
    winner_co = yield context.task_any([decision_event_co, timeout_event_co])

    if winner_co == timeout_event_co:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "contract_owner_signoff",
                        "workflow_type": workflow_type},
        })
        return {"status": "timeout", "phase": "contract_owner_signoff"}
    timeout_event_co.cancel()

    enriched["contract_owner_signoff"] = decision_event_co.result

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "contract_owner_signoff", "workflow_type": workflow_type},
    })

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed", "payload": {"workflow_type": workflow_type},
    })

    return {
        "status": "completed",
        "contract_lookup": contract_lookup_result,
        "market_benchmarker": market_benchmarker_result,
        "renewal_terms_drafter": renewal_terms_drafter_result,
        "finance_signoff": enriched["finance_signoff"],
        "contract_owner_signoff": enriched["contract_owner_signoff"],
    }
