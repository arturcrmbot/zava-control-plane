from __future__ import annotations

import asyncio

from api.functions.graphs import (
    build_proactive_customer_care_entitlement_workflow,
    build_proactive_customer_care_execution_workflow,
)
from api.functions.workflows.activities import _run_workflow


def customer_care_impact_activity(payload: dict) -> dict:
    observation = payload.get("observation") or {}
    accounts = list(observation.get("impacted_accounts") or [])[:3]
    return {
        "accounts": accounts,
        "affected_account_count": len(observation.get("impacted_accounts") or []),
        "incident_site_id": observation.get("incident_site_id"),
    }


def customer_care_entitlement_activity(payload: dict) -> dict:
    return asyncio.run(
        _run_workflow(
            build_proactive_customer_care_entitlement_workflow,
            payload,
            "Entitlement Decision",
            emit_boundaries=False,
        )
    )


def customer_care_execution_activity(payload: dict) -> dict:
    return asyncio.run(
        _run_workflow(
            build_proactive_customer_care_execution_workflow,
            payload,
            "Care Execution",
            emit_boundaries=False,
        )
    )
