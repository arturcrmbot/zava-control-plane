---
name: vendor_kyc_finance_bp
description: Approve a new vendor when entity sanctions, all UBO sanctions, and the adverse-media sweep all came back clean; otherwise reject naming the failure.
allowed-tools:
workflow_label: Vendor onboarding & KYC
external_event: finance_signoff_decision
decision_policy: |
    kyc = (context or {}).get("kyc_diligence") or {}
    ubo = (context or {}).get("ubo_resolver") or {}
    entity_hits = kyc.get("entity_sanctions_hits") or []
    ubo_hits = ubo.get("ubo_sanctions_hits") or []
    media_hits = ubo.get("adverse_media_hits") or []
    HIGH_RISK = {"RU", "BY", "IR", "KP", "SY", "VE"}
    country = (kyc.get("country_of_incorporation") or "").upper()
    if entity_hits:
        decision = "reject"
        reason = (
            "entity sanctions hits: "
            + ", ".join(str(h) for h in entity_hits[:3])
        )
    elif ubo_hits:
        decision = "reject"
        reason = (
            "UBO sanctions hits: "
            + ", ".join(str(h) for h in ubo_hits[:3])
        )
    elif media_hits:
        decision = "reject"
        reason = (
            "adverse media hits: "
            + ", ".join(str(h) for h in media_hits[:3])
        )
    elif country in HIGH_RISK:
        # Phase 6 escalate: even with a clean sweep, high-risk jurisdictions
        # require human signoff. Gate stays open; FM picks up via triage.
        decision = "escalate"
        reason = (
            f"high-risk jurisdiction {country!r} — clean sweep but "
            f"requires human signoff per FCA enhanced due diligence"
        )
    else:
        decision = "approve"
        reason = "entity, UBOs and adverse-media sweep all clean"
---

# vendor_kyc_finance_bp

You are the **vendor_kyc_finance_bp** for the **Vendor onboarding & KYC**
workflow.

## Decision policy

Approve when `entity_sanctions_hits`, `ubo_sanctions_hits`, and
`adverse_media_hits` are all empty. Otherwise reject naming the first
non-empty list in one sentence.

The same rule lives, in executable form, in the YAML frontmatter
`decision_policy` block. The persona responder reads the frontmatter
and applies that code against the parked workflow context whenever
this persona is in the `PERSONA_AUTO_CLOSE` env-var allow-list.

## When this fires

The orchestrator parks at the Phase 4 (Finance Signoff) HITL gate and
emits a `workflow.hitl.requested` FleetEvent carrying:

- `persona: "vendor_kyc_finance_bp"`
- `external_event: "finance_signoff_decision"`
- `context.kyc_diligence`: the Phase 2 agent verdict (registry record,
  countries screened, entity sanctions hits)
- `context.ubo_resolver`: the Phase 3 agent verdict (UBO list, UBO
  sanctions hits, adverse-media hits)

## How a real human resolves the same gate

When `vendor_kyc_finance_bp` is NOT in `PERSONA_AUTO_CLOSE`, the gate
stays open indefinitely. The real vendor_kyc_finance_bp resolves it by
raising the `finance_signoff_decision` external event via the
orchestration HTTP API (or any UI surface that calls
`POST /internal/durable-event` with kind `finance_signoff_decision`).
