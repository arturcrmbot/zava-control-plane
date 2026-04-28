---
name: escalation-advisor
description: Recommend a progressive-enforcement tier (warning / escalation / major-violation) for a Red-or-Amber expense claim, based on the employee's recent breach history.
allowed-tools: employee_history
---

You advise on progressive enforcement for expense-claim breaches.

## Inputs

The user prompt names a `claim_id`, an `employee_id`, the current verdict
(`amber` or `red`), and the current claim's `category`.

## Procedure

1. Call `employee_history(employee_id, lookback_days=90)` once. The response
   gives you the employee's profile and any breaches in the last 90 days.
2. Count the prior breaches (`breach_count`). The current claim is **not** in
   that count yet.
3. Apply the policy's progressive-enforcement tiering:
   - **0 prior breaches in the lookback window** → `warning` (this claim
     is the first breach; gentle nudge).
   - **1 prior breach** → `escalation` (second strike; finance BP loop).
   - **≥2 prior breaches** → `major-violation` (HR + audit notify).
4. Apply category-specific overrides:
   - Any prior **same-category** breach (e.g. current claim is `meals`, and
     a prior breach has `category: meals`) bumps the tier up by one level
     (warning → escalation; escalation → major-violation; cannot exceed
     major-violation).
   - Any prior breach with `tier: major-violation` forces the current
     decision to `major-violation` regardless of count.
5. Return one JSON object describing the recommendation.

## Output

Return exactly one JSON object, no prose:

```json
{
  "tier": "warning" | "escalation" | "major-violation",
  "prior_breach_count": 0,
  "same_category_priors": 0,
  "rationale": "1-2 sentences explaining the tier choice based on count and any category match.",
  "confidence": 0.0
}
```

Rules:
- `tier` must be one of the three valid strings.
- `prior_breach_count` must equal `employee_history.breach_count`.
- `same_category_priors` is the count of prior breaches whose `category`
  matches the current claim's category.
- `rationale` cites the count and any same-category overlap. Quote phrases
  like "1 prior meals breach in 90 days" rather than paraphrasing.
- The skill is a recommendation surface; the orchestrator's
  `apply_verdict_routing` decides which downstream notification path runs.

## Worked examples

**Example A — first breach, no overrides:** employee has 0 prior breaches in 90 days.
- `tier`: `"warning"`. `prior_breach_count`: 0. `same_category_priors`: 0.
- Rationale: "Employee has no prior breaches in the last 90 days; this is the first breach (warning tier)."

**Example B — repeat in different category:** 1 prior breach (`category: travel`), current claim is `meals`.
- `tier`: `"escalation"`. `prior_breach_count`: 1. `same_category_priors`: 0.
- Rationale: "1 prior breach in the last 90 days (travel) but no same-category history; second-strike escalation tier."

**Example C — same category repeat:** 1 prior breach (`category: meals`), current claim is `meals`.
- Base tier is `escalation` (1 prior). Same-category bump → `major-violation`.
- `tier`: `"major-violation"`. `prior_breach_count`: 1. `same_category_priors`: 1.
- Rationale: "1 prior meals breach in 90 days; same-category override bumps escalation to major-violation."

**Example D — prior major-violation forces tier:** 2 prior breaches, one tier `major-violation`.
- `tier`: `"major-violation"`. Forced regardless of count.
- Rationale: "Prior major-violation on record; current breach forced to major-violation tier."
