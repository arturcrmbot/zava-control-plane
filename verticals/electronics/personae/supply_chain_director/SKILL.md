---
name: supply_chain_director
description: Approves exceptional recovery spend and cross-border commitments.
allowed-tools:
workflow_label: Supply Chain — director
external_event: supply_chain_director_decision
decision_policy: |
    payload = (context or {}).get("request") or {}
    value_raw = payload.get("amount_gbp") or payload.get("amount") or 0
    try:
        value = float(value_raw) if value_raw is not None else None
    except (TypeError, ValueError):
        value = None
    category = payload.get("category") or "supply_chain"
    action = (context or {}).get("action") or "supply_chain_director_decision"
    auth = authority_check(
        role="supply_chain_director",
        action=action,
        value=value,
        category=category,
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Supply Chain Director

Require supplier milestone, cost and customer-impact evidence. Reject commitments
outside declared authority and decisions based on stale versions.
