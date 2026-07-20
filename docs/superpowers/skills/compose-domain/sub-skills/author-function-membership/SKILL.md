---
name: author-function-membership
description: |
  v4 sub-skill #4. Adds the `function:` field to the brief — the
  single canonical function-name key the new domain belongs to.
  Validates against api.shared.functions.FUNCTIONS (when Phase 3 is
  merged) or against a 10-key FUNCTIONS_PLACEHOLDER when not.
audience: design-time-only
forbidden-runtime: true
inputs:
  - brief.domain (especially description)
  - brief.phases
outputs:
  - brief.function (one of the 10 canonical keys)
hands_off_to: author-ambient-trigger
---

# author-function-membership

Pick **one** function the new domain belongs to. The valid keys are:

| key                | meaning                                                  |
|--------------------|----------------------------------------------------------|
| `finance`          | spend, vendors, AP, treasury, expense                    |
| `hr`               | hiring, onboarding, calibration, performance, travel     |
| `revenue`          | sales pipeline, customer acquisition                     |
| `ops`              | operations / fulfilment / supply chain                   |
| `legal`            | contracts review, privacy/DPIA, regulatory               |
| `marketing`        | campaigns, brand, creative                               |
| `tech`             | IT access, platform engineering                          |
| `data`             | data products, analytics, ML                             |
| `customer-success` | renewals, onboarding-after-sale, support                 |
| `legacy`           | reserved for POC1/POC2 (`expense-claim`, `hiring`)       |

## Procedure

1. Read `brief.domain.description` and `brief.phases` (intents +
   personae). Propose **one** key.
2. If two keys are plausible (e.g. employee-onboarding could be
   `hr` or `ops`) ask the operator. Do not guess.
3. Write `function: <key>` to the brief.
4. Run `validator.py:validate(brief)`. STOP on `SchemaError`.
5. Hand off to `author-ambient-trigger`.

## Validator behaviour

* If `api.shared.functions.FUNCTIONS` is importable, validate the
  key against the live registry (also rejects when the new
  workflow_type is already claimed by a *different* function).
* Else fall back to the in-file `FUNCTIONS_PLACEHOLDER` set (10
  canonical keys above). The placeholder mirrors Phase 3 TASK-001
  byte-for-byte; drift here would trip Phase 3's boot validator.

## Graduation patch

`graduate.sh` appends the new `workflow_type` to
`FUNCTIONS["<fn>"].owns_domains` in `verticals/<vertical>/functions.py`,
guarded by sentinel comments `# === BEGIN compose-domain <workflow_type> ===`
and matching END, so re-running on an already-claimed domain is a no-op.

The global `api/shared/functions.py` is a read-only active-pack compatibility
adapter: it reexports the selected pack's `verticals/<vertical>/functions.py`
registry at runtime (via `active_runtime().pack`), so authors never write to it.
Only the pack-scoped `verticals/<vertical>/functions.py` is modified.
