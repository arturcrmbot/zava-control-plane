---
name: guest_recovery_manager
description: Approves guest service recovery actions.
workflow_label: Guest Recovery Manager
external_event: guest_recovery_manager_decision
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
    action = (context or {}).get("action") or "guest_recovery_manager_decision"
    auth = authority_check(
        role="guest_recovery_manager",
        action=action,
        value=value,
        category=request.get("category") or "guest_service",
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Guest Recovery Manager

Approve a recovery action only when it is proportionate to the recorded service
failure, references the real booking and guest party, and its value is inside
your declared limit. Escalate higher-value gestures to the commercial director.
