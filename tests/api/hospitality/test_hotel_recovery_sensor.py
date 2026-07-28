"""Task 3: Sensor detection — riverside hot-water-outage golden scenario."""
from __future__ import annotations

import pytest

from verticals.hospitality.world import HospitalityWorld

DEMO_SEED = 20260728
HERO_HOTEL = "HOTEL-RIVERSIDE-CENTRAL"


# ---------------------------------------------------------------------------
# No sensor event before scenario
# ---------------------------------------------------------------------------


def test_no_sensor_event_without_scenario():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    events = world.poll_sensor_events()
    assert events == []


def test_second_poll_without_scenario_is_empty():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.poll_sensor_events()
    assert world.poll_sensor_events() == []


# ---------------------------------------------------------------------------
# Scenario: exact 18 unavailable + 7 not-ready rooms
# ---------------------------------------------------------------------------


def test_scenario_unavailable_room_count():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    unavailable = [
        r
        for r in world.rooms.values()
        if r.hotel_id == HERO_HOTEL and r.status == "unavailable"
    ]
    assert len(unavailable) == 18


def test_scenario_not_ready_room_count():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    not_ready = [
        r
        for r in world.rooms.values()
        if r.hotel_id == HERO_HOTEL and r.status == "not_ready"
    ]
    assert len(not_ready) == 7


def test_scenario_unavailable_and_not_ready_are_disjoint():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    unavailable_ids = {
        r.id for r in world.rooms.values()
        if r.hotel_id == HERO_HOTEL and r.status == "unavailable"
    }
    not_ready_ids = {
        r.id for r in world.rooms.values()
        if r.hotel_id == HERO_HOTEL and r.status == "not_ready"
    }
    assert unavailable_ids.isdisjoint(not_ready_ids)


# ---------------------------------------------------------------------------
# Scenario: near-96% occupancy
# ---------------------------------------------------------------------------


def test_scenario_occupancy_near_96_pct():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    hotel = world.hotels[HERO_HOTEL]
    assert 0.94 <= hotel.occupancy_pct <= 0.98


# ---------------------------------------------------------------------------
# Scenario: exactly 44 arrivals in 4 hours
# ---------------------------------------------------------------------------


def test_scenario_44_arrivals():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    hotel = world.hotels[HERO_HOTEL]
    assert hotel.arrivals_in_4h == 44


# ---------------------------------------------------------------------------
# Protected accessible and family bookings
# ---------------------------------------------------------------------------


def test_protected_accessible_booking_exists():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    protected_accessible = [
        b for b in world.bookings.values()
        if b.hotel_id == HERO_HOTEL
        and b.protected
        and b.requirement == "accessible"
    ]
    assert len(protected_accessible) >= 1


def test_protected_family_booking_exists():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    protected_family = [
        b for b in world.bookings.values()
        if b.hotel_id == HERO_HOTEL
        and b.protected
        and b.requirement == "family"
    ]
    assert len(protected_family) >= 1


# ---------------------------------------------------------------------------
# Sensor: exactly one event then dedupe
# ---------------------------------------------------------------------------


def test_sensor_emits_one_event_after_scenario():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    events = world.poll_sensor_events()
    assert len(events) == 1


def test_sensor_event_type():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    event = world.poll_sensor_events()[0]
    assert event.type == "hotel.operations-risk.detected"


def test_sensor_event_workflow_type():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    event = world.poll_sensor_events()[0]
    assert event.workflow_type == "hotel-operations-recovery"


def test_sensor_event_has_hero_hotel_actor():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    event = world.poll_sensor_events()[0]
    assert HERO_HOTEL in event.actor_ids


def test_sensor_event_tick_is_non_negative():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    event = world.poll_sensor_events()[0]
    assert event.tick >= 0


def test_sensor_event_id_is_deterministic():
    w1 = HospitalityWorld.demo(seed=DEMO_SEED)
    w1.trigger_scenario("riverside-hot-water-outage")
    e1 = w1.poll_sensor_events()[0]

    w2 = HospitalityWorld.demo(seed=DEMO_SEED)
    w2.trigger_scenario("riverside-hot-water-outage")
    e2 = w2.poll_sensor_events()[0]

    assert e1.event_id == e2.event_id


def test_second_poll_emits_no_events():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    world.poll_sensor_events()  # first poll
    events2 = world.poll_sensor_events()  # second poll
    assert events2 == []


def test_dedupe_is_by_event_and_workflow_type_not_timestamp():
    """Dedupe key is (source_event_id, workflow_type); a second trigger of the
    *same* scenario after reset should produce a new event."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    first = world.poll_sensor_events()
    assert len(first) == 1

    world.reset(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    second = world.poll_sensor_events()
    assert len(second) == 1  # new event after reset


# ---------------------------------------------------------------------------
# Sensor payload completeness
# ---------------------------------------------------------------------------


def test_sensor_payload_has_affected_rooms():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert "affected_rooms" in payload
    assert payload["affected_rooms"] == 18


def test_sensor_payload_has_restoration_estimate():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert "restoration_estimate_hours" in payload
    assert isinstance(payload["restoration_estimate_hours"], (int, float))


def test_sensor_payload_has_arrivals_in_4h():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert payload.get("arrivals_in_4h") == 44


def test_sensor_payload_has_arrivals_by_requirement():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert "arrivals_by_requirement" in payload
    abr = payload["arrivals_by_requirement"]
    assert isinstance(abr, dict)
    assert sum(abr.values()) == 44


def test_sensor_payload_has_ready_room_count():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert "ready_room_count" in payload


def test_sensor_payload_has_housekeeping_capacity():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert "housekeeping_capacity" in payload


def test_sensor_payload_has_protected_requirements():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert "protected_requirements" in payload
    pr = payload["protected_requirements"]
    assert isinstance(pr, dict)
    assert "accessible" in pr or "family" in pr


def test_sensor_payload_has_sister_property_capacity():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert "sister_property_capacity" in payload
    assert isinstance(payload["sister_property_capacity"], dict)


def test_sister_capacity_includes_premium_rooms():
    """sister_property_capacity must count available_premium_rooms so sensor
    capacity matches planner capability. RED: current code omits premium."""
    from verticals.hospitality.sensors import evaluate_operations_risk
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    snap = world.snapshot()
    # Give AIRPORT-NORTH premium-only capacity (zero standard/family/accessible)
    snap["hotels"]["HOTEL-AIRPORT-NORTH"]["available_standard_rooms"] = 0
    snap["hotels"]["HOTEL-AIRPORT-NORTH"]["available_family_rooms"] = 0
    snap["hotels"]["HOTEL-AIRPORT-NORTH"]["available_accessible_rooms"] = 0
    snap["hotels"]["HOTEL-AIRPORT-NORTH"]["available_premium_rooms"] = 3
    payload = evaluate_operations_risk(snap)
    assert payload is not None
    assert payload["sister_property_capacity"]["HOTEL-AIRPORT-NORTH"] >= 3, (
        "sister_property_capacity must include available_premium_rooms; "
        f"got {payload['sister_property_capacity']['HOTEL-AIRPORT-NORTH']}, expected >= 3"
    )


def test_sensor_payload_has_engineering_available():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert "engineering_available" in payload


def test_sensor_payload_has_guest_disruption():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert "estimated_guest_disruption_count" in payload


def test_sensor_payload_has_recovery_spend():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert "estimated_recovery_spend_gbp" in payload
    assert isinstance(payload["estimated_recovery_spend_gbp"], (int, float))


def test_sensor_payload_has_revenue_at_risk():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert "revenue_at_risk_gbp" in payload
    assert isinstance(payload["revenue_at_risk_gbp"], (int, float))


# ---------------------------------------------------------------------------
# Malformed snapshot rejection
# ---------------------------------------------------------------------------


def test_malformed_snapshot_raises_value_error():
    from verticals.hospitality.sensors import evaluate_operations_risk
    with pytest.raises(ValueError, match="missing"):
        evaluate_operations_risk({})


def test_insufficient_snapshot_raises():
    from verticals.hospitality.sensors import evaluate_operations_risk
    with pytest.raises(ValueError):
        evaluate_operations_risk({"hotels": {}, "rooms": {}})


# ---------------------------------------------------------------------------
# Fix 2 (RED first): sensor payload must include sister travel times and
# contractor availability — typed, not an unstructured Any bag
# ---------------------------------------------------------------------------


def test_sensor_payload_has_sister_travel_times_minutes():
    """sister_travel_times_minutes: dict[hotel_id, int] of positive integer minutes."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert "sister_travel_times_minutes" in payload, (
        "Payload missing 'sister_travel_times_minutes' — Fix 2 not yet implemented"
    )
    stm = payload["sister_travel_times_minutes"]
    assert isinstance(stm, dict)
    assert len(stm) >= 1
    for hotel_id, minutes in stm.items():
        assert isinstance(hotel_id, str), f"Travel-time key must be str, got {type(hotel_id)}"
        assert isinstance(minutes, int), (
            f"Travel-time minutes must be int for {hotel_id}, got {type(minutes)}"
        )
        assert minutes > 0, f"Travel-time must be positive for {hotel_id}, got {minutes}"


def test_sister_travel_times_cover_hero_sisters():
    """Hero hotel's two sisters must both appear in sister_travel_times_minutes."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    stm = payload["sister_travel_times_minutes"]
    assert "HOTEL-AIRPORT-NORTH" in stm
    assert "HOTEL-CITY-GATE" in stm


def test_sensor_payload_has_contractor_available():
    """contractor_available: bool derived from the critical work order."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert "contractor_available" in payload, (
        "Payload missing 'contractor_available' — Fix 2 not yet implemented"
    )
    assert isinstance(payload["contractor_available"], bool)


def test_contractor_available_is_true_in_golden_scenario():
    """In the golden scenario the escalated work order has a contractor available."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    assert payload["contractor_available"] is True


def test_emitted_sister_travel_times_are_positive_integers_for_known_sisters():
    """Every emitted sister travel time must be a positive integer that corresponds
    exactly to a known sister property of the hero hotel — not external input."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    payload = world.poll_sensor_events()[0].payload
    stm = payload["sister_travel_times_minutes"]
    hotel = world.hotels[HERO_HOTEL]
    expected_sisters = set(hotel.sister_hotel_ids)
    assert set(stm.keys()) == expected_sisters, (
        f"Travel times must cover exactly the hero hotel's sisters; "
        f"expected {expected_sisters}, got {set(stm.keys())}"
    )
    for hotel_id, minutes in stm.items():
        assert isinstance(minutes, int), (
            f"Travel time for {hotel_id} must be int, got {type(minutes).__name__}"
        )
        assert minutes > 0, (
            f"Travel time for {hotel_id} must be positive, got {minutes}"
        )
