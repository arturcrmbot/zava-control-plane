"""Deterministic causal-signal derivation for the Fashion actor world.

These are pure functions over the seeded world history and signal state. The
world evidence builder consumes them so that mutating the demand history,
customer cohort mix, inventory, or signal state changes the derived evidence
and, through the policy thresholds, the decision branch.
"""
from __future__ import annotations

from dataclasses import dataclass

# Cohort demand weighting. Customer cohort is a real multiplier on the demand a
# customer contributes, so the cohort mix of a region moves the aggregate
# signal rather than being decorative metadata.
COHORT_DEMAND_WEIGHT: dict[str, int] = {
    "premium": 4,
    "mainstream": 3,
    "value": 2,
    "occasional": 1,
}

WEEKS_IN_WINDOW = 2
DAYS_IN_WINDOW = 14
AUTO_CONFIDENCE_FLOOR = 0.7


def cohort_weight(cohort: str) -> int:
    return COHORT_DEMAND_WEIGHT.get(cohort, 1)


def daily_series(
    records,
    customers,
    *,
    sku_ids,
    region_prefix: str,
    channel: str | None = None,
) -> list[int]:
    """Cohort-weighted 14-day demand series for a SKU set / region / channel."""
    sku_set = set(sku_ids)
    totals = [0] * DAYS_IN_WINDOW
    for record in records:
        if record.sku_id not in sku_set:
            continue
        customer = customers.get(record.customer_id)
        if customer is None:
            continue
        if region_prefix and not customer.region.startswith(region_prefix):
            continue
        if channel is not None and record.channel != channel:
            continue
        if 1 <= record.day <= DAYS_IN_WINDOW:
            totals[record.day - 1] += record.quantity * cohort_weight(
                customer.cohort
            )
    return totals


def prior_week(series: list[int]) -> int:
    return sum(series[:7])


def recent_week(series: list[int]) -> int:
    return sum(series[7:])


def velocity_change(series: list[int]) -> float:
    """Fractional change of the recent week versus the prior week."""
    prior = prior_week(series)
    recent = recent_week(series)
    if prior == 0:
        return 0.0 if recent == 0 else 1.0
    return round((recent - prior) / prior, 4)


def demand_confidence(series: list[int], *, signal_active: bool) -> float:
    """Derived confidence in the demand read.

    Confidence rises with day-over-day coverage of the window and is
    corroborated by an active weather/campaign signal. With the seeded history
    and an active signal the hero clears the auto-execute floor; without the
    signal it falls below it, flipping the decision branch.
    """
    covered_days = sum(1 for value in series if value > 0)
    coverage = 0.65 * (covered_days / DAYS_IN_WINDOW)
    signal_bonus = 0.25 if signal_active else 0.0
    return round(min(1.0, coverage + signal_bonus), 4)


def weekly_demand(series: list[int]) -> float:
    total = sum(series)
    return total / WEEKS_IN_WINDOW


def weeks_of_supply(on_hand: int, series: list[int]) -> float:
    """Weeks of cover from real inventory against the weekly demand rate."""
    rate = weekly_demand(series)
    if rate <= 0:
        return float(DAYS_IN_WINDOW)
    return round(on_hand / rate, 4)


def signal_recent_share(series: list[int], recent_uplift_units: int) -> float:
    recent = recent_week(series)
    if recent <= 0:
        return 0.0
    return round(min(1.0, recent_uplift_units / recent), 4)


@dataclass(frozen=True, slots=True)
class DemandMetrics:
    series: tuple[int, ...]
    velocity_change: float
    confidence: float
    weekly_demand: float
