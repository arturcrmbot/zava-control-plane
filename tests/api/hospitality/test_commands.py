"""Task 4: Typed Hospitality commands and atomic world mutations.

Covers the eight typed command envelopes/payload validators, the eight
reference-action fixtures, atomic mutation + optimistic-concurrency +
idempotency + authority-boundary behavior of ``HospitalityWorld.apply_command``.
"""
from __future__ import annotations

import copy
import dataclasses as dc
import math

import pytest

from verticals.hospitality.commands import (
    CMD_BOOKING_INVENTORY_PLAN_APPLY,
    CMD_ENERGY_CONTROL_PLAN_APPLY,
    CMD_FOOD_BEVERAGE_SERVICE_PLAN_APPLY,
    CMD_GUEST_RECOVERY_ACTION_ISSUE,
    CMD_HOTEL_RECOVERY_EXECUTE,
    CMD_MAINTENANCE_WORK_ORDER_DISPATCH,
    CMD_ROOM_READINESS_PLAN_APPLY,
    CMD_WORKFORCE_SHIFT_PLAN_APPLY,
    COMMAND_PAYLOAD_PARSERS,
    COMMAND_PAYLOAD_TYPES,
    COMMAND_TYPES,
    ENVELOPE_KEYS,
    BookingInventoryPlanPayload,
    CommandEnvelope,
    EnergyControlPlanPayload,
    FoodBeverageServicePlanPayload,
    GuestRecoveryActionPayload,
    HotelRecoveryPayload,
    MaintenanceWorkOrderDispatchPayload,
    RejectedCommand,
    RoomReadinessPlanPayload,
    WorkforceShiftPlanPayload,
    parse_command,
)
from verticals.hospitality.reference_actions import HOSPITALITY_REFERENCE_ACTIONS
from verticals.hospitality.reference_cases import HOSPITALITY_REFERENCE_CASES
from verticals.hospitality.world import HospitalityWorld

DEMO_SEED = 20260728
HERO_HOTEL = "HOTEL-RIVERSIDE-CENTRAL"

# The production command_type -> payload dataclass mapping is the single
# source of truth (see ``test_command_payload_types_and_parsers_are_all_distinct``
# below) — used here too so tests never drift from what the runtime enforces.
_PAYLOAD_TYPE_BY_COMMAND_TYPE = COMMAND_PAYLOAD_TYPES


# ---------------------------------------------------------------------------
# Fixture helpers (no conftest — plain module-level builders)
# ---------------------------------------------------------------------------


def _hero_world() -> HospitalityWorld:
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    world.trigger_scenario("riverside-hot-water-outage")
    world.poll_sensor_events()
    return world


def _hero_command(world: HospitalityWorld) -> dict:
    return HOSPITALITY_REFERENCE_ACTIONS["hotel-operations-recovery"](world)


def _approved_hero_command(world: HospitalityWorld) -> dict:
    cmd = _hero_command(world)
    assert cmd["approval_ref"]
    return cmd


# ---------------------------------------------------------------------------
# 1. Exactly eight command types, validators, and reference actions
# ---------------------------------------------------------------------------


def test_exactly_eight_command_types():
    assert len(COMMAND_TYPES) == 8
    assert len(set(COMMAND_TYPES)) == 8


def test_exactly_eight_reference_actions_matching_workflows():
    assert set(HOSPITALITY_REFERENCE_ACTIONS) == set(HOSPITALITY_REFERENCE_CASES)
    assert len(HOSPITALITY_REFERENCE_ACTIONS) == 8


@pytest.mark.parametrize("command_type", COMMAND_TYPES)
def test_each_command_type_has_a_distinct_payload_validator(command_type):
    assert command_type in _PAYLOAD_TYPE_BY_COMMAND_TYPE


def test_command_payload_types_and_parsers_are_all_distinct():
    """Read the *production* command_type -> payload/parser mappings and
    assert all eight values are genuinely distinct — a real check against
    the runtime's own registries, not a test-local duplicate."""
    assert set(COMMAND_PAYLOAD_TYPES) == set(COMMAND_TYPES)
    assert len(COMMAND_PAYLOAD_TYPES) == 8
    assert len(set(COMMAND_PAYLOAD_TYPES.values())) == 8

    assert set(COMMAND_PAYLOAD_PARSERS) == set(COMMAND_TYPES)
    assert len(COMMAND_PAYLOAD_PARSERS) == 8
    assert len(set(COMMAND_PAYLOAD_PARSERS.values())) == 8


# ---------------------------------------------------------------------------
# 2. Each reference action parses and executes against a fresh world
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("workflow_type", sorted(HOSPITALITY_REFERENCE_ACTIONS))
def test_reference_action_parses_and_executes(workflow_type):
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    if workflow_type == "hotel-operations-recovery":
        world.trigger_scenario("riverside-hot-water-outage")
        world.poll_sensor_events()

    builder = HOSPITALITY_REFERENCE_ACTIONS[workflow_type]
    raw_command = builder(world)

    parsed = parse_command(raw_command)
    assert isinstance(parsed, CommandEnvelope), (
        f"{workflow_type} reference action failed to parse: {parsed}"
    )
    assert isinstance(parsed.payload, _PAYLOAD_TYPE_BY_COMMAND_TYPE[parsed.command_type])

    result = world.apply_command(raw_command)
    assert result.accepted is True, f"{workflow_type}: {result.reason} {result.details}"
    assert result.idempotent_replay is False


def test_hero_reference_action_always_carries_approval_ref():
    world = _hero_world()
    cmd = _hero_command(world)
    assert cmd["approval_ref"]
    assert isinstance(cmd["approval_ref"], str)
    assert cmd["approval_ref"].strip() != ""


# ---------------------------------------------------------------------------
# 3. Malformed payload rejections preserve the world snapshot
# ---------------------------------------------------------------------------


def _minimal_valid_hero_command(world: HospitalityWorld) -> dict:
    return _hero_command(world)


def test_missing_command_id_is_rejected():
    world = _hero_world()
    cmd = _minimal_valid_hero_command(world)
    del cmd["command_id"]
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before
    assert len(result.events) == 1
    assert result.events[0].payload["reason"] == "invalid_command_payload"


def test_bool_as_number_for_estimated_value_is_rejected():
    world = _hero_world()
    cmd = _minimal_valid_hero_command(world)
    cmd["estimated_value_gbp"] = True
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


def test_non_finite_estimated_value_is_rejected():
    world = _hero_world()
    cmd = _minimal_valid_hero_command(world)
    cmd["estimated_value_gbp"] = math.inf
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


def test_negative_estimated_value_is_rejected():
    world = _hero_world()
    cmd = _minimal_valid_hero_command(world)
    cmd["estimated_value_gbp"] = -1.0
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


def test_bool_as_version_in_expected_versions_is_rejected():
    world = _hero_world()
    cmd = _minimal_valid_hero_command(world)
    some_key = next(iter(cmd["expected_versions"]))
    cmd["expected_versions"][some_key] = True
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


def test_negative_version_in_expected_versions_is_rejected():
    world = _hero_world()
    cmd = _minimal_valid_hero_command(world)
    some_key = next(iter(cmd["expected_versions"]))
    cmd["expected_versions"][some_key] = -1
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


def test_empty_expected_versions_is_rejected():
    world = _hero_world()
    cmd = _minimal_valid_hero_command(world)
    cmd["expected_versions"] = {}
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


def test_empty_command_id_string_is_rejected():
    world = _hero_world()
    cmd = _minimal_valid_hero_command(world)
    cmd["command_id"] = "   "
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


def test_unknown_command_type_is_rejected():
    world = _hero_world()
    cmd = _minimal_valid_hero_command(world)
    cmd["command_type"] = "hotel.teleport.execute"
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "unknown_command_type"
    assert world.snapshot() == before
    assert len(result.events) == 1


def test_missing_payload_field_is_rejected():
    world = _hero_world()
    cmd = _minimal_valid_hero_command(world)
    del cmd["payload"]["work_order_id"]
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


def test_command_that_is_not_a_mapping_is_rejected():
    world = _hero_world()
    before = world.snapshot()
    result = world.apply_command("not-a-command")  # type: ignore[arg-type]
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


# ---------------------------------------------------------------------------
# 4. Stale version / missing version / unknown entity preserve the snapshot
# ---------------------------------------------------------------------------


def test_recovery_rejects_stale_room_version():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    some_room_id = next(iter(cmd["payload"]["rooms_to_restore"]))
    cmd["expected_versions"][some_room_id] -= 1
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "stale_entity_version"
    assert world.snapshot() == before


def test_recovery_rejects_missing_expected_version():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    some_room_id = cmd["payload"]["rooms_to_restore"][0]
    del cmd["expected_versions"][some_room_id]
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "missing_expected_version"
    assert world.snapshot() == before


def test_recovery_rejects_unknown_entity():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    cmd["payload"]["rooms_to_restore"] = list(cmd["payload"]["rooms_to_restore"]) + [
        "ROOM-DOES-NOT-EXIST"
    ]
    cmd["expected_versions"]["ROOM-DOES-NOT-EXIST"] = 1
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "unknown_entity"
    assert world.snapshot() == before


# ---------------------------------------------------------------------------
# 5. Idempotency: exact replay vs. conflicting duplicate ID
# ---------------------------------------------------------------------------


def test_hotel_recovery_command_is_idempotent():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    first = world.apply_command(cmd)
    second = world.apply_command(cmd)
    assert first.accepted is True
    assert second.accepted is True
    assert second.idempotent_replay is True
    assert first.idempotent_replay is False
    assert world.snapshot() == first.snapshot
    assert world.snapshot() == second.snapshot


def test_idempotent_replay_with_list_instead_of_tuple_semantics_still_matches():
    """A JSON-shaped replay (lists, not tuples) is semantically equivalent."""
    world = _hero_world()
    cmd = _approved_hero_command(world)
    first = world.apply_command(cmd)
    replay = copy.deepcopy(cmd)  # still JSON-shaped (lists), same content
    second = world.apply_command(replay)
    assert first.accepted is True
    assert second.idempotent_replay is True


def test_same_command_id_different_payload_is_conflict():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    first = world.apply_command(cmd)
    assert first.accepted is True

    conflicting = copy.deepcopy(cmd)
    conflicting["estimated_value_gbp"] = cmd["estimated_value_gbp"] + 1.0
    before = world.snapshot()
    second = world.apply_command(conflicting)
    assert second.accepted is False
    assert second.reason == "command_id_conflict"
    assert world.snapshot() == before
    assert len(second.events) == 1


def test_no_duplicate_events_on_replay():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    events_before = len(world._events)
    first = world.apply_command(cmd)
    events_after_first = len(world._events)
    second = world.apply_command(cmd)
    events_after_second = len(world._events)
    assert events_after_first > events_before
    assert events_after_second == events_after_first
    assert second.events == first.events


# ---------------------------------------------------------------------------
# 6. Hero: exact mutation counts, version increments, compatibility,
#    2 shift moves, work-order expedite, approval required.
# ---------------------------------------------------------------------------


def test_hero_missing_approval_ref_is_rejected():
    world = _hero_world()
    cmd = _hero_command(world)
    cmd["approval_ref"] = None
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "approval_required"
    assert world.snapshot() == before


def test_hero_expedites_work_order():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    wo_id = cmd["payload"]["work_order_id"]
    before_version = world.work_orders[wo_id].version
    result = world.apply_command(cmd)
    assert result.accepted is True
    wo = world.work_orders[wo_id]
    assert wo.status == "in_progress"
    assert wo.priority == "critical"
    assert wo.version == before_version + 1


def test_hero_restores_exactly_eight_rooms():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    room_ids = cmd["payload"]["rooms_to_restore"]
    assert len(room_ids) == 8
    before_versions = {rid: world.rooms[rid].version for rid in room_ids}
    result = world.apply_command(cmd)
    assert result.accepted is True
    for rid in room_ids:
        room = world.rooms[rid]
        assert room.status == "available"
        assert room.version == before_versions[rid] + 1


def test_hero_relocates_exactly_ten_bookings_compatibly():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    relocations = cmd["payload"]["relocations"]
    assert len(relocations) == 10
    before_versions = {
        r["booking_id"]: world.bookings[r["booking_id"]].version for r in relocations
    }
    result = world.apply_command(cmd)
    assert result.accepted is True
    for reloc in relocations:
        booking = world.bookings[reloc["booking_id"]]
        assert booking.status == "relocated"
        assert booking.hotel_id == reloc["destination_hotel_id"]
        assert booking.room_type == reloc["destination_room_type"]
        assert booking.version == before_versions[reloc["booking_id"]] + 1
        assert booking.hotel_id != HERO_HOTEL


def test_hero_preserves_protected_requirements_on_relocation():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    relocations = cmd["payload"]["relocations"]
    protected_before = {
        r["booking_id"]: world.bookings[r["booking_id"]].protected for r in relocations
    }
    result = world.apply_command(cmd)
    assert result.accepted is True
    for reloc in relocations:
        booking_id = reloc["booking_id"]
        if protected_before[booking_id]:
            booking = world.bookings[booking_id]
            # Protected accessible/family requirement is never changed by relocation.
            assert booking.protected is True
            if booking.requirement == "accessible":
                assert booking.room_type == "accessible"
            elif booking.requirement == "family":
                assert booking.room_type in ("family", "premium")


def test_hero_reassigns_exactly_two_shifts_to_engineering_only():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    shift_moves = cmd["payload"]["shift_moves"]
    assert len(shift_moves) == 2
    before_versions = {
        m["shift_id"]: world.shifts[m["shift_id"]].version for m in shift_moves
    }
    result = world.apply_command(cmd)
    assert result.accepted is True
    for move in shift_moves:
        shift = world.shifts[move["shift_id"]]
        assert shift.skill == "engineering"
        assert shift.hotel_id == move["destination_hotel_id"]
        assert shift.status == "reallocated"
        assert shift.version == before_versions[move["shift_id"]] + 1


def test_hero_rejects_unavailable_destination_room_type():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    booking_id = cmd["payload"]["relocations"][0]["booking_id"]
    booking = world.bookings[booking_id]
    for reloc in cmd["payload"]["relocations"]:
        if reloc["booking_id"] == booking_id:
            reloc["destination_room_type"] = (
                "accessible" if booking.requirement != "accessible" else "standard"
            )
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason in ("incompatible_room", "insufficient_capacity")
    assert world.snapshot() == before


def test_hero_rejects_insufficient_sister_capacity():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    hotel_id = cmd["payload"]["relocations"][0]["destination_hotel_id"]
    room_type = cmd["payload"]["relocations"][0]["destination_room_type"]
    hotel = world.hotels[hotel_id]
    import dataclasses as dc
    world.hotels[hotel_id] = dc.replace(hotel, **{f"available_{room_type}_rooms": 0})
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "insufficient_capacity"
    assert world.snapshot() == before


def test_hero_rejects_invalid_destination_hotel():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    cmd["payload"]["relocations"][0]["destination_hotel_id"] = "HOTEL-DOES-NOT-EXIST"
    cmd["expected_versions"]["HOTEL-DOES-NOT-EXIST"] = 1
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "unknown_entity"
    assert world.snapshot() == before


def test_hero_rejects_closed_work_order():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    wo_id = cmd["payload"]["work_order_id"]
    import dataclasses as dc
    wo = world.work_orders[wo_id]
    world.work_orders[wo_id] = dc.replace(wo, status="completed")
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "closed_work_order"
    assert world.snapshot() == before


def test_hero_rejects_duplicate_mutation_attempt_via_conflict():
    """Attempting the same command_id twice with a materially different
    payload (e.g. an extra relocation) is a conflict, not a second mutation."""
    world = _hero_world()
    cmd = _approved_hero_command(world)
    first = world.apply_command(cmd)
    assert first.accepted is True

    mutated = copy.deepcopy(cmd)
    mutated["payload"]["guest_communication_actions"] = list(
        mutated["payload"]["guest_communication_actions"]
    ) + ["extra-action"]
    before = world.snapshot()
    result = world.apply_command(mutated)
    assert result.accepted is False
    assert result.reason == "command_id_conflict"
    assert world.snapshot() == before


# ---------------------------------------------------------------------------
# 7. Hero atomic rollback when the last proposed target is stale/invalid
# ---------------------------------------------------------------------------


def test_hero_atomic_rollback_when_last_shift_target_is_stale():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    last_shift_id = cmd["payload"]["shift_moves"][-1]["shift_id"]
    cmd["expected_versions"][last_shift_id] += 1  # now stale (too high)
    before = world.snapshot()

    result = world.apply_command(cmd)

    assert result.accepted is False
    assert result.reason == "stale_entity_version"
    # Nothing mutated: not the work order, not any room, not any booking.
    assert world.snapshot() == before
    wo_id = cmd["payload"]["work_order_id"]
    assert world.work_orders[wo_id].status != "in_progress"
    for room_id in cmd["payload"]["rooms_to_restore"]:
        assert world.rooms[room_id].status != "available"
    for reloc in cmd["payload"]["relocations"]:
        assert world.bookings[reloc["booking_id"]].status != "relocated"


def test_hero_atomic_rollback_when_last_shift_target_is_invalid():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    cmd["payload"]["shift_moves"][-1]["shift_id"] = "SHIFT-DOES-NOT-EXIST"
    cmd["expected_versions"]["SHIFT-DOES-NOT-EXIST"] = 1
    before = world.snapshot()

    result = world.apply_command(cmd)

    assert result.accepted is False
    assert result.reason == "unknown_entity"
    assert world.snapshot() == before


# ---------------------------------------------------------------------------
# 8. Every supporting command: successful mutation + a workflow-specific
#    rejection.
# ---------------------------------------------------------------------------


def test_room_readiness_plan_apply_success():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["room-readiness-coordination"](world)
    room_id = cmd["payload"]["room_ids"][0]
    before_version = world.rooms[room_id].version
    result = world.apply_command(cmd)
    assert result.accepted is True
    room = world.rooms[room_id]
    assert room.status == "not_ready"
    assert room.version == before_version + 1


def test_room_readiness_plan_rejects_unavailable_room_without_maintenance_evidence():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    room_id = next(iter(world.rooms))
    import dataclasses as dc
    room = world.rooms[room_id]
    world.rooms[room_id] = dc.replace(room, status="unavailable")
    cmd = {
        "command_id": "CMD-ROOMS-TEST-0001",
        "workflow_id": "ROOMS-TEST-0001",
        "command_type": CMD_ROOM_READINESS_PLAN_APPLY,
        "expected_versions": {room_id: world.rooms[room_id].version},
        "evidence_digest": "EVID-ROOMS-TEST",
        "reason_code": "test-maintenance-evidence-missing",
        "estimated_value_gbp": 0.0,
        "approval_ref": None,
        "payload": {
            "room_ids": [room_id],
            "target_status": "available",
            "maintenance_work_order_id": None,
        },
    }
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "maintenance_evidence_missing"
    assert world.snapshot() == before


def test_maintenance_work_order_dispatch_success():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["asset-maintenance-response"](world)
    wo_id = cmd["payload"]["work_order_id"]
    before_version = world.work_orders[wo_id].version
    result = world.apply_command(cmd)
    assert result.accepted is True
    wo = world.work_orders[wo_id]
    assert wo.status == "in_progress"
    assert wo.assigned_team_member_id == cmd["payload"]["assigned_team_member_id"]
    assert wo.version == before_version + 1


def test_maintenance_work_order_dispatch_rejects_completed_order():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["asset-maintenance-response"](world)
    wo_id = cmd["payload"]["work_order_id"]
    import dataclasses as dc
    wo = world.work_orders[wo_id]
    world.work_orders[wo_id] = dc.replace(wo, status="completed")
    cmd["expected_versions"][wo_id] = world.work_orders[wo_id].version
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "closed_work_order"
    assert world.snapshot() == before


def test_guest_recovery_action_issue_success_does_not_relocate_booking():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["guest-service-recovery"](world)
    booking_id = cmd["payload"]["booking_id"]
    guest_party_id = cmd["payload"]["guest_party_id"]
    before_booking = world.bookings[booking_id]
    before_gp_version = world.guest_parties[guest_party_id].version
    result = world.apply_command(cmd)
    assert result.accepted is True
    after_booking = world.bookings[booking_id]
    assert after_booking == before_booking  # never cancelled or relocated
    assert world.guest_parties[guest_party_id].version == before_gp_version + 1


def test_guest_recovery_action_rejects_guest_party_mismatch():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["guest-service-recovery"](world)
    original_guest_party_id = cmd["payload"]["guest_party_id"]
    other_guest_party_id = next(
        gp_id for gp_id in world.guest_parties if gp_id != original_guest_party_id
    )
    cmd["payload"]["guest_party_id"] = other_guest_party_id
    del cmd["expected_versions"][original_guest_party_id]
    cmd["expected_versions"][other_guest_party_id] = world.guest_parties[
        other_guest_party_id
    ].version
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "guest_party_mismatch"
    assert world.snapshot() == before


def test_booking_inventory_plan_apply_success():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["occupancy-pressure-response"](world)
    booking_id = cmd["payload"]["booking_id"]
    before_version = world.bookings[booking_id].version
    result = world.apply_command(cmd)
    assert result.accepted is True
    booking = world.bookings[booking_id]
    assert booking.room_type == cmd["payload"]["destination_room_type"]
    assert booking.version == before_version + 1


def test_booking_inventory_plan_rejects_incompatible_room():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["occupancy-pressure-response"](world)
    booking = world.bookings[cmd["payload"]["booking_id"]]
    # Force an incompatible destination type for a non-accessible booking.
    cmd["payload"]["destination_room_type"] = (
        "accessible" if booking.requirement != "accessible" else "family"
    )
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "incompatible_room"
    assert world.snapshot() == before


def test_booking_inventory_plan_cross_property_requires_approval():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["occupancy-pressure-response"](world)
    booking = world.bookings[cmd["payload"]["booking_id"]]
    sister_hotel_id = next(
        hid for hid in world.hotels[booking.hotel_id].sister_hotel_ids
    )
    sister_hotel = world.hotels[sister_hotel_id]
    room_type = cmd["payload"]["destination_room_type"]
    if getattr(sister_hotel, f"available_{room_type}_rooms", 0) <= 0:
        pytest.skip("Sister hotel has no compatible capacity in this seed")
    cmd["payload"]["destination_hotel_id"] = sister_hotel_id
    cmd["expected_versions"][sister_hotel_id] = sister_hotel.version
    cmd["approval_ref"] = None
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "approval_required"
    assert world.snapshot() == before


def test_workforce_shift_plan_apply_success():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["workforce-demand-balancing"](world)
    shift_id = cmd["payload"]["shift_id"]
    before_version = world.shifts[shift_id].version
    result = world.apply_command(cmd)
    assert result.accepted is True
    shift = world.shifts[shift_id]
    assert shift.hotel_id == cmd["payload"]["destination_hotel_id"]
    assert shift.status == "reallocated"
    assert shift.version == before_version + 1


def test_workforce_shift_plan_rejects_skill_mismatch():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["workforce-demand-balancing"](world)
    shift_id = cmd["payload"]["shift_id"]
    import dataclasses as dc
    shift = world.shifts[shift_id]
    team_member = world.team_members[shift.team_member_id]
    world.team_members[shift.team_member_id] = dc.replace(team_member, skill="front-office")
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "skill_mismatch"
    assert world.snapshot() == before


def test_food_beverage_service_plan_apply_success():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["food-and-beverage-readiness"](world)
    plan_id = cmd["payload"]["plan_id"]
    before_version = world.food_service_plans[plan_id].version
    result = world.apply_command(cmd)
    assert result.accepted is True
    plan = world.food_service_plans[plan_id]
    assert plan.covers_prepared == cmd["payload"]["covers_prepared"]
    assert plan.status == "ready"
    assert plan.version == before_version + 1


def test_food_beverage_service_plan_rejects_bound_violation():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["food-and-beverage-readiness"](world)
    plan = world.food_service_plans[cmd["payload"]["plan_id"]]
    cmd["payload"]["covers_prepared"] = int(plan.covers_forecast * 2)
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_bounds"
    assert world.snapshot() == before


def test_energy_control_plan_apply_success():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["energy-anomaly-response"](world)
    meter_id = cmd["payload"]["meter_id"]
    before_version = world.energy_meters[meter_id].version
    result = world.apply_command(cmd)
    assert result.accepted is True
    meter = world.energy_meters[meter_id]
    assert meter.reading_kwh == cmd["payload"]["target_reading_kwh"]
    assert meter.status == "normal"
    assert meter.version == before_version + 1


def test_energy_control_plan_rejects_comfort_safety_violation():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["energy-anomaly-response"](world)
    meter = world.energy_meters[cmd["payload"]["meter_id"]]
    cmd["payload"]["target_reading_kwh"] = meter.baseline_kwh * 3.0
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "comfort_safety_violation"
    assert world.snapshot() == before


# ---------------------------------------------------------------------------
# 9. Event identity includes workflow_id/command_id; no duplicates on replay
# ---------------------------------------------------------------------------


def test_accepted_events_carry_workflow_id_and_command_id():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    result = world.apply_command(cmd)
    assert result.accepted is True
    assert len(result.events) > 0
    for event in result.events:
        assert event.payload["command_id"] == cmd["command_id"]
        assert event.payload["workflow_id"] == cmd["workflow_id"]


def test_rejection_event_carries_workflow_id_and_command_id():
    world = _hero_world()
    cmd = _hero_command(world)
    cmd["approval_ref"] = None
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert len(result.events) == 1
    rejection_event = result.events[0]
    assert rejection_event.payload["command_id"] == cmd["command_id"]
    assert rejection_event.payload["workflow_id"] == cmd["workflow_id"]


def test_event_ids_are_unique_across_a_command_application():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    result = world.apply_command(cmd)
    event_ids = [event.event_id for event in result.events]
    assert len(event_ids) == len(set(event_ids))


# ---------------------------------------------------------------------------
# 10. No handler accepts another command's payload shape
# ---------------------------------------------------------------------------


def test_room_readiness_payload_rejected_by_maintenance_dispatch_parser():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    room_cmd = HOSPITALITY_REFERENCE_ACTIONS["room-readiness-coordination"](world)
    mismatched = copy.deepcopy(room_cmd)
    mismatched["command_type"] = CMD_MAINTENANCE_WORK_ORDER_DISPATCH
    mismatched["command_id"] = "CMD-CROSS-SHAPE-0001"
    parsed = parse_command(mismatched)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_hero_payload_rejected_by_room_readiness_parser():
    world = _hero_world()
    hero_cmd = _approved_hero_command(world)
    mismatched = copy.deepcopy(hero_cmd)
    mismatched["command_type"] = CMD_ROOM_READINESS_PLAN_APPLY
    mismatched["command_id"] = "CMD-CROSS-SHAPE-0002"
    parsed = parse_command(mismatched)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_energy_payload_rejected_by_food_beverage_parser():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    energy_cmd = HOSPITALITY_REFERENCE_ACTIONS["energy-anomaly-response"](world)
    mismatched = copy.deepcopy(energy_cmd)
    mismatched["command_type"] = CMD_FOOD_BEVERAGE_SERVICE_PLAN_APPLY
    mismatched["command_id"] = "CMD-CROSS-SHAPE-0003"
    parsed = parse_command(mismatched)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


# ---------------------------------------------------------------------------
# 11. apply_command never mutates its input mapping
# ---------------------------------------------------------------------------


def test_apply_command_does_not_mutate_input_mapping():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    snapshot_before_call = copy.deepcopy(cmd)
    world.apply_command(cmd)
    assert cmd == snapshot_before_call


def test_apply_command_does_not_mutate_input_mapping_on_rejection():
    world = _hero_world()
    cmd = _hero_command(world)
    cmd["approval_ref"] = None
    snapshot_before_call = copy.deepcopy(cmd)
    world.apply_command(cmd)
    assert cmd == snapshot_before_call


def test_apply_command_does_not_mutate_input_mapping_on_malformed_payload():
    world = _hero_world()
    cmd = _hero_command(world)
    del cmd["payload"]["work_order_id"]
    snapshot_before_call = copy.deepcopy(cmd)
    world.apply_command(cmd)
    assert cmd == snapshot_before_call


# ---------------------------------------------------------------------------
# Extra: parse_command direct unit coverage per command type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("workflow_type", sorted(HOSPITALITY_REFERENCE_ACTIONS))
def test_parse_command_accepts_each_reference_action(workflow_type):
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    if workflow_type == "hotel-operations-recovery":
        world.trigger_scenario("riverside-hot-water-outage")
        world.poll_sensor_events()
    cmd = HOSPITALITY_REFERENCE_ACTIONS[workflow_type](world)
    parsed = parse_command(cmd)
    assert isinstance(parsed, CommandEnvelope)


def test_parse_command_rejects_non_mapping():
    parsed = parse_command(42)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_parse_command_already_typed_envelope_passthrough():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    parsed = parse_command(cmd)
    assert isinstance(parsed, CommandEnvelope)
    reparsed = parse_command(parsed)
    assert reparsed is parsed


# ---------------------------------------------------------------------------
# 12. Typed CommandEnvelope validation: parse_command validates a hand-built
#     CommandEnvelope exactly like a mapping — never a bare passthrough.
# ---------------------------------------------------------------------------


def _valid_room_readiness_envelope_kwargs(world: HospitalityWorld) -> dict:
    room = next(
        r for r in world.rooms.values()
        if r.hotel_id == "HOTEL-AIRPORT-NORTH" and r.status == "available"
    )
    return {
        "command_id": "CMD-TYPED-DIRECT-0001",
        "workflow_id": "TYPED-DIRECT-0001",
        "command_type": CMD_ROOM_READINESS_PLAN_APPLY,
        # target_status "not_ready" from "available" changes the owning
        # hotel's available_* counter, so it's a mutation target too.
        "expected_versions": {
            room.id: room.version,
            room.hotel_id: world.hotels[room.hotel_id].version,
        },
        "evidence_digest": "EVID-TYPED-DIRECT",
        "reason_code": "typed-envelope-direct-construction",
        "estimated_value_gbp": 0.0,
        "payload": RoomReadinessPlanPayload(
            room_ids=(room.id,),
            target_status="not_ready",
            maintenance_work_order_id=None,
        ),
        "approval_ref": None,
    }


def test_typed_envelope_constructed_directly_is_accepted_by_apply_command():
    """A hand-built, well-formed CommandEnvelope (never parsed from a raw
    mapping) is accepted end-to-end by apply_command."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    envelope = CommandEnvelope(**_valid_room_readiness_envelope_kwargs(world))
    result = world.apply_command(envelope)
    assert result.accepted is True, result.reason


def test_typed_envelope_with_empty_command_id_is_rejected():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    kwargs = _valid_room_readiness_envelope_kwargs(world)
    kwargs["command_id"] = "   "
    envelope = CommandEnvelope(**kwargs)
    parsed = parse_command(envelope)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_typed_envelope_with_empty_workflow_id_is_rejected():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    kwargs = _valid_room_readiness_envelope_kwargs(world)
    kwargs["workflow_id"] = ""
    envelope = CommandEnvelope(**kwargs)
    parsed = parse_command(envelope)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_typed_envelope_with_unknown_command_type_is_rejected():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    kwargs = _valid_room_readiness_envelope_kwargs(world)
    kwargs["command_type"] = "hotel.teleport.execute"
    envelope = CommandEnvelope(**kwargs)
    parsed = parse_command(envelope)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "unknown_command_type"


def test_typed_envelope_with_empty_expected_versions_is_rejected():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    kwargs = _valid_room_readiness_envelope_kwargs(world)
    kwargs["expected_versions"] = {}
    envelope = CommandEnvelope(**kwargs)
    parsed = parse_command(envelope)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_typed_envelope_with_bool_version_is_rejected():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    kwargs = _valid_room_readiness_envelope_kwargs(world)
    some_key = next(iter(kwargs["expected_versions"]))
    kwargs["expected_versions"] = {some_key: True}
    envelope = CommandEnvelope(**kwargs)
    parsed = parse_command(envelope)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_typed_envelope_with_negative_version_is_rejected():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    kwargs = _valid_room_readiness_envelope_kwargs(world)
    some_key = next(iter(kwargs["expected_versions"]))
    kwargs["expected_versions"] = {some_key: -1}
    envelope = CommandEnvelope(**kwargs)
    parsed = parse_command(envelope)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_typed_envelope_with_empty_evidence_digest_is_rejected():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    kwargs = _valid_room_readiness_envelope_kwargs(world)
    kwargs["evidence_digest"] = ""
    envelope = CommandEnvelope(**kwargs)
    parsed = parse_command(envelope)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_typed_envelope_with_empty_reason_code_is_rejected():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    kwargs = _valid_room_readiness_envelope_kwargs(world)
    kwargs["reason_code"] = "   "
    envelope = CommandEnvelope(**kwargs)
    parsed = parse_command(envelope)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_typed_envelope_with_bool_estimated_value_is_rejected():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    kwargs = _valid_room_readiness_envelope_kwargs(world)
    kwargs["estimated_value_gbp"] = True
    envelope = CommandEnvelope(**kwargs)
    parsed = parse_command(envelope)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_typed_envelope_with_non_finite_estimated_value_is_rejected():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    kwargs = _valid_room_readiness_envelope_kwargs(world)
    kwargs["estimated_value_gbp"] = math.inf
    envelope = CommandEnvelope(**kwargs)
    parsed = parse_command(envelope)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_typed_envelope_with_negative_estimated_value_is_rejected():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    kwargs = _valid_room_readiness_envelope_kwargs(world)
    kwargs["estimated_value_gbp"] = -1.0
    envelope = CommandEnvelope(**kwargs)
    parsed = parse_command(envelope)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_typed_envelope_with_empty_approval_ref_is_rejected():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    kwargs = _valid_room_readiness_envelope_kwargs(world)
    kwargs["approval_ref"] = "   "
    envelope = CommandEnvelope(**kwargs)
    parsed = parse_command(envelope)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_typed_envelope_payload_type_mismatch_is_rejected_not_raised():
    """A CommandEnvelope whose payload type does not match the type
    registered for its command_type must return a RejectedCommand — never
    raise — even though every other field is well-formed."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    kwargs = _valid_room_readiness_envelope_kwargs(world)
    kwargs["payload"] = GuestRecoveryActionPayload(
        booking_id="BKG-DOES-NOT-MATTER",
        guest_party_id="GP-DOES-NOT-MATTER",
        action_code="room-upgrade",
        value_gbp=10.0,
    )
    envelope = CommandEnvelope(**kwargs)
    parsed = parse_command(envelope)
    assert isinstance(parsed, RejectedCommand)
    assert parsed.reason == "invalid_command_payload"


def test_apply_command_with_cross_command_typed_payload_mismatch_returns_result():
    """world.apply_command must return a rejected CommandResult (never
    raise) when handed a typed CommandEnvelope whose payload belongs to a
    different command type."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    kwargs = _valid_room_readiness_envelope_kwargs(world)
    kwargs["payload"] = EnergyControlPlanPayload(
        meter_id="EM-DOES-NOT-MATTER",
        control_action="reset-normal",
        target_reading_kwh=10.0,
    )
    envelope = CommandEnvelope(**kwargs)
    before = world.snapshot()
    result = world.apply_command(envelope)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


# ---------------------------------------------------------------------------
# 13. guest.recovery-action.issue: value_gbp must match estimated_value_gbp
# ---------------------------------------------------------------------------


def test_guest_recovery_action_rejects_value_mismatch():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["guest-service-recovery"](world)
    cmd["payload"]["value_gbp"] = cmd["estimated_value_gbp"] + 50.0
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "value_mismatch"
    assert world.snapshot() == before


def test_guest_recovery_action_rejects_million_value_with_zero_estimate_bypass():
    """A near-zero declared estimate paired with a huge actual value_gbp
    must never bypass the role-limit authority gate via a mismatched
    estimate — it is rejected outright as a value mismatch."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["guest-service-recovery"](world)
    cmd["estimated_value_gbp"] = 0.0
    cmd["payload"]["value_gbp"] = 1_000_000.0
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "value_mismatch"
    assert world.snapshot() == before


def test_guest_recovery_action_accepts_when_value_matches_estimated_exactly():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["guest-service-recovery"](world)
    assert cmd["payload"]["value_gbp"] == cmd["estimated_value_gbp"]
    result = world.apply_command(cmd)
    assert result.accepted is True


# ---------------------------------------------------------------------------
# 14. Hero relocation destination must be a declared sister property
# ---------------------------------------------------------------------------


def test_hero_rejects_relocation_to_non_sister_property():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    reloc = cmd["payload"]["relocations"][0]
    reloc["destination_hotel_id"] = "HOTEL-RHINE-PARK"
    cmd["expected_versions"]["HOTEL-RHINE-PARK"] = world.hotels["HOTEL-RHINE-PARK"].version
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "incompatible_property"
    assert world.snapshot() == before


def test_hero_accepts_relocation_to_declared_sister_property():
    """Regression sanity: the golden plan's own sister-hotel destinations
    are still accepted (Riverside Central's sisters are Airport North and
    City Gate)."""
    world = _hero_world()
    cmd = _approved_hero_command(world)
    for reloc in cmd["payload"]["relocations"]:
        assert reloc["destination_hotel_id"] in (
            "HOTEL-AIRPORT-NORTH",
            "HOTEL-CITY-GATE",
        )
    result = world.apply_command(cmd)
    assert result.accepted is True


# ---------------------------------------------------------------------------
# 15. Cross-property approval (room readiness, maintenance dispatch) and
#     maintenance assignee engineering-skill validation.
# ---------------------------------------------------------------------------


def test_room_readiness_plan_cross_property_requires_approval():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    room_a = next(
        r for r in world.rooms.values()
        if r.hotel_id == "HOTEL-AIRPORT-NORTH" and r.status == "available"
    )
    room_b = next(
        r for r in world.rooms.values()
        if r.hotel_id == "HOTEL-CITY-GATE" and r.status == "available"
    )
    cmd = {
        "command_id": "CMD-ROOMS-XPROP-0001",
        "workflow_id": "ROOMS-XPROP-0001",
        "command_type": CMD_ROOM_READINESS_PLAN_APPLY,
        "expected_versions": {room_a.id: room_a.version, room_b.id: room_b.version},
        "evidence_digest": "EVID-ROOMS-XPROP",
        "reason_code": "test-cross-property-readiness",
        "estimated_value_gbp": 0.0,
        "approval_ref": None,
        "payload": {
            "room_ids": [room_a.id, room_b.id],
            "target_status": "not_ready",
            "maintenance_work_order_id": None,
        },
    }
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "approval_required"
    assert result.details.get("trigger") == "cross_property"
    assert world.snapshot() == before


def test_room_readiness_plan_same_property_still_requires_no_approval():
    """Preserve same-property behavior: a same-hotel plan is unaffected."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["room-readiness-coordination"](world)
    assert cmd["approval_ref"] is None
    result = world.apply_command(cmd)
    assert result.accepted is True


def test_maintenance_dispatch_cross_property_assignee_requires_approval():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["asset-maintenance-response"](world)
    wo_id = cmd["payload"]["work_order_id"]
    work_order = world.work_orders[wo_id]
    other_engineer = next(
        m for m in world.team_members.values()
        if m.hotel_id != work_order.hotel_id and m.skill == "engineering"
    )
    cmd["payload"]["assigned_team_member_id"] = other_engineer.id
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "approval_required"
    assert result.details.get("trigger") == "cross_property"
    assert world.snapshot() == before


def test_maintenance_dispatch_rejects_non_engineering_assignee():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["asset-maintenance-response"](world)
    wo_id = cmd["payload"]["work_order_id"]
    work_order = world.work_orders[wo_id]
    non_engineer = next(
        m for m in world.team_members.values()
        if m.hotel_id == work_order.hotel_id and m.skill != "engineering"
    )
    cmd["payload"]["assigned_team_member_id"] = non_engineer.id
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "skill_mismatch"
    assert world.snapshot() == before


def test_maintenance_dispatch_same_property_engineer_still_succeeds():
    """Preserve same-property behavior: the reference action's own
    same-hotel, engineering-skilled assignment is unaffected."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["asset-maintenance-response"](world)
    result = world.apply_command(cmd)
    assert result.accepted is True


# ---------------------------------------------------------------------------
# 16. Duplicate entity IDs inside a payload collection are rejected before
#     any mutation — a duplicate target cannot increment twice under one
#     expected version.
# ---------------------------------------------------------------------------


def test_hero_rejects_duplicate_room_ids_in_rooms_to_restore():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    first_room = cmd["payload"]["rooms_to_restore"][0]
    cmd["payload"]["rooms_to_restore"] = list(cmd["payload"]["rooms_to_restore"]) + [first_room]
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before
    assert world.rooms[first_room].version == before["rooms"][first_room]["version"]


def test_hero_rejects_duplicate_booking_ids_in_relocations():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    first_reloc = copy.deepcopy(cmd["payload"]["relocations"][0])
    cmd["payload"]["relocations"] = list(cmd["payload"]["relocations"]) + [first_reloc]
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


def test_hero_rejects_duplicate_shift_ids_in_shift_moves():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    first_move = copy.deepcopy(cmd["payload"]["shift_moves"][0])
    cmd["payload"]["shift_moves"] = list(cmd["payload"]["shift_moves"]) + [first_move]
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


def test_room_readiness_plan_rejects_duplicate_room_ids():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["room-readiness-coordination"](world)
    room_id = cmd["payload"]["room_ids"][0]
    cmd["payload"]["room_ids"] = [room_id, room_id]
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before
    assert world.rooms[room_id].version == before["rooms"][room_id]["version"]


def test_room_readiness_plan_typed_envelope_with_duplicate_room_ids_is_rejected():
    """Defense in depth: a hand-built typed CommandEnvelope carrying a
    duplicate room_id (bypassing the mapping parser entirely) is still
    rejected by the world handler before any mutation — a duplicate
    target cannot increment its version twice under one expected version."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    room = next(
        r for r in world.rooms.values()
        if r.hotel_id == "HOTEL-AIRPORT-NORTH" and r.status == "available"
    )
    envelope = CommandEnvelope(
        command_id="CMD-TYPED-DUP-0001",
        workflow_id="TYPED-DUP-0001",
        command_type=CMD_ROOM_READINESS_PLAN_APPLY,
        expected_versions={room.id: room.version},
        evidence_digest="EVID-TYPED-DUP",
        reason_code="typed-envelope-duplicate-room-ids",
        estimated_value_gbp=0.0,
        payload=RoomReadinessPlanPayload(
            room_ids=(room.id, room.id),
            target_status="not_ready",
            maintenance_work_order_id=None,
        ),
        approval_ref=None,
    )
    before = world.snapshot()
    result = world.apply_command(envelope)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before
    assert world.rooms[room.id].version == room.version


# ---------------------------------------------------------------------------
# 17. Unknown top-level envelope keys / unknown payload keys are rejected
#     for every mapping input.
# ---------------------------------------------------------------------------


def test_unknown_top_level_envelope_key_is_rejected():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    cmd["bogus_top_level_field"] = "unexpected"
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


def test_envelope_keys_constant_matches_documented_fields():
    assert ENVELOPE_KEYS == frozenset(
        {
            "command_id",
            "workflow_id",
            "command_type",
            "expected_versions",
            "evidence_digest",
            "reason_code",
            "estimated_value_gbp",
            "approval_ref",
            "payload",
        }
    )


@pytest.mark.parametrize("workflow_type", sorted(HOSPITALITY_REFERENCE_ACTIONS))
def test_unknown_payload_key_is_rejected_for_every_command_type(workflow_type):
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    if workflow_type == "hotel-operations-recovery":
        world.trigger_scenario("riverside-hot-water-outage")
        world.poll_sensor_events()
    cmd = HOSPITALITY_REFERENCE_ACTIONS[workflow_type](world)
    cmd["payload"]["bogus_payload_field"] = "unexpected"
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


def test_unknown_key_in_hero_relocation_item_is_rejected():
    world = _hero_world()
    cmd = _hero_command(world)
    cmd["payload"]["relocations"][0]["bogus_field"] = "unexpected"
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


def test_unknown_key_in_hero_shift_move_item_is_rejected():
    world = _hero_world()
    cmd = _hero_command(world)
    cmd["payload"]["shift_moves"][0]["bogus_field"] = "unexpected"
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


# ---------------------------------------------------------------------------
# 18. Workflow identity is preserved in generic (pre-dispatch) rejection
#     events whenever known.
# ---------------------------------------------------------------------------


def test_generic_parse_rejection_preserves_raw_workflow_id():
    """Even though the command fails to parse (missing command_id), the
    raw mapping's own non-empty workflow_id is preserved on the rejection
    event, rather than always blanked to ''."""
    world = _hero_world()
    cmd = _minimal_valid_hero_command(world)
    real_workflow_id = cmd["workflow_id"]
    del cmd["command_id"]
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert len(result.events) == 1
    assert result.events[0].payload["workflow_id"] == real_workflow_id


def test_command_id_conflict_rejection_preserves_workflow_id():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    first = world.apply_command(cmd)
    assert first.accepted is True

    conflicting = copy.deepcopy(cmd)
    conflicting["estimated_value_gbp"] = cmd["estimated_value_gbp"] + 1.0
    result = world.apply_command(conflicting)
    assert result.accepted is False
    assert result.reason == "command_id_conflict"
    assert len(result.events) == 1
    assert result.events[0].payload["workflow_id"] == cmd["workflow_id"]
    assert result.events[0].payload["command_id"] == cmd["command_id"]


# ---------------------------------------------------------------------------
# 19. Authority triggers: over-role-limit and protected-requirement, plus
#     numeric-edge (bool/non-finite/negative) payload field coverage.
# ---------------------------------------------------------------------------


def test_booking_inventory_plan_value_exceeds_role_limit_requires_approval():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["occupancy-pressure-response"](world)
    cmd["estimated_value_gbp"] = 150_000.0  # exceeds commercial_director's 100,000 limit
    cmd["approval_ref"] = None  # isolate the value-exceeds-limit trigger
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "approval_required"
    assert result.details.get("trigger") == "value_exceeds_role_limit"
    assert world.snapshot() == before


def test_booking_inventory_plan_protected_requirement_requires_approval():
    """Isolate the protected_requirement trigger with a same-property
    reassignment (the reference action itself is always cross-property,
    per Task 4's occupancy-pressure-response design, which would otherwise
    surface the cross_property trigger first)."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    booking_id = "BKG-MESC-STAY-001"
    booking = world.bookings[booking_id]
    assert booking.hotel_id == "HOTEL-MESSE-CENTRAL"
    world.bookings[booking_id] = dc.replace(booking, protected=True)
    booking = world.bookings[booking_id]
    hotel = world.hotels[booking.hotel_id]
    cmd = {
        "command_id": "CMD-OCC-PROTECTED-TEST-0001",
        "workflow_id": "OCC-PROTECTED-TEST-0001",
        "command_type": CMD_BOOKING_INVENTORY_PLAN_APPLY,
        "expected_versions": {booking_id: booking.version, booking.hotel_id: hotel.version},
        "evidence_digest": "EVID-OCC-PROTECTED-TEST",
        "reason_code": "test-protected-requirement-same-property",
        "estimated_value_gbp": 0.0,
        "approval_ref": None,
        "payload": {
            "booking_id": booking_id,
            "destination_hotel_id": booking.hotel_id,  # same property
            "destination_room_type": booking.room_type,
        },
    }
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "approval_required"
    assert result.details.get("trigger") == "protected_requirement"
    assert world.snapshot() == before


@pytest.mark.parametrize("bad_value", [True, math.inf, -1.0])
def test_guest_recovery_value_gbp_numeric_edges_are_rejected(bad_value):
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["guest-service-recovery"](world)
    cmd["payload"]["value_gbp"] = bad_value
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


@pytest.mark.parametrize("bad_value", [True, -1])
def test_food_beverage_covers_prepared_numeric_edges_are_rejected(bad_value):
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["food-and-beverage-readiness"](world)
    cmd["payload"]["covers_prepared"] = bad_value
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


@pytest.mark.parametrize("bad_value", [True, math.inf, -1.0])
def test_energy_target_reading_kwh_numeric_edges_are_rejected(bad_value):
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["energy-anomaly-response"](world)
    cmd["payload"]["target_reading_kwh"] = bad_value
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before


# ---------------------------------------------------------------------------
# 20. Protected bookings emit protected_requirement_breach ahead of the
#     generic incompatible_room reason when a relocation would degrade an
#     accessible/family requirement.
# ---------------------------------------------------------------------------


def test_hero_emits_protected_requirement_breach_before_incompatible_room():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    reloc = cmd["payload"]["relocations"][0]
    booking_id = reloc["booking_id"]
    booking = world.bookings[booking_id]
    world.bookings[booking_id] = dc.replace(booking, protected=True, requirement="accessible")
    reloc["destination_room_type"] = "standard"  # incompatible with "accessible"
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "protected_requirement_breach"
    assert world.snapshot() == before


def test_hero_non_protected_incompatible_relocation_still_uses_generic_reason():
    """Regression sanity: a non-protected booking's incompatible relocation
    keeps the generic incompatible_room reason (not the protected one)."""
    world = _hero_world()
    cmd = _approved_hero_command(world)
    reloc = cmd["payload"]["relocations"][0]
    booking_id = reloc["booking_id"]
    booking = world.bookings[booking_id]
    assert booking.protected is False
    reloc["destination_room_type"] = (
        "accessible" if booking.requirement != "accessible" else "standard"
    )
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason in ("incompatible_room", "insufficient_capacity")
    assert world.snapshot() == before


# ---------------------------------------------------------------------------
# 21. Hero shift validation looks up the real TeamMember and requires
#     actual engineering skill — never trusts shift.skill alone.
# ---------------------------------------------------------------------------


def test_hero_rejects_shift_when_assigned_team_member_lacks_engineering_skill():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    move = cmd["payload"]["shift_moves"][0]
    shift = world.shifts[move["shift_id"]]
    team_member = world.team_members[shift.team_member_id]
    world.team_members[shift.team_member_id] = dc.replace(team_member, skill="front-office")
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "skill_mismatch"
    assert world.snapshot() == before


def test_hero_rejects_shift_with_unknown_team_member():
    world = _hero_world()
    cmd = _approved_hero_command(world)
    move = cmd["payload"]["shift_moves"][0]
    shift = world.shifts[move["shift_id"]]
    del world.team_members[shift.team_member_id]
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "unknown_entity"
    assert world.snapshot() == before


# ---------------------------------------------------------------------------
# 22. Blocking invariant: Hotel.available_<type>_rooms always equals the
#     count of Room entities of that hotel/type with status == "available".
#     Reusable assertion + coverage across all eight reference actions and
#     the hero/booking physical room consume/release paths specifically.
# ---------------------------------------------------------------------------


def _assert_available_room_counts_match_actual_rooms(world: HospitalityWorld) -> None:
    """Reusable invariant assertion: for every hotel and room type, the
    Hotel.available_<type>_rooms denormalized counter equals the actual
    number of Room entities of that hotel/type currently 'available'."""
    for hotel_id, hotel in world.hotels.items():
        actual = world.hotel_available_room_counts(hotel_id)
        assert hotel.available_standard_rooms == actual["standard"], hotel_id
        assert hotel.available_family_rooms == actual["family"], hotel_id
        assert hotel.available_accessible_rooms == actual["accessible"], hotel_id
        assert hotel.available_premium_rooms == actual["premium"], hotel_id


@pytest.mark.parametrize("workflow_type", sorted(HOSPITALITY_REFERENCE_ACTIONS))
def test_available_room_counts_match_actual_rooms_after_each_reference_action(workflow_type):
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    if workflow_type == "hotel-operations-recovery":
        world.trigger_scenario("riverside-hot-water-outage")
        world.poll_sensor_events()
    _assert_available_room_counts_match_actual_rooms(world)  # invariant holds pre-command too

    cmd = HOSPITALITY_REFERENCE_ACTIONS[workflow_type](world)
    result = world.apply_command(cmd)
    assert result.accepted is True, f"{workflow_type}: {result.reason} {result.details}"
    _assert_available_room_counts_match_actual_rooms(world)


def test_hero_restore_updates_source_hotel_available_counters_and_version():
    """Restoring rooms must increment the *owning* hotel's available_*
    counter for each restored room's type — not just flip the Room's own
    status. The hotel is mutated exactly once even though 8 rooms restore."""
    world = _hero_world()
    cmd = _approved_hero_command(world)
    room_ids = cmd["payload"]["rooms_to_restore"]
    hotel_id = world.rooms[room_ids[0]].hotel_id
    before_hotel_version = world.hotels[hotel_id].version
    before_counts = world.hotel_available_room_counts(hotel_id)

    result = world.apply_command(cmd)
    assert result.accepted is True

    after_hotel = world.hotels[hotel_id]
    after_counts = world.hotel_available_room_counts(hotel_id)
    restored_by_type: dict[str, int] = {}
    for room_id in room_ids:
        rt = world.rooms[room_id].room_type
        restored_by_type[rt] = restored_by_type.get(rt, 0) + 1
    for rt, count in restored_by_type.items():
        assert after_counts[rt] == before_counts[rt] + count
    assert getattr(after_hotel, f"available_{next(iter(restored_by_type))}_rooms") == after_counts[
        next(iter(restored_by_type))
    ]
    # Exactly one version increment for this hotel from the whole command,
    # even though multiple room types/relocations may also touch it.
    assert after_hotel.version == before_hotel_version + 1


def test_hero_relocation_consumes_deterministic_destination_room():
    """Each relocation must consume one real, deterministic available Room
    of the declared destination type at the destination hotel — not just
    decrement a denormalized counter with no backing physical room."""
    world = _hero_world()
    cmd = _approved_hero_command(world)
    relocations = cmd["payload"]["relocations"]

    # Precompute, in payload order, the exact deterministic room each
    # relocation will consume — mirrors the handler's own selection.
    used: set[str] = set()
    expected_dest_rooms: list[str] = []
    for reloc in relocations:
        dest_room_id = world.select_available_room(
            reloc["destination_hotel_id"], reloc["destination_room_type"], exclude=frozenset(used)
        )
        assert dest_room_id is not None
        used.add(dest_room_id)
        expected_dest_rooms.append(dest_room_id)

    before_versions = {rid: world.rooms[rid].version for rid in expected_dest_rooms}
    result = world.apply_command(cmd)
    assert result.accepted is True

    assert len(set(expected_dest_rooms)) == len(expected_dest_rooms)  # no physical room reused
    for rid in expected_dest_rooms:
        room = world.rooms[rid]
        assert room.status == "occupied"
        assert room.version == before_versions[rid] + 1


def test_hero_relocation_releases_deterministic_source_room_when_one_exists():
    """A relocation whose original room type still has an occupied physical
    room at the source hotel releases exactly one such room (deterministic,
    lowest ID) back to available — 'when one exists' per the design; a
    relocation with no compatible occupied source room (e.g. all rooms of
    that type at the source are already unavailable/not_ready) releases
    nothing and is not rejected for it."""
    world = _hero_world()
    cmd = _approved_hero_command(world)
    relocations = cmd["payload"]["relocations"]
    hero_hotel_id = HERO_HOTEL

    used: set[str] = set()
    release_expectations: list[tuple[str, str | None]] = []  # (dest_room_id, source_room_id|None)
    for reloc in relocations:
        dest_room_id = world.select_available_room(
            reloc["destination_hotel_id"], reloc["destination_room_type"], exclude=frozenset(used)
        )
        used.add(dest_room_id)
        booking = world.bookings[reloc["booking_id"]]
        source_room_id = world.select_occupied_room(
            booking.hotel_id, booking.room_type, exclude=frozenset(used)
        )
        if source_room_id is not None:
            used.add(source_room_id)
        release_expectations.append((dest_room_id, source_room_id))

    assert any(source is not None for _dest, source in release_expectations), (
        "golden hero scenario must have at least one releasable source room (premium)"
    )
    before_versions = {
        source: world.rooms[source].version
        for _dest, source in release_expectations
        if source is not None
    }

    result = world.apply_command(cmd)
    assert result.accepted is True

    for _dest, source_room_id in release_expectations:
        if source_room_id is None:
            continue
        room = world.rooms[source_room_id]
        assert room.hotel_id == hero_hotel_id
        assert room.status == "available"
        assert room.version == before_versions[source_room_id] + 1


def test_hero_physical_room_transitions_are_not_counted_as_restored_room_events():
    """The 8 'hotel-recovery.room.restored' events remain exactly the
    rooms_to_restore set; the internal destination-consume/source-release
    physical room transitions emit distinct event types instead."""
    world = _hero_world()
    cmd = _approved_hero_command(world)
    result = world.apply_command(cmd)
    assert result.accepted is True

    restored_room_ids = {
        e.payload["room_id"] for e in result.events if e.type == "hotel-recovery.room.restored"
    }
    assert restored_room_ids == set(cmd["payload"]["rooms_to_restore"])

    consumed_events = [e for e in result.events if e.type == "hotel-recovery.room.consumed"]
    assert len(consumed_events) == len(cmd["payload"]["relocations"])
    # None of the physical destination rooms consumed were also emitted as
    # a "restored" room — they are disjoint sets of physical rooms.
    consumed_room_ids = {e.payload["room_id"] for e in consumed_events}
    assert consumed_room_ids.isdisjoint(restored_room_ids)


def test_hero_destination_hotel_version_increments_exactly_once_despite_multiple_relocations():
    """Airport North receives 6 relocations in the golden plan; its version
    (and City Gate's, with 4) must still increment by exactly 1 for the
    whole command — never once per individual relocation."""
    world = _hero_world()
    cmd = _approved_hero_command(world)
    relocations = cmd["payload"]["relocations"]
    dest_hotel_ids = {r["destination_hotel_id"] for r in relocations}
    assert len(dest_hotel_ids) >= 1
    # Sanity: at least one destination hotel receives more than one relocation
    # in the golden plan (exercising the "exactly once" requirement).
    from collections import Counter
    counts = Counter(r["destination_hotel_id"] for r in relocations)
    assert any(c > 1 for c in counts.values())

    before_versions = {hid: world.hotels[hid].version for hid in dest_hotel_ids}
    result = world.apply_command(cmd)
    assert result.accepted is True
    for hid in dest_hotel_ids:
        assert world.hotels[hid].version == before_versions[hid] + 1


def test_hero_atomic_rollback_when_a_dynamically_selected_room_is_stale():
    """If a room the handler will dynamically select to consume/release
    turns stale between reference-action construction and apply (someone
    else mutated it directly), the whole command is rejected atomically —
    no partial mutation — exactly like a stale *declared* target."""
    world = _hero_world()
    cmd = _approved_hero_command(world)
    reloc = cmd["payload"]["relocations"][0]
    dest_room_id = world.select_available_room(
        reloc["destination_hotel_id"], reloc["destination_room_type"]
    )
    assert dest_room_id is not None
    room = world.rooms[dest_room_id]
    # Mutate the room directly (bypassing apply_command) so it is stale
    # relative to what the reference action's expected_versions declared.
    world.rooms[dest_room_id] = dc.replace(room, version=room.version + 1)
    before = world.snapshot()

    result = world.apply_command(cmd)

    assert result.accepted is False
    assert result.reason == "stale_entity_version"
    assert world.snapshot() == before


def test_booking_inventory_plan_consumes_destination_room_and_releases_source_room():
    """booking.inventory-plan.apply must consume a real deterministic
    destination Room and (when a compatible occupied one exists) release a
    real deterministic source Room — mirroring the hero relocation path."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["occupancy-pressure-response"](world)
    booking = world.bookings[cmd["payload"]["booking_id"]]
    source_hotel_id = booking.hotel_id
    source_room_type = booking.room_type
    dest_hotel_id = cmd["payload"]["destination_hotel_id"]
    dest_room_type = cmd["payload"]["destination_room_type"]
    assert dest_hotel_id != source_hotel_id  # genuine cross-property (Task 4 item 9)

    expected_dest_room = world.select_available_room(dest_hotel_id, dest_room_type)
    assert expected_dest_room is not None
    expected_source_room = world.select_occupied_room(
        source_hotel_id, source_room_type, exclude=frozenset({expected_dest_room})
    )

    before_dest_version = world.rooms[expected_dest_room].version
    before_source_version = (
        world.rooms[expected_source_room].version if expected_source_room else None
    )
    before_source_hotel_version = world.hotels[source_hotel_id].version
    before_dest_hotel_version = world.hotels[dest_hotel_id].version

    result = world.apply_command(cmd)
    assert result.accepted is True

    dest_room = world.rooms[expected_dest_room]
    assert dest_room.status == "occupied"
    assert dest_room.version == before_dest_version + 1
    assert world.hotels[dest_hotel_id].version == before_dest_hotel_version + 1

    if expected_source_room is not None:
        source_room = world.rooms[expected_source_room]
        assert source_room.status == "available"
        assert source_room.version == before_source_version + 1
        assert world.hotels[source_hotel_id].version == before_source_hotel_version + 1

    _assert_available_room_counts_match_actual_rooms(world)


def test_room_readiness_plan_updates_owning_hotel_available_counter_and_version():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["room-readiness-coordination"](world)
    room_id = cmd["payload"]["room_ids"][0]
    hotel_id = world.rooms[room_id].hotel_id
    before_hotel_version = world.hotels[hotel_id].version
    before_counts = world.hotel_available_room_counts(hotel_id)
    room_type = world.rooms[room_id].room_type

    result = world.apply_command(cmd)
    assert result.accepted is True

    after_counts = world.hotel_available_room_counts(hotel_id)
    assert after_counts[room_type] == before_counts[room_type] - 1
    assert world.hotels[hotel_id].version == before_hotel_version + 1
    _assert_available_room_counts_match_actual_rooms(world)


def test_room_readiness_plan_no_op_when_room_already_in_target_status():
    """An explicit no-op (room already in target_status) mutates nothing:
    no room version bump, no hotel counter/version change."""
    world = _hero_world()
    room = next(
        r for r in world.rooms.values()
        if r.hotel_id == HERO_HOTEL and r.status == "not_ready"
    )
    hotel = world.hotels[room.hotel_id]
    cmd = {
        "command_id": "CMD-ROOMS-NOOP-0001",
        "workflow_id": "ROOMS-NOOP-0001",
        "command_type": CMD_ROOM_READINESS_PLAN_APPLY,
        "expected_versions": {room.id: room.version},
        "evidence_digest": "EVID-ROOMS-NOOP",
        "reason_code": "test-room-readiness-no-op",
        "estimated_value_gbp": 0.0,
        "approval_ref": None,
        "payload": {
            "room_ids": [room.id],
            "target_status": "not_ready",  # already not_ready: explicit no-op
            "maintenance_work_order_id": None,
        },
    }
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is True
    assert world.rooms[room.id].version == room.version
    assert world.hotels[room.hotel_id].version == hotel.version
    assert world.snapshot() == before
    assert not any(e.type == "room-readiness-plan.room.updated" for e in result.events)


def test_room_readiness_plan_rejects_occupied_room_transition():
    """An occupied (guest-in-residence) room can never be silently flipped
    to available or not_ready by a readiness plan."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    room = next(
        r for r in world.rooms.values()
        if r.hotel_id == "HOTEL-AIRPORT-NORTH" and r.status == "occupied"
    )
    cmd = {
        "command_id": "CMD-ROOMS-OCCUPIED-0001",
        "workflow_id": "ROOMS-OCCUPIED-0001",
        "command_type": CMD_ROOM_READINESS_PLAN_APPLY,
        "expected_versions": {room.id: room.version},
        "evidence_digest": "EVID-ROOMS-OCCUPIED",
        "reason_code": "test-room-readiness-occupied-reject",
        "estimated_value_gbp": 0.0,
        "approval_ref": None,
        "payload": {
            "room_ids": [room.id],
            "target_status": "not_ready",
            "maintenance_work_order_id": None,
        },
    }
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "invalid_room_status"
    assert world.snapshot() == before


# ---------------------------------------------------------------------------
# 23. _check_expected_versions rejects any expected_versions key that falls
#     outside the exact computed target set for the command.
# ---------------------------------------------------------------------------


def test_unexpected_expected_version_key_is_rejected():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["asset-maintenance-response"](world)
    cmd["expected_versions"]["BOGUS-ENTITY-NOT-A-TARGET"] = 1
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "unexpected_expected_version"
    assert "BOGUS-ENTITY-NOT-A-TARGET" in result.details.get("unexpected_keys", [])
    assert world.snapshot() == before


def test_unexpected_expected_version_key_rejected_for_hero_after_dynamic_targets_computed():
    """The same rule holds for the hero command even after its dynamic
    physical-room/hotel targets have been computed — an extra key still
    outside the *complete* target set is rejected, not silently ignored."""
    world = _hero_world()
    cmd = _approved_hero_command(world)
    cmd["expected_versions"]["BOGUS-ENTITY-NOT-A-TARGET"] = 1
    before = world.snapshot()
    result = world.apply_command(cmd)
    assert result.accepted is False
    assert result.reason == "unexpected_expected_version"
    assert world.snapshot() == before


# ---------------------------------------------------------------------------
# 24. Occupancy reference action: real cross-property relocation to a
#     declared sister hotel, with commercial_director approval.
# ---------------------------------------------------------------------------


def test_occupancy_reference_action_is_real_cross_property_relocation_with_approval():
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    cmd = HOSPITALITY_REFERENCE_ACTIONS["occupancy-pressure-response"](world)
    booking = world.bookings[cmd["payload"]["booking_id"]]
    source_hotel = world.hotels[booking.hotel_id]

    assert cmd["payload"]["destination_hotel_id"] != booking.hotel_id
    assert cmd["payload"]["destination_hotel_id"] in source_hotel.sister_hotel_ids
    assert cmd["approval_ref"]
    assert cmd["approval_ref"].startswith("commercial_director_decision:")

    result = world.apply_command(cmd)
    assert result.accepted is True
    reassigned_events = [
        e for e in result.events if e.type == "booking-inventory-plan.booking.reassigned"
    ]
    assert len(reassigned_events) == 1
    assert reassigned_events[0].payload["cross_property"] is True
    assert (
        reassigned_events[0].payload["destination_hotel_id"] in source_hotel.sister_hotel_ids
    )


# ---------------------------------------------------------------------------
# 25. Typed-envelope defense-in-depth: a hand-built CommandEnvelope's
#     payload *values* must be validated with the exact same registered
#     parser used for mapping input — not merely type-checked. A frozen
#     payload dataclass can be constructed with out-of-enum/out-of-bounds
#     field values (e.g. ``target_status="TOTALLY-BOGUS"``) that
#     ``type(payload) is ExpectedType`` alone can never catch. This closes
#     the final Task-4 typed-payload validation gap.
# ---------------------------------------------------------------------------


def _valid_typed_envelope_for_workflow(
    world: HospitalityWorld, workflow_type: str
) -> CommandEnvelope:
    """Build the real reference-action command for *workflow_type* and
    parse it via the mapping route to obtain a genuinely valid, fully-typed
    ``CommandEnvelope`` — never a hand-fabricated one — ready for the tests
    below to mutate exactly one payload field into an adversarial value."""
    cmd = HOSPITALITY_REFERENCE_ACTIONS[workflow_type](world)
    parsed = parse_command(cmd)
    assert isinstance(parsed, CommandEnvelope), f"{workflow_type}: {parsed}"
    return parsed


def _mutate_hotel_recovery_payload_invalid(payload: HotelRecoveryPayload):
    """Corrupt the first relocation's destination_room_type — a nested
    payload field the top-level ``type(payload) is ...`` check can never
    reach."""
    assert len(payload.relocations) > 0
    bad_first = dc.replace(payload.relocations[0], destination_room_type="castle-suite")
    return dc.replace(payload, relocations=(bad_first,) + payload.relocations[1:])


def _mutate_room_readiness_payload_invalid(payload: RoomReadinessPlanPayload):
    return dc.replace(payload, target_status="TOTALLY-BOGUS")


def _mutate_maintenance_payload_invalid(payload: MaintenanceWorkOrderDispatchPayload):
    return dc.replace(payload, priority="ultra-mega-urgent")


def _mutate_guest_recovery_payload_invalid(payload: GuestRecoveryActionPayload):
    return dc.replace(payload, action_code="not-a-real-action-code")


def _mutate_booking_inventory_payload_invalid(payload: BookingInventoryPlanPayload):
    return dc.replace(payload, destination_room_type="castle-suite")


def _mutate_workforce_shift_payload_invalid(payload: WorkforceShiftPlanPayload):
    return dc.replace(payload, destination_hotel_id="")


def _mutate_food_beverage_payload_invalid(payload: FoodBeverageServicePlanPayload):
    return dc.replace(payload, covers_prepared=-5)


def _mutate_energy_payload_invalid(payload: EnergyControlPlanPayload):
    return dc.replace(payload, control_action="beam-me-up")


_TYPED_ENVELOPE_ADVERSARIAL_MUTATORS: dict[str, Any] = {
    "hotel-operations-recovery": _mutate_hotel_recovery_payload_invalid,
    "room-readiness-coordination": _mutate_room_readiness_payload_invalid,
    "asset-maintenance-response": _mutate_maintenance_payload_invalid,
    "guest-service-recovery": _mutate_guest_recovery_payload_invalid,
    "occupancy-pressure-response": _mutate_booking_inventory_payload_invalid,
    "workforce-demand-balancing": _mutate_workforce_shift_payload_invalid,
    "food-and-beverage-readiness": _mutate_food_beverage_payload_invalid,
    "energy-anomaly-response": _mutate_energy_payload_invalid,
}
assert set(_TYPED_ENVELOPE_ADVERSARIAL_MUTATORS) == set(HOSPITALITY_REFERENCE_ACTIONS)
assert len(_TYPED_ENVELOPE_ADVERSARIAL_MUTATORS) == 8


@pytest.mark.parametrize("workflow_type", sorted(_TYPED_ENVELOPE_ADVERSARIAL_MUTATORS))
def test_typed_envelope_adversarial_payload_field_is_rejected_before_any_mutation(workflow_type):
    """A hand-built CommandEnvelope whose payload is the *exact* right
    dataclass type, but carries one out-of-enum/out-of-bounds field value,
    must be rejected before any world handler or mutation runs — for every
    one of the eight command types."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    if workflow_type == "hotel-operations-recovery":
        world.trigger_scenario("riverside-hot-water-outage")
        world.poll_sensor_events()

    valid_envelope = _valid_typed_envelope_for_workflow(world, workflow_type)
    mutate = _TYPED_ENVELOPE_ADVERSARIAL_MUTATORS[workflow_type]
    invalid_payload = mutate(valid_envelope.payload)
    assert invalid_payload != valid_envelope.payload

    bad_envelope = dc.replace(valid_envelope, payload=invalid_payload)
    envelope_before = copy.deepcopy(bad_envelope)
    payload_before = copy.deepcopy(invalid_payload)

    before_snapshot = world.snapshot()
    result = world.apply_command(bad_envelope)

    assert result.accepted is False
    assert result.reason == "invalid_command_payload", (
        workflow_type,
        result.reason,
        result.details,
    )
    assert len(result.events) == 1
    rejection_event = result.events[0]
    assert rejection_event.payload["command_id"] == bad_envelope.command_id
    assert rejection_event.payload["workflow_id"] == bad_envelope.workflow_id

    assert world.snapshot() == before_snapshot
    # Frozen dataclasses cannot mutate, but assert unchanged anyway as a
    # defensive regression guard against any future non-frozen refactor.
    assert bad_envelope == envelope_before
    assert bad_envelope.payload == payload_before


def test_typed_room_readiness_target_status_occupied_is_rejected():
    """target_status must be drawn from the exact enum ("available" |
    "not_ready") — "occupied" is a real *room* status but never a valid
    readiness-plan target."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    room = next(
        r for r in world.rooms.values()
        if r.hotel_id == "HOTEL-AIRPORT-NORTH" and r.status == "available"
    )
    envelope = CommandEnvelope(
        command_id="CMD-TYPED-OCCUPIED-STATUS-0001",
        workflow_id="TYPED-OCCUPIED-STATUS-0001",
        command_type=CMD_ROOM_READINESS_PLAN_APPLY,
        expected_versions={room.id: room.version},
        evidence_digest="EVID-TYPED-OCCUPIED-STATUS",
        reason_code="typed-envelope-occupied-target-status",
        estimated_value_gbp=0.0,
        payload=RoomReadinessPlanPayload(
            room_ids=(room.id,),
            target_status="occupied",
            maintenance_work_order_id=None,
        ),
        approval_ref=None,
    )
    before_snapshot = world.snapshot()
    result = world.apply_command(envelope)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before_snapshot


def test_typed_food_beverage_covers_prepared_bool_is_rejected():
    """``covers_prepared`` is an int count — ``True``/``False`` (a bool
    subclass of int) must never silently pass as a covers count."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    valid_envelope = _valid_typed_envelope_for_workflow(world, "food-and-beverage-readiness")
    bad_payload = dc.replace(valid_envelope.payload, covers_prepared=True)
    envelope = dc.replace(valid_envelope, payload=bad_payload)
    before_snapshot = world.snapshot()
    result = world.apply_command(envelope)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before_snapshot


def test_typed_energy_target_reading_kwh_non_finite_is_rejected():
    """``target_reading_kwh`` must be a finite, non-negative number — a
    hand-built payload carrying ``math.inf`` must never reach the handler."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    valid_envelope = _valid_typed_envelope_for_workflow(world, "energy-anomaly-response")
    bad_payload = dc.replace(valid_envelope.payload, target_reading_kwh=math.inf)
    envelope = dc.replace(valid_envelope, payload=bad_payload)
    before_snapshot = world.snapshot()
    result = world.apply_command(envelope)
    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.snapshot() == before_snapshot


def test_typed_room_readiness_bogus_target_status_no_longer_drifts_available_room_counters():
    """Regression: a hand-built CommandEnvelope with
    ``target_status="TOTALLY-BOGUS"`` must never reach the room-readiness
    handler and mutate ``room.status`` into a non-enum value. Before the
    fix this silently mutated the room (bumping its version and writing an
    invalid status string) while leaving the owning hotel's available_*
    counters untouched — the exact counter drift
    ``_assert_available_room_counts_match_actual_rooms`` guards against."""
    world = HospitalityWorld.demo(seed=DEMO_SEED)
    room = next(
        r for r in world.rooms.values()
        if r.hotel_id == "HOTEL-AIRPORT-NORTH" and r.status == "available"
    )
    envelope = CommandEnvelope(
        command_id="CMD-TYPED-BOGUS-STATUS-0001",
        workflow_id="TYPED-BOGUS-STATUS-0001",
        command_type=CMD_ROOM_READINESS_PLAN_APPLY,
        expected_versions={room.id: room.version},
        evidence_digest="EVID-TYPED-BOGUS-STATUS",
        reason_code="typed-envelope-bogus-target-status",
        estimated_value_gbp=0.0,
        payload=RoomReadinessPlanPayload(
            room_ids=(room.id,),
            target_status="TOTALLY-BOGUS",
            maintenance_work_order_id=None,
        ),
        approval_ref=None,
    )
    before_snapshot = world.snapshot()

    result = world.apply_command(envelope)

    assert result.accepted is False
    assert result.reason == "invalid_command_payload"
    assert world.rooms[room.id].status == "available"
    assert world.rooms[room.id].version == room.version
    assert world.snapshot() == before_snapshot
    _assert_available_room_counts_match_actual_rooms(world)
