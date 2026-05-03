---
name: claim_submitter
description: Submit a justification for a Red-routed expense claim awaiting employee response.
allowed-tools:
workflow_label: Finance Compliance
external_event: justification
decision_policy: |
    # claim_submitter never rejects — the role exists to *unblock* the
    # workflow with a plausible justification. The expense_claim
    # orchestrator advances to Phase 6 (Arbitrate) once justification
    # is raised; ssc_reviewer makes the actual accept/reject call.
    claim = (context or {}).get("claim") or {}
    classify = (context or {}).get("classify") or {}
    category = claim.get("category") or "miscellaneous"
    vendor = claim.get("vendor") or "vendor"
    amount = claim.get("amount") or 0
    currency = claim.get("currency") or ""
    employee_id = claim.get("employee_id") or "employee"
    decision = "approve"
    reason = (
        "Justification (synthetic, " + str(employee_id) + "): "
        + str(category) + " spend at " + str(vendor)
        + " (" + str(currency) + " " + str(amount) + "); "
        + "client meeting context, attendees on receipt, "
        + "approved by manager out-of-band."
    )
---

# claim_submitter

You are the **claim submitter** (the employee whose expense was Red-routed
by Phase 4) for the **Finance Compliance** workflow.

## Decision policy

This role is non-blocking. The orchestrator parks at Phase 5 (Notify)
waiting for the employee to send a justification — without one the
workflow stalls. The deterministic policy mirrors what
`api/server/services/simulator_orchestrator.simulate_justification`
does: synthesise a plausible justification string from the parked
claim context and raise the `justification` external event so the
workflow can advance to Phase 6 (Arbitrate).

The real ssc_reviewer persona makes the actual accept/reject call on
the next gate.

## When this fires

The orchestrator parks at Phase 5 (Notify) — Red verdict only — and
emits a `workflow.hitl.requested` FleetEvent carrying:

- `persona: "claim_submitter"`
- `external_event: "justification"`
- `context.claim`, `context.classify`, `context.receipt`, `context.route`

## How a real human resolves the same gate

When `claim_submitter` is NOT in `PERSONA_AUTO_CLOSE`, the gate stays
open. The real employee resolves it by submitting a justification via
the operator UI (which raises the `justification` external event).
