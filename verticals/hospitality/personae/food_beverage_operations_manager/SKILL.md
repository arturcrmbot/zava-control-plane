---
name: food_beverage_operations_manager
description: Approves food and beverage service readiness plans.
workflow_label: Food Beverage Operations Manager
external_event: food_beverage_operations_manager_decision
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
    action = (context or {}).get("action") or "food_beverage_operations_manager_decision"
    auth = authority_check(
        role="food_beverage_operations_manager",
        action=action,
        value=value,
        category=request.get("category") or "food_beverage",
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Food & Beverage Operations Manager

Approve a service plan only when the covers shortfall, prepared covers and
service window in the evidence support it, and waste exposure stays acceptable.
Reject plans referencing a plan ID not in the evidence.
