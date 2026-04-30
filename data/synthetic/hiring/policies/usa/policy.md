# USA hiring policy bundle (synthetic)

Used by POC2 Phase 8 (Compliance) when `position.jurisdiction == "USA"`. The
`jurisdiction-router` skill loads only this bundle on USA hires; the DE bundle
under `../de/policy.md` is loaded only for DE.

The two bundles diverge — that divergence is the §4.10 demo: same code path,
swap policy bundle, watch the workflow add a Compliance step (BetrVG works-
council notification) on DE without touching code.

---

## §EEOC.1 — Equal Employment Opportunity statement

Every JD must include the WPP EEO statement: "WPP is an equal opportunity
employer. All qualified applicants receive consideration for employment
without regard to race, color, religion, sex, sexual orientation, gender
identity, national origin, disability, or veteran status."

Surface: JD body, careers-site posting, offer letter footer.

## §EEOC.2 — Right-to-work verification

Acceptable `right_to_work.evidence` values for hires in the USA:
- `us_citizen`
- `green_card`
- `h1b` (with current sponsor + expiry on file)
- `f1_opt` (only if start date ≤ OPT end)

Block the offer if `evidence == "unknown"`. The HR BP is the operator who
resolves this — surfaces as a Phase 8 blocker, not a Phase 9 gate.

## §EEOC.3 — Compensation band disclosure

JDs published in CA, CO, NY, WA must disclose the comp band on the public
posting. Other states optional but encouraged.

## §EEOC.4 — Visa thresholds

H1B sponsorship triggers a Finance BP review at the budget phase: total
sponsorship cost (legal + filing) is added to the position's first-year
envelope. Threshold for "needs Finance BP HITL" stays at £10k delta vs band
midpoint as in the default flow.

## §EEOC.5 — Notice periods

USA: at-will employment, no statutory notice required from either side.
Standard offer letter encodes 2-week professional courtesy notice.

## §EEOC.6 — Background check timing

Background check runs *after* offer acceptance, not before. The offer letter
language must state the offer is "contingent on satisfactory background
check completion".

## §EEOC.7 — Works-council notification

Not applicable in the USA. (DE bundle has the BetrVG §99 equivalent.)
