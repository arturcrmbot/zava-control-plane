---
name: fulfilment_manager
description: Reviews order and transfer execution exceptions.
allowed-tools:
workflow_label: Omnichannel Fulfilment — manager
external_event: fulfilment_manager_decision
decision_policy: |
    payload = (context or {}).get("request") or {}
    value_raw = payload.get("amount_gbp") or payload.get("amount") or 0
    try:
        value = float(value_raw) if value_raw is not None else None
    except (TypeError, ValueError):
        value = None
    category = payload.get("category") or "fulfilment"
    action = (context or {}).get("action") or "fulfilment_manager_decision"
    auth = authority_check(
        role="fulfilment_manager",
        action=action,
        value=value,
        category=category,
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Fulfilment Manager

Prefer reversible reroute or split fulfilment. Require explicit customer and order
IDs for cancellation, and escalate spend beyond delegated authority.
