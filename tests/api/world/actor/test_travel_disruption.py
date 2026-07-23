"""TDD contract tests for the Travel vertical's autonomous disruption (Task 5).

Covers the live, deterministic Travel simulation autonomously cancelling
`FLT-ZV204` at simulation minute 180 -- strictly after its own ordinary
shopping/booking activity has produced a real paid package booking on it --
reporting a real `DIS-flight_cancellation-FLT-ZV204` disruption, and then,
through a *separate, state-derived sensor-evaluation step* (never an
unconditional emission), tripping exactly one rising-edge `sensor.tripped`
event for the canonical `sensor:flight_cancellation_impact` sensor. The
whole chain -- `flight.cancelled -> disruption.reported -> sensor.tripped`
-- is linked by `cause_event_id` and shares one `trace_id`.

`verticals.travel.worlds.scenario` and `verticals.travel.worlds.processes`
already exist (Task 3 + Task 4), so this file does not fail at collection.
Before this task's generator changes exist, it fails RED on assertions: the
flight is still merely `"scheduled"` at minute 180, `world.disruptions` is
still empty, and `detect_flight_cancellation_impact` never emits a
`"sensor.tripped"` event at all (the current generated detector emits a
level-triggered `"sensor.flight_cancellation_impact_tripped"` event with no
eligibility gate). After implementation it must pass (GREEN).

No `/processes/*/run` HTTP route, no objective, no workflow and no
responder event is exercised anywhere in this file -- every assertion below
drives `TravelWorld` and the generated detector directly, as pure Python
calls.
"""
from __future__ import annotations

from verticals.travel.worlds import processes as travel_processes
from verticals.travel.worlds.scenario import TravelWorld

_CANCELLED_FLIGHT_ID = "FLT-ZV204"
_CANCELLED_BOOKING_ID = "BKG-4"
_AFFECTED_PARTY_ID = "PTY-4"
_AFFECTED_MEMBER_CUSTOMER_IDS = ("CUS-8", "CUS-9")
_AFFECTED_HOTEL_ID = "HTL-SUN-PMI"
_AFFECTED_ALLOTMENT_ID = "ALT-SUN-PMI"
_AFFECTED_TRANSFER_ID = "TRF-2"
_DISRUPTION_ID = f"DIS-flight_cancellation-{_CANCELLED_FLIGHT_ID}"
_SENSOR_ID = "sensor:flight_cancellation_impact"

_DISRUPTION_MINUTE = 180.0
_PRE_DISRUPTION_MINUTE = 179.0

_NO_LIVE_WIRING_PREFIXES = ("objective.", "workflow.", "process.", "command.")


def _world(until: float) -> TravelWorld:
    world = TravelWorld(seed=42)
    world.run(until)
    return world


def _events_by_id(world: TravelWorld) -> dict:
    return {event.event_id: event for event in world.runtime.journal}


def _events_of_type(world: TravelWorld, event_type: str) -> list:
    return [event for event in world.runtime.journal if event.type == event_type]


# --- strictly before the horizon: ordinary activity only, no disruption ---


def test_before_minute_180_ordinary_activity_produced_a_real_paid_booking_with_full_relationships():
    """Requirement 2/8: at minute 179, FLT-ZV204 is still merely scheduled
    with a real paid package booking, real party/member-customer
    travellers, hotel, transfer and supplier relationships -- and zero
    flight-cancellation/disruption/sensor events exist anywhere yet.
    """
    world = _world(_PRE_DISRUPTION_MINUTE)

    flight = world.flights[_CANCELLED_FLIGHT_ID]
    assert flight.scheduled_departure > _DISRUPTION_MINUTE
    assert flight.status == "scheduled"

    booking = world.bookings[_CANCELLED_BOOKING_ID]
    assert booking.flight_id == _CANCELLED_FLIGHT_ID
    assert booking.party_id == _AFFECTED_PARTY_ID
    assert booking.status == "paid"

    party = world.parties[booking.party_id]
    assert party.member_customer_ids == _AFFECTED_MEMBER_CUSTOMER_IDS
    assert all(customer_id in world.customers for customer_id in party.member_customer_ids)

    hotel = world.hotels[booking.hotel_id]
    assert hotel.id == _AFFECTED_HOTEL_ID
    transfer = world.transfers[booking.transfer_id]
    assert transfer.id == _AFFECTED_TRANSFER_ID

    # real supplier relationships across the flight, hotel and transfer
    assert flight.supplier_id in world.suppliers
    assert hotel.supplier_id in world.suppliers
    assert transfer.supplier_id in world.suppliers

    assert world.disruptions == {}
    assert _events_of_type(world, "flight.cancelled") == []
    assert _events_of_type(world, "disruption.reported") == []
    assert _events_of_type(world, "sensor.tripped") == []


# --- at minute 180: exact world mutation and causal chain ------------------


def test_at_minute_180_flight_cancellation_reports_disruption_and_trips_sensor_once():
    """Requirement 2/3/4/8: at minute 180 a real operations cancellation
    changes FLT-ZV204.status to "cancelled", reports a real disruption, and
    a separate sensor-evaluation step trips exactly one rising-edge
    `sensor.tripped` for `sensor:flight_cancellation_impact`, causally
    chained `flight.cancelled -> disruption.reported -> sensor.tripped` via
    `cause_event_id` and one shared `trace_id`.
    """
    world = _world(_DISRUPTION_MINUTE)

    flight = world.flights[_CANCELLED_FLIGHT_ID]
    assert flight.status == "cancelled"

    disruption = world.disruptions[_DISRUPTION_ID]
    assert disruption.kind == "flight_cancellation"
    assert disruption.resource_id == _CANCELLED_FLIGHT_ID
    assert disruption.status == "reported"

    cancelled_events = _events_of_type(world, "flight.cancelled")
    assert len(cancelled_events) == 1
    cancelled_event = cancelled_events[0]
    assert cancelled_event.actor_id == _CANCELLED_FLIGHT_ID
    assert cancelled_event.sim_time == _DISRUPTION_MINUTE
    assert cancelled_event.payload["status"] == "cancelled"

    reported_events = [e for e in _events_of_type(world, "disruption.reported") if e.actor_id == _DISRUPTION_ID]
    assert len(reported_events) == 1
    reported_event = reported_events[0]
    assert reported_event.target_id == _CANCELLED_FLIGHT_ID
    assert reported_event.cause_event_id == cancelled_event.event_id

    sensor_events = _events_of_type(world, "sensor.tripped")
    assert len(sensor_events) == 1
    sensor_event = sensor_events[0]
    assert sensor_event.payload["sensor_id"] == _SENSOR_ID
    assert sensor_event.actor_id == disruption.id
    assert sensor_event.target_id == _CANCELLED_FLIGHT_ID
    assert sensor_event.cause_event_id == reported_event.event_id

    # one shared trace_id across the whole causal chain
    assert cancelled_event.trace_id == reported_event.trace_id
    assert reported_event.trace_id == sensor_event.trace_id

    # exact journal evidence: last_event_id points at the exact mutating event
    assert flight.last_event_id == cancelled_event.event_id
    assert disruption.last_event_id == reported_event.event_id


def test_sensor_payload_names_real_actors_and_exact_measurements():
    """Requirement 4/8: the payload names real flight/disruption/booking/
    party/member-customer traveller/hotel/transfer/supplier ids, exposes a
    flat `actor_ids` list for downstream observation, and carries exact
    measurements including `material_change=True`.
    """
    world = _world(_DISRUPTION_MINUTE)
    sensor_event = _events_of_type(world, "sensor.tripped")[0]
    payload = sensor_event.payload

    assert payload["disruption_id"] == _DISRUPTION_ID
    assert payload["flight_id"] == _CANCELLED_FLIGHT_ID
    assert payload["booking_ids"] == [_CANCELLED_BOOKING_ID]
    assert payload["party_ids"] == [_AFFECTED_PARTY_ID]
    assert payload["member_customer_ids"] == list(_AFFECTED_MEMBER_CUSTOMER_IDS)
    assert payload["hotel_ids"] == [_AFFECTED_HOTEL_ID]
    assert payload["transfer_ids"] == [_AFFECTED_TRANSFER_ID]

    flight = world.flights[_CANCELLED_FLIGHT_ID]
    hotel = world.hotels[_AFFECTED_HOTEL_ID]
    transfer = world.transfers[_AFFECTED_TRANSFER_ID]
    expected_supplier_ids = sorted({flight.supplier_id, hotel.supplier_id, transfer.supplier_id})
    assert payload["supplier_ids"] == expected_supplier_ids

    expected_actor_ids = sorted(
        {
            _CANCELLED_FLIGHT_ID,
            _DISRUPTION_ID,
            _CANCELLED_BOOKING_ID,
            _AFFECTED_PARTY_ID,
            *_AFFECTED_MEMBER_CUSTOMER_IDS,
            _AFFECTED_HOTEL_ID,
            _AFFECTED_TRANSFER_ID,
            *expected_supplier_ids,
        }
    )
    assert payload["actor_ids"] == expected_actor_ids

    assert payload["measurements"] == {
        "affected_booking_count": 1,
        "affected_party_count": 1,
        "affected_traveller_count": 2,
        "seats_impacted": 2,
        "material_change": True,
    }


def test_every_sensor_payload_actor_id_resolves_to_the_snapshot():
    """Requirement 8: every payload id resolves to the snapshot actor
    collection (`render_state()`), the surface a scene renderer consumes.
    """
    world = _world(_DISRUPTION_MINUTE)
    sensor_event = _events_of_type(world, "sensor.tripped")[0]
    state = world.render_state()

    known_ids: set[str] = set()
    for key in ("flights", "disruptions", "bookings", "parties", "customers", "hotels", "transfers", "suppliers"):
        known_ids |= {row["id"] for row in state[key]}

    for actor_id in sensor_event.payload["actor_ids"]:
        assert actor_id in known_ids, f"payload actor_id {actor_id!r} is not a real snapshot actor"


def test_cancellation_does_not_release_or_rebook_capacity():
    """Requirement 2: the cancellation itself never releases/rebooks
    capacity -- that mutation belongs to Task 6's recovery command.
    """
    before = _world(_PRE_DISRUPTION_MINUTE)
    after = _world(_DISRUPTION_MINUTE)

    assert after.flights[_CANCELLED_FLIGHT_ID].reserved == before.flights[_CANCELLED_FLIGHT_ID].reserved
    assert (
        after.allotments[_AFFECTED_ALLOTMENT_ID].reserved
        == before.allotments[_AFFECTED_ALLOTMENT_ID].reserved
    )
    assert after.transfers[_AFFECTED_TRANSFER_ID].reserved == before.transfers[_AFFECTED_TRANSFER_ID].reserved
    assert after.bookings[_CANCELLED_BOOKING_ID].status == "paid"


def test_no_objective_workflow_process_or_command_events_in_the_direct_scenario():
    """Requirement 6: no objective/workflow/responder event exists in the
    direct scenario -- Task 5 stops at the autonomous sensor event.
    """
    world = _world(_DISRUPTION_MINUTE)
    offending = [
        event.type
        for event in world.runtime.journal
        if any(event.type.startswith(prefix) for prefix in _NO_LIVE_WIRING_PREFIXES)
    ]
    assert offending == []


def test_same_seed_produces_identical_disruption_and_sensor_journal():
    """Requirement 6: deterministic same-seed snapshot/journal."""
    first = _world(_DISRUPTION_MINUTE)
    second = _world(_DISRUPTION_MINUTE)
    assert [e.to_dict() for e in first.runtime.journal] == [e.to_dict() for e in second.runtime.journal]
    assert first.render_state() == second.render_state()


# --- rising edge: never fires twice for the same condition -----------------


def test_sensor_never_retrips_for_the_same_disruption():
    """Requirement 4: the rising edge never fires again while the same
    condition remains true, including repeated detector evaluation
    (calling the detector again directly) and later simulation steps
    (advancing the simulation further).
    """
    world = _world(_DISRUPTION_MINUTE)
    tripped_before = _events_of_type(world, "sensor.tripped")
    assert len(tripped_before) == 1
    journal_len_before = len(world.runtime.journal)

    replayed = travel_processes.detect_flight_cancellation_impact(world)
    assert replayed == []
    assert len(world.runtime.journal) == journal_len_before

    world.run(200.0)
    assert len(_events_of_type(world, "sensor.tripped")) == 1


# --- state-derived: no eligible booking means no sensor, ever --------------


def test_flight_cancellation_disruption_with_no_eligible_booking_never_trips_sensor():
    """Requirement 5: a fresh scenario/reference setup with no eligible
    paid/confirmed booking must never trip the sensor -- state-derived
    detection reads real world state, it is never faked.
    """
    world = TravelWorld(seed=42)
    assert world.bookings == {}, "expected genesis to carry no bookings yet"

    disruption = world.report_disruption(kind="flight_cancellation", resource_id=_CANCELLED_FLIGHT_ID)
    assert disruption.status == "reported"

    events = travel_processes.detect_flight_cancellation_impact(world)
    assert events == []
    assert _events_of_type(world, "sensor.tripped") == []
