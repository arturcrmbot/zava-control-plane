"""
Contract Review generator orchestration — one workflow end-to-end.

4 phases:
  Contract Intake -> Risk Classify -> Authority Resolve (matrix-driven) ->
  Approver Signoff (HITL with persona dynamically picked: contracts_counsel
  / gc depending on contract_type, value and template-deviation).

Sync generator per Azure Durable Functions Python convention.
"""
from __future__ import annotations
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df
from api.shared.constants import CONTRACT_REVIEW_SIGNOFF_TIMEOUT


def fleet_contract_review_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    workflow_type = input_dict.get("type", "contract-review")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {"domain": "fleet-contract-review", "workflow_type": workflow_type},
    })

    contract_intake_result = yield context.call_activity(
        "fleet_contract_review_contract_intake_activity_trigger", enriched
    )
    enriched = {**enriched, "contract_intake": contract_intake_result}

    risk_classify_result = yield context.call_activity(
        "fleet_contract_review_risk_classify_activity_trigger", enriched
    )
    enriched = {**enriched, "risk_classify": risk_classify_result}

    authority_resolve_result = yield context.call_activity(
        "fleet_contract_review_authority_resolve_activity_trigger", enriched
    )
    enriched = {**enriched, "authority_resolve": authority_resolve_result}

    approver = (authority_resolve_result or {}).get("approver_role") or "contracts_counsel"

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": f"awaiting_{approver}",
            "phase": "approver_signoff",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            "persona": approver,
            "external_event": "contract_review_signoff_decision",
            "context": {
                "contract_review": enriched.get("contract_review"),
                "contract_intake": enriched.get("contract_intake"),
                "risk_classify": enriched.get("risk_classify"),
                "authority_resolve": enriched.get("authority_resolve"),
                "action": "contract_review_signoff",
            },
        },
    })

    decision_event = context.wait_for_external_event("contract_review_signoff_decision")
    timeout_event = context.create_timer(context.current_utc_datetime + CONTRACT_REVIEW_SIGNOFF_TIMEOUT)
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
        "contract_intake": contract_intake_result,
        "risk_classify": risk_classify_result,
        "authority_resolve": authority_resolve_result,
        "approver_signoff": enriched["approver_signoff"],
    }
