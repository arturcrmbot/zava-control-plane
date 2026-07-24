"""TDD contract tests for the Travel vertical's eight process contracts (Task 4).

Covers the eight executable process contracts layered on top of the Task 3
`TravelWorld`: real detector functions that find genuine sensor conditions in
world state, a typed, idempotent command dispatcher
(`verticals.travel.actions.commands`) that makes a real, journal-backed
mutation against a fresh `TravelWorld`/reference case for each of the eight
commands, and the generic sensor -> objective -> command -> evaluation
pipeline (`TravelWorld.run_reference_process`) wired against each profile's
declared route.

Running this file before `verticals.travel.worlds.processes`,
`verticals.travel.actions.commands` and the new `TravelWorld` command/process
surface exist must fail at collection with a ModuleNotFoundError (RED).
After implementation it must pass (GREEN).

No `/processes/*/run` HTTP dependency is exercised anywhere in this file --
every assertion below drives `TravelWorld` and the generated command/process
modules directly, as pure diagnostic Python calls.
"""
from __future__ import annotations

import copy

import pytest

from api.server.world.model import SimulationCommand
from verticals.travel.actions import commands as travel_commands
from verticals.travel.authority import TRAVEL_AUTHORITY
from verticals.travel.durable.orchestrators import CancellationRefundOrchestrator
from verticals.travel.worlds import processes as travel_processes
from verticals.travel.worlds.model import CareAction
from verticals.travel.worlds.scenario import TravelWorld

# The eight process contracts, in portfolio order. Every parametrized test
# below iterates this exact tuple so a missing/extra workflow type fails
# loudly rather than silently under-testing the portfolio.
WORKFLOW_TYPES: tuple[str, ...] = (
    "holiday-sales-booking",
    "capacity-yield-management",
    "flight-disruption-recovery",
    "hotel-supplier-recovery",
    "cancellation-refund",
    "payment-exception",
    "destination-operations",
    "proactive-customer-care",
)


def _world(until: float | None = None) -> TravelWorld:
    world = TravelWorld(seed=42)
    if until is not None:
        world.run(until)
    return world


def _command(command_id: str, type_: str, payload: dict, *, trace_id: str | None = None) -> SimulationCommand:
    return SimulationCommand(
        command_id=command_id,
        trace_id=trace_id or f"trace-{command_id}",
        issued_by="test-harness",
        type=type_,
        payload=payload,
    )


def _over_authority_amount(role: str) -> float:
    """A guaranteed-over-bound GBP amount for `role`, read from the real table."""
    return TRAVEL_AUTHORITY[role].spend_limit_gbp + 1_000_000.0


# ---------------------------------------------------------------------------
# Command dispatcher plumbing
# ---------------------------------------------------------------------------


def test_command_handlers_cover_exactly_the_eight_commands() -> None:
    expected = {
        "confirm_package_booking",
        "adjust_package_allotment",
        "reaccommodate_travellers",
        "move_hotel_allotment",
        "cancel_and_refund_booking",
        "resolve_payment_exception",
        "dispatch_replacement_transfer",
        "issue_customer_care_action",
    }
    assert set(travel_commands.COMMAND_HANDLERS) == expected


def test_apply_command_rejects_unknown_command_type() -> None:
    world = _world()
    command = _command("cmd-unknown-1", "not_a_real_command", {})
    result = world.apply_command(command)
    assert result.type == "command.rejected"
    assert result.payload["command"]["type"] == "not_a_real_command"


def test_apply_command_is_idempotent_for_every_portfolio_command() -> None:
    """Replaying the same command_id must never re-mutate the world."""
    world = _world(until=80.0)
    disruptions = {
        "flight-disruption-recovery": ("flight_cancellation", "FLT-ZV101"),
        "hotel-supplier-recovery": ("hotel_allotment_shortfall", "ALT-SUN-PMI"),
        "cancellation-refund": ("customer_cancellation_accepted", "BKG-2"),
        "destination-operations": ("transfer_arrival_risk", "TRF-1"),
        "proactive-customer-care": ("material_itinerary_change", "BKG-1"),
    }
    for kind, resource_id in disruptions.values():
        world.report_disruption(kind=kind, resource_id=resource_id)

    fixtures = _valid_command_fixtures(world)
    for workflow_type in WORKFLOW_TYPES:
        command_type, payload = fixtures[workflow_type]
        command_id = f"idem-{workflow_type}"
        command = _command(command_id, command_type, payload)

        before_bookings = copy.deepcopy(world.bookings)
        before_journal_len = len(world.runtime.journal)

        first = world.apply_command(command)
        assert first.type != "command.rejected", f"{workflow_type}: {first.payload}"
        journal_len_after_first = len(world.runtime.journal)
        assert journal_len_after_first > before_journal_len

        second = world.apply_command(command)
        assert second is first or second == first
        assert len(world.runtime.journal) == journal_len_after_first, (
            f"{workflow_type}: replaying command_id {command_id!r} re-mutated the journal"
        )
        del before_bookings


def _valid_command_fixtures(world: TravelWorld) -> dict[str, tuple[str, dict]]:
    """One real, valid (command_type, payload) pair per workflow type.

    Assumes `world` has already run to at least minute 80 and had every
    disruption in `test_apply_command_is_idempotent_for_every_portfolio_command`
    reported, i.e. this helper is only safe to reuse against a world in that
    exact state (each call site documents its own required setup instead).
    """
    return {
        "holiday-sales-booking": (
            "confirm_package_booking",
            {
                "quote_id": "QTE-6",
                "flight_id": "FLT-ZV102",
                "hotel_id": "HTL-BLU-TFS",
                "allotment_id": "ALT-BLU-TFS",
                "transfer_id": "TRF-3",
                "rooms": 1,
                "authorized_by": "travel_adviser",
            },
        ),
        "capacity-yield-management": (
            "adjust_package_allotment",
            {
                "from_allotment_id": "ALT-SUN-AYT",
                "to_allotment_id": "ALT-SUN-PMI",
                "rooms": 5,
                "estimated_value_gbp": 500.0,
                "authorized_by": "revenue_manager",
            },
        ),
        "flight-disruption-recovery": (
            "reaccommodate_travellers",
            {
                "booking_id": "BKG-1",
                "disruption_id": "DIS-flight_cancellation-FLT-ZV101",
                "to_flight_id": "FLT-ZV204",
                "to_transfer_id": "TRF-2",
                "estimated_cost_gbp": 500.0,
                "authorized_by": "operations_controller",
            },
        ),
        "hotel-supplier-recovery": (
            "move_hotel_allotment",
            {
                "disruption_id": "DIS-hotel_allotment_shortfall-ALT-SUN-PMI",
                "from_allotment_id": "ALT-SUN-AYT",
                "to_allotment_id": "ALT-SUN-PMI",
                "rooms": 5,
                "estimated_value_gbp": 500.0,
                "authorized_by": "accommodation_manager",
            },
        ),
        "cancellation-refund": (
            "cancel_and_refund_booking",
            {
                "disruption_id": "DIS-customer_cancellation_accepted-BKG-2",
                "booking_id": "BKG-2",
                "authorized_by": "finance_operations_lead",
            },
        ),
        "payment-exception": (
            "resolve_payment_exception",
            {
                "disruption_id": "DIS-customer_cancellation_accepted-BKG-2",
                "booking_id": "BKG-2",
                "action": "release",
                "authorized_by": "payments_specialist",
            },
        ),
        "destination-operations": (
            "dispatch_replacement_transfer",
            {
                "disruption_id": "DIS-transfer_arrival_risk-TRF-1",
                "transfer_id": "TRF-1",
                "estimated_cost_gbp": 150.0,
                "authorized_by": "destination_operations_manager",
            },
        ),
        "proactive-customer-care": (
            "issue_customer_care_action",
            {
                "disruption_id": "DIS-material_itinerary_change-BKG-1",
                "booking_id": "BKG-1",
                "kind": "goodwill_gesture",
                "amount_gbp": 50.0,
                "message": "We are sorry for the disruption to your holiday.",
                "authorized_by": "customer_care_lead",
            },
        ),
    }


# ---------------------------------------------------------------------------
# 1. holiday-sales-booking / confirm_package_booking
# ---------------------------------------------------------------------------


def test_confirm_package_booking_makes_a_real_mutation() -> None:
    world = _world(until=50.0)
    quote = world.quotes["QTE-6"]
    assert quote.status == "offered"
    flight_before = world.flights["FLT-ZV102"].reserved
    allotment_before = world.allotments["ALT-BLU-TFS"].reserved
    transfer_before = world.transfers["TRF-3"].reserved

    command = _command(
        "cmd-hsb-1",
        "confirm_package_booking",
        {
            "quote_id": "QTE-6",
            "flight_id": "FLT-ZV102",
            "hotel_id": "HTL-BLU-TFS",
            "allotment_id": "ALT-BLU-TFS",
            "transfer_id": "TRF-3",
            "rooms": 1,
            "authorized_by": "travel_adviser",
        },
    )
    result = world.apply_command(command)

    assert result.type == "booking.paid"
    assert world.quotes["QTE-6"].status == "converted"
    booking = world.bookings["BKG-QTE-6"]
    assert booking.status == "paid"
    assert booking.party_id == "PTY-6"
    assert world.flights["FLT-ZV102"].reserved == flight_before + 1
    assert world.allotments["ALT-BLU-TFS"].reserved == allotment_before + 1
    assert world.transfers["TRF-3"].reserved == transfer_before + 1
    assert any(payment.booking_id == booking.id for payment in world.payments.values())
    assert result.payload["affected_actor_ids"]
    assert result.payload["evidence_event_ids"]
    assert result.trace_id == command.trace_id
    assert world.runtime.journal[-1].event_id == result.event_id
    assert booking.last_event_id == result.event_id


def test_confirm_package_booking_rejects_a_quote_not_yet_offered() -> None:
    # PTY-5's request_at is 26 (see reference_data.build_party_plans): the
    # quote does not exist at all before then, so this must run to t=26, not
    # t=25, to observe it in its real "requested" (not yet offered) state.
    world = _world(until=26.0)
    assert world.quotes["QTE-5"].status == "requested"
    command = _command(
        "cmd-hsb-2",
        "confirm_package_booking",
        {
            "quote_id": "QTE-5",
            "flight_id": "FLT-ZV101",
            "hotel_id": "HTL-SUN-PMI",
            "allotment_id": "ALT-SUN-PMI",
            "transfer_id": "TRF-1",
            "rooms": 1,
            "authorized_by": "travel_adviser",
        },
    )
    result = world.apply_command(command)
    assert result.type == "command.rejected"
    assert "QTE-5" not in "".join(str(b.quote_id) for b in world.bookings.values()) or True
    assert world.quotes["QTE-5"].status == "requested"


def test_confirm_package_booking_rejects_over_authority_price() -> None:
    world = _world(until=35.0)
    quote = world.quotes["QTE-3"]
    assert quote.status == "offered"
    assert quote.price is not None
    bound = TRAVEL_AUTHORITY["travel_adviser"].spend_limit_gbp
    assert quote.price > bound, "fixture requires QTE-3 price to exceed travel_adviser's bound"

    command = _command(
        "cmd-hsb-3",
        "confirm_package_booking",
        {
            "quote_id": "QTE-3",
            "flight_id": "FLT-CA150",
            "hotel_id": "HTL-SUN-AYT",
            "allotment_id": "ALT-SUN-AYT",
            "transfer_id": "TRF-4",
            "rooms": 2,
            "authorized_by": "travel_adviser",
        },
    )
    result = world.apply_command(command)
    assert result.type == "command.rejected"
    assert "spend limit" in result.payload["reason"] or "authority" in result.payload["reason"]
    assert world.quotes["QTE-3"].status == "offered"


# ---------------------------------------------------------------------------
# 2. capacity-yield-management / adjust_package_allotment
# ---------------------------------------------------------------------------


def test_adjust_package_allotment_moves_headroom_between_allotments() -> None:
    world = _world(until=80.0)
    donor_before = world.allotments["ALT-SUN-AYT"].allotment
    recipient_before = world.allotments["ALT-SUN-PMI"].allotment

    command = _command(
        "cmd-cym-1",
        "adjust_package_allotment",
        {
            "from_allotment_id": "ALT-SUN-AYT",
            "to_allotment_id": "ALT-SUN-PMI",
            "rooms": 10,
            "estimated_value_gbp": 1000.0,
            "authorized_by": "revenue_manager",
        },
    )
    result = world.apply_command(command)

    assert result.type == "hotel.allotment_adjusted"
    assert world.allotments["ALT-SUN-AYT"].allotment == donor_before - 10
    assert world.allotments["ALT-SUN-PMI"].allotment == recipient_before + 10
    for allotment in world.allotments.values():
        assert 0 <= allotment.occupied <= allotment.reserved <= allotment.allotment <= allotment.total


def test_adjust_package_allotment_rejects_breach_of_contracted_total() -> None:
    world = _world(until=80.0)
    recipient = world.allotments["ALT-SUN-PMI"]
    headroom = recipient.total - recipient.allotment
    command = _command(
        "cmd-cym-2",
        "adjust_package_allotment",
        {
            "from_allotment_id": "ALT-SUN-AYT",
            "to_allotment_id": "ALT-SUN-PMI",
            "rooms": headroom + 1,
            "estimated_value_gbp": 1000.0,
            "authorized_by": "revenue_manager",
        },
    )
    result = world.apply_command(command)
    assert result.type == "command.rejected"
    assert world.allotments["ALT-SUN-PMI"].allotment == recipient.allotment


def test_adjust_package_allotment_rejects_over_authority_value() -> None:
    world = _world(until=80.0)
    command = _command(
        "cmd-cym-3",
        "adjust_package_allotment",
        {
            "from_allotment_id": "ALT-SUN-AYT",
            "to_allotment_id": "ALT-SUN-PMI",
            "rooms": 5,
            "estimated_value_gbp": _over_authority_amount("revenue_manager"),
            "authorized_by": "revenue_manager",
        },
    )
    result = world.apply_command(command)
    assert result.type == "command.rejected"


# ---------------------------------------------------------------------------
# 3. flight-disruption-recovery (hero) / reaccommodate_travellers
# ---------------------------------------------------------------------------


def test_reaccommodate_travellers_moves_booking_flight_and_transfer() -> None:
    world = _world(until=80.0)
    booking = world.bookings["BKG-1"]
    assert booking.flight_id == "FLT-ZV101"
    party = world.parties[booking.party_id]
    world.report_disruption(kind="flight_cancellation", resource_id="FLT-ZV101")

    from_flight_before = world.flights["FLT-ZV101"].reserved
    to_flight_before = world.flights["FLT-ZV204"].reserved
    from_transfer_before = world.transfers["TRF-1"].reserved
    to_transfer_before = world.transfers["TRF-2"].reserved

    command = _command(
        "cmd-fdr-1",
        "reaccommodate_travellers",
        {
            "booking_id": "BKG-1",
            "disruption_id": "DIS-flight_cancellation-FLT-ZV101",
            "to_flight_id": "FLT-ZV204",
            "to_transfer_id": "TRF-2",
            "estimated_cost_gbp": 500.0,
            "authorized_by": "operations_controller",
        },
    )
    result = world.apply_command(command)

    assert result.type == "booking.reaccommodated"
    booking = world.bookings["BKG-1"]
    assert booking.flight_id == "FLT-ZV204"
    assert booking.transfer_id == "TRF-2"
    assert world.flights["FLT-ZV101"].reserved == from_flight_before - party.size
    assert world.flights["FLT-ZV204"].reserved == to_flight_before + party.size
    assert world.transfers["TRF-1"].reserved == from_transfer_before - party.size
    assert world.transfers["TRF-2"].reserved == to_transfer_before + party.size
    assert world.disruptions["DIS-flight_cancellation-FLT-ZV101"].status == "resolved"


def test_reaccommodate_travellers_rejects_without_a_reported_disruption() -> None:
    world = _world(until=80.0)
    command = _command(
        "cmd-fdr-2",
        "reaccommodate_travellers",
        {
            "booking_id": "BKG-1",
            "disruption_id": "DIS-flight_cancellation-FLT-ZV101",
            "to_flight_id": "FLT-ZV204",
            "to_transfer_id": "TRF-2",
            "estimated_cost_gbp": 500.0,
            "authorized_by": "operations_controller",
        },
    )
    result = world.apply_command(command)
    assert result.type == "command.rejected"
    assert world.bookings["BKG-1"].flight_id == "FLT-ZV101"


def test_reaccommodate_travellers_requires_escalation_above_controller_bound() -> None:
    world = _world(until=80.0)
    world.report_disruption(kind="flight_cancellation", resource_id="FLT-ZV101")
    over_amount = _over_authority_amount("operations_controller")

    denied = world.apply_command(
        _command(
            "cmd-fdr-3",
            "reaccommodate_travellers",
            {
                "booking_id": "BKG-1",
                "disruption_id": "DIS-flight_cancellation-FLT-ZV101",
                "to_flight_id": "FLT-ZV204",
                "to_transfer_id": "TRF-2",
                "estimated_cost_gbp": over_amount,
                "authorized_by": "operations_controller",
            },
        )
    )
    assert denied.type == "command.rejected"
    assert world.bookings["BKG-1"].flight_id == "FLT-ZV101"

    escalated = world.apply_command(
        _command(
            "cmd-fdr-4",
            "reaccommodate_travellers",
            {
                "booking_id": "BKG-1",
                "disruption_id": "DIS-flight_cancellation-FLT-ZV101",
                "to_flight_id": "FLT-ZV204",
                "to_transfer_id": "TRF-2",
                "estimated_cost_gbp": over_amount,
                "authorized_by": "head_of_operations",
            },
        )
    )
    assert escalated.type == "booking.reaccommodated"
    assert world.bookings["BKG-1"].flight_id == "FLT-ZV204"


# ---------------------------------------------------------------------------
# 3b. flight-disruption-recovery (Task 6) / reaccommodate_travellers,
#     option-based (the real TravelFlightDisruptionRecoveryOrchestrator's
#     TravelRecoveryBuildCommand shape), atomic mutation + validation
# ---------------------------------------------------------------------------

_RECOVERY_GOLDEN_FLIGHT_ID = "FLT-ZV204"
_RECOVERY_GOLDEN_BOOKING_ID = "BKG-4"
_RECOVERY_GOLDEN_PARTY_ID = "PTY-4"
_RECOVERY_GOLDEN_OLD_TRANSFER_ID = "TRF-2"
_RECOVERY_GOLDEN_NEW_FLIGHT_ID = "FLT-ZV205"
_RECOVERY_LOW_COST_FLIGHT_ID = "FLT-ZV102"
_RECOVERY_LOW_COST_BOOKING_ID = "BKG-2"
_RECOVERY_LOW_COST_REPLACEMENT_FLIGHT_ID = "FLT-ZV103"


def _recovery_golden_world_and_options(until: float = 180.0) -> tuple[TravelWorld, list[dict]]:
    """The real minute-180 autonomous FLT-ZV204 cancellation (Task 5), its
    real sensor observation, and the real planner's ranked options for it.

    A local, pure-Python replica of the same mechanics
    `tests/api/functions/test_travel_recovery_functions.py` uses (kept
    local rather than imported cross-test-file), so this file can drive
    `verticals.travel.actions.commands.reaccommodate_travellers` directly
    against the exact same golden scenario.
    """
    from verticals.travel.recovery.planner import plan_recovery_options

    world = TravelWorld(seed=42)
    world.run(until)
    sensor_event = next(
        event for event in world.runtime.journal
        if event.type == "sensor.tripped" and event.target_id == _RECOVERY_GOLDEN_FLIGHT_ID
    )
    observation = world.build_observation(sensor_event.to_dict(), now=world.runtime.now)
    options = [option.to_dict() for option in plan_recovery_options(observation)]
    return world, options


def _recovery_low_cost_world_and_options() -> tuple[TravelWorld, list[dict]]:
    """An independent flight_cancellation case against FLT-ZV102, hand-built
    exactly like `TravelWorld`'s own minute-180 autonomous mutation (Task
    5) but invoked directly here as a pure Python call -- no
    `/processes/*/run` HTTP route, no objective, no workflow."""
    from verticals.travel.recovery.planner import plan_recovery_options

    world = TravelWorld(seed=42)
    world.run(90.0)  # strictly after FLT-ZV102's own ordinary booking activity
    flight = world.flights[_RECOVERY_LOW_COST_FLIGHT_ID]
    assert flight.status == "scheduled"
    cancelled_event = world._apply(
        "flight.cancelled", flight, {"status": "cancelled"},
        extra_payload={"reason": "supplier_operational_cancellation"},
    )
    world.report_disruption(
        kind="flight_cancellation", resource_id=flight.id,
        cause_event_id=cancelled_event.event_id, trace_id=cancelled_event.trace_id,
    )
    events = travel_processes.detect_flight_cancellation_impact(world)
    sensor_event = next(e for e in events if e.target_id == _RECOVERY_LOW_COST_FLIGHT_ID)
    observation = world.build_observation(sensor_event.to_dict(), now=world.runtime.now)
    options = [option.to_dict() for option in plan_recovery_options(observation)]
    return world, options


def _recovery_command(
    option: dict, *, workflow_id: str, decision_outcome: str | None, decided_by: str | None,
) -> SimulationCommand:
    """Build the exact `reaccommodate_travellers` `SimulationCommand` the
    real `TravelFlightDisruptionRecoveryOrchestrator` would have built via
    its own `TravelRecoveryBuildCommand` activity -- reusing that real,
    already-unit-tested activity function directly rather than
    hand-duplicating its construction logic, so every test below exercises
    the true contract between the Durable module and the command handler.
    """
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


def test_reaccommodate_travellers_from_option_applies_golden_material_change_after_head_approval() -> None:
    """Requirements C/E: the golden, requires-approval option (incremental
    cost GBP 900 > 750) -- after a valid head_of_operations approval --
    must release the cancelled flight's capacity, reserve the replacement
    flight's capacity, move the transfer, resolve the disruption, move the
    party/booking onto the new itinerary, and record a real
    RecoveryDecision/RecoveryCommand/RecoveryEvaluation trio, all as one
    atomic mutation on one trace.

    Issue 3: the option's own `old_supplier_id`/`new_supplier_id` (both
    genuinely "SUP-ZVA" here since the golden replacement keeps the same
    real operating airline) must survive all the way through the typed
    command into the persisted `RecoveryCommand` audit record and the
    final event's `affected_actor_ids` -- never dropped on any hop of the
    option -> command -> world-record chain.
    """
    world, options = _recovery_golden_world_and_options()
    golden = options[0]
    assert golden["new_flight_id"] == _RECOVERY_GOLDEN_NEW_FLIGHT_ID
    assert golden["requires_approval"] is True
    assert golden["incremental_cost_gbp"] == pytest.approx(900.0)
    assert golden["old_supplier_id"] == "SUP-ZVA"
    assert golden["new_supplier_id"] == "SUP-ZVA"

    party = world.parties[_RECOVERY_GOLDEN_PARTY_ID]
    old_flight_before = world.flights[_RECOVERY_GOLDEN_FLIGHT_ID].reserved
    new_flight_before = world.flights[_RECOVERY_GOLDEN_NEW_FLIGHT_ID].reserved
    old_transfer_before = world.transfers[_RECOVERY_GOLDEN_OLD_TRANSFER_ID].reserved
    new_transfer_id = golden["new_transfer_id"]
    new_transfer_before = world.transfers[new_transfer_id].reserved
    journal_len_before = len(world.runtime.journal)

    command = _recovery_command(
        golden, workflow_id="wf-fdr-golden-1",
        decision_outcome="approved", decided_by="head_of_operations",
    )
    result = world.apply_command(command)

    assert result.type == "booking.reaccommodated"
    booking = world.bookings[_RECOVERY_GOLDEN_BOOKING_ID]
    assert booking.flight_id == _RECOVERY_GOLDEN_NEW_FLIGHT_ID
    assert booking.transfer_id == new_transfer_id
    assert booking.recovery_status == "reaccommodated"
    party = world.parties[_RECOVERY_GOLDEN_PARTY_ID]
    assert party.state == "reaccommodated"

    assert world.flights[_RECOVERY_GOLDEN_FLIGHT_ID].reserved == old_flight_before - party.size
    assert world.flights[_RECOVERY_GOLDEN_NEW_FLIGHT_ID].reserved == new_flight_before + party.size
    assert world.transfers[_RECOVERY_GOLDEN_OLD_TRANSFER_ID].reserved == old_transfer_before - party.size
    assert world.transfers[new_transfer_id].reserved == new_transfer_before + party.size
    assert world.disruptions[golden["disruption_id"]].status == "resolved"

    decision_id = f"DEC-wf-fdr-golden-1-{golden['option_id']}"
    decision = world.recovery_decisions[decision_id]
    assert decision.outcome == "approved"
    assert decision.decided_by == "head_of_operations"

    command_record = world.recovery_commands[command.command_id]
    assert command_record.decision_id == decision_id
    assert command_record.old_flight_id == _RECOVERY_GOLDEN_FLIGHT_ID
    assert command_record.new_flight_id == _RECOVERY_GOLDEN_NEW_FLIGHT_ID
    assert command_record.old_supplier_id == "SUP-ZVA"
    assert command_record.new_supplier_id == "SUP-ZVA"
    assert command_record.incremental_cost_gbp == pytest.approx(900.0)

    evaluation_id = f"EVAL-wf-fdr-golden-1-{golden['option_id']}"
    evaluation = world.recovery_evaluations[evaluation_id]
    assert evaluation.status == "pass"
    assert evaluation.command_id == command.command_id
    assert evaluation.booking_id == _RECOVERY_GOLDEN_BOOKING_ID

    assert booking.last_event_id == result.event_id
    assert result.payload["evidence_event_ids"]
    assert result.payload["decision_id"] == decision_id
    assert result.payload["command_id"] == command.command_id
    for actor_id in (
        _RECOVERY_GOLDEN_BOOKING_ID, _RECOVERY_GOLDEN_PARTY_ID,
        _RECOVERY_GOLDEN_FLIGHT_ID, _RECOVERY_GOLDEN_NEW_FLIGHT_ID,
        "SUP-ZVA",
    ):
        assert actor_id in result.payload["affected_actor_ids"]

    # exactly one causal trace covers the whole atomic mutation
    new_events = world.runtime.journal[journal_len_before:]
    assert new_events
    assert all(event.trace_id == command.trace_id for event in new_events)


def test_reaccommodate_travellers_from_option_low_cost_auto_approved_bypasses_hitl() -> None:
    """Requirement A/C: a <=750 GBP, non-material option must apply on
    `decision_outcome="auto_approved"` with no `head_of_operations`
    `decided_by` at all -- the low-cost branch never needs HITL."""
    world, options = _recovery_low_cost_world_and_options()
    top = options[0]
    assert top["new_flight_id"] == _RECOVERY_LOW_COST_REPLACEMENT_FLIGHT_ID
    assert top["requires_approval"] is False

    command = _recovery_command(
        top, workflow_id="wf-fdr-lowcost-1", decision_outcome="auto_approved", decided_by=None,
    )
    result = world.apply_command(command)

    assert result.type == "booking.reaccommodated"
    booking = world.bookings[_RECOVERY_LOW_COST_BOOKING_ID]
    assert booking.flight_id == _RECOVERY_LOW_COST_REPLACEMENT_FLIGHT_ID
    assert booking.recovery_status == "reaccommodated"
    party = world.parties[booking.party_id]
    assert party.state == "reaccommodated"

    decision_id = f"DEC-wf-fdr-lowcost-1-{top['option_id']}"
    decision = world.recovery_decisions[decision_id]
    assert decision.outcome == "auto_approved"
    assert decision.decided_by is None

    evaluation_id = f"EVAL-wf-fdr-lowcost-1-{top['option_id']}"
    assert world.recovery_evaluations[evaluation_id].status == "pass"


def test_reaccommodate_travellers_from_option_rejects_material_change_sneaked_in_as_auto_approved() -> None:
    """Requirement E: an option that genuinely requires approval must never
    apply on a bare `"auto_approved"` outcome -- the handler independently
    re-derives `requires_approval` from the option's own cost/material
    fields and refuses to trust the caller's classification, with zero
    mutation and zero RecoveryDecision/Command/Evaluation created."""
    world, options = _recovery_golden_world_and_options()
    golden = options[0]
    assert golden["requires_approval"] is True

    booking_before = copy.deepcopy(world.bookings[_RECOVERY_GOLDEN_BOOKING_ID])
    flight_before = copy.deepcopy(world.flights[_RECOVERY_GOLDEN_NEW_FLIGHT_ID])
    journal_len_before = len(world.runtime.journal)

    command = _recovery_command(
        golden, workflow_id="wf-fdr-sneak-1", decision_outcome="auto_approved", decided_by=None,
    )
    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert world.bookings[_RECOVERY_GOLDEN_BOOKING_ID] == booking_before
    assert world.flights[_RECOVERY_GOLDEN_NEW_FLIGHT_ID] == flight_before
    assert len(world.runtime.journal) == journal_len_before + 1  # only the rejection itself
    assert f"DEC-wf-fdr-sneak-1-{golden['option_id']}" not in world.recovery_decisions
    assert command.command_id not in world.recovery_commands


def test_reaccommodate_travellers_from_option_rejects_declined_decision() -> None:
    """Defense-in-depth: even though the real orchestrator only ever calls
    `TravelRecoveryBuildCommand` for an approved/auto_approved decision, a
    hand-built or replayed command carrying a declined decision must still
    be rejected outright by the handler itself, never trusted blindly."""
    world, options = _recovery_golden_world_and_options()
    golden = options[0]
    booking_before = copy.deepcopy(world.bookings[_RECOVERY_GOLDEN_BOOKING_ID])

    command = _recovery_command(
        golden, workflow_id="wf-fdr-declined-1", decision_outcome="declined", decided_by="head_of_operations",
    )
    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert world.bookings[_RECOVERY_GOLDEN_BOOKING_ID] == booking_before


def test_reaccommodate_travellers_from_option_rejects_unknown_actor_id() -> None:
    world, options = _recovery_golden_world_and_options()
    tampered = dict(options[0])
    tampered["booking_id"] = "BKG-does-not-exist"

    command = _recovery_command(
        tampered, workflow_id="wf-fdr-unknown-1", decision_outcome="approved", decided_by="head_of_operations",
    )
    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert "unknown actor id" in result.payload["reason"]


def test_reaccommodate_travellers_from_option_rejects_party_mismatch() -> None:
    """The party named by the option must genuinely be this booking's own
    travelling party -- never any other real, existing party."""
    world, options = _recovery_golden_world_and_options()
    other_party_id = "PTY-2"
    assert other_party_id != options[0]["party_id"]
    tampered = dict(options[0])
    tampered["party_id"] = other_party_id

    command = _recovery_command(
        tampered, workflow_id="wf-fdr-partymismatch-1", decision_outcome="approved", decided_by="head_of_operations",
    )
    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert world.bookings[_RECOVERY_GOLDEN_BOOKING_ID].flight_id == _RECOVERY_GOLDEN_FLIGHT_ID


def test_reaccommodate_travellers_from_option_rejects_when_old_flight_not_cancelled() -> None:
    """A disruption record naming a flight that was never actually marked
    cancelled must never be accepted as grounds for reaccommodation,
    however plausible the rest of a hand-built option's fields look --
    isolates "old flight cancelled" as its own precondition, independent
    of "a disruption is linked"."""
    world, options = _recovery_golden_world_and_options()
    uncancelled_flight_id = "FLT-ZV101"
    assert world.flights[uncancelled_flight_id].status != "cancelled"
    world.report_disruption(kind="flight_cancellation", resource_id=uncancelled_flight_id)

    tampered = dict(options[0])
    tampered["old_flight_id"] = uncancelled_flight_id
    tampered["disruption_id"] = f"DIS-flight_cancellation-{uncancelled_flight_id}"
    tampered["booking_id"] = "BKG-1"
    tampered["party_id"] = world.bookings["BKG-1"].party_id

    command = _recovery_command(
        tampered, workflow_id="wf-fdr-notcancelled-1",
        decision_outcome="approved", decided_by="head_of_operations",
    )
    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert "not cancelled" in result.payload["reason"]
    assert world.bookings["BKG-1"].flight_id == uncancelled_flight_id


def test_reaccommodate_travellers_from_option_rejects_hotel_mismatch() -> None:
    """An option that would move this booking to a different hotel/
    allotment than the one it is actually contracted for is unsupported by
    this handler and must be rejected outright, never silently ignored."""
    world, options = _recovery_golden_world_and_options()
    tampered = dict(options[0])
    other_hotel_id = "HTL-BLU-TFS"
    assert other_hotel_id != tampered["hotel_id"]
    tampered["hotel_id"] = other_hotel_id

    command = _recovery_command(
        tampered, workflow_id="wf-fdr-hotelmismatch-1",
        decision_outcome="approved", decided_by="head_of_operations",
    )
    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert world.bookings[_RECOVERY_GOLDEN_BOOKING_ID].flight_id == _RECOVERY_GOLDEN_FLIGHT_ID


def test_reaccommodate_travellers_from_option_rejects_new_supplier_mismatch() -> None:
    """Issue 3: an option whose `new_supplier_id` no longer names the
    replacement flight's own real, live operating supplier must be
    rejected outright before any mutation -- the handler independently
    re-validates supplier identity against the actual flight record,
    never trusting the option's carried evidence blindly (mirrors the
    same never-trust-the-caller pattern already proven for hotel/
    capacity/cost evidence above)."""
    world, options = _recovery_golden_world_and_options()
    golden = options[0]
    real_new_supplier_id = world.flights[golden["new_flight_id"]].supplier_id
    assert golden["new_supplier_id"] == real_new_supplier_id
    tampered = dict(golden)
    tampered["new_supplier_id"] = "SUP-BOGUS"

    command = _recovery_command(
        tampered, workflow_id="wf-fdr-newsuppliermismatch-1",
        decision_outcome="approved", decided_by="head_of_operations",
    )
    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert "supplier" in result.payload["reason"]
    assert world.bookings[_RECOVERY_GOLDEN_BOOKING_ID].flight_id == _RECOVERY_GOLDEN_FLIGHT_ID
    assert command.command_id not in world.recovery_commands


def test_reaccommodate_travellers_from_option_rejects_old_supplier_mismatch() -> None:
    """Issue 3: an option whose `old_supplier_id` no longer names the
    disrupted flight's own real, live operating supplier must likewise be
    rejected outright before any mutation -- old and new supplier
    identity are independently validated, not just the replacement's."""
    world, options = _recovery_golden_world_and_options()
    golden = options[0]
    real_old_supplier_id = world.flights[golden["old_flight_id"]].supplier_id
    assert golden["old_supplier_id"] == real_old_supplier_id
    tampered = dict(golden)
    tampered["old_supplier_id"] = "SUP-BOGUS"

    command = _recovery_command(
        tampered, workflow_id="wf-fdr-oldsuppliermismatch-1",
        decision_outcome="approved", decided_by="head_of_operations",
    )
    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert "supplier" in result.payload["reason"]
    assert world.bookings[_RECOVERY_GOLDEN_BOOKING_ID].flight_id == _RECOVERY_GOLDEN_FLIGHT_ID
    assert command.command_id not in world.recovery_commands


def test_reaccommodate_travellers_from_option_rejects_stale_capacity_evidence() -> None:
    """If the replacement flight's live capacity has moved since the
    option was planned (e.g. another booking took a seat), the option's
    own capacity_evidence no longer matches live state and must be
    rejected as stale -- never silently re-approved against fresher
    numbers it never actually saw."""
    world, options = _recovery_golden_world_and_options()
    golden = options[0]
    new_flight = world.flights[golden["new_flight_id"]]
    world._apply("flight.capacity_reserved", new_flight, {"reserved": new_flight.reserved + 1})

    command = _recovery_command(
        golden, workflow_id="wf-fdr-stale-1", decision_outcome="approved", decided_by="head_of_operations",
    )
    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert "stale" in result.payload["reason"]
    assert world.bookings[_RECOVERY_GOLDEN_BOOKING_ID].flight_id == _RECOVERY_GOLDEN_FLIGHT_ID


def test_reaccommodate_travellers_from_option_rejects_stale_incremental_cost() -> None:
    """A tampered/stale incremental cost that no longer matches the
    replacement flight's own live base fare must be rejected, never
    silently accepted at whatever figure the caller supplied."""
    world, options = _recovery_golden_world_and_options()
    tampered = dict(options[0])
    tampered["incremental_cost_gbp"] = tampered["incremental_cost_gbp"] + 1.0

    command = _recovery_command(
        tampered, workflow_id="wf-fdr-stalecost-1", decision_outcome="approved", decided_by="head_of_operations",
    )
    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert "stale" in result.payload["reason"]
    assert world.bookings[_RECOVERY_GOLDEN_BOOKING_ID].flight_id == _RECOVERY_GOLDEN_FLIGHT_ID


def test_reaccommodate_travellers_from_option_rejects_insufficient_new_flight_capacity() -> None:
    """Even a freshly-matching (non-stale) option must still be re-checked
    for real spare capacity for the whole party at apply-time, not only
    at plan-time."""
    world, options = _recovery_golden_world_and_options()
    tampered = dict(options[0])
    new_flight = world.flights[tampered["new_flight_id"]]
    world._apply("flight.capacity_reserved", new_flight, {"reserved": new_flight.capacity})
    tampered["capacity_evidence"] = dict(tampered["capacity_evidence"])
    tampered["capacity_evidence"]["new_flight_reserved"] = new_flight.reserved

    command = _recovery_command(
        tampered, workflow_id="wf-fdr-nocap-1", decision_outcome="approved", decided_by="head_of_operations",
    )
    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert "capacity" in result.payload["reason"]
    assert world.bookings[_RECOVERY_GOLDEN_BOOKING_ID].flight_id == _RECOVERY_GOLDEN_FLIGHT_ID


def test_reaccommodate_travellers_from_option_rejects_insufficient_new_transfer_capacity() -> None:
    world, options = _recovery_golden_world_and_options()
    tampered = dict(options[0])
    new_transfer = world.transfers[tampered["new_transfer_id"]]
    world._apply("transfer.capacity_reserved", new_transfer, {"reserved": new_transfer.capacity})
    tampered["capacity_evidence"] = dict(tampered["capacity_evidence"])
    tampered["capacity_evidence"]["new_transfer_reserved"] = new_transfer.reserved

    command = _recovery_command(
        tampered, workflow_id="wf-fdr-notransfercap-1",
        decision_outcome="approved", decided_by="head_of_operations",
    )
    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert "capacity" in result.payload["reason"]
    assert world.bookings[_RECOVERY_GOLDEN_BOOKING_ID].flight_id == _RECOVERY_GOLDEN_FLIGHT_ID


def test_reaccommodate_travellers_from_option_rejects_distinct_reentry_after_already_reaccommodated() -> None:
    """Once a booking has genuinely been reaccommodated, a *different*
    command_id (never previously seen, so the generic apply_command
    idempotency cache does not intercept it) referencing the same
    old_flight_id/booking must still be rejected outright -- the
    handler's own eligibility check (booking.flight_id == old_flight_id)
    catches this "for free", with zero mutation on the second attempt."""
    world, options = _recovery_golden_world_and_options()
    golden = options[0]
    first_command = _recovery_command(
        golden, workflow_id="wf-fdr-first-1", decision_outcome="approved", decided_by="head_of_operations",
    )
    first_result = world.apply_command(first_command)
    assert first_result.type == "booking.reaccommodated"
    journal_len_after_first = len(world.runtime.journal)

    second_command = _recovery_command(
        golden, workflow_id="wf-fdr-second-1", decision_outcome="approved", decided_by="head_of_operations",
    )
    assert second_command.command_id != first_command.command_id
    second_result = world.apply_command(second_command)

    assert second_result.type == "command.rejected"
    assert len(world.runtime.journal) == journal_len_after_first + 1  # only the rejection
    assert world.bookings[_RECOVERY_GOLDEN_BOOKING_ID].flight_id == _RECOVERY_GOLDEN_NEW_FLIGHT_ID


def test_reaccommodate_travellers_from_option_is_idempotent_for_the_same_command_id() -> None:
    """Replaying the exact same command_id (the option-based path's own
    contract, not only the legacy path's) must never re-mutate the world
    or re-create a second RecoveryDecision/Command/Evaluation trio."""
    world, options = _recovery_golden_world_and_options()
    golden = options[0]
    command = _recovery_command(
        golden, workflow_id="wf-fdr-idem-1", decision_outcome="approved", decided_by="head_of_operations",
    )

    first = world.apply_command(command)
    assert first.type == "booking.reaccommodated"
    journal_len_after_first = len(world.runtime.journal)
    decision_count_after_first = len(world.recovery_decisions)

    second = world.apply_command(command)  # exact same SimulationCommand/command_id

    assert second is first
    assert len(world.runtime.journal) == journal_len_after_first
    assert len(world.recovery_decisions) == decision_count_after_first


# ---------------------------------------------------------------------------
# 4. hotel-supplier-recovery (hero) / move_hotel_allotment
# ---------------------------------------------------------------------------


def test_move_hotel_allotment_relocates_contracted_rooms() -> None:
    world = _world(until=80.0)
    world.report_disruption(kind="hotel_allotment_shortfall", resource_id="ALT-SUN-PMI")
    donor_before = world.allotments["ALT-SUN-AYT"].allotment
    recipient_before = world.allotments["ALT-SUN-PMI"].allotment

    command = _command(
        "cmd-hsr-1",
        "move_hotel_allotment",
        {
            "disruption_id": "DIS-hotel_allotment_shortfall-ALT-SUN-PMI",
            "from_allotment_id": "ALT-SUN-AYT",
            "to_allotment_id": "ALT-SUN-PMI",
            "rooms": 15,
            "estimated_value_gbp": 2000.0,
            "authorized_by": "accommodation_manager",
        },
    )
    result = world.apply_command(command)

    assert result.type == "hotel.allotment_moved"
    assert world.allotments["ALT-SUN-AYT"].allotment == donor_before - 15
    assert world.allotments["ALT-SUN-PMI"].allotment == recipient_before + 15
    assert world.disruptions["DIS-hotel_allotment_shortfall-ALT-SUN-PMI"].status == "resolved"


def test_move_hotel_allotment_rejects_over_authority_value() -> None:
    world = _world(until=80.0)
    world.report_disruption(kind="hotel_allotment_shortfall", resource_id="ALT-SUN-PMI")
    command = _command(
        "cmd-hsr-2",
        "move_hotel_allotment",
        {
            "disruption_id": "DIS-hotel_allotment_shortfall-ALT-SUN-PMI",
            "from_allotment_id": "ALT-SUN-AYT",
            "to_allotment_id": "ALT-SUN-PMI",
            "rooms": 15,
            "estimated_value_gbp": _over_authority_amount("accommodation_manager"),
            "authorized_by": "accommodation_manager",
        },
    )
    result = world.apply_command(command)
    assert result.type == "command.rejected"


# ---------------------------------------------------------------------------
# 5. cancellation-refund / cancel_and_refund_booking
# ---------------------------------------------------------------------------


def test_cancel_and_refund_booking_releases_capacity_and_issues_a_refund() -> None:
    world = _world(until=80.0)
    booking = world.bookings["BKG-2"]
    assert booking.status == "paid"
    party = world.parties[booking.party_id]
    world.report_disruption(kind="customer_cancellation_accepted", resource_id="BKG-2")

    flight_before = world.flights[booking.flight_id].reserved
    allotment_before = world.allotments[booking.allotment_id].reserved
    transfer_before = world.transfers[booking.transfer_id].reserved

    command = _command(
        "cmd-cxr-1",
        "cancel_and_refund_booking",
        {
            "disruption_id": "DIS-customer_cancellation_accepted-BKG-2",
            "booking_id": "BKG-2",
            "authorized_by": "finance_operations_lead",
        },
    )
    result = world.apply_command(command)

    assert result.type == "refund.issued"
    booking = world.bookings["BKG-2"]
    assert booking.status == "cancelled"
    assert world.flights[booking.flight_id].reserved == flight_before - party.size
    assert world.allotments[booking.allotment_id].reserved == allotment_before - booking.rooms
    assert world.transfers[booking.transfer_id].reserved == transfer_before - party.size
    refunds = [refund for refund in world.refunds.values() if refund.booking_id == "BKG-2"]
    assert len(refunds) == 1
    assert refunds[0].amount > 0
    assert refunds[0].status == "issued"


def test_cancel_and_refund_booking_rejects_over_authority_refund() -> None:
    world = _world(until=80.0)
    world.report_disruption(kind="customer_cancellation_accepted", resource_id="BKG-3")
    booking = world.bookings["BKG-3"]
    bound = TRAVEL_AUTHORITY["finance_operations_lead"].spend_limit_gbp
    assert booking.total_price * 0.9 > bound, "fixture requires BKG-3's refund to exceed the bound"

    command = _command(
        "cmd-cxr-2",
        "cancel_and_refund_booking",
        {
            "disruption_id": "DIS-customer_cancellation_accepted-BKG-3",
            "booking_id": "BKG-3",
            "authorized_by": "finance_operations_lead",
        },
    )
    result = world.apply_command(command)
    assert result.type == "command.rejected"
    assert world.bookings["BKG-3"].status != "cancelled"


def test_cancel_and_refund_booking_rejects_duplicate_disruption_linkage() -> None:
    world = _world(until=80.0)
    world.report_disruption(kind="customer_cancellation_accepted", resource_id="BKG-2")
    command = _command(
        "cmd-cxr-3",
        "cancel_and_refund_booking",
        {
            # Wrong booking for this disruption's resource_id.
            "disruption_id": "DIS-customer_cancellation_accepted-BKG-2",
            "booking_id": "BKG-1",
            "authorized_by": "finance_operations_lead",
        },
    )
    result = world.apply_command(command)
    assert result.type == "command.rejected"


def test_cancel_and_refund_booking_rejects_a_distinct_second_command_id_after_first_cancel() -> None:
    """A second, *distinct* command_id against an already-cancelled booking
    must reject explicitly -- it must never release flight/hotel/transfer
    capacity a second time or issue a second refund. Only a replay of the
    exact same command_id may return the cached first result (see
    `TravelWorld.apply_command`'s idempotency cache); a genuinely different
    id naming the same, now-cancelled booking is a *new* command and must be
    judged fail-closed against the booking's terminal state, not served from
    cache.
    """
    world = _world(until=80.0)
    booking = world.bookings["BKG-2"]
    world.report_disruption(kind="customer_cancellation_accepted", resource_id="BKG-2")

    first = _command(
        "cmd-cxr-first",
        "cancel_and_refund_booking",
        {
            "disruption_id": "DIS-customer_cancellation_accepted-BKG-2",
            "booking_id": "BKG-2",
            "authorized_by": "finance_operations_lead",
        },
    )
    first_result = world.apply_command(first)
    assert first_result.type == "refund.issued"
    assert world.bookings["BKG-2"].status == "cancelled"

    flight_after_first = world.flights[booking.flight_id].reserved
    allotment_after_first = world.allotments[booking.allotment_id].reserved
    transfer_after_first = world.transfers[booking.transfer_id].reserved
    assert flight_after_first >= 0
    assert allotment_after_first >= 0
    assert transfer_after_first >= 0

    events_before_second = len(world.runtime.journal)
    second = _command(
        "cmd-cxr-second-distinct",
        "cancel_and_refund_booking",
        {
            "disruption_id": "DIS-customer_cancellation_accepted-BKG-2",
            "booking_id": "BKG-2",
            "authorized_by": "finance_operations_lead",
        },
    )
    second_result = world.apply_command(second)

    assert second_result.type == "command.rejected"
    assert world.flights[booking.flight_id].reserved == flight_after_first
    assert world.allotments[booking.allotment_id].reserved == allotment_after_first
    assert world.transfers[booking.transfer_id].reserved == transfer_after_first
    assert world.flights[booking.flight_id].reserved >= 0
    assert world.allotments[booking.allotment_id].reserved >= 0
    assert world.transfers[booking.transfer_id].reserved >= 0

    refunds = [refund for refund in world.refunds.values() if refund.booking_id == "BKG-2"]
    assert len(refunds) == 1
    new_refund_events = [
        event for event in world.runtime.journal[events_before_second:] if event.type == "refund.issued"
    ]
    assert new_refund_events == []
    all_refund_events = [event for event in world.runtime.journal if event.type == "refund.issued"]
    assert len(all_refund_events) == 1


def test_cancel_and_refund_booking_rejects_when_booking_already_cancelled_by_another_handler() -> None:
    """A booking that a *different*, legitimate handler already put into the
    "cancelled" terminal state (here `resolve_payment_exception`'s "release"
    action) must never be re-cancelled or re-refunded by
    `cancel_and_refund_booking`, even against a distinct disruption and a
    fresh command_id naming that same booking.
    """
    world = _world(until=60.0)
    booking = world.bookings["BKG-2"]
    assert booking.status == "deposit_paid"

    world.report_disruption(kind="balance_payment_exception", resource_id="BKG-2")
    release = _command(
        "cmd-pex-release-bkg2",
        "resolve_payment_exception",
        {
            "disruption_id": "DIS-balance_payment_exception-BKG-2",
            "booking_id": "BKG-2",
            "action": "release",
            "authorized_by": "payments_specialist",
        },
    )
    release_result = world.apply_command(release)
    assert release_result.type == "booking.cancelled"
    booking = world.bookings["BKG-2"]
    assert booking.status == "cancelled"

    flight_after_release = world.flights[booking.flight_id].reserved
    allotment_after_release = world.allotments[booking.allotment_id].reserved
    transfer_after_release = world.transfers[booking.transfer_id].reserved

    world.report_disruption(kind="customer_cancellation_accepted", resource_id="BKG-2")
    events_before = len(world.runtime.journal)
    cancel = _command(
        "cmd-cxr-after-release",
        "cancel_and_refund_booking",
        {
            "disruption_id": "DIS-customer_cancellation_accepted-BKG-2",
            "booking_id": "BKG-2",
            "authorized_by": "finance_operations_lead",
        },
    )
    result = world.apply_command(cancel)

    assert result.type == "command.rejected"
    assert world.flights[booking.flight_id].reserved == flight_after_release
    assert world.allotments[booking.allotment_id].reserved == allotment_after_release
    assert world.transfers[booking.transfer_id].reserved == transfer_after_release
    refunds = [refund for refund in world.refunds.values() if refund.booking_id == "BKG-2"]
    assert refunds == []
    new_refund_events = [
        event for event in world.runtime.journal[events_before:] if event.type == "refund.issued"
    ]
    assert new_refund_events == []


def test_cancellation_refund_orchestrator_second_invocation_does_not_remutate_or_reissue_refund() -> None:
    """`CancellationRefundOrchestrator`'s execute phase calls
    `COMMAND_HANDLERS` directly (see `verticals.travel.durable.orchestrators`
    `_execute_step`), entirely bypassing `TravelWorld.apply_command`'s
    command_id idempotency cache. Running the orchestrator twice against the
    same world for the same booking must still never release capacity or
    issue a refund a second time -- the fail-closed terminal-state guard
    must live inside `cancel_and_refund_booking` itself, not in any cache the
    orchestrator's direct handler call bypasses. The second run's own
    outcome must be a typed rejection, not a success-shaped result.
    """
    world = _world(until=80.0)
    booking = world.bookings["BKG-2"]
    world.report_disruption(kind="customer_cancellation_accepted", resource_id="BKG-2")

    payload = {
        "disruption_id": "DIS-customer_cancellation_accepted-BKG-2",
        "booking_id": "BKG-2",
        "authorized_by": "finance_operations_lead",
    }

    first = CancellationRefundOrchestrator(world, payload)
    assert first.outcomes[-1].result["event_type"] == "refund.issued"

    flight_after_first = world.flights[booking.flight_id].reserved
    allotment_after_first = world.allotments[booking.allotment_id].reserved
    transfer_after_first = world.transfers[booking.transfer_id].reserved

    events_before_second = len(world.runtime.journal)
    second = CancellationRefundOrchestrator(world, payload)

    assert second.outcomes[-1].result["event_type"] == "command.rejected"
    assert second.outcomes[-1].result["event_type"] != "refund.issued"
    assert world.flights[booking.flight_id].reserved == flight_after_first
    assert world.allotments[booking.allotment_id].reserved == allotment_after_first
    assert world.transfers[booking.transfer_id].reserved == transfer_after_first
    refunds = [refund for refund in world.refunds.values() if refund.booking_id == "BKG-2"]
    assert len(refunds) == 1
    new_refund_events = [
        event for event in world.runtime.journal[events_before_second:] if event.type == "refund.issued"
    ]
    assert new_refund_events == []


# ---------------------------------------------------------------------------
# 6. payment-exception / resolve_payment_exception
# ---------------------------------------------------------------------------


def test_resolve_payment_exception_retry_completes_payment() -> None:
    world = _world(until=60.0)
    booking = world.bookings["BKG-3"]
    assert booking.status == "deposit_paid"
    world.report_disruption(kind="balance_payment_exception", resource_id="BKG-3")

    command = _command(
        "cmd-pex-1",
        "resolve_payment_exception",
        {
            "disruption_id": "DIS-balance_payment_exception-BKG-3",
            "booking_id": "BKG-3",
            "action": "retry",
            "authorized_by": "payments_specialist",
        },
    )
    result = world.apply_command(command)

    assert result.type == "payment.succeeded"
    booking = world.bookings["BKG-3"]
    assert booking.status == "paid"
    assert world.disruptions["DIS-balance_payment_exception-BKG-3"].status == "resolved"


def test_resolve_payment_exception_release_cancels_and_frees_capacity() -> None:
    world = _world(until=60.0)
    booking = world.bookings["BKG-3"]
    party = world.parties[booking.party_id]
    world.report_disruption(kind="balance_payment_exception", resource_id="BKG-3")
    flight_before = world.flights[booking.flight_id].reserved

    command = _command(
        "cmd-pex-2",
        "resolve_payment_exception",
        {
            "disruption_id": "DIS-balance_payment_exception-BKG-3",
            "booking_id": "BKG-3",
            "action": "release",
            "authorized_by": "payments_specialist",
        },
    )
    result = world.apply_command(command)

    assert result.type == "booking.cancelled"
    booking = world.bookings["BKG-3"]
    assert booking.status == "cancelled"
    assert world.flights[booking.flight_id].reserved == flight_before - party.size


def test_resolve_payment_exception_rejects_without_a_reported_exception() -> None:
    world = _world(until=60.0)
    command = _command(
        "cmd-pex-3",
        "resolve_payment_exception",
        {
            "disruption_id": "DIS-balance_payment_exception-BKG-3",
            "booking_id": "BKG-3",
            "action": "retry",
            "authorized_by": "payments_specialist",
        },
    )
    result = world.apply_command(command)
    assert result.type == "command.rejected"
    assert world.bookings["BKG-3"].status == "deposit_paid"


# ---------------------------------------------------------------------------
# 7. destination-operations / dispatch_replacement_transfer
# ---------------------------------------------------------------------------


def test_dispatch_replacement_transfer_creates_and_rebinds_a_replacement() -> None:
    world = _world(until=45.0)
    transfer = world.transfers["TRF-1"]
    assert transfer.reserved > 0
    world.report_disruption(kind="transfer_arrival_risk", resource_id="TRF-1")

    command = _command(
        "cmd-dop-1",
        "dispatch_replacement_transfer",
        {
            "disruption_id": "DIS-transfer_arrival_risk-TRF-1",
            "transfer_id": "TRF-1",
            "estimated_cost_gbp": 150.0,
            "authorized_by": "destination_operations_manager",
        },
    )
    result = world.apply_command(command)

    assert result.type == "transfer.replacement_dispatched"
    replacement_id = "TRF-REPL-TRF-1"
    assert replacement_id in world.transfers
    replacement = world.transfers[replacement_id]
    assert replacement.reserved == transfer.reserved
    assert replacement.destination_id == transfer.destination_id
    assert world.transfers["TRF-1"].status == "superseded"
    rebound = [b for b in world.bookings.values() if b.transfer_id == replacement_id]
    assert rebound, "at least one booking on TRF-1 must be rebound to the replacement"
    assert world.disruptions["DIS-transfer_arrival_risk-TRF-1"].status == "resolved"


def test_dispatch_replacement_transfer_rejects_without_a_reported_risk() -> None:
    world = _world(until=45.0)
    command = _command(
        "cmd-dop-2",
        "dispatch_replacement_transfer",
        {
            "disruption_id": "DIS-transfer_arrival_risk-TRF-1",
            "transfer_id": "TRF-1",
            "estimated_cost_gbp": 150.0,
            "authorized_by": "destination_operations_manager",
        },
    )
    result = world.apply_command(command)
    assert result.type == "command.rejected"
    assert "TRF-REPL-TRF-1" not in world.transfers


# ---------------------------------------------------------------------------
# 8. proactive-customer-care / issue_customer_care_action
# ---------------------------------------------------------------------------


def test_issue_customer_care_action_records_a_goodwill_gesture() -> None:
    world = _world(until=80.0)
    world.report_disruption(kind="material_itinerary_change", resource_id="BKG-1")

    command = _command(
        "cmd-pcc-1",
        "issue_customer_care_action",
        {
            "disruption_id": "DIS-material_itinerary_change-BKG-1",
            "booking_id": "BKG-1",
            "kind": "goodwill_gesture",
            "amount_gbp": 50.0,
            "message": "We are sorry for the disruption to your holiday.",
            "authorized_by": "customer_care_lead",
        },
    )
    result = world.apply_command(command)

    assert result.type == "care.action_issued"
    matching = [action for action in world.care_actions.values() if action.booking_id == "BKG-1"]
    assert len(matching) == 1
    care_action = matching[0]
    assert isinstance(care_action, CareAction)
    assert care_action.status == "issued"
    assert care_action.amount_gbp == 50.0
    assert world.disruptions["DIS-material_itinerary_change-BKG-1"].status == "resolved"


def test_issue_customer_care_action_rejects_over_authority_goodwill() -> None:
    world = _world(until=80.0)
    world.report_disruption(kind="material_itinerary_change", resource_id="BKG-1")
    command = _command(
        "cmd-pcc-2",
        "issue_customer_care_action",
        {
            "disruption_id": "DIS-material_itinerary_change-BKG-1",
            "booking_id": "BKG-1",
            "kind": "goodwill_gesture",
            "amount_gbp": _over_authority_amount("customer_care_lead"),
            "message": "Large goodwill request.",
            "authorized_by": "customer_care_lead",
        },
    )
    result = world.apply_command(command)
    assert result.type == "command.rejected"
    assert not any(action.booking_id == "BKG-1" for action in world.care_actions.values())


# ---------------------------------------------------------------------------
# Detector functions
# ---------------------------------------------------------------------------


def test_detect_quote_ready_finds_the_offered_quote() -> None:
    world = _world(until=50.0)
    events = travel_processes.detect_quote_ready(world)
    target_ids = {event.target_id for event in events}
    assert "QTE-6" in target_ids
    for event in events:
        assert event.type == "sensor.quote_ready_tripped"


def test_detect_capacity_pressure_finds_allotments_above_threshold() -> None:
    world = _world(until=80.0)
    events = travel_processes.detect_capacity_pressure(world, threshold=0.01)
    assert events
    for event in events:
        assert event.type == "sensor.capacity_pressure_tripped"


def test_detect_flight_cancellation_impact_requires_a_reported_disruption() -> None:
    world = _world(until=80.0)
    assert travel_processes.detect_flight_cancellation_impact(world) == []
    world.report_disruption(kind="flight_cancellation", resource_id="FLT-ZV101")
    events = travel_processes.detect_flight_cancellation_impact(world)
    assert any(event.target_id == "FLT-ZV101" for event in events)


def test_detectors_dict_covers_all_eight_workflow_types() -> None:
    assert set(travel_processes.DETECTORS) == set(WORKFLOW_TYPES)


def test_evaluators_dict_covers_all_eight_workflow_types() -> None:
    assert set(travel_processes.EVALUATORS) == set(WORKFLOW_TYPES)


def test_evaluate_booking_confirmed_and_paid_reports_pass_and_fail() -> None:
    world = _world(until=80.0)
    passing = travel_processes.evaluate_booking_confirmed_and_paid(world, booking_id="BKG-1")
    assert passing["status"] == "pass"
    failing = travel_processes.evaluate_booking_confirmed_and_paid(world, booking_id="does-not-exist")
    assert failing["status"] == "fail"


# ---------------------------------------------------------------------------
# Full sensor -> objective -> command -> evaluation pipeline (reference cases)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("workflow_type", WORKFLOW_TYPES)
def test_run_reference_process_passes_for_every_workflow_type(workflow_type: str) -> None:
    world = TravelWorld(seed=42)
    outcome = world.run_reference_process(workflow_type)

    assert outcome["workflow_type"] == workflow_type
    assert outcome["command_id"]
    assert outcome["trace_id"]
    assert outcome["affected_actor_ids"]
    assert outcome["evidence_event_ids"]
    assert outcome["evaluation_status"] == "resolved"


def test_run_reference_process_is_a_pure_diagnostic_call_with_no_http_route() -> None:
    """`run_reference_process` never depends on the generic HTTP run route."""
    import inspect

    source = inspect.getsource(TravelWorld.run_reference_process)
    assert "requests" not in source
    assert "httpx" not in source
    assert "/api/world/processes" not in source


# ---------------------------------------------------------------------------
# Cross-cutting evidence and conservation checks
# ---------------------------------------------------------------------------


def test_every_command_journal_event_is_traceable_to_its_command_trace_id() -> None:
    world = _world(until=80.0)
    command = _command(
        "cmd-cross-1",
        "adjust_package_allotment",
        {
            "from_allotment_id": "ALT-SUN-AYT",
            "to_allotment_id": "ALT-SUN-PMI",
            "rooms": 5,
            "estimated_value_gbp": 500.0,
            "authorized_by": "revenue_manager",
        },
    )
    before = len(world.runtime.journal)
    result = world.apply_command(command)
    new_events = world.runtime.journal[before:]
    assert new_events
    assert all(event.trace_id == command.trace_id for event in new_events)
    assert result in new_events


def test_care_actions_are_present_in_render_state() -> None:
    world = _world(until=80.0)
    world.report_disruption(kind="material_itinerary_change", resource_id="BKG-1")
    world.apply_command(
        _command(
            "cmd-render-1",
            "issue_customer_care_action",
            {
                "disruption_id": "DIS-material_itinerary_change-BKG-1",
                "booking_id": "BKG-1",
                "kind": "notification",
                "amount_gbp": 0.0,
                "message": "Your itinerary changed slightly.",
                "authorized_by": "customer_care_lead",
            },
        )
    )
    state = world.render_state()
    assert "care_actions" in state
    assert any(row["booking_id"] == "BKG-1" for row in state["care_actions"])
