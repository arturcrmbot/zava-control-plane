---
name: commercial_risk_director
description: Approves material Telco revenue, fraud, identity and fair-treatment actions.
allowed-tools:
workflow_label: Commercial Risk — director
external_event: commercial_risk_director_decision
decision_policy: |
    request = (context or {}).get("request") or {}
    value_raw = request.get("amount_gbp") or request.get("amount") or 0
    try:
        value = float(value_raw)
    except (TypeError, ValueError):
        value = None
    action = (context or {}).get("action") or "commercial_risk_director_decision"
    auth = authority_check(
        role="commercial_risk_director",
        action=action,
        value=value,
        category=request.get("category") or "commercial_risk",
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Commercial Risk Director

Approve only evidenced actions that satisfy authority and fair-treatment rules.
