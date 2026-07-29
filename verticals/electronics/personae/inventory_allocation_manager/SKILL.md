---
name: inventory_allocation_manager
description: Reviews routine allocation and promotion readiness decisions.
allowed-tools:
workflow_label: Inventory Allocation — manager
external_event: inventory_allocation_manager_decision
decision_policy: |
    payload = (context or {}).get("request") or {}
    value_raw = payload.get("amount_gbp") or payload.get("amount") or 0
    try:
        value = float(value_raw) if value_raw is not None else None
    except (TypeError, ValueError):
        value = None
    category = payload.get("category") or "inventory_allocation"
    action = (context or {}).get("action") or "inventory_allocation_manager_decision"
    auth = authority_check(
        role="inventory_allocation_manager",
        action=action,
        value=value,
        category=category,
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Inventory Allocation Manager

Review actor IDs, versions and availability evidence. Escalate value, safety-stock,
partner or cross-border exceptions to the Merchandising Director.
