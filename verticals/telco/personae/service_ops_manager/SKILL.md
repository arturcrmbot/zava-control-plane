---
name: service_ops_manager
description: Approves exceptional Telco service, field and fulfilment actions.
allowed-tools:
workflow_label: Service Operations — manager
external_event: service_ops_manager_decision
decision_policy: |
    request = (context or {}).get("request") or {}
    value_raw = request.get("amount_gbp") or request.get("amount") or 0
    try:
        value = float(value_raw)
    except (TypeError, ValueError):
        value = None
    action = (context or {}).get("action") or "service_ops_manager_decision"
    auth = authority_check(
        role="service_ops_manager",
        action=action,
        value=value,
        category=request.get("category") or "service_operations",
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Service Operations Manager

Approve only evidenced, feasible actions within registered authority.
