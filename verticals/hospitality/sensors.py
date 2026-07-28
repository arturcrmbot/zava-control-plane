"""Hospitality sensor: operational-risk threshold evaluation.

This module is pure — it reads only its ``snapshot`` argument and has no
I/O, randomness, or wall-clock dependence. It raises ``ValueError`` with a
clear message for any malformed or insufficient snapshot rather than
silently returning success.
"""
from __future__ import annotations

from typing import Any

from verticals.hospitality.dynamics import operations_risk_crossed

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
