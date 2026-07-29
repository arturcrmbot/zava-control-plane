---
name: sustainability_director
description: Escalation authority for high-value energy and utilities decisions.
workflow_label: Sustainability Director
external_event: sustainability_director_decision
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
    action = (context or {}).get("action") or "sustainability_director_decision"
    auth = authority_check(
        role="sustainability_director",
        action=action,
        value=value,
        category=request.get("category") or "energy",
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Sustainability Director

Decide only utilities matters escalated past the operations manager's limit.
Confirm the anomaly duration, baseline and avoided-consumption basis before
approving. Reject anything without a real meter reference.
