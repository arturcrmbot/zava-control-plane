---
name: people_operations_director
description: Escalation authority for workforce decisions above manager limits.
workflow_label: People Operations Director
external_event: people_operations_director_decision
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
    action = (context or {}).get("action") or "people_operations_director_decision"
    auth = authority_check(
        role="people_operations_director",
        action=action,
        value=value,
        category=request.get("category") or "workforce",
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# People Operations Director

Decide only workforce matters escalated to you. Confirm the coverage evidence
and the delegation chain. Reject any plan that relies on undeclared overtime.
