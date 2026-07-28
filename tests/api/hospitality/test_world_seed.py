"""Task 3: Deterministic hotel actor world — seed, entity counts, and reset."""
from __future__ import annotations

import dataclasses

import pytest

from verticals.hospitality.domains import HOSPITALITY_DOMAINS
from verticals.hospitality.reference_cases import HOSPITALITY_REFERENCE_CASES
from verticals.hospitality.world import HospitalityWorld

# Import the compiled boundary patterns so this file does not embed the
# literal forbidden terms (which would cause the boundary scanner to flag it).
from tests.api.hospitality.test_customer_boundary import FORBIDDEN as _FORBIDDEN_PATTERNS

DEMO_SEED = 20260728

EXPECTED_HOTEL_NAMES = {
    "Riverside Central",
    "Airport North",
    "City Gate",
    "Harbour View",
    "Messe Central",
    "Rhine Park",
}


# ---------------------------------------------------------------------------
# Entity counts
# ---------------------------------------------------------------------------


def test_hotel_count():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    assert len(world.hotels) == 6


def test_room_count():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    assert len(world.rooms) == 240


def test_booking_count():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    assert len(world.bookings) == 180


def test_team_member_count():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    assert len(world.team_members) == 36


def test_critical_asset_count():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    assert len(world.critical_assets) == 18


def test_work_order_count():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    assert len(world.work_orders) == 12


def test_food_service_plan_count():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    assert len(world.food_service_plans) == 6


def test_energy_meter_count():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    assert len(world.energy_meters) == 12


# ---------------------------------------------------------------------------
# Fictional hotel labels
# ---------------------------------------------------------------------------


def test_fictional_hotel_names():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    names = {h.name for h in world.hotels.values()}
    assert names == EXPECTED_HOTEL_NAMES


def test_hotel_ids_deterministic():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    assert "HOTEL-RIVERSIDE-CENTRAL" in world.hotels
    assert "HOTEL-AIRPORT-NORTH" in world.hotels
    assert "HOTEL-CITY-GATE" in world.hotels
    assert "HOTEL-HARBOUR-VIEW" in world.hotels
    assert "HOTEL-MESSE-CENTRAL" in world.hotels
    assert "HOTEL-RHINE-PARK" in world.hotels


# ---------------------------------------------------------------------------
# Room types
# ---------------------------------------------------------------------------


def test_room_types_present():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    types = {r.room_type for r in world.rooms.values()}
    assert types >= {"standard", "family", "accessible", "premium"}


def test_room_hotel_coverage():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    hotel_ids = set(world.hotels)
    room_hotels = {r.hotel_id for r in world.rooms.values()}
    assert room_hotels == hotel_ids


# ---------------------------------------------------------------------------
# Team member skills
# ---------------------------------------------------------------------------


def test_team_member_skills():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    skills = {m.skill for m in world.team_members.values()}
    assert skills >= {"front-office", "housekeeping", "engineering", "food-service"}


# ---------------------------------------------------------------------------
# Work order statuses
# ---------------------------------------------------------------------------


def test_work_orders_have_open_or_planned():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    statuses = {wo.status for wo in world.work_orders.values()}
    assert statuses <= {"open", "planned", "in_progress", "completed"}
    assert statuses & {"open", "planned"}


# ---------------------------------------------------------------------------
# Same-seed snapshot equality
# ---------------------------------------------------------------------------


def test_same_seed_snapshot_equality():
    w1 = HospitalityWorld.demo(seed=DEMO_SEED)
    w2 = HospitalityWorld.demo(seed=DEMO_SEED)
    assert w1.snapshot() == w2.snapshot()


def test_different_seed_snapshot_differs():
    w1 = HospitalityWorld.demo(seed=DEMO_SEED)
    w2 = HospitalityWorld.demo(seed=DEMO_SEED + 1)
    assert w1.snapshot() != w2.snapshot()


# ---------------------------------------------------------------------------
# Reset equality
# ---------------------------------------------------------------------------


def test_reset_restores_exact_initial_snapshot():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    before = world.snapshot()
    world.trigger_scenario("riverside-hot-water-outage")
    world.reset(seed=DEMO_SEED)
    assert world.snapshot() == before


def test_reset_clears_events():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    world.poll_sensor_events()
    world.reset(seed=DEMO_SEED)
    # After reset, no scenario -> no events
    events = world.poll_sensor_events()
    assert events == []


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------


def test_hotel_order_is_deterministic():
    w1 = HospitalityWorld.demo(seed=DEMO_SEED)
    w2 = HospitalityWorld.demo(seed=DEMO_SEED)
    assert list(w1.hotels.keys()) == list(w2.hotels.keys())


def test_room_order_is_deterministic():
    w1 = HospitalityWorld.demo(seed=DEMO_SEED)
    w2 = HospitalityWorld.demo(seed=DEMO_SEED)
    assert list(w1.rooms.keys()) == list(w2.rooms.keys())


def test_booking_order_is_deterministic():
    w1 = HospitalityWorld.demo(seed=DEMO_SEED)
    w2 = HospitalityWorld.demo(seed=DEMO_SEED)
    assert list(w1.bookings.keys()) == list(w2.bookings.keys())


def test_snapshot_section_keys_ordered():
    w1 = HospitalityWorld.demo(seed=DEMO_SEED)
    w2 = HospitalityWorld.demo(seed=DEMO_SEED)
    snap1 = w1.snapshot()
    snap2 = w2.snapshot()
    # Key order is deterministic across same-seed instances
    assert list(snap1.keys()) == list(snap2.keys())
    # Entity sections (after seed/tick/scenario metadata) are alphabetically sorted
    entity_sections = [k for k in snap1.keys() if k not in ("seed", "tick", "scenario")]
    assert entity_sections == sorted(entity_sections)
    # Booking keys are deterministic and sorted
    booking_keys = list(snap1["bookings"].keys())
    assert booking_keys == sorted(booking_keys)


# ---------------------------------------------------------------------------
# No forbidden customer-identifying terms in snapshot
# ---------------------------------------------------------------------------


def test_snapshot_no_forbidden_terms():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    snap_str = str(world.snapshot())
    for pattern in _FORBIDDEN_PATTERNS:
        assert not pattern.search(snap_str), (
            f"Forbidden pattern '{pattern.pattern}' found in snapshot"
        )


# ---------------------------------------------------------------------------
# Reference cases — exactly eight workflow IDs
# ---------------------------------------------------------------------------


def test_reference_case_count():
    assert len(HOSPITALITY_REFERENCE_CASES) == 8


def test_reference_case_keys_match_domains():
    assert set(HOSPITALITY_REFERENCE_CASES.keys()) == set(HOSPITALITY_DOMAINS.keys())


def test_hero_reference_case_key():
    assert "hotel-operations-recovery" in HOSPITALITY_REFERENCE_CASES


def test_reference_cases_have_expected_fields():
    for key, case in HOSPITALITY_REFERENCE_CASES.items():
        assert case.id, f"Case {key} missing id"
        assert case.workflow_type == key, f"Case {key} workflow_type mismatch"
        assert isinstance(case.subject_ids, tuple), f"Case {key} subject_ids not tuple"
        assert isinstance(case.facts, dict), f"Case {key} facts not dict"


# ---------------------------------------------------------------------------
# Fix 1 (RED first): entity dataclasses must be frozen
# ---------------------------------------------------------------------------


def test_hotel_entity_is_frozen():
    """Mutation of Hotel raises FrozenInstanceError — dataclass must have frozen=True."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    hotel = next(iter(world.hotels.values()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        hotel.status = "degraded"  # type: ignore[misc]


def test_room_entity_is_frozen():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    room = next(iter(world.rooms.values()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        room.status = "unavailable"  # type: ignore[misc]


def test_booking_entity_is_frozen():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    booking = next(iter(world.bookings.values()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        booking.status = "cancelled"  # type: ignore[misc]


def test_guest_party_entity_is_frozen():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    gp = next(iter(world.guest_parties.values()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        gp.size = 99  # type: ignore[misc]


def test_critical_asset_entity_is_frozen():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    asset = next(iter(world.critical_assets.values()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        asset.status = "fault"  # type: ignore[misc]


def test_work_order_entity_is_frozen():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    wo = next(iter(world.work_orders.values()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        wo.status = "in_progress"  # type: ignore[misc]


def test_team_member_entity_is_frozen():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    member = next(iter(world.team_members.values()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        member.status = "off_duty"  # type: ignore[misc]


def test_shift_entity_is_frozen():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    shift = next(iter(world.shifts.values()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        shift.status = "reallocated"  # type: ignore[misc]


def test_food_service_plan_entity_is_frozen():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    fsp = next(iter(world.food_service_plans.values()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        fsp.status = "at_risk"  # type: ignore[misc]


def test_energy_meter_entity_is_frozen():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    em = next(iter(world.energy_meters.values()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        em.status = "alert"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Fix 3 (RED first): all reference case subject IDs must resolve in the world
# ---------------------------------------------------------------------------


def test_all_reference_case_subject_ids_resolve():
    """Every subject_id in HOSPITALITY_REFERENCE_CASES resolves to a real world entity."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    all_ids = (
        set(world.hotels)
        | set(world.rooms)
        | set(world.bookings)
        | set(world.guest_parties)
        | set(world.critical_assets)
        | set(world.work_orders)
        | set(world.team_members)
        | set(world.shifts)
        | set(world.food_service_plans)
        | set(world.energy_meters)
    )
    dangling: list[str] = []
    for case_key, case in HOSPITALITY_REFERENCE_CASES.items():
        for subject_id in case.subject_ids:
            if subject_id not in all_ids:
                dangling.append(f"[{case_key}] {subject_id!r}")
    assert not dangling, f"Dangling subject IDs:\n" + "\n".join(dangling)
