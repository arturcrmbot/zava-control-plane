"""Hospitality actor-world entity definitions.

All entities use frozen/slotted dataclasses with explicit IDs and version
fields wherever state later mutates. Statuses are constrained via string
literals documented per class.
"""
from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Hotels
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Hotel:
    """A single fictional hotel property.

    Status values: "operational", "degraded", "incident"
    """

    id: str
    name: str
    country: str  # "GB" or "DE"
    region: str
    total_rooms: int
    sister_hotel_ids: tuple[str, ...]
    occupancy_pct: float  # 0.0–1.0
    arrivals_in_4h: int
    version: int
    status: str = "operational"
    # Denormalized for quick capacity query
    available_standard_rooms: int = 0
    available_family_rooms: int = 0
    available_accessible_rooms: int = 0
    available_premium_rooms: int = 0


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Room:
    """A single hotel room.

    room_type values: "standard", "family", "accessible", "premium"
    status values: "available", "occupied", "unavailable", "not_ready"
    """

    id: str
    hotel_id: str
    room_type: str
    floor: int
    status: str  # available | occupied | unavailable | not_ready
    version: int


# ---------------------------------------------------------------------------
# Bookings and guest parties
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GuestParty:
    """A group of guests travelling together.

    channel values: "direct", "online", "corporate"
    """

    id: str
    hotel_id: str
    booking_id: str
    size: int
    has_accessibility_needs: bool
    has_family_needs: bool
    channel: str
    version: int


@dataclass(frozen=True, slots=True)
class Booking:
    """A room reservation.

    requirement values: "standard", "family", "accessible", "premium"
    status values: "active", "arriving", "checked_in", "relocated", "cancelled"
    """

    id: str
    hotel_id: str
    room_type: str   # required room type
    requirement: str  # guest requirement
    guest_party_id: str
    status: str
    check_in_tick: int
    protected: bool  # True for accessibility/family protected bookings
    version: int


# ---------------------------------------------------------------------------
# Engineering and maintenance
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CriticalAsset:
    """A critical building system or plant.

    asset_type values: "hot-water", "hvac", "elevator", "power", "fire-suppression"
    status values: "operational", "degraded", "fault"
    """

    id: str
    hotel_id: str
    asset_type: str
    name: str
    affected_room_ids: tuple[str, ...]
    status: str  # operational | degraded | fault
    fault_description: str
    restoration_estimate_hours: float
    version: int


@dataclass(frozen=True, slots=True)
class WorkOrder:
    """A maintenance task targeting a critical asset.

    status values: "open", "planned", "in_progress", "completed"
    priority values: "critical", "high", "medium", "low"
    """

    id: str
    hotel_id: str
    asset_id: str
    title: str
    priority: str
    status: str
    assigned_team_member_id: str | None
    estimated_hours: float
    cost_estimate_gbp: float
    version: int
    contractor_available: bool = False


# ---------------------------------------------------------------------------
# Workforce
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TeamMember:
    """A hotel team member.

    skill values: "front-office", "housekeeping", "engineering", "food-service"
    status values: "available", "on_shift", "off_duty"
    """

    id: str
    hotel_id: str
    name: str
    skill: str
    status: str
    version: int


@dataclass(frozen=True, slots=True)
class Shift:
    """A scheduled work period for a team member.

    status values: "active", "scheduled", "reallocated", "completed"
    """

    id: str
    team_member_id: str
    hotel_id: str
    skill: str
    start_tick: int
    end_tick: int
    status: str
    version: int


# ---------------------------------------------------------------------------
# Food and beverage
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FoodServicePlan:
    """A breakfast or on-site service plan for a hotel.

    status values: "ready", "at_risk", "insufficient"
    """

    id: str
    hotel_id: str
    covers_forecast: int
    covers_prepared: int
    status: str
    version: int


# ---------------------------------------------------------------------------
# Energy and utilities
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EnergyMeter:
    """An energy consumption meter at a hotel.

    status values: "normal", "anomaly", "alert"
    """

    id: str
    hotel_id: str
    meter_type: str  # "electricity" | "gas" | "water"
    reading_kwh: float
    baseline_kwh: float
    status: str
    version: int
