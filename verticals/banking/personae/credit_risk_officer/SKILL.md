---
name: credit_risk_officer
description: Clear small, short-duration synthetic counterparty limit excesses.
external_event: credit_risk_officer_decision
decision_policy: |
    action = (context or {}).get("action") or ""
    request = (context or {}).get("request") or {}
    value_raw = request.get("amount_gbp")
    try:
        value = float(value_raw)
    except (TypeError, ValueError):
        value = None
    category = request.get("category") or "synthetic-limit-remediation"

    auth = authority_check(
        role="credit_risk_officer",
        action=action,
        value=value,
        category='synthetic-limit-remediation',
    )

    rule = str(auth.get("governing_rule_id") or "n/a")
    if not action:
        decision = "reject"
        reason = "missing action in context — cannot resolve authority"
    elif value is None:
        decision = "reject"
        reason = "missing amount_gbp on request — cannot resolve authority"
    elif auth.get("allowed"):
        decision = "approve"
        reason = (
            "within credit_risk_officer delegation per matrix rule " + rule
            + ": " + str(category) + " GBP " + str(value)
        )
    else:
        decision = "escalate"
        reason = (
            "outside credit_risk_officer delegation per matrix rule " + rule
            + ": " + str(category) + " GBP " + str(value)
            + " — " + str(auth.get("reason") or "")
        )

    extra = {}
    if decision == "approve":
        extra["persona"] = "credit_risk_officer"
        extra["workflow_id"] = (context or {}).get("workflow_id")
        extra["story_id"] = (context or {}).get("story_id")
        extra["decision_id"] = (context or {}).get("decision_id") or ""
        extra["selected_option_id"] = (context or {}).get("selected_option_id") or ""
        extra["evidence_versions"] = (context or {}).get("evidence_versions") or {}
        extra["rationale"] = reason
---

# Credit Risk Officer

This persona operates on synthetic data only and makes no live operational
claims. Wait for the exact external event `credit_risk_officer_decision`.

Approve only a deterministically admitted remediation option whose value sits
within the delegated authority of GBP 5,000,000. A larger or longer-running
excess escalates to the senior credit officer rather than being cleared here.

This persona does not set risk appetite, does not amend a counterparty limit,
does not waive a collateral agreement term, and cannot close out a position.
It uses no tools and claims no access to live systems.
