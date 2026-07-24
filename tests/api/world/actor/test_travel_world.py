"""TDD contract tests for the Travel vertical world (Task 3).

Covers the deterministic, synthetic, integrated-tour-operator-style world
built on `api.server.world.runtime.SimulationRuntime`: a seeded (42)
`TravelWorld` whose ordinary autonomous lifecycle -- customers requesting
quotes, advisers making offers, quotes converting into package bookings,
deposits/balances being paid, a flight departing and advancing position,
a transfer advancing and hotel occupancy changing -- runs deterministically
before simulation minute 180, with every mutation traceable through the
causal journal back to the actor/target it names.

Running this file before `verticals.travel.worlds` exists must fail at
collection with a ModuleNotFoundError (RED). After implementation it must
pass (GREEN). No disruption, sensor, objective or workflow behaviour is in
scope for this task -- see the dedicated assertions below that prove none
of it leaks into the ordinary journal.
"""
from __future__ import annotations

import dataclasses
import json

from verticals.travel.worlds.model import (
    Airport,
    Destination,
    Disruption,
    Flight,
    Hotel,
    Refund,
    RoomAllotment,
    StaffMember,
    Supplier,
    Transfer,
    TravellingParty,
)
from verticals.travel.worlds.scenario import TravelWorld

ORDINARY_HORIZON = 180.0

# Task 5 introduces the world's first real disruption/sensor pair as an
# autonomous mutation at exactly sim_time == ORDINARY_HORIZON (a real flight
# cancellation against _TARGET_FUTURE_FLIGHT_ID). Since SimulationRuntime.
# run_until(until) is inclusive of events at exactly t == until, tests in
# this file asserting Task 3's ordinary-lifecycle-only invariants (no
# disruption yet, flight still merely "scheduled", etc.) anchor to one
# minute *before* that boundary instead of the shared default.
_PRE_DISRUPTION_HORIZON = ORDINARY_HORIZON - 1.0

# None of this task's disruption/sensor/objective/workflow/process-run
# machinery exists yet, so the journal must be completely free of it.
_DISALLOWED_EVENT_PREFIXES = (
    "disruption.",
    "sensor.",
    "objective.",
    "workflow.",
    "process.",
)

_TARGET_FUTURE_FLIGHT_ID = "FLT-ZV204"


def _run_world(seed: int = 42, until: float = ORDINARY_HORIZON) -> TravelWorld:
    world = TravelWorld(seed=seed)
    world.run(until)
    return world


def _events_by_id(world: TravelWorld) -> dict:
    return {event.event_id: event for event in world.runtime.journal}


def _all_records(world: TravelWorld):
    for mapping in (
        world.airports,
        world.destinations,
        world.suppliers,
        world.staff,
        world.customers,
        world.parties,
        world.flights,
        world.hotels,
        world.allotments,
        world.transfers,
        world.quotes,
        world.bookings,
        world.payments,
        world.refunds,
        world.disruptions,
    ):
        yield from mapping.values()


# --- determinism -------------------------------------------------------


def test_same_seed_produces_identical_journal():
    first = _run_world()
    second = _run_world()
    assert [e.to_dict() for e in first.runtime.journal] == [e.to_dict() for e in second.runtime.journal]


def test_same_seed_produces_identical_render_state():
    first = _run_world()
    second = _run_world()
    assert first.render_state() == second.render_state()


def test_render_state_round_trips_through_json():
    world = _run_world()
    state = world.render_state()
    assert json.loads(json.dumps(state, sort_keys=True)) == state


# --- required actors, kinds and relationships exist ---------------------


def test_required_airports_exist():
    world = _run_world()
    assert set(world.airports) == {"APT-LGW", "APT-MAN", "APT-BHX"}
    for airport in world.airports.values():
        assert isinstance(airport, Airport)
        assert airport.last_event_id in _events_by_id(world)


def test_required_destinations_exist():
    world = _run_world()
    assert set(world.destinations) == {"DST-PMI", "DST-TFS", "DST-AYT"}
    for destination in world.destinations.values():
        assert isinstance(destination, Destination)


def test_target_future_flight_exists_and_is_operational():
    # anchored just before Task 5's minute-180 cancellation of this exact flight
    world = _run_world(until=_PRE_DISRUPTION_HORIZON)
    flight = world.flights[_TARGET_FUTURE_FLIGHT_ID]
    assert flight.scheduled_departure > ORDINARY_HORIZON
    assert flight.status == "scheduled"
    linked = [b for b in world.bookings.values() if b.flight_id == _TARGET_FUTURE_FLIGHT_ID]
    assert linked, "expected a booking referencing the target future flight"
    assert all(b.status == "paid" for b in linked)


def test_multiple_flights_hotels_transfers_suppliers_exist():
    world = _run_world()
    # 4 ordinary flights/transfers plus 5 Task 6 flight-disruption-recovery
    # replacement candidates (FLT-ZV205/CA160/ZV206/CA161/ZV103), each
    # paired 1:1 with its own transfer (TRF-5..9).
    assert len(world.flights) == 9
    assert len(world.hotels) == 3
    assert len(world.allotments) == 3
    assert len(world.transfers) == 9
    assert len(world.suppliers) == 5
    for flight in world.flights.values():
        assert isinstance(flight, Flight)
    for hotel in world.hotels.values():
        assert isinstance(hotel, Hotel)
    for allotment in world.allotments.values():
        assert isinstance(allotment, RoomAllotment)
    for transfer in world.transfers.values():
        assert isinstance(transfer, Transfer)
    for supplier in world.suppliers.values():
        assert isinstance(supplier, Supplier)


def test_staff_roles_cover_advisers_operations_destination_finance():
    world = _run_world()
    assert len(world.staff) == 5
    roles = {member.role for member in world.staff.values()}
    assert {"adviser", "operations", "destination", "finance"} <= roles
    assert sum(1 for member in world.staff.values() if member.role == "adviser") >= 2
    for member in world.staff.values():
        assert isinstance(member, StaffMember)


def test_customers_and_travelling_parties_exist_with_real_relationships():
    world = _run_world()
    assert len(world.customers) == 11
    assert len(world.parties) == 6
    for party in world.parties.values():
        assert isinstance(party, TravellingParty)
        assert party.lead_customer_id in world.customers
        assert party.lead_customer_id in party.member_customer_ids
        assert all(member_id in world.customers for member_id in party.member_customer_ids)
        assert party.size == len(party.member_customer_ids)


def test_refund_and_disruption_collections_exist_but_start_empty():
    # anchored just before Task 5's minute-180 autonomous disruption
    world = _run_world(until=_PRE_DISRUPTION_HORIZON)
    assert world.refunds == {}
    assert world.disruptions == {}
    # the actor *types* must still exist and be constructible for later tasks
    Refund(id="REF-TEST", booking_id="BKG-1", amount=1.0, reason="test", status="requested")
    Disruption(id="DIS-TEST", resource_id="FLT-ZV101", kind="test", reported_at=0.0)


# --- quote -> confirmed/paid booking progression, exact linked ids ------


def test_hero_quote_converts_to_paid_booking_with_exact_linked_ids():
    world = _run_world()
    quote = world.quotes["QTE-1"]
    assert quote.status == "converted"
    assert quote.party_id == "PTY-1"
    assert quote.customer_id == "CUS-1"

    booking = next(b for b in world.bookings.values() if b.quote_id == quote.id)
    assert booking.party_id == quote.party_id
    assert booking.customer_id == quote.customer_id
    assert booking.status == "paid"

    payments = [p for p in world.payments.values() if p.booking_id == booking.id]
    assert {p.kind for p in payments} == {"deposit", "balance"}
    assert sum(p.amount for p in payments) == booking.total_price


def test_every_paid_booking_has_a_converted_quote_and_matching_payments():
    world = _run_world()
    paid_bookings = [b for b in world.bookings.values() if b.status == "paid"]
    assert len(paid_bookings) == 4
    for booking in paid_bookings:
        quote = world.quotes[booking.quote_id]
        assert quote.status == "converted"
        assert quote.party_id == booking.party_id
        payments = [p for p in world.payments.values() if p.booking_id == booking.id]
        assert sum(p.amount for p in payments) == booking.total_price


def test_some_quotes_remain_unconverted_showing_pipeline_variety():
    world = _run_world()
    statuses = {quote.id: quote.status for quote in world.quotes.values()}
    assert list(statuses.values()).count("requested") == 1
    assert list(statuses.values()).count("offered") == 1
    assert list(statuses.values()).count("converted") == 4


# --- ordinary lifecycle happens deterministically before minute 180 ----


def test_flight_departs_and_advances_position_before_minute_180():
    world = _run_world()
    departures = [e for e in world.runtime.journal if e.type == "flight.departed"]
    arrivals = [e for e in world.runtime.journal if e.type == "flight.arrived"]
    assert departures and all(e.sim_time < ORDINARY_HORIZON for e in departures)
    assert arrivals and all(e.sim_time < ORDINARY_HORIZON for e in arrivals)

    hero_flight = world.flights["FLT-ZV101"]
    assert hero_flight.status == "arrived"
    assert hero_flight.reserved <= hero_flight.capacity


def test_party_moves_booked_through_origin_airport_airborne_transfer_resort():
    world = _run_world()
    hero_party = world.parties["PTY-1"]
    assert hero_party.state == "at_resort"
    assert hero_party.location == "HTL-SUN-PMI"

    expected_types = [
        "party.quote_requested",
        "party.booked",
        "party.checked_in",
        "party.boarded",
        "party.disembarked",
        "party.arrived_at_resort",
    ]
    party_events = [e for e in world.runtime.journal if e.actor_id == "PTY-1"]
    seen_types = [e.type for e in party_events]
    for expected in expected_types:
        assert expected in seen_types
    assert all(e.sim_time < ORDINARY_HORIZON for e in party_events)


def test_transfer_advances_before_minute_180():
    world = _run_world()
    transfer = world.transfers["TRF-1"]
    assert transfer.status == "completed"
    transfer_events = [e for e in world.runtime.journal if e.actor_id == "TRF-1"]
    assert [e.type for e in transfer_events] == [
        "world.transfer_seeded",
        "transfer.capacity_reserved",
        "transfer.departed",
        "transfer.completed",
    ]
    assert all(e.sim_time < ORDINARY_HORIZON for e in transfer_events)


def test_hotel_occupancy_changes_before_minute_180():
    world = _run_world()
    allotment = world.allotments["ALT-SUN-PMI"]
    assert allotment.occupied >= 1
    occupancy_events = [e for e in world.runtime.journal if e.type == "hotel.rooms_occupied"]
    assert occupancy_events
    assert all(e.sim_time < ORDINARY_HORIZON for e in occupancy_events)


def test_capacity_reservations_happen_before_minute_180():
    world = _run_world()
    reservation_types = {"flight.capacity_reserved", "hotel.rooms_reserved", "transfer.capacity_reserved"}
    reservation_events = [e for e in world.runtime.journal if e.type in reservation_types]
    assert len(reservation_events) == 12  # 3 resources x 4 converted bookings
    assert all(e.sim_time < ORDINARY_HORIZON for e in reservation_events)


def test_no_disallowed_events_before_minute_180():
    world = _run_world()
    early_events = [e for e in world.runtime.journal if e.sim_time < ORDINARY_HORIZON]
    assert early_events, "expected at least one ordinary event before minute 180"
    offending = [
        e.type for e in early_events if any(e.type.startswith(prefix) for prefix in _DISALLOWED_EVENT_PREFIXES)
    ]
    assert offending == []


def test_no_disallowed_events_anywhere_in_this_task():
    # anchored just before Task 5's minute-180 autonomous disruption+sensor pair
    world = _run_world(until=_PRE_DISRUPTION_HORIZON)
    offending = [
        e.type
        for e in world.runtime.journal
        if any(e.type.startswith(prefix) for prefix in _DISALLOWED_EVENT_PREFIXES)
    ]
    assert offending == []


# --- conservation invariants ---------------------------------------------


def test_flight_reserved_never_exceeds_capacity():
    world = _run_world()
    for flight in world.flights.values():
        assert 0 <= flight.reserved <= flight.capacity


def test_transfer_reserved_never_exceeds_capacity():
    world = _run_world()
    for transfer in world.transfers.values():
        assert 0 <= transfer.reserved <= transfer.capacity


def test_hotel_allotment_conservation_chain_holds():
    world = _run_world()
    for allotment in world.allotments.values():
        assert 0 <= allotment.occupied <= allotment.reserved <= allotment.allotment <= allotment.total


def test_no_negative_inventory_anywhere():
    world = _run_world()
    for flight in world.flights.values():
        assert flight.reserved >= 0 and flight.capacity >= 0
    for transfer in world.transfers.values():
        assert transfer.reserved >= 0 and transfer.capacity >= 0
    for allotment in world.allotments.values():
        assert min(allotment.occupied, allotment.reserved, allotment.allotment, allotment.total) >= 0
    for payment in world.payments.values():
        assert payment.amount >= 0
    for booking in world.bookings.values():
        assert booking.total_price >= 0
        assert booking.rooms >= 0


def test_payment_totals_match_paid_booking_rules():
    world = _run_world()
    assert world.payments  # some payments must exist
    for booking in world.bookings.values():
        payments = [p for p in world.payments.values() if p.booking_id == booking.id]
        if booking.status == "paid":
            assert sum(p.amount for p in payments) == booking.total_price
            assert {p.kind for p in payments} == {"deposit", "balance"}
        elif booking.status == "deposit_paid":
            assert sum(p.amount for p in payments) < booking.total_price
            assert {p.kind for p in payments} == {"deposit"}


# --- customers browse before requesting a quote --------------------------


def test_customer_browses_before_requesting_a_quote_with_causal_linkage():
    """Ordinary activity must include customers *browsing* before they
    request a quote -- not just advisers handling requests that appear
    from nowhere. This asserts a real `customer.browsed` event exists for
    the hero customer/party, strictly before their `quote.requested`
    event, causally linked (the quote request names the browse event as
    its cause), naming real customer/party ids, and pairs with a visible
    Customer.status transition to "browsing" recorded on the event itself.
    """
    world = _run_world()
    events = world.runtime.journal

    quote_requests = [e for e in events if e.type == "quote.requested"]
    assert quote_requests, "expected at least one quote.requested event"

    hero_quote_request = next(
        e for e in quote_requests if e.payload.get("customer_id") == "CUS-1"
    )
    assert hero_quote_request.payload.get("party_id") == "PTY-1"

    browse_events = [
        e for e in events if e.type == "customer.browsed" and e.actor_id == "CUS-1"
    ]
    assert browse_events, "expected at least one customer.browsed event for CUS-1"
    browse_event = browse_events[0]

    # real customer/party ids named on the browse event
    assert browse_event.actor_id == "CUS-1"
    assert browse_event.target_id == "PTY-1"

    # ordering: browsing happens strictly before the quote request
    assert browse_event.sim_time < hero_quote_request.sim_time

    # causal linkage: the quote request names the browse event as its cause
    assert hero_quote_request.cause_event_id == browse_event.event_id

    # visible customer state transition recorded on the browse event itself
    assert browse_event.payload.get("status") == "browsing"


def test_every_converted_party_browses_before_requesting_its_quote():
    world = _run_world()
    events = world.runtime.journal
    quote_requests_by_party = {
        e.payload["party_id"]: e for e in events if e.type == "quote.requested"
    }
    assert len(quote_requests_by_party) == 6

    for party_id, quote_request in quote_requests_by_party.items():
        customer_id = quote_request.payload["customer_id"]
        browse_events = [
            e
            for e in events
            if e.type == "customer.browsed"
            and e.actor_id == customer_id
            and e.target_id == party_id
        ]
        assert browse_events, f"expected a customer.browsed event for {customer_id}/{party_id}"
        assert browse_events[0].sim_time < quote_request.sim_time
        assert quote_request.cause_event_id == browse_events[0].event_id


# --- last_event_id traceability -------------------------------------------


def test_every_actor_last_event_id_resolves_to_a_referencing_journal_event():
    world = _run_world()
    events_by_id = _events_by_id(world)
    checked = 0
    for record in _all_records(world):
        assert record.last_event_id is not None, f"{record!r} has no last_event_id"
        assert record.last_event_id in events_by_id, f"{record.id} last_event_id not in journal"
        event = events_by_id[record.last_event_id]
        assert event.actor_id == record.id or event.target_id == record.id, (
            f"{record.id}'s last_event_id {record.last_event_id!r} references neither "
            f"actor_id={event.actor_id!r} nor target_id={event.target_id!r}"
        )
        checked += 1
    assert checked > 40  # sanity: genesis alone seeds dozens of actors


def test_every_actor_exposes_real_id_and_last_event_id_fields():
    world = _run_world()
    for record in _all_records(world):
        field_names = {f.name for f in dataclasses.fields(record)}
        assert "id" in field_names
        assert "last_event_id" in field_names
        assert isinstance(record.id, str) and record.id


def test_last_event_evidence_matches_final_mutable_state():
    world = _run_world()
    events_by_id = _events_by_id(world)

    booking = next(b for b in world.bookings.values() if b.status == "paid")
    event = events_by_id[booking.last_event_id]
    assert event.payload.get("status") == booking.status

    flight = world.flights["FLT-ZV101"]
    event = events_by_id[flight.last_event_id]
    assert event.payload.get("status") == flight.status

    allotment = world.allotments["ALT-SUN-PMI"]
    event = events_by_id[allotment.last_event_id]
    assert event.payload.get("occupied") == allotment.occupied


def test_render_state_last_event_id_evidence_resolves_and_matches_payload():
    """Strengthened causal-evidence check (Task 3, item C): iterate every
    *visible* record across all `render_state()` actor/business
    collections -- the JSON-able rows a scene renderer would actually
    consume, not the internal Python dataclass instances -- and, for each
    row that carries a `last_event_id`, assert the referenced journal
    event names that row's id as its actor or target. For any mutable
    final-state field the referencing event's payload also carries,
    assert the payload value matches the rendered row's value exactly.

    This may legitimately pass immediately: it characterizes an
    invariant `TravelWorld._created`/`_apply` already uphold for every
    mutation, now proven against the render_state() surface instead of
    the internal record objects.
    """
    world = _run_world()
    events_by_id = _events_by_id(world)
    state = world.render_state()

    collection_keys = (
        "airports",
        "destinations",
        "suppliers",
        "staff",
        "customers",
        "parties",
        "flights",
        "hotels",
        "allotments",
        "transfers",
        "quotes",
        "bookings",
        "payments",
        "refunds",
        "disruptions",
    )

    checked = 0
    for key in collection_keys:
        rows = state[key]
        for row in rows:
            assert "last_event_id" in row, f"{key} row {row.get('id')!r} has no last_event_id field"
            last_event_id = row["last_event_id"]
            assert last_event_id is not None, f"{key} row {row['id']!r} has a null last_event_id"
            assert last_event_id in events_by_id, (
                f"{key} row {row['id']!r} last_event_id {last_event_id!r} not in journal"
            )

            event = events_by_id[last_event_id]
            assert event.actor_id == row["id"] or event.target_id == row["id"], (
                f"{key} row {row['id']!r}'s last_event_id {last_event_id!r} references neither "
                f"actor_id={event.actor_id!r} nor target_id={event.target_id!r}"
            )

            for field, value in row.items():
                if field in {"id", "last_event_id"}:
                    continue
                if field in event.payload:
                    assert event.payload[field] == value, (
                        f"{key} row {row['id']!r} field {field!r}={value!r} does not match "
                        f"last_event ({last_event_id!r}) payload value {event.payload[field]!r}"
                    )

            checked += 1
    assert checked > 40  # sanity: genesis alone seeds dozens of visible rows


# --- render_state() shape for a later scene renderer ----------------------


def test_render_state_exposes_all_required_collections_with_visible_ids():
    # anchored just before Task 5's minute-180 autonomous disruption
    world = _run_world(until=_PRE_DISRUPTION_HORIZON)
    state = world.render_state()
    required_keys = {
        "airports",
        "destinations",
        "customers",
        "parties",
        "staff",
        "suppliers",
        "flights",
        "hotels",
        "transfers",
        "allotments",
        "quotes",
        "bookings",
        "payments",
        "refunds",
        "disruptions",
        "summary",
    }
    assert required_keys <= set(state)
    assert {row["id"] for row in state["airports"]} == {"APT-LGW", "APT-MAN", "APT-BHX"}
    assert any(row["id"] == "FLT-ZV204" for row in state["flights"])
    assert state["refunds"] == []
    assert state["disruptions"] == []
    assert state["summary"]["bookings_paid"] == 4
