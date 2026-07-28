"""Deterministic virtual-time and tick primitives for the hospitality world.

No wall-clock reads; all time is measured in integer ticks. One tick represents
one hour of virtual hotel time unless overridden by the scenario.
"""
from __future__ import annotations


# Each virtual tick represents this many minutes of hotel time.
TICK_MINUTES: int = 60

# A "four-hour arrival horizon" spans this many ticks.
ARRIVAL_HORIZON_TICKS: int = 4

# Occupancy threshold that, combined with a critical asset fault, triggers
# the hero sensor. This is a synthetic demo assumption.
OCCUPANCY_TRIGGER_THRESHOLD: float = 0.90

# Minimum affected rooms before the sensor fires.
MIN_AFFECTED_ROOMS: int = 5


def tick_to_hours(tick: int) -> float:
    """Convert a virtual tick count to hours."""
    return tick * TICK_MINUTES / 60.0


def hours_to_ticks(hours: float) -> int:
    """Convert hours to the nearest whole number of ticks."""
    return round(hours * 60 / TICK_MINUTES)


def operations_risk_crossed(
    occupancy_pct: float,
    affected_rooms: int,
    has_asset_fault: bool,
) -> bool:
    """Return True when the operational-risk threshold is crossed.

    This is the pure threshold function used by the sensor.
    Deterministic; no I/O.
    """
    return (
        has_asset_fault
        and occupancy_pct >= OCCUPANCY_TRIGGER_THRESHOLD
        and affected_rooms >= MIN_AFFECTED_ROOMS
    )
