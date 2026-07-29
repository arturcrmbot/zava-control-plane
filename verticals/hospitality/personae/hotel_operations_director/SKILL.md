---
name: hotel_operations_director
description: Escalation authority for network-wide hotel operations decisions.
workflow_label: Hotel Operations Director
external_event: hotel_operations_director_decision
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
    action = (context or {}).get("action") or "hotel_operations_director_decision"
    auth = authority_check(
        role="hotel_operations_director",
        action=action,
        value=value,
        category=request.get("category") or "hotel_operations",
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Hotel Operations Director

Take only decisions escalated to you because they exceed a regional limit or
span several properties. Confirm the delegation chain and evidence freshness
before deciding. Never approve an action already refused below you without a
recorded reason.
