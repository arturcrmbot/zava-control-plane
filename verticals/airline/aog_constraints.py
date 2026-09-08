"""Airline Hero 2 – AOG Engineering Recovery constraints.

Immutable action/option/result types and deterministic admission.
Pure and deterministic – no I/O, no world mutation.

Options:
  AOG_OPTION_WORK_LOCAL   – approved work order + local traceable spare
  AOG_OPTION_WORK_REPO    – approved work order + repositionable traceable spare
  AOG_OPTION_SUBSTITUTE   – eligible serviceable A320/A321 substitute + schedule protection
  AOG_OPTION_UNAPPROVED   – deliberately infeasible: unapproved provider
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from verticals.airline.aog_constants import (
    AOG_AFFECTED_TAIL_ID,
    AOG_PROVIDER_ID,
    AOG_SPARE_LOCAL_ID,
    AOG_SPARE_REPO_ID,
    AOG_STORY_ID,
    AOG_SUBSTITUTE_TAIL_ID,
    AOG_THREATENED_SECTOR_ID,
)
from verticals.airline.worlds.reference_data import (
    AOG_CAPABILITY,
    AOG_PART_NUMBER,
    HUB_ID,
)

# Option IDs
AOG_OPTION_WORK_LOCAL = "SYN-AOG-OPTION-WORK-LOCAL"
AOG_OPTION_WORK_REPO = "SYN-AOG-OPTION-WORK-REPO"
AOG_OPTION_SUBSTITUTE = "SYN-AOG-OPTION-SUBSTITUTE"
AOG_OPTION_UNAPPROVED = "SYN-AOG-OPTION-UNAPPROVED"

_KNOWN_OPTIONS = frozenset({
    AOG_OPTION_WORK_LOCAL,
    AOG_OPTION_WORK_REPO,
    AOG_OPTION_SUBSTITUTE,
    AOG_OPTION_UNAPPROVED,
})

_AOG_SUBSTITUTE_CONFIGURATIONS = frozenset({"A320", "A321"})

_WORK_LOCAL_VALUE_GBP = 85_000.0
_WORK_REPO_VALUE_GBP = 95_000.0
_SUBSTITUTE_VALUE_GBP = 120_000.0
_UNAPPROVED_VALUE_GBP = 40_000.0

# Max projected AOG duration for bounded admission (minutes)
_MAX_AOG_DURATION_MINUTES = 1440  # 24 h
_MAX_SPARE_LEAD_TIME_MINUTES = 480  # 8 h


@dataclass(frozen=True, slots=True)
class AogAction:
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
class AogOption:
    option_id: str
    impact: str
    value_gbp: float
    actions: tuple[AogAction, ...]
    evidence_versions: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class AogFeasibilityResult:
    option: AogOption
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


def _all_evidence_consistent(obs: dict[str, Any]) -> bool:
    """Verify all named records in the observation match their declared versions."""
    versions = obs.get("evidence_versions")
    if not isinstance(versions, dict):
        return False
    records: list[dict[str, Any]] = []
    for key in ("technical_status", "maintenance_task", "substitute_candidate", "threatened_sector"):
        r = _record(obs, key)
        if r:
            records.append(r)
    for lst_key in ("approved_providers", "spares"):
        lst = obs.get(lst_key)
        if isinstance(lst, list):
            records.extend(r for r in lst if isinstance(r, dict))
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


def _bounded(value_gbp: float, obs: dict[str, Any]) -> bool:
    maximum = _number(obs.get("maximum_value_gbp"))
    return maximum is not None and 0.0 <= value_gbp <= maximum


def _story_active(obs: dict[str, Any]) -> bool:
    return obs.get("aog_story_active") is True


# ---------------------------------------------------------------------------
# Per-option feasibility checkers
# ---------------------------------------------------------------------------

def _work_feasibility(
    obs: dict[str, Any],
    option: AogOption,
    spare_id: str,
) -> AogFeasibilityResult:
    reasons: list[str] = []

    if not _story_active(obs):
        reasons.append("aog story not active")

    # Affected tail must be grounded
    tail = _record(obs, "technical_status")
    if tail.get("status") != "grounded":
        reasons.append("aircraft not grounded")
    if tail.get("aircraft_id") != AOG_AFFECTED_TAIL_ID:
        reasons.append("technical status aircraft mismatch")

    # Maintenance task must be open with matching capability
    task = _record(obs, "maintenance_task")
    if task.get("status") != "open":
        reasons.append("maintenance task not open")
    if task.get("required_capability") != AOG_CAPABILITY:
        reasons.append("task capability mismatch")
    if task.get("spare_part_number") != AOG_PART_NUMBER:
        reasons.append("task part number mismatch")

    # Provider: approved and capability match
    providers = obs.get("approved_providers")
    provider: dict[str, Any] | None = None
    if isinstance(providers, list):
        provider = next(
            (p for p in providers if p.get("id") == AOG_PROVIDER_ID and isinstance(p, dict)),
            None,
        )
    if provider is None or not provider.get("approved"):
        reasons.append("no approved provider")
    elif AOG_CAPABILITY not in (provider.get("capabilities") or []):
        reasons.append("provider capability mismatch")

    # Spare: traceable, available, matching part, lead time bounded
    spares = obs.get("spares")
    spare: dict[str, Any] | None = None
    if isinstance(spares, list):
        spare = next(
            (s for s in spares if s.get("id") == spare_id and isinstance(s, dict)),
            None,
        )
    if spare is None:
        reasons.append("spare not found")
    else:
        if not spare.get("traceable"):
            reasons.append("spare not traceable")
        if spare.get("status") != "available":
            reasons.append("spare not available")
        if spare.get("part_number") != AOG_PART_NUMBER:
            reasons.append("spare part number mismatch")
        lead_time = _number(spare.get("lead_time_minutes"))
        if lead_time is None or lead_time > _MAX_SPARE_LEAD_TIME_MINUTES:
            reasons.append("spare lead time exceeds bound")

    if not _all_evidence_consistent(obs):
        reasons.append("evidence versions")
    elif not _evidence_is_current(
        obs,
        tuple(r for r in [tail, task, provider, spare] if r is not None),
    ):
        reasons.append("evidence versions")

    if not _bounded(option.value_gbp, obs):
        reasons.append("bounded value")

    return AogFeasibilityResult(option, not reasons, tuple(reasons))


def _substitute_feasibility(
    obs: dict[str, Any],
    option: AogOption,
) -> AogFeasibilityResult:
    reasons: list[str] = []

    if not _story_active(obs):
        reasons.append("aog story not active")

    # Grounded tail must be grounded
    tail = _record(obs, "technical_status")
    if tail.get("status") != "grounded":
        reasons.append("aircraft not grounded")

    # Substitute must be A320/A321, reserve, at hub, not already scheduled on threatened sector
    sub = _record(obs, "substitute_candidate")
    if sub.get("id") != AOG_SUBSTITUTE_TAIL_ID:
        reasons.append("substitute candidate id mismatch")
    if sub.get("configuration") not in _AOG_SUBSTITUTE_CONFIGURATIONS:
        reasons.append("substitute configuration mismatch")
    if sub.get("status") != "reserve":
        reasons.append("substitute not in reserve status")
    if sub.get("current_station_id") != HUB_ID:
        reasons.append("substitute not at hub")

    # Threatened sector must be scheduled and reference the correct rotation
    threatened = _record(obs, "threatened_sector")
    if threatened.get("id") != AOG_THREATENED_SECTOR_ID:
        reasons.append("threatened sector id mismatch")
    if threatened.get("status") == "cancelled":
        reasons.append("threatened sector already cancelled")

    # Non-overlap: substitute must not appear in any other non-cancelled sector
    sectors = obs.get("sectors")
    if isinstance(sectors, list):
        overlap = any(
            isinstance(s, dict)
            and s.get("aircraft_id") == AOG_SUBSTITUTE_TAIL_ID
            and s.get("status") not in {"cancelled", "completed"}
            for s in sectors
        )
        if overlap:
            reasons.append("substitute aircraft overlap")

    if not _all_evidence_consistent(obs):
        reasons.append("evidence versions")
    elif not _evidence_is_current(obs, (tail, sub, threatened)):
        reasons.append("evidence versions")

    if not _bounded(option.value_gbp, obs):
        reasons.append("bounded value")

    return AogFeasibilityResult(option, not reasons, tuple(reasons))


def _unapproved_feasibility(
    obs: dict[str, Any],
    option: AogOption,
) -> AogFeasibilityResult:
    """Deliberately infeasible – unapproved provider."""
    reasons: list[str] = []

    if not _story_active(obs):
        reasons.append("aog story not active")

    providers = obs.get("approved_providers")
    unapproved_provider: dict[str, Any] | None = None
    if isinstance(providers, list):
        unapproved_provider = next(
            (p for p in providers if p.get("id") == "SYN-PROV-UNAP-001" and isinstance(p, dict)),
            None,
        )
    if unapproved_provider is None or unapproved_provider.get("approved"):
        reasons.append("no unapproved provider found")
    else:
        # Provider is unapproved – this is the infeasible reason
        reasons.append("provider not approved")

    return AogFeasibilityResult(option, False, tuple(reasons))


# ---------------------------------------------------------------------------
# Public admission entry point
# ---------------------------------------------------------------------------

def admit_aog_options(obs: dict[str, Any]) -> tuple[AogFeasibilityResult, ...]:
    """Deterministic, pure admission for all AOG recovery options."""
    ev = _evidence_versions(obs)

    work_local = AogOption(
        option_id=AOG_OPTION_WORK_LOCAL,
        impact="material",
        value_gbp=_WORK_LOCAL_VALUE_GBP,
        actions=(
            AogAction("engage_approved_provider", AOG_PROVIDER_ID),
            AogAction("reserve_spare", AOG_SPARE_LOCAL_ID),
            AogAction("open_work_order", AOG_AFFECTED_TAIL_ID),
        ),
        evidence_versions=ev,
    )
    work_repo = AogOption(
        option_id=AOG_OPTION_WORK_REPO,
        impact="material",
        value_gbp=_WORK_REPO_VALUE_GBP,
        actions=(
            AogAction("engage_approved_provider", AOG_PROVIDER_ID),
            AogAction("reposition_spare", AOG_SPARE_REPO_ID),
            AogAction("open_work_order", AOG_AFFECTED_TAIL_ID),
        ),
        evidence_versions=ev,
    )
    substitute = AogOption(
        option_id=AOG_OPTION_SUBSTITUTE,
        impact="material",
        value_gbp=_SUBSTITUTE_VALUE_GBP,
        actions=(
            AogAction("assign_substitute_aircraft", AOG_THREATENED_SECTOR_ID, AOG_SUBSTITUTE_TAIL_ID),
            AogAction("create_engineering_coordination", AOG_AFFECTED_TAIL_ID),
        ),
        evidence_versions=ev,
    )
    unapproved = AogOption(
        option_id=AOG_OPTION_UNAPPROVED,
        impact="low",
        value_gbp=_UNAPPROVED_VALUE_GBP,
        actions=(
            AogAction("engage_unapproved_provider", "SYN-PROV-UNAP-001"),
        ),
        evidence_versions=ev,
    )

    return (
        _work_feasibility(obs, work_local, AOG_SPARE_LOCAL_ID),
        _work_feasibility(obs, work_repo, AOG_SPARE_REPO_ID),
        _substitute_feasibility(obs, substitute),
        _unapproved_feasibility(obs, unapproved),
    )
