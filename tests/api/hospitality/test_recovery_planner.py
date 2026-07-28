"""Task 3: Recovery planner — golden scenario and no-action cases."""
from __future__ import annotations

import pytest

from verticals.hospitality.recovery import plan_recovery
from verticals.hospitality.world import HospitalityWorld

DEMO_SEED = 20260728
HERO_HOTEL = "HOTEL-RIVERSIDE-CENTRAL"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _golden_snapshot():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    world.poll_sensor_events()  # consume sensor event
    return world.snapshot()


def _zero_sister_capacity_snapshot():
    """Snapshot with sister hotels having no available rooms."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    snap = world.snapshot()
    # Zero out available rooms at all hotels except hero
    for hotel_id, hotel in snap["hotels"].items():
        if hotel_id != HERO_HOTEL:
            hotel["available_standard_rooms"] = 0
            hotel["available_accessible_rooms"] = 0
            hotel["available_family_rooms"] = 0
            hotel["available_premium_rooms"] = 0
    for room_id, room in snap["rooms"].items():
        if room["hotel_id"] != HERO_HOTEL:
            room["status"] = "occupied"
    return snap


# ---------------------------------------------------------------------------
# Golden plan — status
# ---------------------------------------------------------------------------


def test_golden_plan_status_is_selected():
    result = plan_recovery(_golden_snapshot())
    assert result.status == "selected"


def test_golden_plan_is_not_none():
    result = plan_recovery(_golden_snapshot())
    assert result.plan is not None


# ---------------------------------------------------------------------------
# Golden plan — exactly 8 rooms to restore
# ---------------------------------------------------------------------------


def test_golden_plan_exact_8_rooms_to_restore():
    result = plan_recovery(_golden_snapshot())
    assert len(result.plan.rooms_to_restore) == 8


def test_rooms_to_restore_are_from_hero_hotel():
    result = plan_recovery(_golden_snapshot())
    snap = _golden_snapshot()
    for room_id in result.plan.rooms_to_restore:
        assert snap["rooms"][room_id]["hotel_id"] == HERO_HOTEL


def test_rooms_to_restore_are_currently_unavailable():
    result = plan_recovery(_golden_snapshot())
    snap = _golden_snapshot()
    for room_id in result.plan.rooms_to_restore:
        assert snap["rooms"][room_id]["status"] == "unavailable"


# ---------------------------------------------------------------------------
# Golden plan — exactly 10 relocations across exactly 2 sister hotels
# ---------------------------------------------------------------------------


def test_golden_plan_exact_10_relocations():
    result = plan_recovery(_golden_snapshot())
    assert len(result.plan.relocations) == 10


def test_golden_plan_relocations_across_exactly_2_sister_hotels():
    result = plan_recovery(_golden_snapshot())
    destination_hotels = {r.destination_hotel_id for r in result.plan.relocations}
    assert len(destination_hotels) == 2


def test_golden_plan_relocations_not_to_hero_hotel():
    result = plan_recovery(_golden_snapshot())
    for reloc in result.plan.relocations:
        assert reloc.destination_hotel_id != HERO_HOTEL


def test_golden_plan_relocations_split_across_sister_hotels():
    """Each sister hotel receives at least 1 relocation."""
    result = plan_recovery(_golden_snapshot())
    counts = {}
    for reloc in result.plan.relocations:
        counts[reloc.destination_hotel_id] = counts.get(reloc.destination_hotel_id, 0) + 1
    for hotel_id, count in counts.items():
        assert count >= 1


# ---------------------------------------------------------------------------
# Relocation room-type / requirement compatibility
# ---------------------------------------------------------------------------


def test_relocations_are_requirement_compatible():
    result = plan_recovery(_golden_snapshot())
    snap = _golden_snapshot()
    for reloc in result.plan.relocations:
        req = reloc.original_requirement
        dest_type = reloc.destination_room_type
        assert _is_compatible(req, dest_type), (
            f"Booking requirement '{req}' incompatible with "
            f"destination room type '{dest_type}'"
        )


def _is_compatible(requirement: str, room_type: str) -> bool:
    """Return True if room_type satisfies booking requirement."""
    # accessible requirement must get accessible room
    if requirement == "accessible":
        return room_type == "accessible"
    # family can use family or premium (upgrade); standard/accessible not compatible
    if requirement == "family":
        return room_type in ("family", "premium")
    # premium prefers premium but can use standard
    if requirement == "premium":
        return room_type in ("premium", "standard")
    # standard uses standard or premium only
    return room_type in ("standard", "premium")


# ---------------------------------------------------------------------------
# Protected bookings not degraded
# ---------------------------------------------------------------------------


def test_protected_accessible_bookings_not_relocated_unless_compatible():
    result = plan_recovery(_golden_snapshot())
    for reloc in result.plan.relocations:
        if reloc.original_requirement == "accessible":
            assert reloc.requirement_met is True, (
                "Accessible booking relocated without accessible room"
            )


def test_protected_family_bookings_not_degraded():
    result = plan_recovery(_golden_snapshot())
    for reloc in result.plan.relocations:
        if reloc.original_requirement == "family":
            assert reloc.requirement_met is True, (
                "Family booking relocated without compatible room"
            )


def test_protected_bookings_not_downgraded_to_incompatible_room():
    result = plan_recovery(_golden_snapshot())
    for reloc in result.plan.relocations:
        assert reloc.requirement_met is True, (
            f"Relocation for {reloc.booking_id} failed requirement check"
        )


# ---------------------------------------------------------------------------
# Golden plan — exactly 2 shift reallocations
# ---------------------------------------------------------------------------


def test_golden_plan_exact_2_shift_reallocations():
    result = plan_recovery(_golden_snapshot())
    assert len(result.plan.shift_reallocations) == 2


def test_shift_reallocations_are_engineering_skill():
    result = plan_recovery(_golden_snapshot())
    for sr in result.plan.shift_reallocations:
        assert sr.skill == "engineering"


# ---------------------------------------------------------------------------
# HITL required
# ---------------------------------------------------------------------------


def test_golden_plan_requires_hitl():
    result = plan_recovery(_golden_snapshot())
    assert result.plan.requires_hitl is True


# ---------------------------------------------------------------------------
# Guest communication / recovery actions
# ---------------------------------------------------------------------------


def test_golden_plan_has_guest_communication_actions():
    result = plan_recovery(_golden_snapshot())
    assert len(result.plan.guest_communication_actions) >= 1


# ---------------------------------------------------------------------------
# Evidence and financial fields
# ---------------------------------------------------------------------------


def test_golden_plan_has_evidence_versions():
    result = plan_recovery(_golden_snapshot())
    ev = result.plan.evidence_versions
    assert isinstance(ev, dict)
    assert len(ev) >= 1


def test_golden_plan_has_recovery_cost():
    result = plan_recovery(_golden_snapshot())
    assert isinstance(result.plan.estimated_recovery_cost_gbp, (int, float))
    # Synthetic demo assumption — label is documented in recovery.py
    assert result.plan.estimated_recovery_cost_gbp > 0


def test_golden_plan_has_revenue_protected():
    result = plan_recovery(_golden_snapshot())
    assert isinstance(result.plan.revenue_protected_gbp, (int, float))
    assert result.plan.revenue_protected_gbp > 0


def test_golden_plan_has_residual_shortfall():
    result = plan_recovery(_golden_snapshot())
    assert isinstance(result.plan.residual_shortfall, int)
    assert result.plan.residual_shortfall >= 0


def test_golden_plan_has_guest_disruption_count():
    result = plan_recovery(_golden_snapshot())
    assert isinstance(result.plan.guest_disruption_count, int)


def test_golden_plan_has_binding_constraints():
    result = plan_recovery(_golden_snapshot())
    assert isinstance(result.plan.binding_constraints, tuple)


# ---------------------------------------------------------------------------
# No-action case
# ---------------------------------------------------------------------------


def test_no_action_when_no_sister_capacity():
    snap = _zero_sister_capacity_snapshot()
    result = plan_recovery(snap)
    assert result.status == "no_action"


def test_no_action_has_binding_constraints():
    snap = _zero_sister_capacity_snapshot()
    result = plan_recovery(snap)
    assert len(result.binding_constraints) >= 1


def test_no_action_has_baseline_comparison():
    snap = _zero_sister_capacity_snapshot()
    result = plan_recovery(snap)
    assert result.baseline_comparison is not None
    assert isinstance(result.baseline_comparison, dict)


def test_no_action_plan_is_none():
    snap = _zero_sister_capacity_snapshot()
    result = plan_recovery(snap)
    assert result.plan is None


def test_no_action_is_never_empty_success():
    """no_action must always carry constraints and baseline — never silent ok."""
    snap = _zero_sister_capacity_snapshot()
    result = plan_recovery(snap)
    assert result.status == "no_action"
    assert result.binding_constraints  # non-empty
    assert result.baseline_comparison  # non-None and non-empty dict


# ---------------------------------------------------------------------------
# Planner must not mutate world snapshot
# ---------------------------------------------------------------------------


def test_planner_does_not_mutate_world():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    world.poll_sensor_events()

    before = world.snapshot()
    plan_recovery(world.snapshot())  # planner receives a fresh copy
    after = world.snapshot()

    assert before == after


# ---------------------------------------------------------------------------
# Fix 4 (RED first): HITL constraint only when relocations actually exist
# ---------------------------------------------------------------------------


def _no_arriving_bookings_snapshot():
    """Golden scenario world but with all arriving bookings set to checked_in."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    snap = world.snapshot()
    for bkg in snap["bookings"].values():
        if bkg["status"] == "arriving":
            bkg["status"] = "checked_in"
    return snap


def test_no_relocation_candidate_means_no_hitl_constraint():
    """When no arriving bookings → no relocations → must NOT add HITL constraint."""
    snap = _no_arriving_bookings_snapshot()
    result = plan_recovery(snap)
    assert result.status == "selected", (
        "Expected 'selected' (fault exists with sister capacity but no arrivals)"
    )
    assert result.plan is not None
    assert len(result.plan.relocations) == 0
    assert "cross-property-relocation-requires-hitl" not in result.plan.binding_constraints, (
        "HITL constraint must not appear when there are no relocations"
    )
    assert result.plan.requires_hitl is False


# ---------------------------------------------------------------------------
# Fix 1 (RED → GREEN): no-force-split regression
# ---------------------------------------------------------------------------


def _one_sided_capacity_snapshot():
    """Snapshot where AIRPORT-NORTH has ample standard capacity and CITY-GATE
    has zero capacity across all room types."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    snap = world.snapshot()
    snap["hotels"]["HOTEL-AIRPORT-NORTH"]["available_standard_rooms"] = 20
    snap["hotels"]["HOTEL-AIRPORT-NORTH"]["available_family_rooms"] = 0
    snap["hotels"]["HOTEL-AIRPORT-NORTH"]["available_accessible_rooms"] = 0
    snap["hotels"]["HOTEL-AIRPORT-NORTH"]["available_premium_rooms"] = 0
    snap["hotels"]["HOTEL-CITY-GATE"]["available_standard_rooms"] = 0
    snap["hotels"]["HOTEL-CITY-GATE"]["available_family_rooms"] = 0
    snap["hotels"]["HOTEL-CITY-GATE"]["available_accessible_rooms"] = 0
    snap["hotels"]["HOTEL-CITY-GATE"]["available_premium_rooms"] = 0
    return snap


def test_no_relocation_to_zero_capacity_sister():
    """Regression: planner must never assign a relocation to a sister hotel that
    has zero capacity. The old force-split did exactly this."""
    snap = _one_sided_capacity_snapshot()
    result = plan_recovery(snap)
    assert result.status == "selected"
    dest_hotels = {r.destination_hotel_id for r in result.plan.relocations}
    assert "HOTEL-CITY-GATE" not in dest_hotels, (
        "Force-split assigned relocation(s) to HOTEL-CITY-GATE "
        "despite zero available rooms — this violates capacity constraints"
    )


def test_per_destination_per_type_never_exceeds_initial_availability():
    """Each (hotel, room_type) pair in relocations must not exceed initial availability."""
    from collections import defaultdict
    snap = _one_sided_capacity_snapshot()
    result = plan_recovery(snap)
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for reloc in result.plan.relocations:
        counts[reloc.destination_hotel_id][reloc.destination_room_type] += 1
    for hotel_id, by_type in counts.items():
        for rt, placed in by_type.items():
            initial = snap["hotels"][hotel_id].get(f"available_{rt}_rooms", 0)
            assert placed <= initial, (
                f"{hotel_id}/{rt}: placed {placed} but only {initial} initially available"
            )


# ---------------------------------------------------------------------------
# Fix 4 (RED → GREEN): standard bookings must not consume accessible/family
# ---------------------------------------------------------------------------


def _scarce_specialised_rooms_snapshot():
    """Snapshot where sisters have ONLY accessible(2) and family(2) rooms each,
    no standard or premium. Standard bookings come first in the relocation list
    and must NOT consume these specialised room types."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    snap = world.snapshot()
    for sister_id in ("HOTEL-AIRPORT-NORTH", "HOTEL-CITY-GATE"):
        snap["hotels"][sister_id]["available_standard_rooms"] = 0
        snap["hotels"][sister_id]["available_premium_rooms"] = 0
        snap["hotels"][sister_id]["available_accessible_rooms"] = 2
        snap["hotels"][sister_id]["available_family_rooms"] = 2
    return snap


def test_standard_bookings_do_not_consume_accessible_rooms():
    """Standard-requirement bookings must not be placed in accessible rooms."""
    snap = _scarce_specialised_rooms_snapshot()
    result = plan_recovery(snap)
    for reloc in result.plan.relocations:
        if reloc.original_requirement == "standard":
            assert reloc.destination_room_type != "accessible", (
                f"Standard booking {reloc.booking_id} placed in accessible room — "
                "violates accessible-room reservation for protected guests"
            )


def test_standard_bookings_do_not_consume_family_rooms():
    """Standard-requirement bookings must not be placed in family rooms."""
    snap = _scarce_specialised_rooms_snapshot()
    result = plan_recovery(snap)
    for reloc in result.plan.relocations:
        if reloc.original_requirement == "standard":
            assert reloc.destination_room_type != "family", (
                f"Standard booking {reloc.booking_id} placed in family room — "
                "violates family-room reservation for protected guests"
            )


def test_protected_accessible_bookings_find_accessible_rooms_when_standard_constrained():
    """When sisters have only accessible/family rooms, protected accessible bookings
    must be placed (standard demand must not have consumed their rooms)."""
    snap = _scarce_specialised_rooms_snapshot()
    result = plan_recovery(snap)
    accessible_relocations = [
        r for r in result.plan.relocations
        if r.original_requirement == "accessible"
    ]
    # 4 accessible bookings exist; sisters have 2+2=4 accessible rooms total
    assert len(accessible_relocations) == 4, (
        "All 4 accessible protected bookings should be relocated when 4 accessible "
        "rooms are available across sisters. Standard demand must not have consumed them."
    )
    for reloc in accessible_relocations:
        assert reloc.requirement_met is True


def test_relocated_protected_bookings_keep_requirement_compatible_type():
    """Any relocated protected booking must land in a requirement-compatible room type."""
    snap = _scarce_specialised_rooms_snapshot()
    result = plan_recovery(snap)
    for reloc in result.plan.relocations:
        if reloc.original_requirement in ("accessible", "family"):
            assert reloc.requirement_met is True, (
                f"Protected {reloc.original_requirement} booking {reloc.booking_id} "
                f"placed in incompatible room type {reloc.destination_room_type}"
            )
