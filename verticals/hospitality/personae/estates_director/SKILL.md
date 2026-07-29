---
name: estates_director
description: Escalation authority for high-value estates and asset spend.
workflow_label: Estates Director
external_event: estates_director_decision
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
    action = (context or {}).get("action") or "estates_director_decision"
    auth = authority_check(
        role="estates_director",
        action=action,
        value=value,
        category=request.get("category") or "asset_maintenance",
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Estates Director

Decide only maintenance matters escalated past the maintenance manager's limit.
Confirm the cost basis and rooms-out-of-service impact before approving.
Reject anything lacking a real work order reference.
