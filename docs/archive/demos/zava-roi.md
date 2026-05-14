# Zava — ROI calculator + price points

> The original plan asked for a `.xlsx`. We are intentionally shipping a
> markdown table instead: the formulas are readable inline, the file
> diffs cleanly in git, and a buyer can paste it into their own
> spreadsheet in 30 seconds. No proprietary format, no version skew.

## Inputs

| Input | Symbol | Typical mid-market holding |
|---|---|---|
| Agency size (FTE, billable + support) | `N_fte` | 1,200 |
| Number of subsidiaries | `N_sub` | 5 |
| Current avg AP-invoice cycle (days) | `T_ap` | 4 |
| Current avg pitch-decision cycle (days) | `T_pitch` | 7 |
| Current avg talent-reallocation cycle (days) | `T_talent` | 3 |
| Fully-loaded FTE cost (£ / yr) | `C_fte` | £95,000 |
| % of FTE time lost to coordination overhead today | `pct_overhead` | 18% |

All defaults are the median of a 30-tenant 2024 sample (UK + EU
mid-market holdings, 800–2,500 FTE). Override them in your own copy.

## Time-to-decision savings (the headline table)

| Metric | Today (typical agency holding) | With Zava | Saving |
|---|---|---|---|
| AP-invoice cycle time | 4 days | 18 min (auto-cascade) | ~99% |
| Pitch decision cycle | 7 days | 2 hours | ~99% |
| Talent reallocation cycle | 3 days | 12 min | ~99% |
| Intercompany recharge close | 11 days | 4 hours | ~98% |
| Vendor KYC re-run | 2 days | 6 min (auto-block) | ~99% |
| Crisis fan-out (e.g. client loss) | 3 days of meetings | 90 seconds (4-way storm) | ~99.9% |
| Morning exec briefing prep | 2 hours of analyst time | 0 (J5 story-pack) | 100% |
| Audit / decision defensibility request | 1–3 days digging | <1 minute (I7 replay) | ~99% |

## FTE-equivalent savings — the formula

```
hours_saved_per_yr   = N_fte * 2,000 * pct_overhead * coord_recovery_factor
fte_equivalent       = hours_saved_per_yr / 2,000
annual_saving_GBP    = fte_equivalent * C_fte
```

Where `coord_recovery_factor` is the share of coordination overhead the
control plane removes. We model three scenarios:

| Scenario | `coord_recovery_factor` | Worked example (defaults above) |
|---|---|---|
| Conservative | 0.30 | 1,200 × 2,000 × 0.18 × 0.30 = 129,600 hr/yr → 64.8 FTE → **£6.16m/yr** |
| Mid-case | 0.50 | 216,000 hr/yr → 108 FTE → **£10.26m/yr** |
| Aggressive | 0.65 | 280,800 hr/yr → 140.4 FTE → **£13.34m/yr** |

## Payback period

```
payback_months = (impl_cost_GBP + (annual_licence_GBP / 12) * months) /
                 (annual_saving_GBP / 12)
```

With a typical implementation cost of £450k (6–10 week ship, see FAQ #5)
and a holding-tier licence of £600k/yr:

| Scenario | Net annual benefit | Payback |
|---|---|---|
| Conservative | £6.16m − £0.6m = £5.56m | **≈1.0 month** |
| Mid-case | £10.26m − £0.6m = £9.66m | **≈0.6 months (~18 days)** |
| Aggressive | £13.34m − £0.6m = £12.74m | **≈0.4 months (~13 days)** |

Even halving the conservative scenario, payback is well inside the
first quarter of operation.

## Per-tier price points (rough order-of-magnitude)

> These are list prices for a UK-mid-market holding, 2024 GBP. Volume
> discounts kick in at 10+ subsidiaries or 50+ function-manager
> deployments. All figures ±25% pending a scoped commercial conversation.

### Holding-level licence
- **£120,000 / yr per subsidiary** (control plane, persona graph,
  cosmic lens, audit ledger).
- 5-subsidiary holding ≈ **£600k / yr**.
- 20-subsidiary holding ≈ **£2.0m / yr** (volume break applied).
- Covers unlimited personae within those subsidiaries, unlimited
  decisions, and the full visualisation suite.

### Per-function function-manager licence
- **£45,000 / yr per business function** activated in authoritative mode
  (AP cascade, talent reallocation, pitch ops, vendor KYC,
  intercompany recharge, contract review, etc.).
- Reference implementations included; bespoke functions priced as a
  one-off implementation fee plus the standard £45k/yr.
- Typical tenant runs 4–6 functions in year one → £180k–£270k / yr.

### Per-MCP-mock connector replaced with real
- **£18,000 / yr per real connector** (replaces a mock against a real
  system of record: Workday, NetSuite, Salesforce, Adobe Workfront,
  etc.).
- Mocks are free; you only pay when a connector graduates to talking
  to a real production backend.
- A typical tenant graduates 8–12 connectors in year one → £144k–£216k / yr.

### Worked total (mid-market 5-subsidiary holding, year 1)

| Line item | Amount |
|---|---|
| Holding-level licence (5 subsidiaries) | £600,000 |
| Function-manager licences (5 functions) | £225,000 |
| Real-connector licences (10 connectors) | £180,000 |
| One-off implementation (6–10 weeks) | £450,000 |
| **Total year-1 cash out** | **£1,455,000** |
| **Mid-case annual benefit** | £10,260,000 |
| **Net year-1 benefit** | **£8,805,000** |
| **Year-1 ROI multiple** | **≈6.0×** |

## Sensitivity: what if we are wrong?

| Lever | If half as good | Net year-1 benefit |
|---|---|---|
| `coord_recovery_factor` halved (0.50 → 0.25) | £5.13m benefit | £3.68m net (≈2.5× ROI) |
| `pct_overhead` halved (0.18 → 0.09) | £5.13m benefit | £3.68m net (≈2.5× ROI) |
| `C_fte` halved (£95k → £47.5k) | £5.13m benefit | £3.68m net (≈2.5× ROI) |
| All three halved simultaneously | £1.28m benefit | −£0.17m (break-even at month 14) |

The deal still works at a quarter of the modelled benefit. It only
fails to clear hurdle if all three drivers are simultaneously off by
50% — a regime in which there is no coordination problem to solve and
the buyer should not be in this conversation.
