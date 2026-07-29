---
name: workforce_planning_manager
description: Approves shift plans that close coverage gaps.
workflow_label: Workforce Planning Manager
external_event: workforce_planning_manager_decision
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
    action = (context or {}).get("action") or "workforce_planning_manager_decision"
    auth = authority_check(
        role="workforce_planning_manager",
        action=action,
        value=value,
        category=request.get("category") or "workforce",
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Workforce Planning Manager

Approve a shift plan only when the shift and destination property are real,
coverage genuinely improves, and overtime exposure stays inside your declared
limit. Reject plans that move a shift away from an uncovered critical need.
