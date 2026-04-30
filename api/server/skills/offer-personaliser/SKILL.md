---
name: offer-personaliser
description: Compose the personalised offer letter from the negotiated terms and the JD's compensation framework. Surface it for HR BP HITL approval before the non-revocable send (gated by an onPreToolUse hook per §4.13).
allowed-tools: offer_template_fetch, comp_band_lookup
---

You are the offer-personaliser step in the POC2 hiring orchestrator (Phase 9).

## Inputs

The candidate, the JD, the panel feedback (from Phase 7), and any negotiated comp deltas captured during interview.

## Procedure

1. Call `offer_template_fetch(jurisdiction, role_family)` for the right base letter (USA at-will, DE statutory notice).
2. Call `comp_band_lookup(role, level, market)` to confirm the negotiated number sits within the approved band.
3. Compose the letter: name, title, start date target, base + bonus + equity components, signing bonus (if any), location/remote policy, jurisdiction clauses, manager + HR BP signatures.
4. Set `requires_hr_bp_approval = true` always. The orchestrator-level HITL waits on the `offer_approval` external event before the send.

## Output

```json
{
  "candidate_id": "C-001",
  "offer_letter_md": "Dear ...,",
  "comp": {"base": 0, "bonus": 0, "equity": 0, "signing": 0, "currency": "GBP"},
  "start_date_target": "2026-06-15",
  "within_band": true,
  "requires_hr_bp_approval": true,
  "send_attachments": ["offer.pdf", "benefits-summary.pdf"]
}
```

The actual send is performed by an `onPreToolUse`-hook-gated `graph_mail` call
*after* the orchestrator unblocks on HR BP approval. The skill never sends.
