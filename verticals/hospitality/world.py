"""Hospitality actor world: deterministic seed, scenario, and sensor polling.

``HospitalityWorld.demo(seed)`` builds the complete deterministic state.
``HospitalityWorld.reset(seed)`` restores the exact initial snapshot and
clears all sensor dedupe / scenario state.

All IDs and serialized ordering are deterministic. Identical seed → identical
snapshot bytes. No wall-clock dependence; time is measured in integer ticks.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

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
from verticals.hospitality.dynamics import (
    ARRIVAL_HORIZON_TICKS,
)
from verticals.hospitality.sensors import evaluate_operations_risk


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
        """Evaluate sensor thresholds and return any new events.

        Dedupe key is ``(source_event_id, workflow_type)``; each unique
        combination fires at most once regardless of how many times this
        method is called.
        """
        snap = self.snapshot()
        measurement = evaluate_operations_risk(snap)
        if measurement is None:
            return []

        source_event_id = f"SRC-{self._seed}-{self._scenario_applied}"
        workflow_type = "hotel-operations-recovery"
        dedupe_key = (source_event_id, workflow_type)
        if dedupe_key in self._seen_sensor_keys:
            return []

        self._seen_sensor_keys.add(dedupe_key)
        self._event_counter += 1
        event_id = (
            f"EVT-HOSP-{self.tick:06d}-{self._event_counter:06d}"
            f"-{self._seed}"
        )
        hotel_id = measurement["hotel_id"]
        asset_id = measurement["asset_id"]

        event = WorldEvent(
            event_id=event_id,
            type="hotel.operations-risk.detected",
            workflow_type=workflow_type,
            actor_ids=(hotel_id, asset_id),
            payload=dict(measurement, source_event_id=source_event_id),
            tick=self.tick,
            source="hospitality-operations-sensor",
            trace_id=f"hosp-ops-{self._seed}-{self._scenario_applied}",
        )
        self._events.append(event)
        return [event]

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
            self.shifts[shift_id] = Shift(
                id=shift_id,
                team_member_id=member_id,
                hotel_id=member.hotel_id,
                skill=member.skill,
                start_tick=1,
                end_tick=9,
                status="scheduled",
                version=1,
            )

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
                estimated_hours=6.0,
                cost_estimate_gbp=2_400.0,  # SYNTHETIC ASSUMPTION
                version=wo.version + 1,
                contractor_available=True,
            )

        # --- Ensure sister hotels have capacity for 10 relocations ------
        # Airport North: 5 compatible standard rooms
        # City Gate: 5 compatible standard rooms
        self._ensure_sister_capacity("HOTEL-AIRPORT-NORTH", standard=5)
        self._ensure_sister_capacity("HOTEL-CITY-GATE", standard=5)

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
