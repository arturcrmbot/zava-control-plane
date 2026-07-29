---
name: returns_operations_manager
description: Approves high-value and non-standard return dispositions.
allowed-tools:
workflow_label: Returns and Repairs — manager
external_event: returns_operations_manager_decision
decision_policy: |
    payload = (context or {}).get("request") or {}
    value_raw = payload.get("amount_gbp") or payload.get("amount") or 0
    try:
        value = float(value_raw) if value_raw is not None else None
    except (TypeError, ValueError):
        value = None
    category = payload.get("category") or "returns_repairs"
    action = (context or {}).get("action") or "returns_operations_manager_decision"
    auth = authority_check(
        role="returns_operations_manager",
        action=action,
        value=value,
        category=category,
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Returns Operations Manager

Use condition, ownership, order and SKU evidence. Prefer value recovery and waste
avoidance within policy; reject unknown or stale disposition commands.
