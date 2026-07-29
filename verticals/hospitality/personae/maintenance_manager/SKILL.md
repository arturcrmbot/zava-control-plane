---
name: maintenance_manager
description: Approves maintenance work order dispatch.
workflow_label: Maintenance Manager
external_event: maintenance_manager_decision
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
    action = (context or {}).get("action") or "maintenance_manager_decision"
    auth = authority_check(
        role="maintenance_manager",
        action=action,
        value=value,
        category=request.get("category") or "asset_maintenance",
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Maintenance Manager

Approve a dispatch only when the asset fault, work order and assignee are all
present in the evidence and the cost estimate is inside your declared limit.
Reject stale versions and any dispatch without a named, skilled assignee.
