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


# ---------------------------------------------------------------------------
# Contention economics
#
# These constants turn world state into *finite* labour and service pools.
# Because command handlers mutate the same state the sensors read, consuming
# a pool in one domain genuinely starves another. All values are synthetic
# demo assumptions; none reference a real property or workforce agreement.
# ---------------------------------------------------------------------------

# Labour hours to turn one room from ``not_ready`` to ``available``.
HOUSEKEEPING_HOURS_PER_ROOM: float = 0.75

# A scheduled shift contributes this many productive hours per tick worked.
PRODUCTIVE_HOURS_PER_SHIFT_TICK: float = 1.0

# Minimum labour-hour deficit before the workforce sensor fires.
WORKFORCE_DEFICIT_HOURS_THRESHOLD: float = 2.0

# Minimum unturned rooms before the readiness sensor fires.
MIN_READINESS_GAP_ROOMS: int = 3

# Minimum arriving bookings that cannot be matched before guest service fires.
MIN_UNFULFILLABLE_ARRIVALS: int = 2

# Occupancy at or above this, with fewer ready rooms than imminent arrivals,
# is treated as commercial occupancy pressure.
OCCUPANCY_PRESSURE_THRESHOLD: float = 0.88

# Minimum shortfall between forecast and prepared covers before F&B fires.
# Calibrated above the seeded baseline maximum (14) so a normally-busy
# service does not register as an incident.
MIN_COVERS_SHORTFALL: int = 20

# Fractional deviation from baseline that counts as an energy anomaly.
ENERGY_DEVIATION_THRESHOLD: float = 0.15

# Rooms degrade this many per tick while an approval gate is left open.
DEGRADATION_ROOMS_PER_TICK: int = 2


def housekeeping_hours_required(not_ready_rooms: int) -> float:
    """Labour hours needed to bring ``not_ready_rooms`` back to available."""
    return not_ready_rooms * HOUSEKEEPING_HOURS_PER_ROOM


def labour_hours_available(scheduled_shift_ticks: int) -> float:
    """Productive labour hours offered by the scheduled shift ticks given."""
    return scheduled_shift_ticks * PRODUCTIVE_HOURS_PER_SHIFT_TICK


def workforce_deficit_crossed(required_hours: float, available_hours: float) -> bool:
    """True when labour demand outruns supply by more than the threshold."""
    return (required_hours - available_hours) >= WORKFORCE_DEFICIT_HOURS_THRESHOLD


def readiness_gap_crossed(not_ready_rooms: int, arrivals: int, ready_rooms: int) -> bool:
    """True when unturned rooms are material and arrivals outrun ready stock."""
    return (
        not_ready_rooms >= MIN_READINESS_GAP_ROOMS
        and arrivals > ready_rooms
    )


def occupancy_pressure_crossed(
    occupancy_pct: float,
    ready_rooms: int,
    arrivals: int,
) -> bool:
    """True when a full house cannot absorb its own imminent arrivals."""
    return occupancy_pct >= OCCUPANCY_PRESSURE_THRESHOLD and ready_rooms < arrivals


def covers_shortfall_crossed(forecast: int, prepared: int) -> bool:
    """True when prepared covers fall materially short of the forecast."""
    return (forecast - prepared) >= MIN_COVERS_SHORTFALL


def energy_deviation(reading_kwh: float, baseline_kwh: float) -> float:
    """Signed fractional deviation of a meter reading from its baseline."""
    if baseline_kwh <= 0:
        return 0.0
    return (reading_kwh - baseline_kwh) / baseline_kwh


def energy_anomaly_crossed(reading_kwh: float, baseline_kwh: float) -> bool:
    """True when a meter deviates from baseline beyond the threshold."""
    return abs(energy_deviation(reading_kwh, baseline_kwh)) >= ENERGY_DEVIATION_THRESHOLD
