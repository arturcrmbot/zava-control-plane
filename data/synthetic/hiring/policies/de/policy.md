# Germany hiring policy bundle (synthetic, BetrVG-aligned)

Used by POC2 Phase 8 (Compliance) when `position.jurisdiction == "DE"`. The
`jurisdiction-router` skill dispatches to `betrvg_check` on DE hires; this
bundle drives the rule lookups.

Diverges from `../usa/policy.md` on §99 works-council notification, AGG
non-discrimination breadth, and statutory notice periods. The §4.10 demo
flips the country flag USA → DE and watches the workflow grow a Compliance
step without code changes.

---

## §AGG.1 — Allgemeines Gleichbehandlungsgesetz statement

Every JD must include the §11 AGG-compliant non-discrimination clause:
"Wir freuen uns über Bewerbungen unabhängig von Geschlecht, ethnischer
Herkunft, Religion, Behinderung, Alter oder sexueller Identität (gem. AGG)."

The English translation appears in the same JD if the role is bilingual.

## §AGG.2 — Gendered job titles

JD title must use either gender-neutral form ("Engineer (m/w/d)") or both
masculine and feminine forms. Pure masculine titles trigger a §AGG.2 block at
Phase 2 JD-drafter; the validator returns `ok: false` with the reason
`gendered_title_violation`.

## §BetrVG.99 — Works-council co-determination notification

Hires in DE legal entities require a §99 BetrVG notification to the local
works council before the offer is sent. Notification carries:
- Position id + level + cost centre
- Candidate's name + start date target
- Comp band (not the negotiated number)
- Internal-vs-external sourcing breakdown for the role

The works council has 7 calendar days to object. The orchestrator's Phase 9
HITL on `offer_approval` MUST NOT fire until either:
- The works council has assented, or
- The 7-day window has lapsed without objection.

`betrvg_check` in `mocks/servicenow-mcp` returns `{status: "assented"}` for
the demo path. A real integration would be Microsoft Graph webhook → WorksCouncil
mailbox.

## §BetrVG.111 — Larger restructure notification

Not triggered by individual hires — only relevant when more than 20% of the
DE legal entity's headcount changes in a 12-month window. POC2 ignores this.

## §KSchG.1 — Notice periods

DE statutory notice scales with tenure (1 month after probation, then up to
7 months for >20-year tenure). Offer letter pulls the right number from the
position record at draft time.

## §EEOC.7 equivalent — Right-to-work verification

Acceptable `right_to_work.evidence` values for hires in DE:
- `eu_citizen`
- `blue_card` (with current employer name + visa expiry)
- `niederlassungserlaubnis` (permanent settlement permit)

`unknown` blocks the offer at Phase 8 the same way as USA.

## §AVE.1 — Tarifvertrag binding

If the role's cost centre is covered by a Tarifvertrag (collective wage
agreement), the comp band must respect the relevant Lohngruppe minimum. This
appears as a `comp_band_lookup` validator in Phase 9.
