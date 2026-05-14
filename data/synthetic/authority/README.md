# Delegated Authority Matrix

Single source of truth for "who is allowed to approve what, up to which value, in which scope".
Consumed by the [`delegated_authority`](../../../api/server/mcp_tools/delegated_authority.py)
MCP tool, which proxies to the [`authority-mcp`](../../../mocks/authority-mcp/)
Node mock (port 4108).

## Why this exists

Before this matrix landed, every approval threshold lived inline in a persona's
`decision_policy` (e.g. `abs(delta) > 10000` in `finance_bp`, `>25%` price-jump
in `contract_finance_bp`). Authority changes meant code edits. Adding a new
business unit / geography / category meant per-persona work.

The matrix collapses all of that into one ordered ruleset. Personae stop carrying
threshold values; they delegate every "is this approver allowed to sign off?"
question to the authority MCP, and just decide whether the *facts* match the
*rule*.

## Rule schema

Each entry in `matrix.json` is one object with these fields:

| Field             | Type                              | Meaning                                                             |
|-------------------|-----------------------------------|---------------------------------------------------------------------|
| `rule_id`         | string                            | Stable identifier, surfaced in resolution responses for traceability |
| `action`          | string (snake_case)               | What is being approved (e.g. `expense_claim_approval`)               |
| `category`        | string \| `"*"`                  | Sub-classification of the action; `"*"` matches anything             |
| `value_band_gbp`  | `{min: number\|null, max: number\|null}` | Inclusive value range; `null` on either bound = unbounded; both `null` = non-monetary action |
| `business_unit`   | string \| `"*"`                  | Scope filter; `"*"` matches anything                                 |
| `geography`       | string \| `"*"`                  | Scope filter; `"*"` matches anything                                 |
| `requester_role`  | string \| `"*"`                  | Optional filter on who is asking; `"*"` matches anything             |
| `approver_role`   | string                            | Persona role that owns the decision (matches `api/server/personae/<role>/`) |
| `escalation_chain`| `string[]`                        | Ordered fallback approvers if primary defers                         |
| `basis`           | string                            | Human-readable rationale, surfaced to operators and auditors         |

## Precedence

**First match wins.** The resolver walks `matrix.json` top-to-bottom. The first rule whose
non-wildcard fields all match the request — and whose `value_band_gbp` contains the
request's `value` — is returned. If no rule matches, the resolver returns
`{matched: false, reason: "no rule matched"}` and the caller is expected to
escalate to a default operator surface.

This means **specificity matters and ordering matters**. More specific rules
(e.g. `business_unit: "production", geography: "AMER"`) must appear *before*
their wildcard equivalents in the file. Two `DEFAULT-*` rules at the bottom
catch any expense or perf-calibration category not otherwise enumerated.

## Wildcards

`"*"` is a literal match-anything sentinel. Used for:

- `category` when an action's behaviour is the same across all sub-classifications.
- `business_unit` and `geography` when a rule is global.
- `requester_role` when the rule is independent of who is asking.

For `value_band_gbp`, "wildcard" is expressed by setting `min: null, max: null`
on a non-monetary action, or one bound `null` for "open at this end".

## Live editing

The Node mock exposes `POST /reload` which re-reads `matrix.json` from disk. Use
this during demos to show authority changes taking effect without a restart.
The Python MCP tool wrapper does *not* cache rule data — it round-trips to the
mock on every call — so a `/reload` is the only step.

## Reading the resolution

A successful `resolve_approver` call returns:

```json
{
  "matched": true,
  "approver_role": "ssc_reviewer",
  "threshold_gbp": 2500,
  "escalation_chain": ["finance_controller"],
  "rule_id": "EXP-003",
  "basis": "Material meals expense; SSC reviewer applies policy + cross-checks receipts."
}
```

`threshold_gbp` is the upper bound of the matched band (or `null` for open-ended /
non-monetary). It exists so callers can render "approve up to £2,500" UI copy
without re-reading the matrix.

## Worked examples — one per existing domain

| Domain (workflow_type)   | Sample request                                                                                              | Matched rule        | Approver           |
|--------------------------|-------------------------------------------------------------------------------------------------------------|---------------------|--------------------|
| `expense-claim`          | meals, £180, EMEA, creative                                                                                 | `EXP-002`           | `line_manager`     |
| `expense-claim`          | client_entertainment, £900, AMER, media                                                                     | `EXP-021`           | `ssc_reviewer`     |
| `travel-preapproval`     | international, £4,200, APAC, data                                                                           | `TRV-011`           | `finance_controller` |
| `travel-preapproval`     | client_pitch, £3,800, EMEA, consulting                                                                       | `TRV-020`           | `account_director` |
| `vendor-kyc`             | high_risk (sanctions watchlist hit on UBO)                                                                   | `VKY-003`           | `contracts_counsel` |
| `contract-renewal`       | flat_renewal, £180,000                                                                                       | `CRN-002`           | `contract_finance_bp` |
| `contract-renewal`       | price_jump, £35,000                                                                                          | `CRN-010`           | `contract_finance_bp` |
| `it-access-request`      | privileged_role (global admin)                                                                               | `ITAR-003`          | `it_access_it_admin` |
| `employee-onboarding`    | external_contractor                                                                                          | `ONB-003`           | `onboarding_it_admin` |
| `perf-review`            | calibration_outlier (>2 bands shift)                                                                         | `PRR-002`           | `perf_review_hr_bp` |
| `hiring`                 | hire_budget_approval, within_band, delta £8,000                                                              | `HIRE-BUDGET-002`   | `finance_bp`       |
| `hiring`                 | hire_budget_approval, within_band, delta £12,500                                                             | `HIRE-BUDGET-003`   | `finance_controller` |
| `hiring`                 | hire_offer_approval, standard_offer, £95,000                                                                 | `HIRE-OFFER-002`    | `hr_bp`            |
| `hiring`                 | hire_offer_approval, executive_offer, £220,000                                                               | `HIRE-OFFER-010`    | `comp_ben_analyst` |

## Forward-looking actions

The matrix also contains rules for actions whose domains haven't been composed
yet (`ap_invoice_approval`, `purchase_order_approval`, `contract_review_signoff`,
`privacy_dpia_signoff`, `internal_mobility_approval`, `offboarding_signoff`,
`incident_triage_signoff`, `access_recertification_signoff`, `pitch_resourcing_approval`,
`treasury_fx_hedge`). These exist so the matrix and the persona library
*precede* the domains that will use them — when the next dozen domains are
composed via `compose-domain`, the authority resolution path is already in place.

## Engagement-POC swap

This file is the lab seed. In an engagement-POC, the matrix MCP backend is
replaced with a Foundry IQ index over the customer's real delegated-authority
register. The MCP-tool contract on the Python side is unchanged.
