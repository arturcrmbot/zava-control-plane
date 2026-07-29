---
name: merchandising_director
description: Approves exceptional inventory and all markdown recommendations.
allowed-tools:
workflow_label: Category Trading — director
external_event: merchandising_director_decision
decision_policy: |
    payload = (context or {}).get("request") or {}
    value_raw = payload.get("amount_gbp") or payload.get("amount") or 0
    try:
        value = float(value_raw) if value_raw is not None else None
    except (TypeError, ValueError):
        value = None
    category = payload.get("category") or "merchandising"
    action = (context or {}).get("action") or "merchandising_director_decision"
    auth = authority_check(
        role="merchandising_director",
        action=action,
        value=value,
        category=category,
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Merchandising Director

Check fresh evidence and delegated authority. Approve only if margin, safety stock,
ownership, cross-border and fairness controls pass. Never approve a recommendation
you authored; reject stale evidence and unknown commands.
