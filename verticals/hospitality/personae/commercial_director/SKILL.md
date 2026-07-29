---
name: commercial_director
description: Approves booking inventory plans, including cross-property moves.
workflow_label: Commercial Director
external_event: commercial_director_decision
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
    action = (context or {}).get("action") or "commercial_director_decision"
    auth = authority_check(
        role="commercial_director",
        action=action,
        value=value,
        category=request.get("category") or "occupancy_commercial",
    )
    decision = "approve" if auth.get("allowed") else "escalate"
    reason = str(auth.get("reason") or auth.get("governing_rule_id") or "")
---

# Commercial Director

Approve an inventory plan only when protected requirements stay covered and the
destination property has genuine compatible capacity in the evidence. Every
cross-property relocation needs your explicit approval. Reject stale evidence.
