"""Airline Hero 3 – Preemptive Schedule Resilience constraints.

Immutable action/option/result types and deterministic admission.
Pure and deterministic – no I/O, no world mutation.

Options:
  SCHED_OPTION_BUFFER_RETIME   – retime affected sectors/slots within existing slot tolerance
  SCHED_OPTION_PREPOSITION     – pre-position reserve aircraft/crew using existing reserve resources
  SCHED_OPTION_CANCEL_LIMITED  – pre-day cancellation of one sector where constraint permits
  SCHED_OPTION_MONITOR_RISK    – explicit no-action / accepted-risk decision (GBP 0)
  SCHED_OPTION_INFEASIBLE      – deliberately infeasible (requires confidence > 0.95)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from verticals.airline.schedule_constants import (
    SCHED_AFFECTED_CREW_IDS,
    SCHED_AFFECTED_SECTOR_IDS,
    SCHED_AFFECTED_SLOT_IDS,
    SCHED_BUFFER_MINUTES,
    SCHED_CANCEL_SECTOR_ID,
    SCHED_MAX_VALUE_GBP,
    SCHED_RESERVE_AIRCRAFT_ID,
    SCHED_RESERVE_CREW_ID,
    SCHED_RISK_SIGNAL_ID,
)

# ---------------------------------------------------------------------------
# Option IDs
# ---------------------------------------------------------------------------

SCHED_OPTION_BUFFER_RETIME = "SYN-SCHED-OPTION-BUFFER-RETIME"
SCHED_OPTION_PREPOSITION = "SYN-SCHED-OPTION-PREPOSITION"
SCHED_OPTION_CANCEL_LIMITED = "SYN-SCHED-OPTION-CANCEL-LIMITED"
SCHED_OPTION_MONITOR_RISK = "SYN-SCHED-OPTION-MONITOR-RISK"
SCHED_OPTION_INFEASIBLE = "SYN-SCHED-OPTION-INFEASIBLE"

_ADMITTED_OPTIONS = frozenset({
    SCHED_OPTION_BUFFER_RETIME,
    SCHED_OPTION_PREPOSITION,
    SCHED_OPTION_CANCEL_LIMITED,
    SCHED_OPTION_MONITOR_RISK,
})

# Option costs (GBP)
_BUFFER_RETIME_VALUE_GBP = 45_000.0
_PREPOSITION_VALUE_GBP = 75_000.0
_CANCEL_LIMITED_VALUE_GBP = 110_000.0
_MONITOR_RISK_VALUE_GBP = 0.0
_INFEASIBLE_VALUE_GBP = 35_000.0

# Minimum crew duty required to retime (minutes)
_MIN_CREW_DUTY_FOR_RETIME = 30


# ---------------------------------------------------------------------------
# Immutable types
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SchedAction:
    action_type: str
    resource_id: str | None = None
    actor_id: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "action_type": self.action_type,
            "resource_id": self.resource_id,
            "actor_id": self.actor_id,
        }


@dataclass(frozen=True, slots=True)
class SchedOption:
    option_id: str
    impact: str
    value_gbp: float
    actions: tuple[SchedAction, ...]
    evidence_versions: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class SchedFeasibilityResult:
    option: SchedOption
    feasible: bool
    reasons: tuple[str, ...]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record(obs: dict[str, Any], key: str) -> dict[str, Any]:
    v = obs.get(key)
    return v if isinstance(v, dict) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    n = float(value)
    return n if math.isfinite(n) else None


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    n = float(value)
    return n if math.isfinite(n) else None


def _evidence_versions(obs: dict[str, Any]) -> tuple[tuple[str, int], ...]:
    versions = obs.get("evidence_versions")
    if not isinstance(versions, dict):
        return ()
    return tuple(
        sorted(
            (rid, v)
            for rid, v in versions.items()
            if isinstance(rid, str) and isinstance(v, int) and not isinstance(v, bool)
        )
    )


def _story_active(obs: dict[str, Any]) -> bool:
    return obs.get("sched_story_active") is True


def _bounded(value_gbp: float, obs: dict[str, Any]) -> bool:
    maximum = _num(obs.get("maximum_value_gbp"))
    return maximum is not None and 0.0 <= value_gbp <= maximum


def _all_evidence_consistent(obs: dict[str, Any]) -> bool:
    """Verify named records in the observation match their declared versions."""
    versions = obs.get("evidence_versions")
    if not isinstance(versions, dict):
        return False

    records: list[dict[str, Any]] = []
    # Risk signal
    rs = _record(obs, "risk_signal")
    if rs:
        records.append(rs)
    # Forecast constraints
    for fc in (obs.get("forecast_constraints") or []):
        if isinstance(fc, dict):
            records.append(fc)
    # Affected sectors
    for s in (obs.get("affected_sectors") or []):
        if isinstance(s, dict):
            records.append(s)
    # Affected slots
    for sl in (obs.get("affected_slots") or []):
        if isinstance(sl, dict):
            records.append(sl)
    # Affected crew
    for c in (obs.get("affected_crew") or []):
        if isinstance(c, dict):
            records.append(c)
    # Reserve resources
    res_ac = _record(obs, "reserve_aircraft")
    if res_ac:
        records.append(res_ac)
    res_crew = _record(obs, "reserve_crew")
    if res_crew:
        records.append(res_crew)

    return all(
        isinstance(r.get("id"), str) and versions.get(r["id"]) == r.get("version")
        for r in records
    )


def _evidence_is_current(obs: dict[str, Any], records: tuple[dict[str, Any], ...]) -> bool:
    versions = obs.get("evidence_versions")
    if not isinstance(versions, dict):
        return False
    return all(
        isinstance(r.get("id"), str)
        and isinstance(r.get("version"), int)
        and versions.get(r["id"]) == r["version"]
        for r in records
    )


# ---------------------------------------------------------------------------
# Per-option feasibility
# ---------------------------------------------------------------------------

def _buffer_retime_feasibility(
    obs: dict[str, Any],
    option: SchedOption,
) -> SchedFeasibilityResult:
    reasons: list[str] = []

    if not _story_active(obs):
        reasons.append("sched story not active")

    # All affected sectors must be scheduled (not cancelled)
    affected = obs.get("affected_sectors") or []
    for s in affected:
        if not isinstance(s, dict):
            continue
        if s.get("status") == "cancelled":
            reasons.append(f"sector {s.get('id')} already cancelled")

    # All affected slots must have tolerance >= buffer
    affected_slots = obs.get("affected_slots") or []
    for sl in affected_slots:
        if not isinstance(sl, dict):
            continue
        tol = _num(sl.get("tolerance_minutes"))
        if tol is None or tol < SCHED_BUFFER_MINUTES:
            reasons.append(f"slot {sl.get('id')} tolerance insufficient")

    # Affected crew must have remaining duty capacity
    affected_crew = obs.get("affected_crew") or []
    for c in affected_crew:
        if not isinstance(c, dict):
            continue
        remaining = _num(c.get("remaining_duty_minutes"))
        if remaining is None or remaining < _MIN_CREW_DUTY_FOR_RETIME:
            reasons.append(f"crew {c.get('id')} insufficient remaining duty")

    if not _all_evidence_consistent(obs):
        reasons.append("evidence versions")
    if not _bounded(option.value_gbp, obs):
        reasons.append("bounded value")

    return SchedFeasibilityResult(option, not reasons, tuple(reasons))


def _preposition_feasibility(
    obs: dict[str, Any],
    option: SchedOption,
) -> SchedFeasibilityResult:
    reasons: list[str] = []

    if not _story_active(obs):
        reasons.append("sched story not active")

    # Reserve aircraft must be in reserve status at hub
    res_ac = _record(obs, "reserve_aircraft")
    if res_ac.get("id") != SCHED_RESERVE_AIRCRAFT_ID:
        reasons.append("reserve aircraft id mismatch")
    if res_ac.get("status") != "reserve":
        reasons.append("reserve aircraft not in reserve status")
    if res_ac.get("current_station_id") != "SYN-HUB-01":
        reasons.append("reserve aircraft not at hub")

    # Reserve crew must be a reserve, not already assigned
    res_crew = _record(obs, "reserve_crew")
    if res_crew.get("id") != SCHED_RESERVE_CREW_ID:
        reasons.append("reserve crew id mismatch")
    if res_crew.get("status") not in {"reserve"}:
        reasons.append("reserve crew not in reserve status")

    # Non-overlap: reserve aircraft must not appear in any active sector
    sectors = obs.get("sectors") or []
    if isinstance(sectors, list):
        overlap_ac = any(
            isinstance(s, dict)
            and s.get("aircraft_id") == SCHED_RESERVE_AIRCRAFT_ID
            and s.get("status") not in {"cancelled", "completed"}
            for s in sectors
        )
        if overlap_ac:
            reasons.append("reserve aircraft overlap with active sector")

    # Non-overlap: reserve crew must not appear in any active sector
    if isinstance(sectors, list):
        overlap_crew = any(
            isinstance(s, dict)
            and s.get("crew_duty_id") == SCHED_RESERVE_CREW_ID
            and s.get("status") not in {"cancelled", "completed"}
            for s in sectors
        )
        if overlap_crew:
            reasons.append("reserve crew overlap with active sector")

    if not _all_evidence_consistent(obs):
        reasons.append("evidence versions")
    if not _bounded(option.value_gbp, obs):
        reasons.append("bounded value")

    return SchedFeasibilityResult(option, not reasons, tuple(reasons))


def _cancel_limited_feasibility(
    obs: dict[str, Any],
    option: SchedOption,
) -> SchedFeasibilityResult:
    reasons: list[str] = []

    if not _story_active(obs):
        reasons.append("sched story not active")

    # max_cancellations_permitted must be >= 1
    max_cancel = obs.get("max_cancellations_permitted")
    if not isinstance(max_cancel, int) or max_cancel < 1:
        reasons.append("constraint does not permit pre-day cancellation")

    # The specific cancel sector must be scheduled (not already cancelled)
    affected = obs.get("affected_sectors") or []
    cancel_sector = next(
        (s for s in affected if isinstance(s, dict) and s.get("id") == SCHED_CANCEL_SECTOR_ID),
        None,
    )
    if cancel_sector is None:
        reasons.append("cancel sector not found in affected sectors")
    elif cancel_sector.get("status") == "cancelled":
        reasons.append(f"cancel sector {SCHED_CANCEL_SECTOR_ID} already cancelled")

    # No pre-existing cancellations in the affected window sectors
    already_cancelled = sum(
        1
        for s in affected
        if isinstance(s, dict) and s.get("status") == "cancelled"
    )
    if already_cancelled > 0:
        reasons.append("pre-existing cancellations in affected window")

    if not _all_evidence_consistent(obs):
        reasons.append("evidence versions")
    if not _bounded(option.value_gbp, obs):
        reasons.append("bounded value")

    return SchedFeasibilityResult(option, not reasons, tuple(reasons))


def _monitor_risk_feasibility(
    obs: dict[str, Any],
    option: SchedOption,
) -> SchedFeasibilityResult:
    reasons: list[str] = []

    if not _story_active(obs):
        reasons.append("sched story not active")

    # Risk signal must be present and active
    rs = _record(obs, "risk_signal")
    if rs.get("id") != SCHED_RISK_SIGNAL_ID:
        reasons.append("risk signal not found in observation")
    elif rs.get("status") not in {"detected", "active"}:
        reasons.append("risk signal is not in active/detected state")

    # Value must be exactly GBP 0
    if option.value_gbp != 0.0:
        reasons.append("monitor_risk option must have GBP 0 value")

    if not _all_evidence_consistent(obs):
        reasons.append("evidence versions")

    return SchedFeasibilityResult(option, not reasons, tuple(reasons))


def _infeasible_feasibility(
    obs: dict[str, Any],
    option: SchedOption,
) -> SchedFeasibilityResult:
    """Deliberately infeasible – requires forecast confidence > 0.95 (never satisfied)."""
    reasons: list[str] = []

    if not _story_active(obs):
        reasons.append("sched story not active")

    confidence = _num(obs.get("forecast_confidence"))
    if confidence is None or confidence <= 0.95:
        reasons.append(
            "slot_override_without_backup requires forecast confidence > 0.95 "
            f"(actual: {confidence})"
        )

    # Always infeasible
    return SchedFeasibilityResult(option, False, tuple(reasons))


# ---------------------------------------------------------------------------
# Public admission entry point
# ---------------------------------------------------------------------------

def admit_schedule_options(obs: dict[str, Any]) -> tuple[SchedFeasibilityResult, ...]:
    """Deterministic, pure admission for all schedule resilience options."""
    ev = _evidence_versions(obs)

    buffer_retime = SchedOption(
        option_id=SCHED_OPTION_BUFFER_RETIME,
        impact="material",
        value_gbp=_BUFFER_RETIME_VALUE_GBP,
        actions=(
            SchedAction("retime_sector", "SYN-SECTOR-OUT-003"),
            SchedAction("retime_sector", "SYN-SECTOR-OUT-004"),
            SchedAction("update_slot", "SYN-SLOT-07"),
            SchedAction("update_slot", "SYN-SLOT-08"),
        ),
        evidence_versions=ev,
    )
    preposition = SchedOption(
        option_id=SCHED_OPTION_PREPOSITION,
        impact="material",
        value_gbp=_PREPOSITION_VALUE_GBP,
        actions=(
            SchedAction("preposition_reserve_aircraft", SCHED_RESERVE_AIRCRAFT_ID),
            SchedAction("preposition_reserve_crew", SCHED_RESERVE_CREW_ID),
        ),
        evidence_versions=ev,
    )
    cancel_limited = SchedOption(
        option_id=SCHED_OPTION_CANCEL_LIMITED,
        impact="material",
        value_gbp=_CANCEL_LIMITED_VALUE_GBP,
        actions=(
            SchedAction("cancel_sector", SCHED_CANCEL_SECTOR_ID),
            SchedAction("adjust_rotation", "SYN-ROTATION-04"),
            SchedAction("release_crew_duty", "SYN-CREW-DUTY-04"),
        ),
        evidence_versions=ev,
    )
    monitor_risk = SchedOption(
        option_id=SCHED_OPTION_MONITOR_RISK,
        impact="none",
        value_gbp=_MONITOR_RISK_VALUE_GBP,
        actions=(
            SchedAction("accept_risk", SCHED_RISK_SIGNAL_ID),
        ),
        evidence_versions=ev,
    )
    infeasible = SchedOption(
        option_id=SCHED_OPTION_INFEASIBLE,
        impact="low",
        value_gbp=_INFEASIBLE_VALUE_GBP,
        actions=(
            SchedAction("slot_override_without_backup", "SYN-SLOT-07"),
        ),
        evidence_versions=ev,
    )

    return (
        _buffer_retime_feasibility(obs, buffer_retime),
        _preposition_feasibility(obs, preposition),
        _cancel_limited_feasibility(obs, cancel_limited),
        _monitor_risk_feasibility(obs, monitor_risk),
        _infeasible_feasibility(obs, infeasible),
    )
