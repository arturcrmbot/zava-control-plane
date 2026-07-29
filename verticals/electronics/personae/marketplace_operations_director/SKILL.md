---
name: marketplace_operations_director
description: Approves seller suppression and partner escalation.
allowed-tools:
workflow_label: Marketplace Operations — director
external_event: marketplace_operations_director_decision
decision_policy: |
    payload = (context or {}).get("request") or {}
    value_raw = payload.get("amount_gbp") or payload.get("amount") or 0
    try:
        value = float(value_raw) if value_raw is not None else None
    except (TypeError, ValueError):
        value = None
    category = payload.get("category") or "marketplace_operations"
    action = (context or {}).get("action") or "marketplace_operations_director_decision"
    auth = authority_check(
        role="marketplace_operations_director",
        action=action,
        value=value,
        category=category,
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Marketplace Operations Director

Marketplace inventory remains seller-controlled. Require stock/SLA evidence and
fair partner treatment before suppressing an offer.
