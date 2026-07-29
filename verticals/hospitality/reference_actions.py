"""Deterministic, executable reference command fixtures for Hospitality.

Each entry in ``HOSPITALITY_REFERENCE_ACTIONS`` maps a workflow type to a
builder function that returns a fully-shaped ``apply_command`` mapping,
derived from real seeded world state (never hard-coded, mismatched IDs).

These are deterministic *test inputs* — they exercise the Task 4 typed
command machinery end to end. They do not prove that any Durable/HITL
workflow ran (that is Task 6 scope) and must not be presented as such.

The hero builder (``build_hotel_recovery_reference_action``) expects a
world that has already had the golden scenario triggered; it derives its
payload from ``plan_recovery(world.snapshot())``. Every supporting builder
takes a freshly seeded world and reads real entity IDs and current versions
directly from ``world.snapshot()`` — never fabricated strings.
"""
from __future__ import annotations

from typing import Any, Callable

from verticals.hospitality.commands import (
    CMD_BOOKING_INVENTORY_PLAN_APPLY,
    CMD_ENERGY_CONTROL_PLAN_APPLY,
    CMD_FOOD_BEVERAGE_SERVICE_PLAN_APPLY,
    CMD_GUEST_RECOVERY_ACTION_ISSUE,
    CMD_HOTEL_RECOVERY_EXECUTE,
    CMD_MAINTENANCE_WORK_ORDER_DISPATCH,
    CMD_ROOM_READINESS_PLAN_APPLY,
    CMD_WORKFORCE_SHIFT_PLAN_APPLY,
)
from verticals.hospitality.reference_cases import HOSPITALITY_REFERENCE_CASES
from verticals.hospitality.recovery import plan_recovery
from verticals.hospitality.world import HospitalityWorld

_COMPATIBLE_ROOM_TYPES: dict[str, tuple[str, ...]] = {
    "accessible": ("accessible",),
    "family": ("family", "premium"),
    "premium": ("premium", "standard"),
    "standard": ("standard", "premium"),
}


# ---------------------------------------------------------------------------
# Hero: hotel-operations-recovery
# ---------------------------------------------------------------------------


def build_hotel_recovery_reference_action(world: HospitalityWorld) -> dict[str, Any]:
    """Build the hero ``hotel.recovery.execute`` command from the golden plan.

    *world* must already have the golden scenario triggered via
    ``world.trigger_scenario("riverside-hot-water-outage")``. The payload is
    derived entirely from ``plan_recovery(world.snapshot())`` — this
    fixture is a deterministic test input, not proof the workflow ran.
    """
    snapshot = world.snapshot()
    result = plan_recovery(snapshot)
    if result.status != "selected" or result.plan is None:
        raise ValueError(
            "Golden scenario did not produce a selected recovery plan — "
            "trigger 'riverside-hot-water-outage' before building this action"
        )
    plan = result.plan

    expected_versions: dict[str, int] = {
        plan.work_order_id: snapshot["work_orders"][plan.work_order_id]["version"],
    }
    for room_id in plan.rooms_to_restore:
        expected_versions[room_id] = snapshot["rooms"][room_id]["version"]

    # Every hotel that owns a restored room will have its available_*
    # counters synchronized (+1 per restored room) — declare it as a target.
    for room_id in plan.rooms_to_restore:
        restore_hotel_id = snapshot["rooms"][room_id]["hotel_id"]
        if restore_hotel_id not in expected_versions:
            expected_versions[restore_hotel_id] = snapshot["hotels"][restore_hotel_id]["version"]

    # Deterministically mirror the handler's own physical-room selection
    # (same shared world.select_available_room/select_occupied_room helpers,
    # same processing order, same running exclude set) so the expected
    # physical room/hotel targets the handler will validate are declared
    # up front — never a silent, undeclared mutation.
    used_rooms: set[str] = set()
    for reloc in plan.relocations:
        expected_versions[reloc.booking_id] = snapshot["bookings"][reloc.booking_id]["version"]
        if reloc.destination_hotel_id not in expected_versions:
            expected_versions[reloc.destination_hotel_id] = snapshot["hotels"][
                reloc.destination_hotel_id
            ]["version"]

        dest_room_id = world.select_available_room(
            reloc.destination_hotel_id, reloc.destination_room_type, exclude=frozenset(used_rooms)
        )
        if dest_room_id is not None:
            used_rooms.add(dest_room_id)
            expected_versions[dest_room_id] = snapshot["rooms"][dest_room_id]["version"]

        booking = snapshot["bookings"][reloc.booking_id]
        source_room_id = world.select_occupied_room(
            booking["hotel_id"], booking["room_type"], exclude=frozenset(used_rooms)
        )
        if source_room_id is not None:
            used_rooms.add(source_room_id)
            expected_versions[source_room_id] = snapshot["rooms"][source_room_id]["version"]
            if booking["hotel_id"] not in expected_versions:
                expected_versions[booking["hotel_id"]] = snapshot["hotels"][booking["hotel_id"]]["version"]

    for move in plan.shift_reallocations:
        expected_versions[move.shift_id] = snapshot["shifts"][move.shift_id]["version"]

    evidence = plan.evidence_versions
    return {
        "command_id": f"CMD-{plan.plan_id}",
        "workflow_id": f"HOPREC-{snapshot['seed']}-{snapshot['tick']:06d}",
        "command_type": CMD_HOTEL_RECOVERY_EXECUTE,
        "expected_versions": expected_versions,
        "evidence_digest": (
            f"EVID-HOPREC-hv{evidence['hotel_version']}"
            f"-av{evidence['asset_version']}-wv{evidence['work_order_version']}"
        ),
        "reason_code": "hotel-operations-recovery-golden-scenario",
        "estimated_value_gbp": plan.estimated_recovery_cost_gbp,
        # The hero command always requires approval (Task 4 authority boundary).
        "approval_ref": "regional_operations_manager_decision:approved:REF-HOPREC-DEMO-0001",
        "payload": {
            "work_order_id": plan.work_order_id,
            "rooms_to_restore": list(plan.rooms_to_restore),
            "relocations": [
                {
                    "booking_id": reloc.booking_id,
                    "destination_hotel_id": reloc.destination_hotel_id,
                    "destination_room_type": reloc.destination_room_type,
                }
                for reloc in plan.relocations
            ],
            "shift_moves": [
                {"shift_id": move.shift_id, "destination_hotel_id": move.to_hotel_id}
                for move in plan.shift_reallocations
            ],
            "guest_communication_actions": list(plan.guest_communication_actions),
        },
    }


# ---------------------------------------------------------------------------
# Supporting: room-readiness-coordination
# ---------------------------------------------------------------------------


def build_room_readiness_plan_reference_action(world: HospitalityWorld) -> dict[str, Any]:
    """Build ``room.readiness-plan.apply`` from a real seeded Airport North room."""
    snapshot = world.snapshot()
    hotel_id = "HOTEL-AIRPORT-NORTH"
    candidates = sorted(
        (
            r for r in snapshot["rooms"].values()
            if r["hotel_id"] == hotel_id and r["status"] == "available"
        ),
        key=lambda r: r["id"],
    )
    if not candidates:
        raise ValueError(f"No available room found at {hotel_id} for reference action")
    room = candidates[0]
    hotel = snapshot["hotels"][hotel_id]
    return {
        "command_id": "CMD-ROOMS-REF-0001",
        "workflow_id": "ROOMS-REF-0001",
        "command_type": CMD_ROOM_READINESS_PLAN_APPLY,
        # target_status "not_ready" from "available" changes the owning
        # hotel's available_* counter, so the hotel is a mutation target too.
        "expected_versions": {room["id"]: room["version"], hotel_id: hotel["version"]},
        "evidence_digest": f"EVID-ROOMS-{room['id']}-v{room['version']}",
        "reason_code": "room-readiness-coordination-reference",
        "estimated_value_gbp": 0.0,
        "approval_ref": None,
        "payload": {
            "room_ids": [room["id"]],
            "target_status": "not_ready",
            "maintenance_work_order_id": None,
        },
    }


# ---------------------------------------------------------------------------
# Supporting: asset-maintenance-response
# ---------------------------------------------------------------------------


def build_maintenance_work_order_dispatch_reference_action(
    world: HospitalityWorld,
) -> dict[str, Any]:
    """Build ``maintenance.work-order.dispatch`` from the real City Gate case."""
    snapshot = world.snapshot()
    case = HOSPITALITY_REFERENCE_CASES["asset-maintenance-response"]
    hotel_id = "HOTEL-CITY-GATE"
    work_order_id = next(sid for sid in case.subject_ids if sid.startswith("WO-"))
    work_order = snapshot["work_orders"].get(work_order_id)
    if work_order is None:
        raise ValueError(f"{work_order_id} not found in seeded world")
    engineers = sorted(
        (
            m for m in snapshot["team_members"].values()
            if m["hotel_id"] == hotel_id and m["skill"] == "engineering"
        ),
        key=lambda m: m["id"],
    )
    if not engineers:
        raise ValueError(f"No engineering team member found at {hotel_id}")
    engineer = engineers[0]
    return {
        "command_id": "CMD-MAINT-REF-0001",
        "workflow_id": "MAINT-REF-0001",
        "command_type": CMD_MAINTENANCE_WORK_ORDER_DISPATCH,
        "expected_versions": {work_order_id: work_order["version"]},
        "evidence_digest": f"EVID-MAINT-{work_order_id}-v{work_order['version']}",
        "reason_code": "asset-maintenance-response-reference",
        "estimated_value_gbp": work_order["cost_estimate_gbp"],
        "approval_ref": None,
        "payload": {
            "work_order_id": work_order_id,
            "assigned_team_member_id": engineer["id"],
            "priority": "high",
        },
    }


# ---------------------------------------------------------------------------
# Supporting: guest-service-recovery
# ---------------------------------------------------------------------------


def build_guest_recovery_action_reference_action(world: HospitalityWorld) -> dict[str, Any]:
    """Build ``guest.recovery-action.issue`` from the real Harbour View case."""
    snapshot = world.snapshot()
    case = HOSPITALITY_REFERENCE_CASES["guest-service-recovery"]
    booking_id = next(sid for sid in case.subject_ids if sid.startswith("BKG-"))
    guest_party_id = next(sid for sid in case.subject_ids if sid.startswith("GP-"))
    booking = snapshot["bookings"].get(booking_id)
    guest_party = snapshot["guest_parties"].get(guest_party_id)
    if booking is None or guest_party is None:
        raise ValueError("Reference booking/guest party not found in seeded world")
    return {
        "command_id": "CMD-GREC-REF-0001",
        "workflow_id": "GREC-REF-0001",
        "command_type": CMD_GUEST_RECOVERY_ACTION_ISSUE,
        "expected_versions": {
            booking_id: booking["version"],
            guest_party_id: guest_party["version"],
        },
        "evidence_digest": f"EVID-GREC-{booking_id}-v{guest_party['version']}",
        "reason_code": "guest-service-recovery-reference",
        "estimated_value_gbp": 120.0,
        "approval_ref": None,
        "payload": {
            "booking_id": booking_id,
            "guest_party_id": guest_party_id,
            "action_code": "room-upgrade",
            "value_gbp": 120.0,
        },
    }


# ---------------------------------------------------------------------------
# Supporting: occupancy-pressure-response
# ---------------------------------------------------------------------------


def build_booking_inventory_plan_reference_action(world: HospitalityWorld) -> dict[str, Any]:
    """Build ``booking.inventory-plan.apply`` as a real cross-property
    relocation from the CASE-OCC hotel (Messe Central) to a declared sister
    property with genuine compatible physical capacity.

    Since this always crosses a property boundary it always requires
    ``commercial_director`` approval (the domain's HITL persona for
    ``occupancy-pressure-response``) — the reference action supplies it.
    """
    snapshot = world.snapshot()
    case = HOSPITALITY_REFERENCE_CASES["occupancy-pressure-response"]
    booking_id = next(sid for sid in case.subject_ids if sid.startswith("BKG-"))
    booking = snapshot["bookings"].get(booking_id)
    if booking is None:
        raise ValueError(f"{booking_id} not found in seeded world")
    source_hotel_id = booking["hotel_id"]
    source_hotel = snapshot["hotels"][source_hotel_id]
    requirement = booking["requirement"]

    destination_hotel_id: str | None = None
    destination_room_type: str | None = None
    for sister_id in source_hotel["sister_hotel_ids"]:
        sister = snapshot["hotels"].get(sister_id)
        if sister is None:
            continue
        for room_type in _COMPATIBLE_ROOM_TYPES[requirement]:
            if sister.get(f"available_{room_type}_rooms", 0) > 0:
                destination_hotel_id = sister_id
                destination_room_type = room_type
                break
        if destination_hotel_id is not None:
            break
    if destination_hotel_id is None or destination_room_type is None:
        raise ValueError(
            f"No declared sister hotel with compatible capacity found for {booking_id}"
        )

    destination_hotel = snapshot["hotels"][destination_hotel_id]
    expected_versions: dict[str, int] = {
        booking_id: booking["version"],
        destination_hotel_id: destination_hotel["version"],
    }

    # Mirror the handler's own deterministic physical-room selection (same
    # shared world.select_available_room/select_occupied_room helpers) so
    # every room/hotel the handler will mutate is declared up front.
    dest_room_id = world.select_available_room(destination_hotel_id, destination_room_type)
    if dest_room_id is not None:
        expected_versions[dest_room_id] = snapshot["rooms"][dest_room_id]["version"]
        source_room_id = world.select_occupied_room(
            source_hotel_id, booking["room_type"], exclude=frozenset({dest_room_id})
        )
    else:
        source_room_id = world.select_occupied_room(source_hotel_id, booking["room_type"])
    if source_room_id is not None:
        expected_versions[source_room_id] = snapshot["rooms"][source_room_id]["version"]
        if source_hotel_id not in expected_versions:
            expected_versions[source_hotel_id] = source_hotel["version"]

    return {
        "command_id": "CMD-OCC-REF-0001",
        "workflow_id": "OCC-REF-0001",
        "command_type": CMD_BOOKING_INVENTORY_PLAN_APPLY,
        "expected_versions": expected_versions,
        "evidence_digest": f"EVID-OCC-{booking_id}-v{destination_hotel['version']}",
        "reason_code": "occupancy-pressure-response-reference",
        "estimated_value_gbp": 0.0,
        # Cross-property relocation always requires approval (Task 4
        # authority boundary) — the commercial_director is the declared
        # HITL persona for occupancy-pressure-response.
        "approval_ref": "commercial_director_decision:approved:REF-OCC-DEMO-0001",
        "payload": {
            "booking_id": booking_id,
            "destination_hotel_id": destination_hotel_id,
            "destination_room_type": destination_room_type,
        },
    }


# ---------------------------------------------------------------------------
# Supporting: workforce-demand-balancing
# ---------------------------------------------------------------------------


def build_workforce_shift_plan_reference_action(world: HospitalityWorld) -> dict[str, Any]:
    """Build ``workforce.shift-plan.apply`` from the real Rhine Park case.

    Reassigns a real seeded housekeeping shift to a known sister hotel — a
    genuine cross-property move, so approval is required per the Task 4
    authority boundary.
    """
    snapshot = world.snapshot()
    case = HOSPITALITY_REFERENCE_CASES["workforce-demand-balancing"]
    shift_id = case.subject_ids[1]  # SHIFT-TEAM-RPAR-HO-03
    shift = snapshot["shifts"].get(shift_id)
    if shift is None:
        raise ValueError(f"{shift_id} not found in seeded world")
    destination_hotel_id = "HOTEL-HARBOUR-VIEW"
    if destination_hotel_id not in snapshot["hotels"]:
        raise ValueError(f"{destination_hotel_id} not found in seeded world")
    return {
        "command_id": "CMD-WRKFRC-REF-0001",
        "workflow_id": "WRKFRC-REF-0001",
        "command_type": CMD_WORKFORCE_SHIFT_PLAN_APPLY,
        "expected_versions": {shift_id: shift["version"]},
        "evidence_digest": f"EVID-WRKFRC-{shift_id}-v{shift['version']}",
        "reason_code": "workforce-demand-balancing-reference",
        "estimated_value_gbp": 0.0,
        "approval_ref": "workforce_planning_manager_decision:approved:REF-WRKFRC-DEMO-0001",
        "payload": {
            "shift_id": shift_id,
            "destination_hotel_id": destination_hotel_id,
        },
    }


# ---------------------------------------------------------------------------
# Supporting: food-and-beverage-readiness
# ---------------------------------------------------------------------------


def build_food_beverage_service_plan_reference_action(
    world: HospitalityWorld,
) -> dict[str, Any]:
    """Build ``food-beverage.service-plan.apply`` from the real Airport North plan."""
    snapshot = world.snapshot()
    case = HOSPITALITY_REFERENCE_CASES["food-and-beverage-readiness"]
    plan_id = next(sid for sid in case.subject_ids if sid.startswith("FSP-"))
    plan = snapshot["food_service_plans"].get(plan_id)
    if plan is None:
        raise ValueError(f"{plan_id} not found in seeded world")
    return {
        "command_id": "CMD-FNBRD-REF-0001",
        "workflow_id": "FNBRD-REF-0001",
        "command_type": CMD_FOOD_BEVERAGE_SERVICE_PLAN_APPLY,
        "expected_versions": {plan_id: plan["version"]},
        "evidence_digest": f"EVID-FNBRD-{plan_id}-v{plan['version']}",
        "reason_code": "food-and-beverage-readiness-reference",
        "estimated_value_gbp": 0.0,
        "approval_ref": None,
        "payload": {
            "plan_id": plan_id,
            "covers_prepared": plan["covers_forecast"],
        },
    }


# ---------------------------------------------------------------------------
# Supporting: energy-anomaly-response
# ---------------------------------------------------------------------------


def build_energy_control_plan_reference_action(world: HospitalityWorld) -> dict[str, Any]:
    """Build ``energy.control-plan.apply`` from the real City Gate meter."""
    snapshot = world.snapshot()
    case = HOSPITALITY_REFERENCE_CASES["energy-anomaly-response"]
    meter_id = next(sid for sid in case.subject_ids if sid.startswith("EM-"))
    meter = snapshot["energy_meters"].get(meter_id)
    if meter is None:
        raise ValueError(f"{meter_id} not found in seeded world")
    return {
        "command_id": "CMD-ENERGY-REF-0001",
        "workflow_id": "ENERGY-REF-0001",
        "command_type": CMD_ENERGY_CONTROL_PLAN_APPLY,
        "expected_versions": {meter_id: meter["version"]},
        "evidence_digest": f"EVID-ENERGY-{meter_id}-v{meter['version']}",
        "reason_code": "energy-anomaly-response-reference",
        "estimated_value_gbp": 0.0,
        "approval_ref": None,
        "payload": {
            "meter_id": meter_id,
            "control_action": "reset-normal",
            "target_reading_kwh": meter["baseline_kwh"],
        },
    }


# ---------------------------------------------------------------------------
# Registry — exactly the eight workflow IDs
# ---------------------------------------------------------------------------

HOSPITALITY_REFERENCE_ACTIONS: dict[str, Callable[[HospitalityWorld], dict[str, Any]]] = {
    "hotel-operations-recovery": build_hotel_recovery_reference_action,
    "room-readiness-coordination": build_room_readiness_plan_reference_action,
    "asset-maintenance-response": build_maintenance_work_order_dispatch_reference_action,
    "guest-service-recovery": build_guest_recovery_action_reference_action,
    "occupancy-pressure-response": build_booking_inventory_plan_reference_action,
    "workforce-demand-balancing": build_workforce_shift_plan_reference_action,
    "food-and-beverage-readiness": build_food_beverage_service_plan_reference_action,
    "energy-anomaly-response": build_energy_control_plan_reference_action,
}
assert set(HOSPITALITY_REFERENCE_ACTIONS) == set(HOSPITALITY_REFERENCE_CASES)
assert len(HOSPITALITY_REFERENCE_ACTIONS) == 8
