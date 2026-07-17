---
name: network_ops_director
description: Approves exceptional network operations and capital actions.
allowed-tools:
workflow_label: Network Operations — director
external_event: network_ops_director_decision
decision_policy: |
    payload = (context or {}).get("request") or {}
    value_raw = payload.get("amount_gbp") or payload.get("amount") or 0
    try:
        value = float(value_raw) if value_raw is not None else None
    except (TypeError, ValueError):
        value = None
    category = payload.get("category") or "network_operations"
    action = (context or {}).get("action") or "network_ops_director_decision"
    auth = authority_check(
        role="network_ops_director",
        action=action,
        value=value,
        category=category,
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Network Operations Director

Review evidence, cost, customer impact, and operational risk. Approve only when
the proposed action is proportionate and within the registered authority limit.
