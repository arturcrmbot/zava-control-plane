"""TDD contract tests for the Travel world's scene-renderer-ready derived
fields on `render_state()` (Task 8, Part A).

A generic spatial world scene renderer (`web/shared/worldScene.ts`) must be
able to position every actor token without inventing any data. This file
proves `TravelWorld.render_state()` adds the JSON-safe derived fields a
scene mapping needs -- on top of the existing raw dataclass rows already
covered by `test_travel_world.py` -- and that every one of them is
authoritatively derived from real, mutable world state (never decorative
or random):

- `flights`/`transfers` expose `route_location_ids` (the real origin/
  destination -- or destination/hotel -- location ids) and `progress`,
  discrete-status-derived (scheduled/cancelled -> 0.0, departed/
  in_progress -> 0.5, arrived/completed -> 1.0). `SimulationRuntime.now`
  only ever advances to the sim_time of the most recently processed
  event *anywhere* in the shared world (`run_until` steps event-by-event
  rather than forcing a wall clock), so it cannot be used to interpolate
  a single flight's own elapsed fraction of its journey without risking
  a stale, misleadingly-precise value driven by an unrelated event
  elsewhere in the world -- a real, authoritative, status-derived
  progress value is preferred over that false precision.
- `parties`/`customers`/`bookings`/`disruptions`/`recovery_decisions`
  expose `current_location_id`, derived from each record's own real
  location/relationship fields -- honestly `None` for a party mid-flight
  (an airborne gap the underlying model has no location for), never a
  fabricated position.
- `hotels` expose `occupancy_ratio`/`capacity_ratio`/`occupancy_status`,
  derived from their real, paired `RoomAllotment`'s occupied/reserved/
  allotment numbers.
- The golden flight-disruption-recovery mutation (BKG-4/PTY-4 off
  cancelled FLT-ZV204 onto FLT-ZV205) is visibly reflected across these
  scene fields between a before/after `render_state()` snapshot.

Running this file before these derived fields exist must fail at
assertion (a `KeyError` on the still-missing field), not at collection
(RED). After implementation it must pass (GREEN).
"""
from __future__ import annotations

import pytest

from api.server.world.model import SimulationCommand
from verticals.travel.worlds.scenario import TravelWorld

ORDINARY_HORIZON = 180.0


def _run_world(seed: int = 42, until: float = ORDINARY_HORIZON) -> TravelWorld:
    world = TravelWorld(seed=seed)
    world.run(until)
    return world


def _row(state: dict, collection: str, record_id: str) -> dict:
    for row in state[collection]:
        if row["id"] == record_id:
            return row
    raise AssertionError(f"{record_id!r} not found in state[{collection!r}]")


def _events_by_id(world: TravelWorld) -> dict:
    return {event.event_id: event for event in world.runtime.journal}


# --- flights: route_location_ids + progress ---------------------------------


def test_scheduled_flight_exposes_its_real_route_and_zero_progress() -> None:
    world = _run_world(until=1.0)  # well before any departure
    row = _row(world.render_state(), "flights", "FLT-ZV101")
    assert world.flights["FLT-ZV101"].status == "scheduled"
    assert row["route_location_ids"] == ["APT-LGW", "DST-PMI"]
    assert row["progress"] == 0.0


def test_arrived_flight_exposes_full_progress() -> None:
    world = _run_world(until=150.0)  # strictly after FLT-ZV101 arrives at 140
    row = _row(world.render_state(), "flights", "FLT-ZV101")
    assert world.flights["FLT-ZV101"].status == "arrived"
    assert row["progress"] == 1.0


def test_departed_flight_exposes_half_progress() -> None:
    # FLT-ZV101 departs at 90.0 and arrives at 140.0 (reference_data.py).
    # Progress is discrete-status-derived (see module docstring for why a
    # continuous time interpolation against the shared runtime clock would
    # be unreliable), matching the same "departed"/"in_progress" -> 0.5
    # convention transfers already use below.
    world = _run_world(until=100.0)
    row = _row(world.render_state(), "flights", "FLT-ZV101")
    assert world.flights["FLT-ZV101"].status == "departed"
    assert row["progress"] == 0.5


def test_cancelled_flight_never_departed_exposes_zero_progress_but_a_real_route() -> None:
    world = _run_world()  # minute-180 autonomous cancellation of FLT-ZV204
    row = _row(world.render_state(), "flights", "FLT-ZV204")
    assert world.flights["FLT-ZV204"].status == "cancelled"
    assert row["progress"] == 0.0
    assert row["route_location_ids"] == ["APT-LGW", "DST-PMI"]


# --- transfers: route_location_ids + progress -------------------------------


def test_scheduled_transfer_exposes_route_to_its_real_paired_hotel_and_zero_progress() -> None:
    world = _run_world(until=1.0)
    row = _row(world.render_state(), "transfers", "TRF-1")
    assert world.transfers["TRF-1"].status == "scheduled"
    # TRF-1 is destination_id="DST-PMI"; the one real hotel sharing that
    # destination is HTL-SUN-PMI (reference_data.py) -- never guessed.
    assert row["route_location_ids"] == ["DST-PMI", "HTL-SUN-PMI"]
    assert row["progress"] == 0.0


def test_in_progress_transfer_exposes_half_progress() -> None:
    # TRF-1 flips to "in_progress" the instant FLT-ZV101 arrives at t=140.
    world = _run_world(until=141.0)
    row = _row(world.render_state(), "transfers", "TRF-1")
    assert world.transfers["TRF-1"].status == "in_progress"
    assert row["progress"] == 0.5


def test_completed_transfer_exposes_full_progress() -> None:
    world = _run_world()  # TRF-1 completes at t=160, well before the 180 horizon
    row = _row(world.render_state(), "transfers", "TRF-1")
    assert world.transfers["TRF-1"].status == "completed"
    assert row["progress"] == 1.0


# --- parties: current_location_id -------------------------------------------


def test_party_not_yet_travelling_exposes_the_home_location() -> None:
    # BKG-1 is confirmed at t=40 (booking.confirmed); PTY-1 only starts
    # travelling at its t=80 check-in, so t=45 is real evidence of a
    # booked-but-not-yet-travelling party still sitting at "home".
    world = _run_world(until=45.0)
    booking = world.bookings["BKG-1"]
    row = _row(world.render_state(), "parties", booking.party_id)
    assert world.parties[booking.party_id].location == "home"
    assert row["current_location_id"] == "home"


def test_party_mid_flight_exposes_no_fabricated_location() -> None:
    # FLT-ZV101 departs at 90.0 and arrives at 140.0; a party whose real
    # `location` field is a flight id (airborne) has no scene location at
    # all -- rendering must surface that honestly as None, never invent
    # a position the underlying model does not have.
    world = _run_world(until=100.0)
    booking = world.bookings["BKG-1"]
    party = world.parties[booking.party_id]
    assert party.location == "FLT-ZV101"
    row = _row(world.render_state(), "parties", party.id)
    assert row["current_location_id"] is None


def test_party_at_resort_exposes_the_real_hotel_location() -> None:
    world = _run_world()  # well past FLT-ZV101's party settling in at their hotel
    booking = world.bookings["BKG-1"]
    party = world.parties[booking.party_id]
    assert party.location == booking.hotel_id
    row = _row(world.render_state(), "parties", party.id)
    assert row["current_location_id"] == booking.hotel_id


# --- customers: current_location_id derived via their party -----------------


def test_customer_exposes_their_partys_real_location() -> None:
    world = _run_world()
    booking = world.bookings["BKG-1"]
    party = world.parties[booking.party_id]
    customer_id = party.lead_customer_id
    row = _row(world.render_state(), "customers", customer_id)
    assert row["current_location_id"] == party.location == booking.hotel_id


# --- bookings: current_location_id derived via their party ------------------


def test_booking_exposes_their_partys_real_location() -> None:
    world = _run_world()
    booking = world.bookings["BKG-1"]
    party = world.parties[booking.party_id]
    row = _row(world.render_state(), "bookings", booking.id)
    assert row["current_location_id"] == party.location == booking.hotel_id


# --- disruptions: current_location_id as the affected flight's origin ------


def test_disruption_exposes_the_cancelled_flights_real_origin_airport() -> None:
    world = _run_world()  # triggers the real minute-180 autonomous cancellation
    flight = world.flights["FLT-ZV204"]
    disruption_id = f"DIS-flight_cancellation-{flight.id}"
    assert disruption_id in world.disruptions
    row = _row(world.render_state(), "disruptions", disruption_id)
    assert row["current_location_id"] == flight.origin_airport_id == "APT-LGW"


# --- hotels: occupancy_ratio / capacity_ratio / occupancy_status -----------


def test_hotel_exposes_ratios_derived_from_its_real_paired_allotment() -> None:
    world = _run_world()  # BKG-1's party has settled into HTL-SUN-PMI by t=180
    allotment = next(a for a in world.allotments.values() if a.hotel_id == "HTL-SUN-PMI")
    assert allotment.occupied > 0  # sanity: a real, non-trivial occupancy exists
    row = _row(world.render_state(), "hotels", "HTL-SUN-PMI")
    assert row["occupancy_ratio"] == pytest.approx(allotment.occupied / allotment.allotment)
    assert row["capacity_ratio"] == pytest.approx(allotment.reserved / allotment.allotment)
    assert row["occupancy_status"] in {"normal", "near_full", "full"}
    # a single settled party's rooms is nowhere near this hotel's 80-room
    # allotment, so the real ratio must genuinely be "normal" here.
    assert row["occupancy_ratio"] < 0.85
    assert row["occupancy_status"] == "normal"


def test_hotel_with_no_bookings_yet_exposes_zero_ratios() -> None:
    world = _run_world(until=1.0)
    row = _row(world.render_state(), "hotels", "HTL-BLU-TFS")
    assert row["occupancy_ratio"] == 0.0
    assert row["capacity_ratio"] == 0.0
    assert row["occupancy_status"] == "normal"


# --- golden flight-disruption-recovery: scene fields reflect the mutation --


_RECOVERY_GOLDEN_FLIGHT_ID = "FLT-ZV204"
_RECOVERY_GOLDEN_BOOKING_ID = "BKG-4"
_RECOVERY_GOLDEN_PARTY_ID = "PTY-4"
_RECOVERY_GOLDEN_NEW_FLIGHT_ID = "FLT-ZV205"


def _recovery_golden_world_and_options(until: float = 180.0):
    """The real minute-180 autonomous FLT-ZV204 cancellation (Task 5), its
    real sensor observation, and the real planner's ranked options for it.

    A local, pure-Python replica of the same mechanics
    `tests/api/world/actor/test_travel_process_commands.py` uses (kept
    local rather than imported cross-test-file, matching that file's own
    stated convention), so this file can drive the real command handler
    directly against the exact same golden scenario and observe the
    scene-rendering surface before and after.
    """
    from verticals.travel.recovery.planner import plan_recovery_options

    world = TravelWorld(seed=42)
    world.run(until)
    sensor_event = next(
        event
        for event in world.runtime.journal
        if event.type == "sensor.tripped" and event.target_id == _RECOVERY_GOLDEN_FLIGHT_ID
    )
    observation = world.build_observation(sensor_event.to_dict(), now=world.runtime.now)
    options = [option.to_dict() for option in plan_recovery_options(observation)]
    return world, options


def _recovery_command(
    option: dict, *, workflow_id: str, decision_outcome: str, decided_by: str
) -> SimulationCommand:
    """Build the exact `reaccommodate_travellers` `SimulationCommand` the
    real `TravelFlightDisruptionRecoveryOrchestrator` would have built,
    reusing that real, already-unit-tested activity function directly."""
    from verticals.travel.durable.functions import TravelRecoveryBuildCommand

    built = TravelRecoveryBuildCommand(
        {
            "workflow_id": workflow_id,
            "trace_id": f"trace-{workflow_id}",
            "option": option,
            "decision": {"outcome": decision_outcome, "decided_by": decided_by},
        }
    )
    command_dict = built["command"]
    return SimulationCommand(
        command_id=command_dict["command_id"],
        trace_id=command_dict["trace_id"],
        issued_by=command_dict["issued_by"],
        type=command_dict["type"],
        payload=command_dict["payload"],
    )


def test_golden_recovery_visibly_moves_the_scene_fields_for_bkg4_pty4_flt_zv205() -> None:
    world, options = _recovery_golden_world_and_options()
    golden = options[0]
    assert golden["new_flight_id"] == _RECOVERY_GOLDEN_NEW_FLIGHT_ID

    before = world.render_state()
    before_booking = _row(before, "bookings", _RECOVERY_GOLDEN_BOOKING_ID)
    assert before_booking["flight_id"] == _RECOVERY_GOLDEN_FLIGHT_ID
    assert before["recovery_decisions"] == []

    command = _recovery_command(
        golden, workflow_id="wf-fdr-scene-1", decision_outcome="approved", decided_by="head_of_operations"
    )
    result = world.apply_command(command)
    assert result.type == "booking.reaccommodated"

    after = world.render_state()
    after_booking = _row(after, "bookings", _RECOVERY_GOLDEN_BOOKING_ID)
    after_party = _row(after, "parties", _RECOVERY_GOLDEN_PARTY_ID)

    # the booking's real flight/transfer assignment visibly changed --
    # never a fabricated position, a real identifier reassignment plus
    # its knock-on capacity numbers on the real flight/transfer rows.
    assert after_booking["flight_id"] == _RECOVERY_GOLDEN_NEW_FLIGHT_ID
    assert after_booking["flight_id"] != before_booking["flight_id"]
    assert after_booking["recovery_status"] == "reaccommodated"
    assert after_party["state"] == "reaccommodated"

    before_old_flight = _row(before, "flights", _RECOVERY_GOLDEN_FLIGHT_ID)
    after_old_flight = _row(after, "flights", _RECOVERY_GOLDEN_FLIGHT_ID)
    after_new_flight = _row(after, "flights", _RECOVERY_GOLDEN_NEW_FLIGHT_ID)
    before_new_flight = _row(before, "flights", _RECOVERY_GOLDEN_NEW_FLIGHT_ID)
    assert after_old_flight["reserved"] < before_old_flight["reserved"]
    assert after_new_flight["reserved"] > before_new_flight["reserved"]

    # a brand new, real recovery_decision actor token appears on the scene
    # that was not there before -- itself journal-backed.
    assert len(after["recovery_decisions"]) == 1
    decision_row = after["recovery_decisions"][0]
    assert decision_row["outcome"] == "approved"
    assert decision_row["decided_by"] == "head_of_operations"
    assert "current_location_id" in decision_row

    events_by_id = _events_by_id(world)
    decision_event = events_by_id[decision_row["last_event_id"]]
    assert decision_event.actor_id == decision_row["id"]
    assert decision_event.type == "recovery.decision_recorded"
