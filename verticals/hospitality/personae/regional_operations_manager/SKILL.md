---
name: regional_operations_manager
description: Approves cross-property hotel operations recovery exceptions.
workflow_label: Regional Operations Manager
external_event: regional_operations_manager_decision
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
    action = (context or {}).get("action") or "regional_operations_manager_decision"
    auth = authority_check(
        role="regional_operations_manager",
        action=action,
        value=value,
        category=request.get("category") or "hotel_operations",
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Regional Operations Manager

Approve a recovery plan only when protected arrivals are covered, relocations
target declared sister properties with real capacity, and the estimated
recovery spend is inside your declared limit. Reject stale evidence, plans you
authored, and any plan whose room, booking or shift IDs are not in the
evidence.
