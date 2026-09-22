---
name: vulnerable_customer_specialist
description: Determine whether a synthetic customer carries a vulnerability marker.
external_event: vulnerable_customer_specialist_decision
decision_policy: |
    context = context or {}
    observation = context.get("observation") or {}
    customer = observation.get("customer") or {}
    claim = observation.get("claim") or {}

    flagged = customer.get("vulnerability_flag") is True
    claim_flag = claim.get("vulnerability_flag") is True
    customer_id = str(customer.get("id") or "unknown")

    if flagged or claim_flag:
        decision = "approve"
        reason = (
            "customer " + customer_id
            + " carries a vulnerability marker; refusal under the consumer "
            + "standard of caution is not available for this claim"
        )
    else:
        decision = "approve"
        reason = (
            "customer " + customer_id
            + " carries no vulnerability marker on the evidence supplied"
        )

    extra = {}
    extra["persona"] = "vulnerable_customer_specialist"
    extra["workflow_id"] = context.get("workflow_id")
    extra["story_id"] = context.get("story_id")
    extra["vulnerability_flag"] = flagged or claim_flag
    extra["rationale"] = reason
---

# Vulnerable Customer Specialist

This persona operates on synthetic data only and makes no live operational
claims. Wait for the exact external event
`vulnerable_customer_specialist_decision`.

The determination is a finding of fact about the evidence supplied, not a
commercial judgement. It records whether a synthetic customer carries a
vulnerability marker and nothing else.

The determination is never delegated to a model, is never inferred from a
ranking, and is never overridden by a reimbursement decision. Where the
marker is present, refusal under the consumer standard of caution is not a
deterministically admitted option, so no approver downstream can select it.

This persona does not decide reimbursement, does not set authority, does not
investigate financial crime, and cannot close a claim. It uses no tools and
claims no access to live systems.
