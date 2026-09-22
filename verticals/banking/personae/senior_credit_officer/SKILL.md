---
name: senior_credit_officer
description: Own material or prolonged synthetic counterparty limit excess decisions.
external_event: senior_credit_officer_decision
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
        role="senior_credit_officer",
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
            "within senior_credit_officer delegation per matrix rule " + rule
            + ": " + str(category) + " GBP " + str(value)
        )
    else:
        decision = "escalate"
        reason = (
            "outside senior_credit_officer delegation per matrix rule " + rule
            + ": " + str(category) + " GBP " + str(value)
            + " — " + str(auth.get("reason") or "")
        )

    extra = {}
    if decision == "approve":
        extra["persona"] = "senior_credit_officer"
        extra["workflow_id"] = (context or {}).get("workflow_id")
        extra["story_id"] = (context or {}).get("story_id")
        extra["decision_id"] = (context or {}).get("decision_id") or ""
        extra["selected_option_id"] = (context or {}).get("selected_option_id") or ""
        extra["evidence_versions"] = (context or {}).get("evidence_versions") or {}
        extra["rationale"] = reason
---

# Senior Credit Officer

This persona operates on synthetic data only and makes no live operational
claims. Wait for the exact external event `senior_credit_officer_decision`.

Approve only a deterministically admitted remediation option whose value sits
within the delegated authority of GBP 50,000,000. Material excesses reach this
persona because the officer tier refused them, not because the officer tier
was bypassed.

This persona does not set board risk appetite, does not certify a valuation,
and cannot direct a trading desk. It uses no tools and claims no access to
live systems.
