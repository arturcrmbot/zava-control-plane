---
name: sustainability_operations_manager
description: Approves energy control plans responding to consumption anomalies.
workflow_label: Sustainability Operations Manager
external_event: sustainability_operations_manager_decision
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
    action = (context or {}).get("action") or "sustainability_operations_manager_decision"
    auth = authority_check(
        role="sustainability_operations_manager",
        action=action,
        value=value,
        category=request.get("category") or "energy",
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Sustainability Operations Manager

Approve a control plan only when the anomaly is evidenced against a real
baseline and the action will not create guest comfort exceptions. Reject stale
meter readings and unknown control actions.
