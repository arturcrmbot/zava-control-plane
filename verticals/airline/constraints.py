from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

_TAIL_OPTION_ID = "SYN-OPTION-TAIL-CREW-STAND"
_CANCEL_OPTION_ID = "SYN-OPTION-CANCEL"
_RETIME_OPTION_ID = "SYN-OPTION-RETIME-ONLY"
_TARGET_SECTOR_ID = "SYN-SECTOR-OUT-001"
_TAIL_ID = "SYN-TAIL-005"
_CREW_ID = "SYN-DUTY-006"
_STAND_ID = "SYN-STAND-05"
_TAIL_VALUE_GBP = 75_000.0
_CANCEL_VALUE_GBP = 145_000.0
_RETIME_VALUE_GBP = 20_000.0
_RETIME_MINUTES = 390
_REQUIRED_CREW_MARGIN_MINUTES = 90


@dataclass(frozen=True, slots=True)
class RecoveryAction:
    action_type: str
    sector_id: str
    resource_id: str | None = None
    minutes: int | None = None

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "action_type": self.action_type,
            "sector_id": self.sector_id,
            "resource_id": self.resource_id,
            "minutes": self.minutes,
        }


@dataclass(frozen=True, slots=True)
class RecoveryOption:
    option_id: str
    impact: str
    value_gbp: float
    actions: tuple[RecoveryAction, ...]
    evidence_versions: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class FeasibilityResult:
    option: RecoveryOption
    feasible: bool
    reasons: tuple[str, ...]


def _record(observation: dict[str, Any], key: str) -> dict[str, Any]:
    value = observation.get(key)
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _evidence_versions(observation: dict[str, Any]) -> tuple[tuple[str, int], ...]:
    versions = observation.get("evidence_versions")
    if not isinstance(versions, dict):
        return ()
    return tuple(
        sorted(
            (record_id, version)
            for record_id, version in versions.items()
            if isinstance(record_id, str) and isinstance(version, int) and not isinstance(version, bool)
        )
    )


def _evidence_is_current(
    observation: dict[str, Any],
    records: tuple[dict[str, Any], ...],
) -> bool:
    versions = observation.get("evidence_versions")
    if not isinstance(versions, dict):
        return False
    return all(
        isinstance(record.get("id"), str)
        and isinstance(record.get("version"), int)
        and versions.get(record["id"]) == record["version"]
        for record in records
    )


def _bounded(value_gbp: float, observation: dict[str, Any]) -> bool:
    maximum = _number(observation.get("maximum_value_gbp"))
    return maximum is not None and 0.0 <= value_gbp <= maximum


def _tail_feasibility(
    observation: dict[str, Any],
    option: RecoveryOption,
) -> FeasibilityResult:
    inbound = _record(observation, "sector")
    target = _record(observation, "outbound_sector")
    rotation = _record(observation, "rotation")
    current_aircraft = _record(observation, "outbound_aircraft")
    current_crew = _record(observation, "outbound_crew_duty")
    aircraft = _record(observation, "candidate_aircraft")
    crew = _record(observation, "candidate_crew_duty")
    slot = _record(observation, "outbound_slot")
    stand = _record(observation, "candidate_stand")
    reasons: list[str] = []

    if (
        aircraft.get("id") != _TAIL_ID
        or aircraft.get("status") != "reserve"
        or aircraft.get("current_station_id") != target.get("origin_id")
    ):
        reasons.append("aircraft availability")
    if aircraft.get("configuration") != current_aircraft.get("configuration"):
        reasons.append("aircraft configuration")

    sectors = observation.get("sectors")
    if not isinstance(sectors, list) or any(
        isinstance(sector, dict)
        and sector.get("id") != target.get("id")
        and sector.get("aircraft_id") == aircraft.get("id")
        and sector.get("status") not in {"cancelled", "completed"}
        for sector in sectors
    ):
        reasons.append("aircraft overlap")

    if crew.get("id") != _CREW_ID or crew.get("status") != "reserve" or crew.get("is_reserve") is not True:
        reasons.append("crew availability")
    if crew.get("qualification") != aircraft.get("configuration"):
        reasons.append("crew qualification")
    crew_sectors = crew.get("sector_ids")
    if not isinstance(crew_sectors, list) or crew_sectors:
        reasons.append("crew overlap")
    remaining_duty = _number(crew.get("remaining_duty_minutes"))
    if remaining_duty is None or remaining_duty < _REQUIRED_CREW_MARGIN_MINUTES:
        reasons.append("crew duty margin")

    scheduled_departure = _number(target.get("scheduled_departure"))
    inbound_departure = _number(inbound.get("scheduled_departure"))
    inbound_delay = _number(inbound.get("delay_minutes"))
    turnaround = _number(rotation.get("minimum_turnaround_minutes"))
    slot_time = _number(slot.get("scheduled_time"))
    slot_tolerance = _number(slot.get("tolerance_minutes"))
    planned_departure = None
    if None not in (
        scheduled_departure,
        inbound_departure,
        inbound_delay,
        turnaround,
    ):
        planned_departure = max(
            scheduled_departure,
            inbound_departure + inbound_delay + turnaround,
        )
    if (
        slot.get("sector_id") != target.get("id")
        or slot.get("status") != "allocated"
        or planned_departure is None
        or slot_time is None
        or slot_tolerance is None
        or abs(planned_departure - slot_time) > slot_tolerance
    ):
        reasons.append("slot window")

    compatible = stand.get("compatible_configurations")
    if (
        stand.get("id") != _STAND_ID
        or stand.get("station_id") != target.get("origin_id")
        or stand.get("status") != "available"
        or not isinstance(compatible, list)
        or aircraft.get("configuration") not in compatible
    ):
        reasons.append("stand compatibility")

    if not _evidence_is_current(
        observation,
        (
            inbound,
            target,
            rotation,
            current_aircraft,
            current_crew,
            aircraft,
            crew,
            slot,
            stand,
        ),
    ):
        reasons.append("evidence versions")
    if not _bounded(option.value_gbp, observation):
        reasons.append("bounded value")
    return FeasibilityResult(option, not reasons, tuple(reasons))


def _cancel_feasibility(
    observation: dict[str, Any],
    option: RecoveryOption,
) -> FeasibilityResult:
    target = _record(observation, "outbound_sector")
    reasons: list[str] = []
    if target.get("id") != _TARGET_SECTOR_ID or target.get("status") == "cancelled":
        reasons.append("sector availability")
    if not _evidence_is_current(observation, (target,)):
        reasons.append("evidence versions")
    if not _bounded(option.value_gbp, observation):
        reasons.append("bounded value")
    return FeasibilityResult(option, not reasons, tuple(reasons))


def _retime_feasibility(
    observation: dict[str, Any],
    option: RecoveryOption,
) -> FeasibilityResult:
    target = _record(observation, "outbound_sector")
    crew = _record(observation, "outbound_crew_duty")
    slot = _record(observation, "outbound_slot")
    reasons: list[str] = []
    remaining_duty = _number(crew.get("remaining_duty_minutes"))
    if remaining_duty is None or remaining_duty < _RETIME_MINUTES:
        reasons.append("crew")
    departure = _number(target.get("scheduled_departure"))
    slot_time = _number(slot.get("scheduled_time"))
    tolerance = _number(slot.get("tolerance_minutes"))
    if (
        departure is None
        or slot_time is None
        or tolerance is None
        or abs(departure + _RETIME_MINUTES - slot_time) > tolerance
    ):
        reasons.append("slot")
    if not _evidence_is_current(observation, (target, crew, slot)):
        reasons.append("evidence versions")
    if not _bounded(option.value_gbp, observation):
        reasons.append("bounded value")
    return FeasibilityResult(option, not reasons, tuple(reasons))


def admit_recovery_options(
    observation: dict[str, Any],
) -> tuple[FeasibilityResult, ...]:
    evidence_versions = _evidence_versions(observation)
    tail = RecoveryOption(
        option_id=_TAIL_OPTION_ID,
        impact="material",
        value_gbp=_TAIL_VALUE_GBP,
        actions=(
            RecoveryAction("assign_aircraft", _TARGET_SECTOR_ID, _TAIL_ID),
            RecoveryAction("assign_crew", _TARGET_SECTOR_ID, _CREW_ID),
            RecoveryAction("assign_stand", _TARGET_SECTOR_ID, _STAND_ID),
        ),
        evidence_versions=evidence_versions,
    )
    cancel = RecoveryOption(
        option_id=_CANCEL_OPTION_ID,
        impact="high",
        value_gbp=_CANCEL_VALUE_GBP,
        actions=(RecoveryAction("cancel_sector", _TARGET_SECTOR_ID),),
        evidence_versions=evidence_versions,
    )
    retime = RecoveryOption(
        option_id=_RETIME_OPTION_ID,
        impact="material",
        value_gbp=_RETIME_VALUE_GBP,
        actions=(
            RecoveryAction(
                "retime_sector",
                _TARGET_SECTOR_ID,
                resource_id="SYN-SLOT-05",
                minutes=_RETIME_MINUTES,
            ),
        ),
        evidence_versions=evidence_versions,
    )
    return (
        _tail_feasibility(observation, tail),
        _cancel_feasibility(observation, cancel),
        _retime_feasibility(observation, retime),
    )
