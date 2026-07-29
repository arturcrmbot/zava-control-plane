"""Hospitality sensor: operational-risk threshold evaluation.

This module is pure — it reads only its ``snapshot`` argument and has no
I/O, randomness, or wall-clock dependence. It raises ``ValueError`` with a
clear message for any malformed or insufficient snapshot rather than
silently returning success.
"""
from __future__ import annotations

from typing import Any

from verticals.hospitality.dynamics import (
    MIN_UNFULFILLABLE_ARRIVALS,
    covers_shortfall_crossed,
    energy_anomaly_crossed,
    energy_deviation,
    housekeeping_hours_required,
    labour_hours_available,
    occupancy_pressure_crossed,
    operations_risk_crossed,
    readiness_gap_crossed,
    workforce_deficit_crossed,
)

# Required top-level sections for a valid snapshot.
_REQUIRED_SECTIONS = (
    "hotels",
    "rooms",
    "bookings",
    "team_members",
    "critical_assets",
    "work_orders",
    "shifts",
    "tick",
    "seed",
)

# Deterministic sister-property travel times (integer minutes) derived from
# the anonymous hotel topology.  Values are fixed by the topology seed and
# must not reference any real-world property or route.
_SISTER_TRAVEL_MINUTES: dict[str, dict[str, int]] = {
    "HOTEL-RIVERSIDE-CENTRAL": {
        "HOTEL-AIRPORT-NORTH": 35,
        "HOTEL-CITY-GATE": 50,
    },
    "HOTEL-AIRPORT-NORTH": {
        "HOTEL-RIVERSIDE-CENTRAL": 35,
        "HOTEL-CITY-GATE": 28,
    },
    "HOTEL-CITY-GATE": {
        "HOTEL-RIVERSIDE-CENTRAL": 50,
        "HOTEL-AIRPORT-NORTH": 28,
    },
    "HOTEL-HARBOUR-VIEW": {
        "HOTEL-MESSE-CENTRAL": 90,
        "HOTEL-RHINE-PARK": 115,
    },
    "HOTEL-MESSE-CENTRAL": {
        "HOTEL-HARBOUR-VIEW": 90,
        "HOTEL-RHINE-PARK": 65,
    },
    "HOTEL-RHINE-PARK": {
        "HOTEL-HARBOUR-VIEW": 115,
        "HOTEL-MESSE-CENTRAL": 65,
    },
}


def _require(snapshot: dict[str, Any], *keys: str) -> None:
    missing = [k for k in keys if k not in snapshot]
    if missing:
        raise ValueError(
            f"Snapshot missing required sections: {missing!r}. "
            "Provide a complete HospitalityWorld.snapshot() output."
        )


def evaluate_operations_risk(
    snapshot: dict[str, Any],
) -> dict[str, Any] | None:
    """Evaluate the hotel-operations-risk threshold for a world snapshot.

    Returns a typed measurement dict when the threshold is crossed, or
    ``None`` when it is not. Raises ``ValueError`` for malformed snapshots.

    Parameters
    ----------
    snapshot:
        Output of ``HospitalityWorld.snapshot()``.

    Returns
    -------
    dict or None:
        Measurement payload suitable for a ``WorldEvent``, or ``None``.
    """
    _require(snapshot, *_REQUIRED_SECTIONS)

    hotels: dict[str, dict] = snapshot["hotels"]
    rooms: dict[str, dict] = snapshot["rooms"]
    bookings: dict[str, dict] = snapshot["bookings"]
    team_members: dict[str, dict] = snapshot["team_members"]
    critical_assets: dict[str, dict] = snapshot["critical_assets"]
    work_orders: dict[str, dict] = snapshot["work_orders"]
    shifts: dict[str, dict] = snapshot["shifts"]
    scenario: str | None = snapshot.get("scenario")

    if not hotels:
        raise ValueError(
            "Snapshot missing required sections: ['hotels data']. "
            "Provide a complete HospitalityWorld.snapshot() output."
        )

    # Find any hotel with a critical asset fault
    faulted_hotel_id: str | None = None
    faulted_asset: dict | None = None
    for asset in critical_assets.values():
        if asset["status"] == "fault":
            faulted_hotel_id = asset["hotel_id"]
            faulted_asset = asset
            break

    if faulted_hotel_id is None or faulted_asset is None:
        return None

    hotel = hotels.get(faulted_hotel_id)
    if hotel is None:
        return None

    occupancy_pct: float = hotel["occupancy_pct"]
    arrivals_in_4h: int = hotel["arrivals_in_4h"]

    # Count affected rooms
    affected_rooms = [
        r for r in rooms.values()
        if r["hotel_id"] == faulted_hotel_id and r["status"] == "unavailable"
    ]
    not_ready_rooms = [
        r for r in rooms.values()
        if r["hotel_id"] == faulted_hotel_id and r["status"] == "not_ready"
    ]
    available_rooms = [
        r for r in rooms.values()
        if r["hotel_id"] == faulted_hotel_id and r["status"] == "available"
    ]

    if not operations_risk_crossed(occupancy_pct, len(affected_rooms), True):
        return None

    # Arrivals by requirement
    arriving_bookings = [
        b for b in bookings.values()
        if b["hotel_id"] == faulted_hotel_id and b["status"] == "arriving"
    ]
    arrivals_by_requirement: dict[str, int] = {}
    for b in arriving_bookings:
        req = b["requirement"]
        arrivals_by_requirement[req] = arrivals_by_requirement.get(req, 0) + 1

    # Protected requirements (accessible, family bookings that are protected)
    protected_requirements: dict[str, int] = {}
    for b in arriving_bookings:
        if b["protected"]:
            req = b["requirement"]
            protected_requirements[req] = protected_requirements.get(req, 0) + 1

    # Housekeeping capacity: available housekeeping team members at the hotel
    housekeeping_members = [
        m for m in team_members.values()
        if m["hotel_id"] == faulted_hotel_id and m["skill"] == "housekeeping"
    ]
    housekeeping_capacity = len(
        [m for m in housekeeping_members if m["status"] == "available"]
    )

    # Engineering availability
    engineering_members = [
        m for m in team_members.values()
        if m["hotel_id"] == faulted_hotel_id and m["skill"] == "engineering"
    ]
    engineering_available = len(
        [m for m in engineering_members if m["status"] == "available"]
    )

    # Sister property capacity: available rooms at sister hotels
    sister_hotel_ids: list[str] = hotel.get("sister_hotel_ids", [])
    sister_property_capacity: dict[str, int] = {}
    for sister_id in sister_hotel_ids:
        sister = hotels.get(sister_id, {})
        available_standard = sister.get("available_standard_rooms", 0)
        available_accessible = sister.get("available_accessible_rooms", 0)
        available_family = sister.get("available_family_rooms", 0)
        available_premium = sister.get("available_premium_rooms", 0)
        sister_property_capacity[sister_id] = (
            available_standard + available_accessible + available_family + available_premium
        )

    # Work order for the faulted asset
    critical_work_order = None
    for wo in work_orders.values():
        if wo["asset_id"] == faulted_asset["id"]:
            critical_work_order = wo
            break

    restoration_estimate = faulted_asset.get("restoration_estimate_hours", 6.0)

    # Financial estimates (synthetic demo assumptions)
    avg_room_rate_gbp = 89.0  # synthetic demo assumption
    revenue_at_risk_gbp = len(affected_rooms) * avg_room_rate_gbp
    recovery_spend_per_relocation_gbp = 150.0  # synthetic demo assumption
    estimated_guest_disruption_count = len(arriving_bookings)
    total_sister_capacity = sum(sister_property_capacity.values())
    relocations_possible = min(
        len(arriving_bookings),
        total_sister_capacity,
    )
    estimated_recovery_spend_gbp = (
        relocations_possible * recovery_spend_per_relocation_gbp
        + (critical_work_order["cost_estimate_gbp"] if critical_work_order else 0)
    )

    # Sister-property travel times (deterministic integer minutes from topology)
    sister_travel_times_minutes: dict[str, int] = {
        sid: _SISTER_TRAVEL_MINUTES.get(faulted_hotel_id, {}).get(sid, 60)
        for sid in sister_hotel_ids
    }

    # Contractor availability from the critical work order's typed field
    contractor_available: bool = bool(
        critical_work_order.get("contractor_available", False)
    ) if critical_work_order else False

    return {
        "hotel_id": faulted_hotel_id,
        "asset_id": faulted_asset["id"],
        "scenario": scenario,
        "affected_rooms": len(affected_rooms),
        "not_ready_rooms": len(not_ready_rooms),
        "restoration_estimate_hours": restoration_estimate,
        "arrivals_in_4h": arrivals_in_4h,
        "arrivals_by_requirement": arrivals_by_requirement,
        "ready_room_count": len(available_rooms),
        "housekeeping_capacity": housekeeping_capacity,
        "protected_requirements": protected_requirements,
        "sister_property_capacity": sister_property_capacity,
        "sister_travel_times_minutes": sister_travel_times_minutes,
        "engineering_available": engineering_available,
        "contractor_available": contractor_available,
        "critical_work_order_id": (
            critical_work_order["id"] if critical_work_order else None
        ),
        "estimated_guest_disruption_count": estimated_guest_disruption_count,
        "estimated_recovery_spend_gbp": estimated_recovery_spend_gbp,
        "revenue_at_risk_gbp": revenue_at_risk_gbp,
    }


# ---------------------------------------------------------------------------
# Derived pool helpers
#
# These read only the snapshot. Because command handlers mutate the same
# state (assigning team members, changing room status), consuming capacity
# in one domain genuinely reduces it for every other sensor below.
# ---------------------------------------------------------------------------


def _rooms_by_status(rooms: dict[str, dict], hotel_id: str, status: str) -> list[dict]:
    return [r for r in rooms.values() if r["hotel_id"] == hotel_id and r["status"] == status]


def _arriving_bookings(bookings: dict[str, dict], hotel_id: str) -> list[dict]:
    return [
        b for b in bookings.values()
        if b["hotel_id"] == hotel_id and b["status"] == "arriving"
    ]


def _available_staff(team_members: dict[str, dict], hotel_id: str, skill: str) -> list[dict]:
    return [
        m for m in team_members.values()
        if m["hotel_id"] == hotel_id
        and m["skill"] == skill
        and m["status"] == "available"
    ]


def _scheduled_shift_ticks(
    shifts: dict[str, dict],
    team_members: dict[str, dict],
    hotel_id: str,
    skill: str,
) -> int:
    """Total scheduled shift ticks offered by *available* staff of a skill.

    Staff already assigned elsewhere (status != available) contribute zero.
    This is what makes the pool finite and contended.
    """
    available_ids = {m["id"] for m in _available_staff(team_members, hotel_id, skill)}
    total = 0
    for shift in shifts.values():
        if shift["hotel_id"] != hotel_id or shift["skill"] != skill:
            continue
        if shift["status"] != "scheduled":
            continue
        if shift["team_member_id"] not in available_ids:
            continue
        total += max(0, int(shift["end_tick"]) - int(shift["start_tick"]))
    return total


def _has_capacity_loss(rooms: dict[str, dict], hotel_id: str) -> bool:
    """True when a hotel has rooms out of service or awaiting a turn.

    At the seeded baseline every hotel has zero of both, so this cleanly
    separates "normally busy" from "something has gone wrong".
    """
    return bool(
        _rooms_by_status(rooms, hotel_id, "unavailable")
        or _rooms_by_status(rooms, hotel_id, "not_ready")
    )


def _hotel_ids(snapshot: dict[str, Any]) -> list[str]:
    """Deterministic hotel iteration order."""
    return sorted(snapshot["hotels"].keys())


def evaluate_room_readiness_gap(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Fire when unturned rooms outrun the ready stock imminent arrivals need.

    Caused, in practice, by a recovery plan taking rooms out of service.
    """
    _require(snapshot, *_REQUIRED_SECTIONS)
    rooms, bookings = snapshot["rooms"], snapshot["bookings"]
    team_members, shifts = snapshot["team_members"], snapshot["shifts"]

    for hotel_id in _hotel_ids(snapshot):
        not_ready = _rooms_by_status(rooms, hotel_id, "not_ready")
        ready = _rooms_by_status(rooms, hotel_id, "available")
        arrivals = _arriving_bookings(bookings, hotel_id)
        if not readiness_gap_crossed(len(not_ready), len(arrivals), len(ready)):
            continue

        required = housekeeping_hours_required(len(not_ready))
        supply = labour_hours_available(
            _scheduled_shift_ticks(shifts, team_members, hotel_id, "housekeeping")
        )
        return {
            "hotel_id": hotel_id,
            "not_ready_rooms": len(not_ready),
            "ready_room_count": len(ready),
            "arrivals_in_4h": len(arrivals),
            "housekeeping_hours_required": round(required, 2),
            "housekeeping_hours_available": round(supply, 2),
            "housekeeping_hours_deficit": round(max(0.0, required - supply), 2),
            "not_ready_room_ids": sorted(r["id"] for r in not_ready)[:12],
        }
    return None


def evaluate_asset_fault_alert(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Fire for a faulted critical asset with no work order yet in flight."""
    _require(snapshot, *_REQUIRED_SECTIONS)
    assets, work_orders = snapshot["critical_assets"], snapshot["work_orders"]
    team_members = snapshot["team_members"]

    # "open" is deliberately excluded: an open order is exactly what this
    # domain responds to by dispatching.
    active = {"dispatched", "in_progress", "completed"}
    for asset_id in sorted(assets):
        asset = assets[asset_id]
        if asset["status"] != "fault":
            continue
        covered = any(
            wo["asset_id"] == asset_id and wo["status"] in active
            for wo in work_orders.values()
        )
        if covered:
            continue

        hotel_id = asset["hotel_id"]
        engineers = _available_staff(team_members, hotel_id, "engineering")
        pending = [
            wo for wo in work_orders.values()
            if wo["asset_id"] == asset_id and wo["status"] == "planned"
        ]
        return {
            "hotel_id": hotel_id,
            "asset_id": asset_id,
            "asset_type": asset["asset_type"],
            "fault_description": asset["fault_description"],
            "restoration_estimate_hours": asset["restoration_estimate_hours"],
            "affected_room_count": len(asset.get("affected_room_ids", ()) or ()),
            "engineering_available": len(engineers),
            "planned_work_order_id": sorted(w["id"] for w in pending)[0] if pending else None,
        }
    return None


def evaluate_guest_service_failure(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Fire when arriving guests cannot be matched to a room they can use."""
    _require(snapshot, *_REQUIRED_SECTIONS)
    rooms, bookings = snapshot["rooms"], snapshot["bookings"]
    guest_parties = snapshot.get("guest_parties", {})

    for hotel_id in _hotel_ids(snapshot):
        arrivals = _arriving_bookings(bookings, hotel_id)
        if not arrivals:
            continue
        # This is an incident sensor, not a "busy hotel" sensor: a fully
        # booked property that is coping is normal. It only fires once the
        # hotel has actually lost usable capacity.
        if not _has_capacity_loss(rooms, hotel_id):
            continue
        stock: dict[str, int] = {}
        for room in _rooms_by_status(rooms, hotel_id, "available"):
            stock[room["room_type"]] = stock.get(room["room_type"], 0) + 1

        unfulfillable: list[dict] = []
        for booking in sorted(arrivals, key=lambda b: b["id"]):
            requirement = booking["requirement"]
            if stock.get(requirement, 0) > 0:
                stock[requirement] -= 1
            else:
                unfulfillable.append(booking)

        if len(unfulfillable) < MIN_UNFULFILLABLE_ARRIVALS:
            continue

        protected = [b for b in unfulfillable if b["protected"]]
        affected_parties = [
            guest_parties[b["guest_party_id"]]
            for b in unfulfillable
            if b["guest_party_id"] in guest_parties
        ]
        return {
            "hotel_id": hotel_id,
            "unfulfillable_arrivals": len(unfulfillable),
            "protected_arrivals": len(protected),
            "guests_affected": sum(p["size"] for p in affected_parties),
            "accessibility_cases": sum(
                1 for p in affected_parties if p["has_accessibility_needs"]
            ),
            "family_cases": sum(1 for p in affected_parties if p["has_family_needs"]),
            "booking_ids": sorted(b["id"] for b in unfulfillable)[:12],
        }
    return None


def evaluate_occupancy_pressure(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Fire when a near-full property cannot absorb its imminent arrivals."""
    _require(snapshot, *_REQUIRED_SECTIONS)
    hotels, rooms, bookings = snapshot["hotels"], snapshot["rooms"], snapshot["bookings"]

    for hotel_id in _hotel_ids(snapshot):
        hotel = hotels[hotel_id]
        ready = _rooms_by_status(rooms, hotel_id, "available")
        arrivals = _arriving_bookings(bookings, hotel_id)
        if not _has_capacity_loss(rooms, hotel_id):
            continue
        if not occupancy_pressure_crossed(
            hotel["occupancy_pct"], len(ready), len(arrivals)
        ):
            continue

        sister_capacity = {
            sid: hotels.get(sid, {}).get("available_standard_rooms", 0)
            + hotels.get(sid, {}).get("available_family_rooms", 0)
            + hotels.get(sid, {}).get("available_accessible_rooms", 0)
            + hotels.get(sid, {}).get("available_premium_rooms", 0)
            for sid in hotel.get("sister_hotel_ids", ())
        }
        return {
            "hotel_id": hotel_id,
            "occupancy_pct": hotel["occupancy_pct"],
            "ready_room_count": len(ready),
            "arrivals_in_4h": len(arrivals),
            "overflow_count": max(0, len(arrivals) - len(ready)),
            "sister_property_capacity": sister_capacity,
            "total_sister_capacity": sum(sister_capacity.values()),
        }
    return None


def evaluate_workforce_demand_imbalance(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Fire when labour demand outruns the supply left in the pool.

    This is the contention sensor: every engineer assigned to a work order
    and every room turned to ``not_ready`` moves this closer to firing.
    """
    _require(snapshot, *_REQUIRED_SECTIONS)
    rooms, team_members, shifts = (
        snapshot["rooms"], snapshot["team_members"], snapshot["shifts"]
    )
    work_orders = snapshot["work_orders"]

    for hotel_id in _hotel_ids(snapshot):
        not_ready = _rooms_by_status(rooms, hotel_id, "not_ready")
        hk_required = housekeeping_hours_required(len(not_ready))
        hk_supply = labour_hours_available(
            _scheduled_shift_ticks(shifts, team_members, hotel_id, "housekeeping")
        )

        open_orders = [
            wo for wo in work_orders.values()
            if wo["hotel_id"] == hotel_id
            and wo["status"] in {"open", "planned", "dispatched", "in_progress"}
        ]
        eng_required = sum(float(wo["estimated_hours"]) for wo in open_orders)
        eng_supply = labour_hours_available(
            _scheduled_shift_ticks(shifts, team_members, hotel_id, "engineering")
        )

        hk_short = workforce_deficit_crossed(hk_required, hk_supply)
        eng_short = workforce_deficit_crossed(eng_required, eng_supply)
        if not (hk_short or eng_short):
            continue

        return {
            "hotel_id": hotel_id,
            "housekeeping_hours_required": round(hk_required, 2),
            "housekeeping_hours_available": round(hk_supply, 2),
            "housekeeping_deficit_hours": round(max(0.0, hk_required - hk_supply), 2),
            "engineering_hours_required": round(eng_required, 2),
            "engineering_hours_available": round(eng_supply, 2),
            "engineering_deficit_hours": round(max(0.0, eng_required - eng_supply), 2),
            "constrained_skills": [
                s for s, short in (("housekeeping", hk_short), ("engineering", eng_short))
                if short
            ],
            "open_work_order_count": len(open_orders),
            "not_ready_rooms": len(not_ready),
        }
    return None


def evaluate_food_service_gap(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Fire when prepared covers fall materially short of the forecast."""
    _require(snapshot, *_REQUIRED_SECTIONS)
    plans = snapshot.get("food_service_plans", {})
    team_members = snapshot["team_members"]

    for plan_id in sorted(plans):
        plan = plans[plan_id]
        if not covers_shortfall_crossed(plan["covers_forecast"], plan["covers_prepared"]):
            continue
        hotel_id = plan["hotel_id"]
        return {
            "hotel_id": hotel_id,
            "plan_id": plan_id,
            "covers_forecast": plan["covers_forecast"],
            "covers_prepared": plan["covers_prepared"],
            "covers_shortfall": plan["covers_forecast"] - plan["covers_prepared"],
            "plan_status": plan["status"],
            "food_service_available": len(
                _available_staff(team_members, hotel_id, "food_service")
            ),
        }
    return None


def evaluate_energy_anomaly(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Fire when a meter deviates from its baseline beyond the threshold.

    A plant fault shifts consumption, so this typically trails an asset fault.
    """
    _require(snapshot, *_REQUIRED_SECTIONS)
    meters = snapshot.get("energy_meters", {})
    assets = snapshot["critical_assets"]

    for meter_id in sorted(meters):
        meter = meters[meter_id]
        if not energy_anomaly_crossed(meter["reading_kwh"], meter["baseline_kwh"]):
            continue
        hotel_id = meter["hotel_id"]
        faulted = sorted(
            a["id"] for a in assets.values()
            if a["hotel_id"] == hotel_id and a["status"] == "fault"
        )
        deviation = energy_deviation(meter["reading_kwh"], meter["baseline_kwh"])
        return {
            "hotel_id": hotel_id,
            "meter_id": meter_id,
            "meter_type": meter["meter_type"],
            "reading_kwh": meter["reading_kwh"],
            "baseline_kwh": meter["baseline_kwh"],
            "deviation_pct": round(deviation * 100, 2),
            "direction": "over" if deviation > 0 else "under",
            "correlated_asset_ids": faulted,
        }
    return None


# Sensor registry: one entry per declared ``sensor_id`` in the process
# profiles. ``poll_sensor_events`` walks this in order, so every domain can
# detect its own trigger condition instead of relying on manual injection.
SENSOR_REGISTRY: tuple[tuple[str, str, str, object], ...] = (
    (
        "sensor:hotel_operations_risk",
        "hotel-operations-recovery",
        "hotel.operations-risk.detected",
        evaluate_operations_risk,
    ),
    (
        "sensor:asset_fault_alert",
        "asset-maintenance-response",
        "hotel.asset-fault.detected",
        evaluate_asset_fault_alert,
    ),
    (
        "sensor:room_readiness_gap",
        "room-readiness-coordination",
        "hotel.readiness-gap.detected",
        evaluate_room_readiness_gap,
    ),
    (
        "sensor:guest_service_failure",
        "guest-service-recovery",
        "hotel.guest-service-failure.detected",
        evaluate_guest_service_failure,
    ),
    (
        "sensor:occupancy_pressure",
        "occupancy-pressure-response",
        "hotel.occupancy-pressure.detected",
        evaluate_occupancy_pressure,
    ),
    (
        "sensor:workforce_demand_imbalance",
        "workforce-demand-balancing",
        "hotel.workforce-imbalance.detected",
        evaluate_workforce_demand_imbalance,
    ),
    (
        "sensor:food_service_gap",
        "food-and-beverage-readiness",
        "hotel.food-service-gap.detected",
        evaluate_food_service_gap,
    ),
    (
        "sensor:energy_anomaly",
        "energy-anomaly-response",
        "hotel.energy-anomaly.detected",
        evaluate_energy_anomaly,
    ),
)
