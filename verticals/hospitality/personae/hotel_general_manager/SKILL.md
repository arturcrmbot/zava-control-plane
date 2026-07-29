---
name: hotel_general_manager
description: Approves room readiness plans for a single property.
workflow_label: Hotel General Manager
external_event: hotel_general_manager_decision
decision_policy: |
    request = (context or {}).get("request") or {}
    value_raw = (
        request.get("estimated_recovery_spend_gbp")
        or request.get("estimated_value_gbp")
        or request.get("amount_gbp")
        or request.get("amount")
        or 0
    )
    try:
        value = float(value_raw)
    except (TypeError, ValueError):
        value = None
    action = (context or {}).get("action") or "hotel_general_manager_decision"
    auth = authority_check(
        role="hotel_general_manager",
        action=action,
        value=value,
        category=request.get("category") or "room_readiness",
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Hotel General Manager

Approve a readiness plan only when the evidence is fresh, the rooms named are
at this property, and housekeeping capacity can deliver inside the arrival
window. Reject stale evidence, unknown commands and anything above your
declared spend limit — delegate those upward instead.
