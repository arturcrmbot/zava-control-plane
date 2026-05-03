---
name: ssc_reviewer
description: Accept or reject the SSC arbitration recommendation on a Red expense claim.
allowed-tools:
workflow_label: Finance Compliance
external_event: reviewer_decision
decision_policy: |
    # Mirror the modal pattern in the existing reviewer-decision corpus:
    # accept-justification on small meals/travel claims, reject on
    # everything else. The thresholds are deliberately conservative —
    # the demo intent is that ~70% of routed claims accept on the
    # first review, ~30% reject.
    claim = (context or {}).get("claim") or {}
    classify = (context or {}).get("classify") or {}
    arbitrate = (context or {}).get("arbitrate") or {}
    category = (claim.get("category") or "miscellaneous").lower()
    amount = float(claim.get("amount") or 0)
    currency = (claim.get("currency") or "").upper()
    rec = (arbitrate.get("recommendation") or "").lower()

    if rec == "reject":
        decision = "reject"
        reason = "agreed with arbitration recommendation: reject"
    elif category in {"meals", "travel", "accommodation"} and amount <= 500:
        decision = "approve"
        reason = (
            "accept-justification: " + category + " "
            + currency + " " + str(amount) + " within delegation"
        )
    elif category == "entertainment" and amount > 250:
        decision = "reject"
        reason = (
            "entertainment over delegation: " + currency + " " + str(amount)
        )
    elif amount > 1000:
        decision = "reject"
        reason = "amount over delegation: " + currency + " " + str(amount)
    else:
        decision = "approve"
        reason = (
            "accept-justification: " + category + " "
            + currency + " " + str(amount) + " within delegation"
        )
---

# ssc_reviewer

You are the **SSC reviewer** (Shared Service Centre operator) for the
**Finance Compliance** workflow.

## Decision policy

Accept the agent's arbitration recommendation when the claim is in a
delegated category (meals / travel / accommodation) and below £500,
OR when the agent recommended reject. Reject entertainment over £250
and any claim over £1000. Otherwise accept the justification.

This mirrors the modal accept-justification pattern in the existing
reviewer-decision corpus (`data/synthetic/labels.csv`) — small,
in-category claims accept; large or out-of-policy ones reject.

## When this fires

The orchestrator parks at Phase 6 (Arbitrate) and emits a
`workflow.hitl.requested` FleetEvent carrying:

- `persona: "ssc_reviewer"`
- `external_event: "reviewer_decision"`
- `context.claim`, `context.classify`, `context.justification`,
  `context.arbitrate`

## How a real human resolves the same gate

When `ssc_reviewer` is NOT in `PERSONA_AUTO_CLOSE`, the gate stays open
and ages on the operator queue. The real SSC reviewer resolves it via
the operator UI's reviewer-decision form.
