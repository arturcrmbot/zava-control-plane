from __future__ import annotations

import asyncio
import os

from api.functions.graphs import (
    build_proactive_customer_care_entitlement_workflow,
    build_proactive_customer_care_execution_workflow,
)
from api.functions.workflows.activities import _run_workflow
from verticals.telco.mcp_tools.customer_care import (
    lookup_entitlement,
    prepare_credit,
    prepare_notification,
)


def customer_care_impact_activity(payload: dict) -> dict:
    observation = payload.get("observation") or {}
    accounts = list(observation.get("impacted_accounts") or [])[:3]
    return {
        "accounts": accounts,
        "affected_account_count": len(observation.get("impacted_accounts") or []),
        "incident_site_id": observation.get("incident_site_id"),
    }


def customer_care_entitlement_activity(payload: dict) -> dict:
    if os.environ.get("ZAVA_TELCO_AGENT_MODE") == "deterministic":
        accounts = (payload.get("impact_assessment") or {}).get("accounts") or []
        actions = []
        for account in accounts:
            policy = lookup_entitlement(
                str(account.get("segment") or "consumer"),
                bool(account.get("vulnerable")),
                bool(account.get("approval_required")),
            )
            actions.append({"account_id": account["id"], **policy})
        return {
            "actions": actions,
            "aggregate_credit": round(
                sum(float(action["credit_amount"]) for action in actions),
                2,
            ),
            "requires_approval": any(
                bool(action["requires_approval"]) for action in actions
            ),
            "reasoning": "Deterministic TELCO-CARE-001 policy evaluation.",
        }
    return asyncio.run(
        _run_workflow(
            build_proactive_customer_care_entitlement_workflow,
            payload,
            "Entitlement Decision",
            emit_boundaries=False,
        )
    )


def customer_care_execution_activity(payload: dict) -> dict:
    if os.environ.get("ZAVA_TELCO_AGENT_MODE") == "deterministic":
        entitlement = payload.get("entitlement_decision") or {}
        approved = (payload.get("approval") or {}).get("decision") == "approve"
        actions = []
        for item in entitlement.get("actions") or []:
            notification = prepare_notification(
                item["account_id"],
                item["channel"],
            )
            credit = prepare_credit(
                item["account_id"],
                float(item["credit_amount"]),
                approved,
            )
            actions.append({**notification, **credit})
        workflow_id = str(payload.get("workflow_id") or "unknown")
        trace_id = str(payload.get("trace_id") or "unknown")
        return {
            "command": {
                "command_id": f"care-{workflow_id}",
                "trace_id": trace_id,
                "issued_by": "customer_care",
                "type": "apply_customer_remediation",
                "payload": {"actions": actions},
            },
            "reasoning": "Prepared deterministic governed care actions.",
        }
    return asyncio.run(
        _run_workflow(
            build_proactive_customer_care_execution_workflow,
            payload,
            "Care Execution",
            emit_boundaries=False,
        )
    )
