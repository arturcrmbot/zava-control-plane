"""Deterministic activities for the Telco order-to-activate workflow."""
from __future__ import annotations


def order_activation_feasibility_activity(payload: dict) -> dict:
    observation = payload.get("observation") or {}
    order = observation.get("order") or {}
    site = observation.get("requested_site") or {}
    feasible = site.get("status") == "healthy" and float(
        site.get("utilization", 1.0)
    ) < 0.9
    return {
        "order_id": order.get("id"),
        "site_id": site.get("id"),
        "feasible": feasible,
        "requires_approval": not feasible,
        "reason": (
            "capacity available"
            if feasible
            else "requested site requires capacity exception"
        ),
    }


def order_activation_prepare_activity(payload: dict) -> dict:
    feasibility = payload.get("feasibility") or {}
    approval = payload.get("approval") or {}
    approved = approval.get("decision") == "approve"
    if feasibility.get("requires_approval") and not approved:
        return {
            "command": None,
            "reasoning": "capacity exception was not approved",
        }
    trace_id = str(payload.get("trace_id") or "unknown")
    order_id = str(feasibility.get("order_id") or "")
    return {
        "command": {
            "command_id": f"cmd-{trace_id}-activate",
            "trace_id": trace_id,
            "issued_by": "service_fulfillment",
            "type": "activate_service_order",
            "payload": {
                "order_id": order_id,
                "capacity_approved": bool(
                    feasibility.get("requires_approval") and approved
                ),
            },
        },
        "reasoning": f"activation prepared for {order_id}",
    }
