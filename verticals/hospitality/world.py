"""Hospitality actor world: deterministic seed, scenario, and sensor polling.

``HospitalityWorld.demo(seed)`` builds the complete deterministic state.
``HospitalityWorld.reset(seed)`` restores the exact initial snapshot and
clears all sensor dedupe / scenario state.

All IDs and serialized ordering are deterministic. Identical seed → identical
snapshot bytes. No wall-clock dependence; time is measured in integer ticks.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass, replace as dc_replace
from typing import Any, Callable, Mapping

from verticals.hospitality.actors import (
    Booking,
    CriticalAsset,
    EnergyMeter,
    FoodServicePlan,
    GuestParty,
    Hotel,
    Room,
    Shift,
    TeamMember,
    WorkOrder,
)
from verticals.hospitality.authority import HOSPITALITY_AUTHORITY
from verticals.hospitality.commands import (
    CMD_BOOKING_INVENTORY_PLAN_APPLY,
    CMD_ENERGY_CONTROL_PLAN_APPLY,
    CMD_FOOD_BEVERAGE_SERVICE_PLAN_APPLY,
    CMD_GUEST_RECOVERY_ACTION_ISSUE,
    CMD_HOTEL_RECOVERY_EXECUTE,
    CMD_MAINTENANCE_WORK_ORDER_DISPATCH,
    CMD_ROOM_READINESS_PLAN_APPLY,
    CMD_WORKFORCE_SHIFT_PLAN_APPLY,
    BookingInventoryPlanPayload,
    CommandEnvelope,
    CommandResult,
    EnergyControlPlanPayload,
    FoodBeverageServicePlanPayload,
    GuestRecoveryActionPayload,
    HotelRecoveryPayload,
    MaintenanceWorkOrderDispatchPayload,
    RejectedCommand,
    RoomReadinessPlanPayload,
    WorkforceShiftPlanPayload,
    canonical_signature,
    parse_command,
)
from verticals.hospitality.domains import HOSPITALITY_DOMAINS
from verticals.hospitality.dynamics import (
    ARRIVAL_HORIZON_TICKS,
    DEGRADATION_ROOMS_PER_TICK,
)
from verticals.hospitality.sensors import evaluate_operations_risk

# ---------------------------------------------------------------------------
# Command authority boundary (Task 4 scope — full governance in Task 6)
# ---------------------------------------------------------------------------

_COMMAND_TYPE_TO_WORKFLOW_TYPE: dict[str, str] = {
    CMD_HOTEL_RECOVERY_EXECUTE: "hotel-operations-recovery",
    CMD_ROOM_READINESS_PLAN_APPLY: "room-readiness-coordination",
    CMD_MAINTENANCE_WORK_ORDER_DISPATCH: "asset-maintenance-response",
    CMD_GUEST_RECOVERY_ACTION_ISSUE: "guest-service-recovery",
    CMD_BOOKING_INVENTORY_PLAN_APPLY: "occupancy-pressure-response",
    CMD_WORKFORCE_SHIFT_PLAN_APPLY: "workforce-demand-balancing",
    CMD_FOOD_BEVERAGE_SERVICE_PLAN_APPLY: "food-and-beverage-readiness",
    CMD_ENERGY_CONTROL_PLAN_APPLY: "energy-anomaly-response",
}


def _primary_role_limit_gbp(command_type: str) -> float:
    """Return the primary approving persona's spend limit for *command_type*.

    Reuses the exact synthetic values already declared in ``authority.py`` /
    ``domains.py`` rather than inventing a parallel bound.
    """
    workflow_type = _COMMAND_TYPE_TO_WORKFLOW_TYPE[command_type]
    domain = HOSPITALITY_DOMAINS[workflow_type]
    persona = domain.hitl_gates[0].persona
    return HOSPITALITY_AUTHORITY[persona].spend_limit_gbp


def _is_requirement_compatible(requirement: str, room_type: str) -> bool:
    """Return True if *room_type* satisfies a booking's *requirement*.

    Mirrors the compatibility rule used by ``recovery.py``'s planner (kept
    as an independent, small pure function so this module has no coupling
    to the planner's private helpers).
    """
    if requirement == "accessible":
        return room_type == "accessible"
    if requirement == "family":
        return room_type in ("family", "premium")
    if requirement == "premium":
        return room_type in ("premium", "standard")
    return room_type in ("standard", "premium")  # standard


# ---------------------------------------------------------------------------
# World event
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorldEvent:
    """A typed, deterministic event emitted by the world.

    Fields
    ------
    event_id:
        Globally unique, deterministic identifier.
    type:
        Dot-separated event type (e.g. "hotel.operations-risk.detected").
    workflow_type:
        Target workflow type (e.g. "hotel-operations-recovery").
    actor_ids:
        Tuple of actor IDs involved in this event.
    payload:
        Typed measurement payload.
    tick:
        Virtual tick at which the event was emitted.
    source:
        Identity of the sensor or component that emitted this event.
    trace_id:
        Trace identifier linking related events.
    """

    event_id: str
    type: str
    workflow_type: str
    actor_ids: tuple[str, ...]
    payload: dict[str, Any]
    tick: int
    source: str
    trace_id: str
    cause_event_id: str | None = None


# ---------------------------------------------------------------------------
# Hotel/room layout constants
# ---------------------------------------------------------------------------

# (hotel_id, name, country, region, total_rooms)
_HOTEL_SEED: tuple[tuple[str, str, str, str, int], ...] = (
    ("HOTEL-RIVERSIDE-CENTRAL", "Riverside Central", "GB", "UK South", 48),
    ("HOTEL-AIRPORT-NORTH",     "Airport North",     "GB", "UK North", 42),
    ("HOTEL-CITY-GATE",         "City Gate",         "GB", "UK Midlands", 42),
    ("HOTEL-HARBOUR-VIEW",      "Harbour View",      "GB", "UK South", 40),
    ("HOTEL-MESSE-CENTRAL",     "Messe Central",     "DE", "DE West", 36),
    ("HOTEL-RHINE-PARK",        "Rhine Park",        "DE", "DE West", 32),
)

# Sister-hotel relationships (bidirectional; each hotel lists its sisters)
_SISTER_MAP: dict[str, tuple[str, ...]] = {
    "HOTEL-RIVERSIDE-CENTRAL": ("HOTEL-AIRPORT-NORTH", "HOTEL-CITY-GATE"),
    "HOTEL-AIRPORT-NORTH":     ("HOTEL-RIVERSIDE-CENTRAL", "HOTEL-CITY-GATE"),
    "HOTEL-CITY-GATE":         ("HOTEL-RIVERSIDE-CENTRAL", "HOTEL-AIRPORT-NORTH"),
    "HOTEL-HARBOUR-VIEW":      ("HOTEL-MESSE-CENTRAL", "HOTEL-RHINE-PARK"),
    "HOTEL-MESSE-CENTRAL":     ("HOTEL-HARBOUR-VIEW", "HOTEL-RHINE-PARK"),
    "HOTEL-RHINE-PARK":        ("HOTEL-HARBOUR-VIEW", "HOTEL-MESSE-CENTRAL"),
}

# Room type distribution per hotel total_rooms
# (standard%, family%, accessible%, premium%) — must sum to 1
_ROOM_TYPE_RATIOS = (0.50, 0.21, 0.15, 0.14)
_ROOM_TYPES = ("standard", "family", "accessible", "premium")

# Trace-ID prefix per workflow, matching the process-profile prefixes so a
# cascade is greppable end to end.
_TRACE_PREFIX_BY_WORKFLOW: dict[str, str] = {
    "hotel-operations-recovery": "hosp-ops",
    "room-readiness-coordination": "hosp-rooms",
    "asset-maintenance-response": "hosp-maint",
    "guest-service-recovery": "hosp-grec",
    "occupancy-pressure-response": "hosp-occ",
    "workforce-demand-balancing": "hosp-wrkfrc",
    "food-and-beverage-readiness": "hosp-fnbrd",
    "energy-anomaly-response": "hosp-energy",
}

# Short slugs used in IDs
_HOTEL_SLUG: dict[str, str] = {
    "HOTEL-RIVERSIDE-CENTRAL": "RIVC",
    "HOTEL-AIRPORT-NORTH":     "ANTH",
    "HOTEL-CITY-GATE":         "CGAT",
    "HOTEL-HARBOUR-VIEW":      "HARV",
    "HOTEL-MESSE-CENTRAL":     "MESC",
    "HOTEL-RHINE-PARK":        "RPAR",
}

# Asset types per hotel (3 assets each)
_ASSET_TYPES = ("hot-water", "hvac", "elevator")

# Team member names (36 total, reused cyclically)
_MEMBER_NAMES = (
    "Alex Morgan", "Sam Patel", "Jordan Lee", "Taylor Brooks", "Casey Rivers",
    "Riley Stone", "Quinn Taylor", "Drew Collins", "Morgan Hayes", "Avery Walsh",
    "Jamie Reeves", "Blake Foster", "Cameron Hart", "Dana Ellis", "Evan Moss",
    "Fran Nolan", "Gene Curtis", "Hayden Clark", "Iris Dean", "Jules Grant",
    "Kai Pearce", "Lane Hudson", "Milo Jacobs", "Nova King", "Ollie Nash",
    "Parker Reid", "Quinn Shaw", "Reese Tate", "Sage Webb", "Tyler Young",
    "Uma Ford", "Vale Green", "Wren Hill", "Xen James", "Yara Knox", "Zara Lang",
)

# Skills assigned per hotel (6 members: 2 front-office, 2 housekeeping,
# 1 engineering, 1 food-service)
_SKILL_PATTERN = (
    "front-office", "front-office",
    "housekeeping", "housekeeping",
    "engineering",
    "food-service",
)

# Booking counts per hotel (totals to 180)
_BOOKING_COUNTS: dict[str, int] = {
    "HOTEL-RIVERSIDE-CENTRAL": 50,
    "HOTEL-AIRPORT-NORTH":     35,
    "HOTEL-CITY-GATE":         35,
    "HOTEL-HARBOUR-VIEW":      30,
    "HOTEL-MESSE-CENTRAL":     16,
    "HOTEL-RHINE-PARK":        14,
}
assert sum(_BOOKING_COUNTS.values()) == 180

# Arriving bookings at Riverside Central — 44 total
# (30 standard, 6 family, 4 accessible, 4 premium)
_RIVC_ARRIVING = (
    # (requirement, protected)
    # 4 accessible — all protected
    ("accessible", True),
    ("accessible", True),
    ("accessible", True),
    ("accessible", True),
    # 6 family — all protected
    ("family", True),
    ("family", True),
    ("family", True),
    ("family", True),
    ("family", True),
    ("family", True),
    # 30 standard — not protected
    *[("standard", False)] * 30,
    # 4 premium — not protected
    ("premium", False),
    ("premium", False),
    ("premium", False),
    ("premium", False),
)
assert len(_RIVC_ARRIVING) == 44


def _room_type_counts(total: int) -> dict[str, int]:
    """Return room type counts for a hotel with *total* rooms."""
    counts: dict[str, int] = {}
    allocated = 0
    for i, rt in enumerate(_ROOM_TYPES):
        if i == len(_ROOM_TYPES) - 1:
            counts[rt] = total - allocated
        else:
            counts[rt] = round(total * _ROOM_TYPE_RATIOS[i])
            allocated += counts[rt]
    return counts


class HospitalityWorld:
    """Deterministic hotel actor world.

    Use ``HospitalityWorld.demo(seed=20260728)`` to build the canonical
    demonstration state. Use ``reset(seed)`` to restore it.
    """

    def __init__(self) -> None:
        self.tick: int = 0
        self.hotels: dict[str, Hotel] = {}
        self.rooms: dict[str, Room] = {}
        self.bookings: dict[str, Booking] = {}
        self.guest_parties: dict[str, GuestParty] = {}
        self.critical_assets: dict[str, CriticalAsset] = {}
        self.work_orders: dict[str, WorkOrder] = {}
        self.team_members: dict[str, TeamMember] = {}
        self.shifts: dict[str, Shift] = {}
        self.food_service_plans: dict[str, FoodServicePlan] = {}
        self.energy_meters: dict[str, EnergyMeter] = {}
        self._events: list[WorldEvent] = []
        self._seen_sensor_keys: set[tuple[str, str]] = set()
        self._scenario_applied: str | None = None
        self._seed: int = 0
        self._event_counter: int = 0
        # command_id -> {"signature": str, "result": CommandResult} — accepted only.
        self._command_log: dict[str, dict[str, Any]] = {}
        self._command_handlers: dict[str, Callable[[CommandEnvelope], CommandResult]] = {
            CMD_HOTEL_RECOVERY_EXECUTE: self._apply_hotel_recovery,
            CMD_ROOM_READINESS_PLAN_APPLY: self._apply_room_readiness_plan,
            CMD_MAINTENANCE_WORK_ORDER_DISPATCH: self._apply_maintenance_work_order_dispatch,
            CMD_GUEST_RECOVERY_ACTION_ISSUE: self._apply_guest_recovery_action,
            CMD_BOOKING_INVENTORY_PLAN_APPLY: self._apply_booking_inventory_plan,
            CMD_WORKFORCE_SHIFT_PLAN_APPLY: self._apply_workforce_shift_plan,
            CMD_FOOD_BEVERAGE_SERVICE_PLAN_APPLY: self._apply_food_beverage_service_plan,
            CMD_ENERGY_CONTROL_PLAN_APPLY: self._apply_energy_control_plan,
        }

    # -----------------------------------------------------------------------
    # Class-level factory
    # -----------------------------------------------------------------------

    @classmethod
    def demo(cls, seed: int = 20260728) -> "HospitalityWorld":
        """Build and return a fully seeded deterministic world."""
        world = cls()
        world._seed = seed
        world._seed_world()
        return world

    def reset(self, seed: int | None = None) -> None:
        """Restore the exact initial snapshot and clear all runtime state."""
        if seed is not None:
            self._seed = seed
        self.tick = 0
        self.hotels.clear()
        self.rooms.clear()
        self.bookings.clear()
        self.guest_parties.clear()
        self.critical_assets.clear()
        self.work_orders.clear()
        self.team_members.clear()
        self.shifts.clear()
        self.food_service_plans.clear()
        self.energy_meters.clear()
        self._events.clear()
        self._seen_sensor_keys.clear()
        self._scenario_applied = None
        self._event_counter = 0
        self._command_log.clear()
        self._seed_world()

    # -----------------------------------------------------------------------
    # Snapshot
    # -----------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a deep-copy serializable dict of the complete world state.

        The same seed + same mutations always produce the same dict.
        """
        def _sorted(d: dict) -> dict:
            return {k: asdict(v) for k, v in sorted(d.items())}

        return {
            "seed": self._seed,
            "tick": self.tick,
            "scenario": self._scenario_applied,
            "bookings": _sorted(self.bookings),
            "critical_assets": _sorted(self.critical_assets),
            "energy_meters": _sorted(self.energy_meters),
            "food_service_plans": _sorted(self.food_service_plans),
            "guest_parties": _sorted(self.guest_parties),
            "hotels": _sorted(self.hotels),
            "rooms": _sorted(self.rooms),
            "shifts": _sorted(self.shifts),
            "team_members": _sorted(self.team_members),
            "work_orders": _sorted(self.work_orders),
        }

    # -----------------------------------------------------------------------
    # Scenario
    # -----------------------------------------------------------------------

    def trigger_scenario(self, name: str) -> None:
        """Apply a named causal scenario to the world state.

        Currently supported: ``"riverside-hot-water-outage"``.
        """
        if name == "riverside-hot-water-outage":
            self._apply_riverside_hot_water_outage()
            self._scenario_applied = name
        else:
            raise ValueError(f"Unknown scenario: {name!r}")

    # -----------------------------------------------------------------------
    # Sensor polling
    # -----------------------------------------------------------------------

    def poll_sensor_events(self) -> list[WorldEvent]:
        """Evaluate every registered sensor and return any new events.

        Each sensor is a pure function of the snapshot, so a command handler
        that mutates state can cause a *different* domain's sensor to cross
        on a later poll. That is the cascade: nothing calls a downstream
        workflow, it detects its own trigger.

        Dedupe key is ``(workflow_type, subject_id)``; each unique condition
        fires at most once regardless of how many times this method is called.
        """
        from verticals.hospitality.sensors import SENSOR_REGISTRY

        snap = self.snapshot()
        emitted: list[WorldEvent] = []
        cause_event_id = self._events[-1].event_id if self._events else None

        for sensor_id, workflow_type, event_type, evaluate in SENSOR_REGISTRY:
            measurement = evaluate(snap)
            if measurement is None:
                continue

            subject_id = self._sensor_subject_id(workflow_type, measurement)
            dedupe_key = (workflow_type, subject_id)
            if dedupe_key in self._seen_sensor_keys:
                continue
            self._seen_sensor_keys.add(dedupe_key)

            event = self._emit_sensor_event(
                workflow_type=workflow_type,
                event_type=event_type,
                sensor_id=sensor_id,
                measurement=measurement,
                cause_event_id=cause_event_id,
            )
            emitted.append(event)
            # Later sensors in this same sweep descend from the event just
            # emitted, which keeps the causal chain contiguous.
            cause_event_id = event.event_id

        return emitted

    def degrade_unresolved_faults(self) -> list[str]:
        """Let an unrepaired fault keep eating the property, one tick at a time.

        While a critical asset is still in ``fault``, rooms at that hotel keep
        falling out of service. They land in ``not_ready`` rather than
        ``unavailable``, so the damage accrues directly against the
        housekeeping pool: the longer an approval sits unanswered, the larger
        the labour deficit the responder has to solve.

        Deterministic — rooms are taken in sorted ID order. Returns the room
        IDs degraded so a caller can report them.
        """
        faulted_hotels = sorted(
            {
                asset.hotel_id
                for asset in self.critical_assets.values()
                if asset.status == "fault"
            }
        )
        if not faulted_hotels:
            return []

        degraded: list[str] = []
        hotel_deltas: dict[str, dict[str, int]] = {}
        for hotel_id in faulted_hotels:
            available = sorted(
                (
                    room for room in self.rooms.values()
                    if room.hotel_id == hotel_id and room.status == "available"
                ),
                key=lambda room: room.id,
            )
            for room in available[:DEGRADATION_ROOMS_PER_TICK]:
                self.rooms[room.id] = Room(
                    id=room.id,
                    hotel_id=room.hotel_id,
                    room_type=room.room_type,
                    floor=room.floor,
                    status="not_ready",
                    version=room.version + 1,
                )
                deltas = hotel_deltas.setdefault(hotel_id, {})
                deltas[room.room_type] = deltas.get(room.room_type, 0) - 1
                degraded.append(room.id)

        self._apply_hotel_availability_deltas(hotel_deltas)
        return degraded

    @staticmethod
    def _sensor_subject_id(workflow_type: str, measurement: dict[str, Any]) -> str:
        """Stable identity for the condition a measurement describes."""
        for key in ("asset_id", "meter_id", "plan_id", "hotel_id"):
            value = measurement.get(key)
            if value:
                return str(value)
        return workflow_type

    def _emit_sensor_event(
        self,
        *,
        workflow_type: str,
        event_type: str,
        sensor_id: str,
        measurement: dict[str, Any],
        cause_event_id: str | None,
    ) -> WorldEvent:
        self._event_counter += 1
        event_id = (
            f"EVT-HOSP-{self.tick:06d}-{self._event_counter:06d}"
            f"-{self._seed}"
        )
        payload = dict(measurement)
        actor_ids: tuple[str, ...]
        source = sensor_id
        if workflow_type == "hotel-operations-recovery":
            # Preserve the hero contract byte-for-byte.
            source = "hospitality-operations-sensor"
            source_event_id = f"SRC-{self._seed}-{self._scenario_applied}"
            payload["source_event_id"] = source_event_id
            actor_ids = (measurement["hotel_id"], measurement["asset_id"])
            trace_id = f"hosp-ops-{self._seed}-{self._scenario_applied}"
        else:
            subject = self._sensor_subject_id(workflow_type, measurement)
            payload["source_event_id"] = f"SRC-{self._seed}-{subject}"
            actor_ids = tuple(
                str(measurement[key])
                for key in ("hotel_id", "asset_id", "meter_id", "plan_id")
                if measurement.get(key)
            )
            prefix = _TRACE_PREFIX_BY_WORKFLOW.get(workflow_type, "hosp")
            trace_id = f"{prefix}-{self._seed}-{subject}"

        event = WorldEvent(
            event_id=event_id,
            type=event_type,
            workflow_type=workflow_type,
            actor_ids=actor_ids,
            payload=payload,
            tick=self.tick,
            source=source,
            trace_id=trace_id,
            cause_event_id=cause_event_id,
        )
        self._events.append(event)
        return event

    # -----------------------------------------------------------------------
    # Internal seeding
    # -----------------------------------------------------------------------

    def _seed_world(self) -> None:
        self._seed_hotels()
        self._seed_rooms()
        self._seed_assets()
        self._seed_work_orders()
        self._seed_team_members()
        self._seed_shifts()
        self._seed_bookings()
        self._seed_food_service_plans()
        self._seed_energy_meters()

    def _seed_hotels(self) -> None:
        for hi, (hotel_id, name, country, region, total) in enumerate(_HOTEL_SEED):
            slug = _HOTEL_SLUG[hotel_id]
            rt_counts = _room_type_counts(total)
            # Pre-scenario availability: each hotel has ~10% available rooms
            avail_std = max(1, round(rt_counts["standard"] * 0.12))
            avail_fam = max(1, round(rt_counts["family"] * 0.10))
            avail_acc = max(1, round(rt_counts["accessible"] * 0.10))
            avail_prm = max(1, round(rt_counts["premium"] * 0.10))
            # Riverside Central: ~96% occupancy => very few available
            if hotel_id == "HOTEL-RIVERSIDE-CENTRAL":
                avail_std = 1
                avail_fam = 0
                avail_acc = 0
                avail_prm = 1
                occ_pct = round(
                    (total - avail_std - avail_fam - avail_acc - avail_prm) / total, 4
                )
                arrivals = 6  # pre-scenario arrivals (non-hero)
            else:
                occ_pct = round(
                    (total - avail_std - avail_fam - avail_acc - avail_prm) / total, 4
                )
                arrivals = _BOOKING_COUNTS[hotel_id] // 5

            self.hotels[hotel_id] = Hotel(
                id=hotel_id,
                name=name,
                country=country,
                region=region,
                total_rooms=total,
                sister_hotel_ids=_SISTER_MAP[hotel_id],
                occupancy_pct=occ_pct,
                arrivals_in_4h=arrivals,
                version=1,
                status="operational",
                available_standard_rooms=avail_std,
                available_family_rooms=avail_fam,
                available_accessible_rooms=avail_acc,
                available_premium_rooms=avail_prm,
            )

    def _seed_rooms(self) -> None:
        for hi, (hotel_id, *_rest, total) in enumerate(_HOTEL_SEED):
            slug = _HOTEL_SLUG[hotel_id]
            rt_counts = _room_type_counts(total)
            room_seq = 0
            for rt in _ROOM_TYPES:
                count = rt_counts[rt]
                for ri in range(count):
                    room_seq += 1
                    room_id = f"ROOM-{slug}-{room_seq:03d}"
                    # Determine status: available rooms match hotel counters
                    hotel = self.hotels[hotel_id]
                    avail_key = f"available_{rt}_rooms"
                    avail_count = getattr(hotel, avail_key, 0)
                    # First avail_count rooms of each type are "available"
                    status = "available" if ri < avail_count else "occupied"
                    self.rooms[room_id] = Room(
                        id=room_id,
                        hotel_id=hotel_id,
                        room_type=rt,
                        floor=(ri // 10) + 1,
                        status=status,
                        version=1,
                    )

    def _seed_assets(self) -> None:
        for hi, (hotel_id, *_rest) in enumerate(_HOTEL_SEED):
            slug = _HOTEL_SLUG[hotel_id]
            for ai, asset_type in enumerate(_ASSET_TYPES):
                asset_id = f"ASSET-{slug}-{asset_type.upper().replace('-', '')[:2]}-{ai + 1:02d}"
                # More descriptive asset IDs
                asset_tag = {
                    "hot-water": "HW",
                    "hvac": "HVAC",
                    "elevator": "ELEV",
                }[asset_type]
                asset_id = f"ASSET-{slug}-{asset_tag}-{ai + 1:02d}"
                self.critical_assets[asset_id] = CriticalAsset(
                    id=asset_id,
                    hotel_id=hotel_id,
                    asset_type=asset_type,
                    name=f"{asset_type.replace('-', ' ').title()} Plant {ai + 1}",
                    affected_room_ids=(),
                    status="operational",
                    fault_description="",
                    restoration_estimate_hours=0.0,
                    version=1,
                )

    def _seed_work_orders(self) -> None:
        # 12 work orders: 2 per hotel; alternating open/planned
        wo_seq = 0
        for hi, (hotel_id, *_rest) in enumerate(_HOTEL_SEED):
            slug = _HOTEL_SLUG[hotel_id]
            # First work order for this hotel: open, targets hot-water asset
            asset_id = f"ASSET-{slug}-HW-01"
            wo_seq += 1
            wo_id = f"WO-{slug}-{wo_seq:03d}"
            self.work_orders[wo_id] = WorkOrder(
                id=wo_id,
                hotel_id=hotel_id,
                asset_id=asset_id,
                title=f"Preventive hot-water inspection — {self.hotels[hotel_id].name}",
                priority="medium",
                status="planned",
                assigned_team_member_id=None,
                estimated_hours=2.0,
                cost_estimate_gbp=480.0,
                version=1,
            )
            # Second work order: open, targets HVAC asset
            hvac_asset_id = f"ASSET-{slug}-HVAC-02"
            wo_seq += 1
            wo_id2 = f"WO-{slug}-{wo_seq:03d}"
            self.work_orders[wo_id2] = WorkOrder(
                id=wo_id2,
                hotel_id=hotel_id,
                asset_id=hvac_asset_id,
                title=f"HVAC filter replacement — {self.hotels[hotel_id].name}",
                priority="low",
                status="open",
                assigned_team_member_id=None,
                estimated_hours=1.0,
                cost_estimate_gbp=240.0,
                version=1,
            )

    def _seed_team_members(self) -> None:
        member_seq = 0
        for hi, (hotel_id, *_rest) in enumerate(_HOTEL_SEED):
            slug = _HOTEL_SLUG[hotel_id]
            for si, skill in enumerate(_SKILL_PATTERN):
                member_seq += 1
                member_id = f"TEAM-{slug}-{skill[:2].upper()}-{si + 1:02d}"
                self.team_members[member_id] = TeamMember(
                    id=member_id,
                    hotel_id=hotel_id,
                    name=_MEMBER_NAMES[(member_seq - 1) % len(_MEMBER_NAMES)],
                    skill=skill,
                    status="available",
                    version=1,
                )

    def _seed_shifts(self) -> None:
        for member_id, member in self.team_members.items():
            shift_id = f"SHIFT-{member_id}"
            start_tick, end_tick = self._shift_span(member_id)
            self.shifts[shift_id] = Shift(
                id=shift_id,
                team_member_id=member_id,
                hotel_id=member.hotel_id,
                skill=member.skill,
                start_tick=start_tick,
                end_tick=end_tick,
                status="scheduled",
                version=1,
            )

    def _shift_span(self, member_id: str) -> tuple[int, int]:
        """Deterministic per-seed rota for one team member.

        Rota depth is the supply side of the labour pool, so varying it is
        what makes two seeds tell different stories: the same fault produces
        different deficits, and therefore different agent decisions.

        Derived from ``(seed, member_id)`` alone, so a given seed always
        rebuilds the identical rota — reproducible, not random.
        """
        rng = random.Random(f"hospitality-rota:{self._seed}:{member_id}")
        start_tick = rng.choice((1, 1, 2))
        return start_tick, start_tick + rng.choice((6, 7, 8, 8))

    def _seed_bookings(self) -> None:
        for hi, (hotel_id, *_rest) in enumerate(_HOTEL_SEED):
            slug = _HOTEL_SLUG[hotel_id]
            total_bookings = _BOOKING_COUNTS[hotel_id]

            if hotel_id == "HOTEL-RIVERSIDE-CENTRAL":
                self._seed_riverside_bookings(hotel_id, slug)
            else:
                # Generic bookings for other hotels
                for bi in range(total_bookings):
                    bkg_id = f"BKG-{slug}-STAY-{bi + 1:03d}"
                    gp_id = f"GP-{slug}-{bi + 1:03d}"
                    rt_idx = bi % len(_ROOM_TYPES)
                    rt = _ROOM_TYPES[rt_idx]
                    # First few are "arriving"
                    status = "arriving" if bi < (total_bookings // 5) else "checked_in"
                    self.guest_parties[gp_id] = GuestParty(
                        id=gp_id,
                        hotel_id=hotel_id,
                        booking_id=bkg_id,
                        size=2,
                        has_accessibility_needs=(rt == "accessible"),
                        has_family_needs=(rt == "family"),
                        channel="online",
                        version=1,
                    )
                    self.bookings[bkg_id] = Booking(
                        id=bkg_id,
                        hotel_id=hotel_id,
                        room_type=rt,
                        requirement=rt,
                        guest_party_id=gp_id,
                        status=status,
                        check_in_tick=(bi % ARRIVAL_HORIZON_TICKS) + 1,
                        protected=(rt in ("accessible", "family")),
                        version=1,
                    )

    def _seed_riverside_bookings(self, hotel_id: str, slug: str) -> None:
        total = _BOOKING_COUNTS[hotel_id]  # 50
        arriving_count = 44

        # 44 arriving bookings (the hero scenario arrivals)
        for bi, (req, protected) in enumerate(_RIVC_ARRIVING):
            bkg_id = f"BKG-{slug}-ARR-{bi + 1:03d}"
            gp_id = f"GP-{slug}-ARR-{bi + 1:03d}"
            self.guest_parties[gp_id] = GuestParty(
                id=gp_id,
                hotel_id=hotel_id,
                booking_id=bkg_id,
                size=(3 if req == "family" else 1 if req == "accessible" else 2),
                has_accessibility_needs=(req == "accessible"),
                has_family_needs=(req == "family"),
                channel="online",
                version=1,
            )
            self.bookings[bkg_id] = Booking(
                id=bkg_id,
                hotel_id=hotel_id,
                room_type=req,
                requirement=req,
                guest_party_id=gp_id,
                status="arriving",
                check_in_tick=(bi % ARRIVAL_HORIZON_TICKS) + 1,
                protected=protected,
                version=1,
            )

        # 6 already checked-in bookings
        for bi in range(total - arriving_count):
            bkg_id = f"BKG-{slug}-STAY-{bi + 1:03d}"
            gp_id = f"GP-{slug}-STAY-{bi + 1:03d}"
            rt = _ROOM_TYPES[bi % len(_ROOM_TYPES)]
            self.guest_parties[gp_id] = GuestParty(
                id=gp_id,
                hotel_id=hotel_id,
                booking_id=bkg_id,
                size=2,
                has_accessibility_needs=(rt == "accessible"),
                has_family_needs=(rt == "family"),
                channel="direct",
                version=1,
            )
            self.bookings[bkg_id] = Booking(
                id=bkg_id,
                hotel_id=hotel_id,
                room_type=rt,
                requirement=rt,
                guest_party_id=gp_id,
                status="checked_in",
                check_in_tick=0,
                protected=(rt in ("accessible", "family")),
                version=1,
            )

    def _seed_food_service_plans(self) -> None:
        for hi, (hotel_id, *_rest, total) in enumerate(_HOTEL_SEED):
            slug = _HOTEL_SLUG[hotel_id]
            plan_id = f"FSP-{slug}-001"
            covers_forecast = total * 2  # 2 covers per room
            self.food_service_plans[plan_id] = FoodServicePlan(
                id=plan_id,
                hotel_id=hotel_id,
                covers_forecast=covers_forecast,
                covers_prepared=round(covers_forecast * 0.85),
                status="ready",
                version=1,
            )

    def _seed_energy_meters(self) -> None:
        meter_types = ("electricity", "gas")
        for hi, (hotel_id, *_rest, total) in enumerate(_HOTEL_SEED):
            slug = _HOTEL_SLUG[hotel_id]
            for mi, meter_type in enumerate(meter_types):
                meter_id = f"EM-{slug}-{meter_type[:4].upper()}-{mi + 1:02d}"
                baseline = total * 12.5  # kWh synthetic baseline
                self.energy_meters[meter_id] = EnergyMeter(
                    id=meter_id,
                    hotel_id=hotel_id,
                    meter_type=meter_type,
                    reading_kwh=round(baseline * 1.02, 1),  # slight over-baseline
                    baseline_kwh=baseline,
                    status="normal",
                    version=1,
                )

    # -----------------------------------------------------------------------
    # Golden scenario mutations
    # -----------------------------------------------------------------------

    def _apply_riverside_hot_water_outage(self) -> None:
        hotel_id = "HOTEL-RIVERSIDE-CENTRAL"
        slug = _HOTEL_SLUG[hotel_id]
        hotel = self.hotels[hotel_id]

        # --- Fault the hot-water asset -----------------------------------
        asset_id = f"ASSET-{slug}-HW-01"
        asset = self.critical_assets[asset_id]

        # Find the 18 unavailable rooms (first 18 occupied standard rooms)
        hotel_rooms = sorted(
            [r for r in self.rooms.values() if r.hotel_id == hotel_id],
            key=lambda r: r.id,
        )
        # Standard rooms first (they're affected by hot-water zone)
        standard_rooms = [r for r in hotel_rooms if r.room_type == "standard"]
        unavailable_targets = standard_rooms[:18]
        unavailable_ids = tuple(r.id for r in unavailable_targets)

        # Update asset
        self.critical_assets[asset_id] = CriticalAsset(
            id=asset.id,
            hotel_id=asset.hotel_id,
            asset_type=asset.asset_type,
            name=asset.name,
            affected_room_ids=unavailable_ids,
            status="fault",
            fault_description=(
                "Hot-water plant failure — lower floors without hot water"
            ),
            restoration_estimate_hours=6.0,
            version=asset.version + 1,
        )

        # Mark 18 rooms as unavailable
        for room in unavailable_targets:
            self.rooms[room.id] = Room(
                id=room.id,
                hotel_id=room.hotel_id,
                room_type=room.room_type,
                floor=room.floor,
                status="unavailable",
                version=room.version + 1,
            )

        # Mark 7 additional rooms as not_ready
        # (late checkout rooms not yet cleaned — standard and family types)
        not_ready_candidates = [
            r for r in hotel_rooms
            if r.id not in set(unavailable_ids)
            and r.room_type in ("standard", "family")
        ]
        not_ready_targets = not_ready_candidates[:7]
        for room in not_ready_targets:
            self.rooms[room.id] = Room(
                id=room.id,
                hotel_id=room.hotel_id,
                room_type=room.room_type,
                floor=room.floor,
                status="not_ready",
                version=room.version + 1,
            )

        # --- Update hotel occupancy and arrivals --------------------------
        # Near-96% occupancy: 48 total, 46 occupied ≈ 95.8%
        # After fault: 18 unavailable, 7 not_ready; set denormalized fields
        total_rooms = hotel.total_rooms  # 48

        # Recount available by type after mutations
        avail_std = sum(
            1 for r in self.rooms.values()
            if r.hotel_id == hotel_id and r.room_type == "standard" and r.status == "available"
        )
        avail_fam = sum(
            1 for r in self.rooms.values()
            if r.hotel_id == hotel_id and r.room_type == "family" and r.status == "available"
        )
        avail_acc = sum(
            1 for r in self.rooms.values()
            if r.hotel_id == hotel_id and r.room_type == "accessible" and r.status == "available"
        )
        avail_prm = sum(
            1 for r in self.rooms.values()
            if r.hotel_id == hotel_id and r.room_type == "premium" and r.status == "available"
        )

        self.hotels[hotel_id] = Hotel(
            id=hotel.id,
            name=hotel.name,
            country=hotel.country,
            region=hotel.region,
            total_rooms=hotel.total_rooms,
            sister_hotel_ids=hotel.sister_hotel_ids,
            occupancy_pct=0.9583,  # ~96% — exactly what the design spec requires
            arrivals_in_4h=44,
            version=hotel.version + 1,
            status="incident",
            available_standard_rooms=avail_std,
            available_family_rooms=avail_fam,
            available_accessible_rooms=avail_acc,
            available_premium_rooms=avail_prm,
        )

        # --- Expedite the hot-water work order ---------------------------
        wo_id = f"WO-{slug}-001"
        if wo_id in self.work_orders:
            wo = self.work_orders[wo_id]
            self.work_orders[wo_id] = WorkOrder(
                id=wo.id,
                hotel_id=wo.hotel_id,
                asset_id=wo.asset_id,
                title=f"URGENT: Hot-water plant fault restoration — {hotel.name}",
                priority="critical",
                status="open",
                assigned_team_member_id=None,
                estimated_hours=12.0,
                cost_estimate_gbp=2_400.0,  # SYNTHETIC ASSUMPTION
                version=wo.version + 1,
                contractor_available=True,
            )

        # --- Plant failure shifts the energy profile ----------------------
        # Boiler offline: gas draw collapses while electric backup heating
        # spikes. This is what makes the energy sensor a *consequence* of the
        # asset fault rather than an independent event.
        for meter_id, meter in list(self.energy_meters.items()):
            if meter.hotel_id != hotel_id:
                continue
            if meter.meter_type == "electricity":
                reading = round(meter.baseline_kwh * 1.24, 1)
                status = "anomalous"
            elif meter.meter_type == "gas":
                reading = round(meter.baseline_kwh * 0.58, 1)
                status = "anomalous"
            else:
                continue
            self.energy_meters[meter_id] = EnergyMeter(
                id=meter.id,
                hotel_id=meter.hotel_id,
                meter_type=meter.meter_type,
                reading_kwh=reading,
                baseline_kwh=meter.baseline_kwh,
                status=status,
                version=meter.version + 1,
            )

        # --- Ensure sister hotels have capacity for 10 relocations ------
        # Airport North: 5 compatible standard rooms
        # City Gate: 5 compatible standard rooms
        self._ensure_sister_capacity("HOTEL-AIRPORT-NORTH", standard=5)
        self._ensure_sister_capacity("HOTEL-CITY-GATE", standard=5)

        # --- Relocations surge food service at the receiving hotels -------
        # Five relocated rooms of guests eat where they sleep. The sister
        # kitchens forecast the extra covers but have not prepared them, so
        # the F&B gap appears downstream of the Riverside fault.
        relocation_covers = 5 * 2 * 2  # rooms x guests x services
        for plan_id, plan in list(self.food_service_plans.items()):
            if plan.hotel_id not in ("HOTEL-AIRPORT-NORTH", "HOTEL-CITY-GATE"):
                continue
            self.food_service_plans[plan_id] = FoodServicePlan(
                id=plan.id,
                hotel_id=plan.hotel_id,
                covers_forecast=plan.covers_forecast + relocation_covers,
                covers_prepared=plan.covers_prepared,
                status="at_risk",
                version=plan.version + 1,
            )

        # --- Ensure engineering shifts exist at sister hotels for realloc -
        self._ensure_engineering_shifts_at_sisters()

    def _ensure_sister_capacity(self, hotel_id: str, standard: int = 5) -> None:
        """Ensure *hotel_id* has at least *standard* available standard rooms."""
        hotel = self.hotels[hotel_id]
        current_std = hotel.available_standard_rooms
        if current_std >= standard:
            return

        slug = _HOTEL_SLUG[hotel_id]
        # Mark enough occupied standard rooms as available
        needed = standard - current_std
        occupied_std = sorted(
            [r for r in self.rooms.values()
             if r.hotel_id == hotel_id and r.room_type == "standard" and r.status == "occupied"],
            key=lambda r: r.id,
        )
        for room in occupied_std[:needed]:
            self.rooms[room.id] = Room(
                id=room.id,
                hotel_id=room.hotel_id,
                room_type=room.room_type,
                floor=room.floor,
                status="available",
                version=room.version + 1,
            )

        new_avail_std = hotel.available_standard_rooms + needed
        self.hotels[hotel_id] = Hotel(
            id=hotel.id,
            name=hotel.name,
            country=hotel.country,
            region=hotel.region,
            total_rooms=hotel.total_rooms,
            sister_hotel_ids=hotel.sister_hotel_ids,
            occupancy_pct=hotel.occupancy_pct,
            arrivals_in_4h=hotel.arrivals_in_4h,
            version=hotel.version + 1,
            status=hotel.status,
            available_standard_rooms=new_avail_std,
            available_family_rooms=hotel.available_family_rooms,
            available_accessible_rooms=hotel.available_accessible_rooms,
            available_premium_rooms=hotel.available_premium_rooms,
        )

    def _ensure_engineering_shifts_at_sisters(self) -> None:
        """Ensure at least 2 engineering shifts are scheduled at sister hotels."""
        sister_ids = ("HOTEL-AIRPORT-NORTH", "HOTEL-CITY-GATE")
        for sister_id in sister_ids:
            slug = _HOTEL_SLUG[sister_id]
            # Find or mark one engineering shift as scheduled
            eng_members = [
                m for m in self.team_members.values()
                if m.hotel_id == sister_id and m.skill == "engineering"
            ]
            for member in eng_members:
                shift_id = f"SHIFT-{member.id}"
                if shift_id in self.shifts:
                    shift = self.shifts[shift_id]
                    if shift.status != "scheduled":
                        self.shifts[shift_id] = Shift(
                            id=shift.id,
                            team_member_id=shift.team_member_id,
                            hotel_id=shift.hotel_id,
                            skill=shift.skill,
                            start_tick=shift.start_tick,
                            end_tick=shift.end_tick,
                            status="scheduled",
                            version=shift.version + 1,
                        )
                break  # one per sister hotel is enough

    # -----------------------------------------------------------------------
    # Task 4: typed commands and atomic mutations
    # -----------------------------------------------------------------------

    def _digest(self) -> str:
        """Return a stable sha256 digest of the current snapshot."""
        canonical = json.dumps(self.snapshot(), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _make_event(
        self,
        envelope: CommandEnvelope,
        event_type: str,
        actor_ids: tuple[str, ...],
        payload_extra: Mapping[str, Any],
    ) -> WorldEvent:
        self._event_counter += 1
        event_id = f"EVT-CMD-{envelope.command_id}-{self._event_counter:06d}"
        workflow_type = _COMMAND_TYPE_TO_WORKFLOW_TYPE.get(
            envelope.command_type, envelope.command_type
        )
        payload = dict(payload_extra)
        payload["command_id"] = envelope.command_id
        payload["workflow_id"] = envelope.workflow_id
        return WorldEvent(
            event_id=event_id,
            type=event_type,
            workflow_type=workflow_type,
            actor_ids=tuple(actor_ids),
            payload=payload,
            tick=self.tick,
            source="hospitality-command-handler",
            trace_id=f"cmd-{envelope.command_id}",
        )

    def _reject(
        self,
        envelope: CommandEnvelope,
        reason: str,
        details: Mapping[str, Any],
    ) -> CommandResult:
        """Build and record a typed rejection — the world is left unchanged."""
        rejection_event = self._make_event(
            envelope,
            f"{envelope.command_type}.rejected",
            (),
            {"reason": reason, "details": dict(details)},
        )
        self._events.append(rejection_event)
        return CommandResult(
            accepted=False,
            reason=reason,
            command_id=envelope.command_id,
            command_type=envelope.command_type,
            idempotent_replay=False,
            events=(rejection_event,),
            snapshot=self.snapshot(),
            snapshot_digest=self._digest(),
            details=dict(details),
        )

    def _check_target_versions(
        self,
        expected_versions: Mapping[str, int],
        targets: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, dict[str, Any]] | None:
        """Validate optimistic-concurrency versions for every *targets* entry.

        *targets* is an ordered list of ``(entity_id, entity_collection)``
        pairs. Returns ``(reason, details)`` for the first failure found, in
        declared order, or ``None`` if every target is current. Unlike
        ``_check_expected_versions`` this does *not* reject extra
        ``expected_versions`` keys outside *targets* — it is used for a
        handler's first (base) validation phase, before any dynamically
        selected physical rooms/hotels have been computed.
        """
        for entity_id, collection in targets:
            if entity_id not in collection:
                return ("unknown_entity", {"entity_id": entity_id})
            if entity_id not in expected_versions:
                return ("missing_expected_version", {"entity_id": entity_id})
            actual_version = collection[entity_id].version
            expected_version = expected_versions[entity_id]
            if expected_version != actual_version:
                return (
                    "stale_entity_version",
                    {
                        "entity_id": entity_id,
                        "expected_version": expected_version,
                        "actual_version": actual_version,
                    },
                )
        return None

    def _check_expected_versions(
        self,
        expected_versions: Mapping[str, int],
        targets: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, dict[str, Any]] | None:
        """Validate *targets* exactly: every declared key is a real target,
        every target has a matching version, and no ``expected_versions``
        key falls outside the exact computed target set.

        Call this once, with the *complete* (final) target list a handler
        will mutate — for handlers with a dynamic component (physical room/
        hotel selection), first validate the base/declared targets with
        ``_check_target_versions``, compute the dynamic targets, then call
        this with the full combined list before any mutation.
        """
        target_ids = {entity_id for entity_id, _ in targets}
        unexpected = sorted(set(expected_versions) - target_ids)
        if unexpected:
            return ("unexpected_expected_version", {"unexpected_keys": unexpected})
        return self._check_target_versions(expected_versions, targets)

    # -----------------------------------------------------------------------
    # Physical room selection and hotel-availability synchronization
    # -----------------------------------------------------------------------
    #
    # Source of truth for the blocking invariant: Hotel.available_<type>_rooms
    # must always equal the count of Room entities of that hotel/type with
    # status == "available". These helpers are the *only* place a command
    # handler selects a physical Room to consume/release, and the *only*
    # place a Hotel's denormalized counters are adjusted — every caller
    # (handlers here, and the reference-action builders) uses them so
    # build-time and apply-time selection always agree.

    def _room_by_status(
        self,
        hotel_id: str,
        room_type: str,
        status: str,
        exclude: frozenset[str] = frozenset(),
    ) -> str | None:
        """Return the deterministic (lowest-ID) Room id at *hotel_id* of
        *room_type* currently in *status*, excluding any id in *exclude*, or
        ``None`` if none exists."""
        candidates = sorted(
            r.id
            for r in self.rooms.values()
            if r.hotel_id == hotel_id
            and r.room_type == room_type
            and r.status == status
            and r.id not in exclude
        )
        return candidates[0] if candidates else None

    def select_available_room(
        self, hotel_id: str, room_type: str, exclude: frozenset[str] = frozenset()
    ) -> str | None:
        """Return the deterministic available Room id to *consume* next."""
        return self._room_by_status(hotel_id, room_type, "available", exclude)

    def select_occupied_room(
        self, hotel_id: str, room_type: str, exclude: frozenset[str] = frozenset()
    ) -> str | None:
        """Return the deterministic occupied Room id to *release* next."""
        return self._room_by_status(hotel_id, room_type, "occupied", exclude)

    def hotel_available_room_counts(self, hotel_id: str) -> dict[str, int]:
        """Return the *actual* available-room counts per type for *hotel_id*,
        computed directly from ``self.rooms`` — the ground truth used to
        validate the Hotel.available_* denormalized counters never drift."""
        counts = {rt: 0 for rt in _ROOM_TYPES}
        for room in self.rooms.values():
            if room.hotel_id == hotel_id and room.status == "available":
                counts[room.room_type] += 1
        return counts

    def _apply_hotel_availability_deltas(
        self, hotel_deltas: Mapping[str, Mapping[str, int]]
    ) -> None:
        """Apply per-hotel, per-room-type availability deltas atomically.

        Each hotel with any non-zero delta is replaced exactly once (version
        incremented exactly once), regardless of how many individual room
        transitions contributed to its combined delta.
        """
        for hotel_id, deltas in hotel_deltas.items():
            nonzero = {rt: d for rt, d in deltas.items() if d != 0}
            if not nonzero:
                continue
            hotel = self.hotels[hotel_id]
            updates = {
                f"available_{rt}_rooms": getattr(hotel, f"available_{rt}_rooms") + delta
                for rt, delta in nonzero.items()
            }
            self.hotels[hotel_id] = dc_replace(hotel, version=hotel.version + 1, **updates)

    def _requires_approval(
        self, envelope: CommandEnvelope
    ) -> tuple[bool, str]:
        """Return ``(required, trigger)`` per the Task 4 authority boundary.

        A command requires a non-empty ``approval_ref`` when it crosses a
        property boundary, touches a protected requirement, or its
        estimated value exceeds the primary approving persona's spend
        limit. The hero command always requires approval. Full governance
        (persona identity, self-approval, expiry) is Task 6 scope — this
        rule never invents an authority bypass.

        Payload-type checks below are explicit ``isinstance`` guards (never
        bare ``assert``) so a mismatched payload safely falls through to "no
        trigger from this branch" instead of raising, including under
        ``python -O``.
        """
        if envelope.command_type == CMD_HOTEL_RECOVERY_EXECUTE:
            return True, "hero_workflow"

        limit = _primary_role_limit_gbp(envelope.command_type)
        if envelope.estimated_value_gbp > limit:
            return True, "value_exceeds_role_limit"

        payload = envelope.payload
        if envelope.command_type == CMD_BOOKING_INVENTORY_PLAN_APPLY and isinstance(
            payload, BookingInventoryPlanPayload
        ):
            booking = self.bookings.get(payload.booking_id)
            if booking is not None:
                if booking.hotel_id != payload.destination_hotel_id:
                    return True, "cross_property"
                if booking.protected:
                    return True, "protected_requirement"
        elif envelope.command_type == CMD_WORKFORCE_SHIFT_PLAN_APPLY and isinstance(
            payload, WorkforceShiftPlanPayload
        ):
            shift = self.shifts.get(payload.shift_id)
            if shift is not None and shift.hotel_id != payload.destination_hotel_id:
                return True, "cross_property"
        elif envelope.command_type == CMD_ROOM_READINESS_PLAN_APPLY and isinstance(
            payload, RoomReadinessPlanPayload
        ):
            hotel_ids = {
                self.rooms[room_id].hotel_id
                for room_id in payload.room_ids
                if room_id in self.rooms
            }
            if len(hotel_ids) > 1:
                return True, "cross_property"
        elif envelope.command_type == CMD_MAINTENANCE_WORK_ORDER_DISPATCH and isinstance(
            payload, MaintenanceWorkOrderDispatchPayload
        ):
            work_order = self.work_orders.get(payload.work_order_id)
            team_member = self.team_members.get(payload.assigned_team_member_id)
            if (
                work_order is not None
                and team_member is not None
                and team_member.hotel_id != work_order.hotel_id
            ):
                return True, "cross_property"

        return False, ""

    def _make_generic_rejection_event(
        self,
        command_id: str,
        command_type: str,
        reason: str,
        details: Mapping[str, Any],
        workflow_id: str = "",
    ) -> WorldEvent:
        """Build a typed rejection event for top-level (pre-dispatch) rejections.

        Used for malformed payloads, unknown command types, and command-ID
        conflicts — cases where a full ``CommandEnvelope`` may not exist.
        *workflow_id* is preserved whenever it is known (a non-empty
        ``workflow_id`` on the raw input, or the already-parsed envelope's
        ``workflow_id``) rather than always being blanked out.
        """
        self._event_counter += 1
        safe_id = command_id or "UNKNOWN"
        event_id = f"EVT-CMD-REJECT-{safe_id}-{self._event_counter:06d}"
        workflow_type = _COMMAND_TYPE_TO_WORKFLOW_TYPE.get(command_type, command_type or "unknown")
        payload = {
            "reason": reason,
            "details": dict(details),
            "command_id": command_id,
            "workflow_id": workflow_id,
        }
        event = WorldEvent(
            event_id=event_id,
            type=f"{command_type or 'unknown'}.rejected",
            workflow_type=workflow_type,
            actor_ids=(),
            payload=payload,
            tick=self.tick,
            source="hospitality-command-handler",
            trace_id=f"cmd-{safe_id}",
        )
        self._events.append(event)
        return event

    def apply_command(
        self, command: Mapping[str, Any] | CommandEnvelope
    ) -> CommandResult:
        """Validate and, if accepted, atomically apply *command*.

        Accepts a plain mapping (e.g. from JSON) or a pre-built
        ``CommandEnvelope``. Never mutates *command*. Never raises for a
        business rejection — only returns a typed ``CommandResult``.
        """
        parsed = parse_command(command)
        if isinstance(parsed, RejectedCommand):
            raw_command_id = ""
            raw_command_type = ""
            raw_workflow_id = ""
            if isinstance(command, Mapping):
                candidate_id = command.get("command_id")
                if isinstance(candidate_id, str):
                    raw_command_id = candidate_id
                candidate_type = command.get("command_type")
                if isinstance(candidate_type, str):
                    raw_command_type = candidate_type
                candidate_workflow_id = command.get("workflow_id")
                if isinstance(candidate_workflow_id, str) and candidate_workflow_id.strip() != "":
                    raw_workflow_id = candidate_workflow_id
            elif isinstance(command, CommandEnvelope):
                raw_command_id = command.command_id
                raw_command_type = command.command_type
                raw_workflow_id = command.workflow_id
            rejection_event = self._make_generic_rejection_event(
                raw_command_id,
                raw_command_type,
                parsed.reason,
                parsed.details,
                workflow_id=raw_workflow_id,
            )
            return CommandResult(
                accepted=False,
                reason=parsed.reason,
                command_id=raw_command_id,
                command_type=raw_command_type,
                idempotent_replay=False,
                events=(rejection_event,),
                snapshot=self.snapshot(),
                snapshot_digest=self._digest(),
                details=dict(parsed.details),
            )

        signature = canonical_signature(parsed)
        logged = self._command_log.get(parsed.command_id)
        if logged is not None:
            if logged["signature"] == signature:
                prior_result: CommandResult = logged["result"]
                return dc_replace(
                    prior_result,
                    idempotent_replay=True,
                    snapshot=self.snapshot(),
                    snapshot_digest=self._digest(),
                )
            rejection_event = self._make_generic_rejection_event(
                parsed.command_id,
                parsed.command_type,
                "command_id_conflict",
                {"command_id": parsed.command_id},
                workflow_id=parsed.workflow_id,
            )
            return CommandResult(
                accepted=False,
                reason="command_id_conflict",
                command_id=parsed.command_id,
                command_type=parsed.command_type,
                idempotent_replay=False,
                events=(rejection_event,),
                snapshot=self.snapshot(),
                snapshot_digest=self._digest(),
                details={"command_id": parsed.command_id},
            )

        handler = self._command_handlers.get(parsed.command_type)
        if handler is None:
            rejection_event = self._make_generic_rejection_event(
                parsed.command_id,
                parsed.command_type,
                "unknown_command_type",
                {"command_type": parsed.command_type},
                workflow_id=parsed.workflow_id,
            )
            return CommandResult(
                accepted=False,
                reason="unknown_command_type",
                command_id=parsed.command_id,
                command_type=parsed.command_type,
                idempotent_replay=False,
                events=(rejection_event,),
                snapshot=self.snapshot(),
                snapshot_digest=self._digest(),
                details={"command_type": parsed.command_type},
            )

        result = handler(parsed)
        if result.accepted:
            self._command_log[parsed.command_id] = {
                "signature": signature,
                "result": result,
            }
        return result

    # --- A. hotel.recovery.execute (hero) -----------------------------------

    def _apply_hotel_recovery(self, envelope: CommandEnvelope) -> CommandResult:
        payload = envelope.payload
        if type(payload) is not HotelRecoveryPayload:
            return self._reject(
                envelope,
                "invalid_command_payload",
                {"field": "payload", "error": "payload_type_mismatch"},
            )

        if len(set(payload.rooms_to_restore)) != len(payload.rooms_to_restore):
            return self._reject(
                envelope,
                "invalid_command_payload",
                {"field": "rooms_to_restore", "error": "duplicate_ids"},
            )
        relocation_booking_ids = tuple(r.booking_id for r in payload.relocations)
        if len(set(relocation_booking_ids)) != len(relocation_booking_ids):
            return self._reject(
                envelope,
                "invalid_command_payload",
                {"field": "relocations[].booking_id", "error": "duplicate_ids"},
            )
        shift_move_ids = tuple(m.shift_id for m in payload.shift_moves)
        if len(set(shift_move_ids)) != len(shift_move_ids):
            return self._reject(
                envelope,
                "invalid_command_payload",
                {"field": "shift_moves[].shift_id", "error": "duplicate_ids"},
            )

        base_targets: list[tuple[str, dict[str, Any]]] = [(payload.work_order_id, self.work_orders)]
        base_targets += [(room_id, self.rooms) for room_id in payload.rooms_to_restore]
        seen_dest_hotels: set[str] = set()
        for reloc in payload.relocations:
            base_targets.append((reloc.booking_id, self.bookings))
            if reloc.destination_hotel_id not in seen_dest_hotels:
                base_targets.append((reloc.destination_hotel_id, self.hotels))
                seen_dest_hotels.add(reloc.destination_hotel_id)
        base_targets += [(move.shift_id, self.shifts) for move in payload.shift_moves]

        version_failure = self._check_target_versions(envelope.expected_versions, base_targets)
        if version_failure is not None:
            reason, details = version_failure
            return self._reject(envelope, reason, details)

        work_order = self.work_orders[payload.work_order_id]
        if work_order.status not in ("open", "planned", "in_progress"):
            return self._reject(
                envelope,
                "closed_work_order",
                {"work_order_id": work_order.id, "status": work_order.status},
            )

        for room_id in payload.rooms_to_restore:
            room = self.rooms[room_id]
            if room.status not in ("unavailable", "not_ready"):
                return self._reject(
                    envelope,
                    "unavailable_room",
                    {"room_id": room_id, "status": room.status},
                )

        consumption: dict[tuple[str, str], int] = {}
        for reloc in payload.relocations:
            booking = self.bookings[reloc.booking_id]
            dest_hotel = self.hotels.get(reloc.destination_hotel_id)
            if dest_hotel is None:
                return self._reject(
                    envelope, "unknown_entity", {"entity_id": reloc.destination_hotel_id}
                )
            source_hotel = self.hotels.get(booking.hotel_id)
            source_sisters = source_hotel.sister_hotel_ids if source_hotel is not None else ()
            if reloc.destination_hotel_id not in source_sisters:
                return self._reject(
                    envelope,
                    "incompatible_property",
                    {
                        "booking_id": booking.id,
                        "source_hotel_id": booking.hotel_id,
                        "destination_hotel_id": reloc.destination_hotel_id,
                    },
                )
            if not _is_requirement_compatible(booking.requirement, reloc.destination_room_type):
                details = {
                    "booking_id": booking.id,
                    "requirement": booking.requirement,
                    "destination_room_type": reloc.destination_room_type,
                }
                if booking.protected:
                    return self._reject(envelope, "protected_requirement_breach", details)
                return self._reject(envelope, "incompatible_room", details)
            key = (reloc.destination_hotel_id, reloc.destination_room_type)
            consumption[key] = consumption.get(key, 0) + 1

        for (hotel_id, room_type), needed in consumption.items():
            available = getattr(self.hotels[hotel_id], f"available_{room_type}_rooms", 0)
            if needed > available:
                return self._reject(
                    envelope,
                    "insufficient_capacity",
                    {"hotel_id": hotel_id, "room_type": room_type, "needed": needed, "available": available},
                )

        for move in payload.shift_moves:
            shift = self.shifts[move.shift_id]
            dest_hotel = self.hotels.get(move.destination_hotel_id)
            if dest_hotel is None:
                return self._reject(
                    envelope, "unknown_entity", {"entity_id": move.destination_hotel_id}
                )
            team_member = self.team_members.get(shift.team_member_id)
            if team_member is None:
                return self._reject(
                    envelope, "unknown_entity", {"entity_id": shift.team_member_id}
                )
            if team_member.skill != "engineering":
                return self._reject(
                    envelope,
                    "skill_mismatch",
                    {
                        "shift_id": shift.id,
                        "team_member_id": team_member.id,
                        "skill": team_member.skill,
                    },
                )

        required, trigger = self._requires_approval(envelope)
        if required and not envelope.approval_ref:
            return self._reject(envelope, "approval_required", {"trigger": trigger})

        # --- Deterministically select every physical room this command will
        # mutate (destination consumption + best-effort source release) and
        # accumulate the exact per-hotel counter deltas those selections
        # imply, *before* mutating anything. Every selected room and every
        # hotel whose counters will actually change becomes a required
        # target: the caller's expected_versions must already declare it
        # (§ do not silently mutate an entity absent from expected_versions).
        used_rooms: set[str] = set()
        hotel_deltas: dict[str, dict[str, int]] = {}
        relocation_rooms: dict[str, tuple[str, str | None]] = {}  # booking_id -> (dest_room_id, source_room_id)

        for room_id in payload.rooms_to_restore:
            room = self.rooms[room_id]
            hotel_deltas.setdefault(room.hotel_id, {})
            hotel_deltas[room.hotel_id][room.room_type] = (
                hotel_deltas[room.hotel_id].get(room.room_type, 0) + 1
            )

        for reloc in payload.relocations:
            booking = self.bookings[reloc.booking_id]
            dest_room_id = self.select_available_room(
                reloc.destination_hotel_id, reloc.destination_room_type, exclude=frozenset(used_rooms)
            )
            if dest_room_id is None:
                return self._reject(
                    envelope,
                    "insufficient_capacity",
                    {
                        "hotel_id": reloc.destination_hotel_id,
                        "room_type": reloc.destination_room_type,
                        "reason": "no_physical_room",
                    },
                )
            used_rooms.add(dest_room_id)
            hotel_deltas.setdefault(reloc.destination_hotel_id, {})
            hotel_deltas[reloc.destination_hotel_id][reloc.destination_room_type] = (
                hotel_deltas[reloc.destination_hotel_id].get(reloc.destination_room_type, 0) - 1
            )

            source_room_id = self.select_occupied_room(
                booking.hotel_id, booking.room_type, exclude=frozenset(used_rooms)
            )
            if source_room_id is not None:
                used_rooms.add(source_room_id)
                hotel_deltas.setdefault(booking.hotel_id, {})
                hotel_deltas[booking.hotel_id][booking.room_type] = (
                    hotel_deltas[booking.hotel_id].get(booking.room_type, 0) + 1
                )

            relocation_rooms[reloc.booking_id] = (dest_room_id, source_room_id)

        full_targets_by_id: dict[str, dict[str, Any]] = {eid: coll for eid, coll in base_targets}
        for room_id in used_rooms:
            full_targets_by_id[room_id] = self.rooms
        for hotel_id, deltas in hotel_deltas.items():
            if any(delta != 0 for delta in deltas.values()):
                full_targets_by_id[hotel_id] = self.hotels

        version_failure = self._check_expected_versions(
            envelope.expected_versions, list(full_targets_by_id.items())
        )
        if version_failure is not None:
            reason, details = version_failure
            return self._reject(envelope, reason, details)

        # --- All validation passed: mutate atomically -----------------------
        events: list[WorldEvent] = []

        self.work_orders[work_order.id] = dc_replace(
            work_order, status="in_progress", priority="critical", version=work_order.version + 1
        )
        events.append(
            self._make_event(
                envelope,
                "hotel-recovery.work-order.expedited",
                (work_order.id,),
                {"work_order_id": work_order.id},
            )
        )

        for room_id in payload.rooms_to_restore:
            room = self.rooms[room_id]
            self.rooms[room_id] = dc_replace(room, status="available", version=room.version + 1)
            events.append(
                self._make_event(
                    envelope,
                    "hotel-recovery.room.restored",
                    (room_id,),
                    {"room_id": room_id},
                )
            )

        for reloc in payload.relocations:
            booking = self.bookings[reloc.booking_id]
            self.bookings[reloc.booking_id] = dc_replace(
                booking,
                hotel_id=reloc.destination_hotel_id,
                room_type=reloc.destination_room_type,
                status="relocated",
                version=booking.version + 1,
            )
            dest_room_id, source_room_id = relocation_rooms[reloc.booking_id]
            dest_room = self.rooms[dest_room_id]
            self.rooms[dest_room_id] = dc_replace(dest_room, status="occupied", version=dest_room.version + 1)
            events.append(
                self._make_event(
                    envelope,
                    "hotel-recovery.room.consumed",
                    (reloc.booking_id, dest_room_id),
                    {
                        "booking_id": reloc.booking_id,
                        "room_id": dest_room_id,
                        "hotel_id": reloc.destination_hotel_id,
                        "room_type": reloc.destination_room_type,
                    },
                )
            )
            if source_room_id is not None:
                source_room = self.rooms[source_room_id]
                self.rooms[source_room_id] = dc_replace(
                    source_room, status="available", version=source_room.version + 1
                )
                events.append(
                    self._make_event(
                        envelope,
                        "hotel-recovery.room.released",
                        (reloc.booking_id, source_room_id),
                        {
                            "booking_id": reloc.booking_id,
                            "room_id": source_room_id,
                            "hotel_id": booking.hotel_id,
                            "room_type": booking.room_type,
                        },
                    )
                )
            events.append(
                self._make_event(
                    envelope,
                    "hotel-recovery.booking.relocated",
                    (reloc.booking_id, reloc.destination_hotel_id),
                    {
                        "booking_id": reloc.booking_id,
                        "destination_hotel_id": reloc.destination_hotel_id,
                        "destination_room_type": reloc.destination_room_type,
                    },
                )
            )

        if hotel_deltas:
            mutated_hotels_before = {
                hid for hid, deltas in hotel_deltas.items() if any(d != 0 for d in deltas.values())
            }
            self._apply_hotel_availability_deltas(hotel_deltas)
            for hotel_id in sorted(mutated_hotels_before):
                events.append(
                    self._make_event(
                        envelope,
                        "hotel-recovery.hotel.availability-synced",
                        (hotel_id,),
                        {"hotel_id": hotel_id},
                    )
                )

        for move in payload.shift_moves:
            shift = self.shifts[move.shift_id]
            self.shifts[move.shift_id] = dc_replace(
                shift,
                hotel_id=move.destination_hotel_id,
                status="reallocated",
                version=shift.version + 1,
            )
            events.append(
                self._make_event(
                    envelope,
                    "hotel-recovery.shift.reallocated",
                    (move.shift_id, move.destination_hotel_id),
                    {"shift_id": move.shift_id, "destination_hotel_id": move.destination_hotel_id},
                )
            )

        for action in payload.guest_communication_actions:
            events.append(
                self._make_event(
                    envelope,
                    "hotel-recovery.guest-action.issued",
                    (),
                    {"action": action},
                )
            )

        result = CommandResult(
            accepted=True,
            reason="accepted",
            command_id=envelope.command_id,
            command_type=envelope.command_type,
            idempotent_replay=False,
            events=tuple(events),
            snapshot=self.snapshot(),
            snapshot_digest=self._digest(),
            details={},
        )
        self._events.extend(events)
        return result

    # --- B. room.readiness-plan.apply ---------------------------------------

    def _apply_room_readiness_plan(self, envelope: CommandEnvelope) -> CommandResult:
        payload = envelope.payload
        if type(payload) is not RoomReadinessPlanPayload:
            return self._reject(
                envelope,
                "invalid_command_payload",
                {"field": "payload", "error": "payload_type_mismatch"},
            )

        if len(set(payload.room_ids)) != len(payload.room_ids):
            return self._reject(
                envelope,
                "invalid_command_payload",
                {"field": "room_ids", "error": "duplicate_ids"},
            )

        base_targets: list[tuple[str, dict[str, Any]]] = [
            (room_id, self.rooms) for room_id in payload.room_ids
        ]
        if payload.maintenance_work_order_id is not None:
            base_targets.append((payload.maintenance_work_order_id, self.work_orders))

        version_failure = self._check_target_versions(envelope.expected_versions, base_targets)
        if version_failure is not None:
            reason, details = version_failure
            return self._reject(envelope, reason, details)

        maintenance_wo: WorkOrder | None = None
        if payload.maintenance_work_order_id is not None:
            maintenance_wo = self.work_orders[payload.maintenance_work_order_id]

        for room_id in payload.room_ids:
            room = self.rooms[room_id]
            if room.status == "unavailable" and payload.target_status == "available":
                if maintenance_wo is None or maintenance_wo.status != "completed":
                    return self._reject(
                        envelope,
                        "maintenance_evidence_missing",
                        {"room_id": room_id},
                    )
            # Explicit reject rule: a currently occupied (guest-in-residence)
            # room can never be silently made available or not_ready by a
            # readiness plan — that would evict/disturb an active stay.
            if room.status == "occupied":
                return self._reject(
                    envelope,
                    "invalid_room_status",
                    {"room_id": room_id, "status": room.status, "target_status": payload.target_status},
                )

        required, trigger = self._requires_approval(envelope)
        if required and not envelope.approval_ref:
            return self._reject(envelope, "approval_required", {"trigger": trigger})

        # --- Explicit no-op vs. real-transition classification, and the
        # exact per-hotel availability delta each real transition implies.
        # available <-> not_ready is the only transition that changes a
        # hotel's denormalized available_* counters; unavailable -> not_ready
        # and identical current==target transitions never do.
        rooms_to_mutate: list[str] = []
        hotel_deltas: dict[str, dict[str, int]] = {}
        for room_id in payload.room_ids:
            room = self.rooms[room_id]
            target = payload.target_status
            if room.status == target:
                continue  # explicit no-op: nothing changes, nothing mutated
            rooms_to_mutate.append(room_id)
            if target == "available" and room.status in ("not_ready", "unavailable"):
                hotel_deltas.setdefault(room.hotel_id, {})
                hotel_deltas[room.hotel_id][room.room_type] = (
                    hotel_deltas[room.hotel_id].get(room.room_type, 0) + 1
                )
            elif target == "not_ready" and room.status == "available":
                hotel_deltas.setdefault(room.hotel_id, {})
                hotel_deltas[room.hotel_id][room.room_type] = (
                    hotel_deltas[room.hotel_id].get(room.room_type, 0) - 1
                )
            # target == "not_ready" and room.status == "unavailable": no
            # counter change — neither status counts as available.

        full_targets_by_id: dict[str, dict[str, Any]] = {eid: coll for eid, coll in base_targets}
        for hotel_id, deltas in hotel_deltas.items():
            if any(delta != 0 for delta in deltas.values()):
                full_targets_by_id[hotel_id] = self.hotels

        version_failure = self._check_expected_versions(
            envelope.expected_versions, list(full_targets_by_id.items())
        )
        if version_failure is not None:
            reason, details = version_failure
            return self._reject(envelope, reason, details)

        events: list[WorldEvent] = []
        for room_id in rooms_to_mutate:
            room = self.rooms[room_id]
            self.rooms[room_id] = dc_replace(
                room, status=payload.target_status, version=room.version + 1
            )
            events.append(
                self._make_event(
                    envelope,
                    "room-readiness-plan.room.updated",
                    (room_id,),
                    {"room_id": room_id, "target_status": payload.target_status},
                )
            )

        if hotel_deltas:
            mutated_hotels = {
                hid for hid, deltas in hotel_deltas.items() if any(d != 0 for d in deltas.values())
            }
            self._apply_hotel_availability_deltas(hotel_deltas)
            for hotel_id in sorted(mutated_hotels):
                events.append(
                    self._make_event(
                        envelope,
                        "room-readiness-plan.hotel.availability-synced",
                        (hotel_id,),
                        {"hotel_id": hotel_id},
                    )
                )

        if maintenance_wo is not None:
            self.work_orders[maintenance_wo.id] = dc_replace(
                maintenance_wo, version=maintenance_wo.version + 1
            )
            events.append(
                self._make_event(
                    envelope,
                    "room-readiness-plan.work-order.acknowledged",
                    (maintenance_wo.id,),
                    {"work_order_id": maintenance_wo.id},
                )
            )

        result = CommandResult(
            accepted=True,
            reason="accepted",
            command_id=envelope.command_id,
            command_type=envelope.command_type,
            idempotent_replay=False,
            events=tuple(events),
            snapshot=self.snapshot(),
            snapshot_digest=self._digest(),
            details={},
        )
        self._events.extend(events)
        return result

    # --- C. maintenance.work-order.dispatch ---------------------------------

    def _apply_maintenance_work_order_dispatch(
        self, envelope: CommandEnvelope
    ) -> CommandResult:
        payload = envelope.payload
        if type(payload) is not MaintenanceWorkOrderDispatchPayload:
            return self._reject(
                envelope,
                "invalid_command_payload",
                {"field": "payload", "error": "payload_type_mismatch"},
            )

        targets = [(payload.work_order_id, self.work_orders)]
        version_failure = self._check_expected_versions(envelope.expected_versions, targets)
        if version_failure is not None:
            reason, details = version_failure
            return self._reject(envelope, reason, details)

        if payload.assigned_team_member_id not in self.team_members:
            return self._reject(
                envelope, "unknown_entity", {"entity_id": payload.assigned_team_member_id}
            )

        assigned_team_member = self.team_members[payload.assigned_team_member_id]
        if assigned_team_member.skill != "engineering":
            return self._reject(
                envelope,
                "skill_mismatch",
                {
                    "team_member_id": assigned_team_member.id,
                    "skill": assigned_team_member.skill,
                },
            )

        work_order = self.work_orders[payload.work_order_id]
        if work_order.status not in ("open", "planned"):
            return self._reject(
                envelope,
                "closed_work_order",
                {"work_order_id": work_order.id, "status": work_order.status},
            )

        required, trigger = self._requires_approval(envelope)
        if required and not envelope.approval_ref:
            return self._reject(envelope, "approval_required", {"trigger": trigger})

        self.work_orders[work_order.id] = dc_replace(
            work_order,
            status="in_progress",
            assigned_team_member_id=payload.assigned_team_member_id,
            priority=payload.priority,
            version=work_order.version + 1,
        )
        event = self._make_event(
            envelope,
            "maintenance-work-order.dispatched",
            (work_order.id,),
            {
                "work_order_id": work_order.id,
                "assigned_team_member_id": payload.assigned_team_member_id,
                "priority": payload.priority,
            },
        )
        self._events.append(event)
        return CommandResult(
            accepted=True,
            reason="accepted",
            command_id=envelope.command_id,
            command_type=envelope.command_type,
            idempotent_replay=False,
            events=(event,),
            snapshot=self.snapshot(),
            snapshot_digest=self._digest(),
            details={},
        )

    # --- D. guest.recovery-action.issue --------------------------------------

    def _apply_guest_recovery_action(self, envelope: CommandEnvelope) -> CommandResult:
        payload = envelope.payload
        if type(payload) is not GuestRecoveryActionPayload:
            return self._reject(
                envelope,
                "invalid_command_payload",
                {"field": "payload", "error": "payload_type_mismatch"},
            )

        # The declared estimated value gates the authority/approval check
        # below (role spend limits). A payload value_gbp that does not
        # match it — including a low/zero estimate paired with a large
        # actual value — would silently bypass that gate, so the two must
        # agree (to the penny) before anything else is evaluated.
        if round(payload.value_gbp, 2) != round(envelope.estimated_value_gbp, 2):
            return self._reject(
                envelope,
                "value_mismatch",
                {
                    "value_gbp": payload.value_gbp,
                    "estimated_value_gbp": envelope.estimated_value_gbp,
                },
            )

        targets = [
            (payload.booking_id, self.bookings),
            (payload.guest_party_id, self.guest_parties),
        ]
        version_failure = self._check_expected_versions(envelope.expected_versions, targets)
        if version_failure is not None:
            reason, details = version_failure
            return self._reject(envelope, reason, details)

        booking = self.bookings[payload.booking_id]
        if booking.guest_party_id != payload.guest_party_id:
            return self._reject(
                envelope,
                "guest_party_mismatch",
                {"booking_id": booking.id, "guest_party_id": payload.guest_party_id},
            )

        required, trigger = self._requires_approval(envelope)
        if required and not envelope.approval_ref:
            return self._reject(envelope, "approval_required", {"trigger": trigger})

        guest_party = self.guest_parties[payload.guest_party_id]
        self.guest_parties[payload.guest_party_id] = dc_replace(
            guest_party, version=guest_party.version + 1
        )
        # The booking itself is never cancelled or relocated by this command.
        event = self._make_event(
            envelope,
            "guest-recovery-action.issued",
            (payload.booking_id, payload.guest_party_id),
            {
                "booking_id": payload.booking_id,
                "guest_party_id": payload.guest_party_id,
                "action_code": payload.action_code,
                "value_gbp": payload.value_gbp,
            },
        )
        self._events.append(event)
        return CommandResult(
            accepted=True,
            reason="accepted",
            command_id=envelope.command_id,
            command_type=envelope.command_type,
            idempotent_replay=False,
            events=(event,),
            snapshot=self.snapshot(),
            snapshot_digest=self._digest(),
            details={},
        )

    # --- E. booking.inventory-plan.apply -------------------------------------

    def _apply_booking_inventory_plan(self, envelope: CommandEnvelope) -> CommandResult:
        payload = envelope.payload
        if type(payload) is not BookingInventoryPlanPayload:
            return self._reject(
                envelope,
                "invalid_command_payload",
                {"field": "payload", "error": "payload_type_mismatch"},
            )

        base_targets = [
            (payload.booking_id, self.bookings),
            (payload.destination_hotel_id, self.hotels),
        ]
        version_failure = self._check_target_versions(envelope.expected_versions, base_targets)
        if version_failure is not None:
            reason, details = version_failure
            return self._reject(envelope, reason, details)

        booking = self.bookings[payload.booking_id]
        if not _is_requirement_compatible(booking.requirement, payload.destination_room_type):
            return self._reject(
                envelope,
                "incompatible_room",
                {
                    "booking_id": booking.id,
                    "requirement": booking.requirement,
                    "destination_room_type": payload.destination_room_type,
                },
            )

        dest_hotel = self.hotels[payload.destination_hotel_id]
        avail_key = f"available_{payload.destination_room_type}_rooms"
        available = getattr(dest_hotel, avail_key, 0)
        if available <= 0:
            return self._reject(
                envelope,
                "insufficient_capacity",
                {
                    "hotel_id": dest_hotel.id,
                    "room_type": payload.destination_room_type,
                    "available": available,
                },
            )

        required, trigger = self._requires_approval(envelope)
        if required and not envelope.approval_ref:
            return self._reject(envelope, "approval_required", {"trigger": trigger})

        # --- Deterministically select the physical destination room to
        # consume and (best-effort) the physical source room to release,
        # exactly like the hero relocation path, before mutating anything.
        dest_room_id = self.select_available_room(dest_hotel.id, payload.destination_room_type)
        if dest_room_id is None:
            return self._reject(
                envelope,
                "insufficient_capacity",
                {
                    "hotel_id": dest_hotel.id,
                    "room_type": payload.destination_room_type,
                    "reason": "no_physical_room",
                },
            )
        source_room_id = self.select_occupied_room(
            booking.hotel_id, booking.room_type, exclude=frozenset({dest_room_id})
        )

        hotel_deltas: dict[str, dict[str, int]] = {
            dest_hotel.id: {payload.destination_room_type: -1}
        }
        if source_room_id is not None:
            hotel_deltas.setdefault(booking.hotel_id, {})
            hotel_deltas[booking.hotel_id][booking.room_type] = (
                hotel_deltas[booking.hotel_id].get(booking.room_type, 0) + 1
            )

        full_targets_by_id: dict[str, dict[str, Any]] = {eid: coll for eid, coll in base_targets}
        full_targets_by_id[dest_room_id] = self.rooms
        if source_room_id is not None:
            full_targets_by_id[source_room_id] = self.rooms
        for hotel_id, deltas in hotel_deltas.items():
            if any(delta != 0 for delta in deltas.values()):
                full_targets_by_id[hotel_id] = self.hotels

        version_failure = self._check_expected_versions(
            envelope.expected_versions, list(full_targets_by_id.items())
        )
        if version_failure is not None:
            reason, details = version_failure
            return self._reject(envelope, reason, details)

        cross_property = booking.hotel_id != payload.destination_hotel_id
        new_status = "relocated" if cross_property else booking.status
        self.bookings[booking.id] = dc_replace(
            booking,
            hotel_id=payload.destination_hotel_id,
            room_type=payload.destination_room_type,
            status=new_status,
            version=booking.version + 1,
        )

        events: list[WorldEvent] = []
        self._apply_hotel_availability_deltas(hotel_deltas)

        dest_room = self.rooms[dest_room_id]
        self.rooms[dest_room_id] = dc_replace(dest_room, status="occupied", version=dest_room.version + 1)
        events.append(
            self._make_event(
                envelope,
                "booking-inventory-plan.room.consumed",
                (booking.id, dest_room_id),
                {"booking_id": booking.id, "room_id": dest_room_id, "hotel_id": dest_hotel.id},
            )
        )
        if source_room_id is not None:
            source_room = self.rooms[source_room_id]
            self.rooms[source_room_id] = dc_replace(
                source_room, status="available", version=source_room.version + 1
            )
            events.append(
                self._make_event(
                    envelope,
                    "booking-inventory-plan.room.released",
                    (booking.id, source_room_id),
                    {"booking_id": booking.id, "room_id": source_room_id, "hotel_id": booking.hotel_id},
                )
            )

        events.append(
            self._make_event(
                envelope,
                "booking-inventory-plan.booking.reassigned",
                (booking.id, dest_hotel.id),
                {
                    "booking_id": booking.id,
                    "destination_hotel_id": dest_hotel.id,
                    "destination_room_type": payload.destination_room_type,
                    "cross_property": cross_property,
                },
            )
        )
        self._events.extend(events)
        return CommandResult(
            accepted=True,
            reason="accepted",
            command_id=envelope.command_id,
            command_type=envelope.command_type,
            idempotent_replay=False,
            events=tuple(events),
            snapshot=self.snapshot(),
            snapshot_digest=self._digest(),
            details={},
        )

    # --- F. workforce.shift-plan.apply --------------------------------------

    def _apply_workforce_shift_plan(self, envelope: CommandEnvelope) -> CommandResult:
        payload = envelope.payload
        if type(payload) is not WorkforceShiftPlanPayload:
            return self._reject(
                envelope,
                "invalid_command_payload",
                {"field": "payload", "error": "payload_type_mismatch"},
            )

        targets = [(payload.shift_id, self.shifts)]
        version_failure = self._check_expected_versions(envelope.expected_versions, targets)
        if version_failure is not None:
            reason, details = version_failure
            return self._reject(envelope, reason, details)

        if payload.destination_hotel_id not in self.hotels:
            return self._reject(
                envelope, "unknown_entity", {"entity_id": payload.destination_hotel_id}
            )

        shift = self.shifts[payload.shift_id]
        team_member = self.team_members.get(shift.team_member_id)
        if team_member is None or team_member.skill != shift.skill:
            return self._reject(
                envelope,
                "skill_mismatch",
                {"shift_id": shift.id, "skill": shift.skill},
            )

        required, trigger = self._requires_approval(envelope)
        if required and not envelope.approval_ref:
            return self._reject(envelope, "approval_required", {"trigger": trigger})

        self.shifts[shift.id] = dc_replace(
            shift,
            hotel_id=payload.destination_hotel_id,
            status="reallocated",
            version=shift.version + 1,
        )
        event = self._make_event(
            envelope,
            "workforce-shift-plan.shift.reassigned",
            (shift.id, payload.destination_hotel_id),
            {"shift_id": shift.id, "destination_hotel_id": payload.destination_hotel_id},
        )
        self._events.append(event)
        return CommandResult(
            accepted=True,
            reason="accepted",
            command_id=envelope.command_id,
            command_type=envelope.command_type,
            idempotent_replay=False,
            events=(event,),
            snapshot=self.snapshot(),
            snapshot_digest=self._digest(),
            details={},
        )

    # --- G. food-beverage.service-plan.apply ---------------------------------

    def _apply_food_beverage_service_plan(self, envelope: CommandEnvelope) -> CommandResult:
        payload = envelope.payload
        if type(payload) is not FoodBeverageServicePlanPayload:
            return self._reject(
                envelope,
                "invalid_command_payload",
                {"field": "payload", "error": "payload_type_mismatch"},
            )

        targets = [(payload.plan_id, self.food_service_plans)]
        version_failure = self._check_expected_versions(envelope.expected_versions, targets)
        if version_failure is not None:
            reason, details = version_failure
            return self._reject(envelope, reason, details)

        plan = self.food_service_plans[payload.plan_id]
        # SYNTHETIC ASSUMPTION: prepared covers may never exceed 150% of the
        # forecast — a bounded reversible readiness adjustment.
        bound = plan.covers_forecast * 1.5
        if payload.covers_prepared > bound:
            return self._reject(
                envelope,
                "invalid_bounds",
                {"plan_id": plan.id, "covers_prepared": payload.covers_prepared, "bound": bound},
            )

        required, trigger = self._requires_approval(envelope)
        if required and not envelope.approval_ref:
            return self._reject(envelope, "approval_required", {"trigger": trigger})

        if payload.covers_prepared >= plan.covers_forecast:
            status = "ready"
        elif payload.covers_prepared >= plan.covers_forecast * 0.7:
            status = "at_risk"
        else:
            status = "insufficient"

        self.food_service_plans[plan.id] = dc_replace(
            plan,
            covers_prepared=payload.covers_prepared,
            status=status,
            version=plan.version + 1,
        )
        event = self._make_event(
            envelope,
            "food-beverage-service-plan.plan.updated",
            (plan.id,),
            {"plan_id": plan.id, "covers_prepared": payload.covers_prepared, "status": status},
        )
        self._events.append(event)
        return CommandResult(
            accepted=True,
            reason="accepted",
            command_id=envelope.command_id,
            command_type=envelope.command_type,
            idempotent_replay=False,
            events=(event,),
            snapshot=self.snapshot(),
            snapshot_digest=self._digest(),
            details={},
        )

    # --- H. energy.control-plan.apply ----------------------------------------

    def _apply_energy_control_plan(self, envelope: CommandEnvelope) -> CommandResult:
        payload = envelope.payload
        if type(payload) is not EnergyControlPlanPayload:
            return self._reject(
                envelope,
                "invalid_command_payload",
                {"field": "payload", "error": "payload_type_mismatch"},
            )

        targets = [(payload.meter_id, self.energy_meters)]
        version_failure = self._check_expected_versions(envelope.expected_versions, targets)
        if version_failure is not None:
            reason, details = version_failure
            return self._reject(envelope, reason, details)

        meter = self.energy_meters[payload.meter_id]
        # SYNTHETIC ASSUMPTION: comfort/safety band is +/-30% of baseline.
        lower_bound = meter.baseline_kwh * 0.7
        upper_bound = meter.baseline_kwh * 1.3
        if not (lower_bound <= payload.target_reading_kwh <= upper_bound):
            return self._reject(
                envelope,
                "comfort_safety_violation",
                {
                    "meter_id": meter.id,
                    "target_reading_kwh": payload.target_reading_kwh,
                    "lower_bound": lower_bound,
                    "upper_bound": upper_bound,
                },
            )

        required, trigger = self._requires_approval(envelope)
        if required and not envelope.approval_ref:
            return self._reject(envelope, "approval_required", {"trigger": trigger})

        if abs(payload.target_reading_kwh - meter.baseline_kwh) <= meter.baseline_kwh * 0.05:
            status = "normal"
        else:
            status = "anomaly"

        self.energy_meters[meter.id] = dc_replace(
            meter,
            reading_kwh=payload.target_reading_kwh,
            status=status,
            version=meter.version + 1,
        )
        event = self._make_event(
            envelope,
            "energy-control-plan.meter.adjusted",
            (meter.id,),
            {
                "meter_id": meter.id,
                "control_action": payload.control_action,
                "target_reading_kwh": payload.target_reading_kwh,
                "status": status,
            },
        )
        self._events.append(event)
        return CommandResult(
            accepted=True,
            reason="accepted",
            command_id=envelope.command_id,
            command_type=envelope.command_type,
            idempotent_replay=False,
            events=(event,),
            snapshot=self.snapshot(),
            snapshot_digest=self._digest(),
            details={},
        )
