"""Typed Hospitality command envelopes, payload schemas, and parsing.

This module is pure — it never touches ``HospitalityWorld`` state. It only
validates the *shape* of an incoming command mapping (or a pre-built
``CommandEnvelope``) and produces an immutable, typed envelope with a typed,
workflow-specific payload. Business-rule validation (versions, capacity,
compatibility, authority) and mutation live in ``world.py``.

Malformed programmer input (missing/incorrectly-typed fields, unknown command
types, bad enum values) is reported as a ``RejectedCommand`` — this module
never raises for a business rejection. There are exactly eight command types,
one per Hospitality workflow.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Command type constants — exactly eight, one per Hospitality workflow.
# ---------------------------------------------------------------------------

CMD_HOTEL_RECOVERY_EXECUTE = "hotel.recovery.execute"
CMD_ROOM_READINESS_PLAN_APPLY = "room.readiness-plan.apply"
CMD_MAINTENANCE_WORK_ORDER_DISPATCH = "maintenance.work-order.dispatch"
CMD_GUEST_RECOVERY_ACTION_ISSUE = "guest.recovery-action.issue"
CMD_BOOKING_INVENTORY_PLAN_APPLY = "booking.inventory-plan.apply"
CMD_WORKFORCE_SHIFT_PLAN_APPLY = "workforce.shift-plan.apply"
CMD_FOOD_BEVERAGE_SERVICE_PLAN_APPLY = "food-beverage.service-plan.apply"
CMD_ENERGY_CONTROL_PLAN_APPLY = "energy.control-plan.apply"

COMMAND_TYPES: tuple[str, ...] = (
    CMD_HOTEL_RECOVERY_EXECUTE,
    CMD_ROOM_READINESS_PLAN_APPLY,
    CMD_MAINTENANCE_WORK_ORDER_DISPATCH,
    CMD_GUEST_RECOVERY_ACTION_ISSUE,
    CMD_BOOKING_INVENTORY_PLAN_APPLY,
    CMD_WORKFORCE_SHIFT_PLAN_APPLY,
    CMD_FOOD_BEVERAGE_SERVICE_PLAN_APPLY,
    CMD_ENERGY_CONTROL_PLAN_APPLY,
)
assert len(COMMAND_TYPES) == 8

_ROOM_TYPES = ("standard", "family", "accessible", "premium")

# ---------------------------------------------------------------------------
# Explicit, closed key sets — every mapping input (envelope and payload) is
# rejected if it carries a key outside these sets.
# ---------------------------------------------------------------------------

ENVELOPE_KEYS: frozenset[str] = frozenset(
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

_RELOCATION_KEYS: frozenset[str] = frozenset(
    {"booking_id", "destination_hotel_id", "destination_room_type"}
)
_SHIFT_MOVE_KEYS: frozenset[str] = frozenset({"shift_id", "destination_hotel_id"})


# ---------------------------------------------------------------------------
# Primitive validators — explicit, no broad exception handling.
# ---------------------------------------------------------------------------


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_finite_number(value: Any) -> bool:
    if _is_bool(value):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _is_non_negative_finite(value: Any) -> bool:
    return _is_finite_number(value) and float(value) >= 0.0


def _is_non_negative_int(value: Any) -> bool:
    if _is_bool(value):
        return False
    return isinstance(value, int) and value >= 0


def _as_str_tuple(value: Any) -> tuple[str, ...] | None:
    """Return a tuple of non-empty strings from a list/tuple, else None."""
    if not isinstance(value, (list, tuple)):
        return None
    items: list[str] = []
    for item in value:
        if not _is_non_empty_str(item):
            return None
        items.append(item)
    return tuple(items)


def _has_duplicates(items: tuple[str, ...]) -> bool:
    return len(set(items)) != len(items)


def _reject_unknown_keys(
    mapping: Mapping[str, Any], allowed: frozenset[str], field: str
) -> RejectedCommand | None:
    """Return a rejection if *mapping* carries any key outside *allowed*."""
    unexpected = sorted(set(mapping.keys()) - allowed)
    if unexpected:
        return RejectedCommand(
            "invalid_command_payload", {"field": field, "unexpected_keys": unexpected}
        )
    return None


# ---------------------------------------------------------------------------
# Typed workflow-specific payloads
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HotelRecoveryRelocation:
    booking_id: str
    destination_hotel_id: str
    destination_room_type: str


@dataclass(frozen=True, slots=True)
class HotelRecoveryShiftMove:
    shift_id: str
    destination_hotel_id: str


@dataclass(frozen=True, slots=True)
class HotelRecoveryPayload:
    """Payload for ``hotel.recovery.execute`` (the hero command)."""

    work_order_id: str
    rooms_to_restore: tuple[str, ...]
    relocations: tuple[HotelRecoveryRelocation, ...]
    shift_moves: tuple[HotelRecoveryShiftMove, ...]
    guest_communication_actions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RoomReadinessPlanPayload:
    """Payload for ``room.readiness-plan.apply``."""

    room_ids: tuple[str, ...]
    target_status: str  # "available" | "not_ready"
    maintenance_work_order_id: str | None = None


@dataclass(frozen=True, slots=True)
class MaintenanceWorkOrderDispatchPayload:
    """Payload for ``maintenance.work-order.dispatch``."""

    work_order_id: str
    assigned_team_member_id: str
    priority: str  # "critical" | "high" | "medium" | "low"


@dataclass(frozen=True, slots=True)
class GuestRecoveryActionPayload:
    """Payload for ``guest.recovery-action.issue``.

    This command must never cancel or relocate a booking by itself.
    """

    booking_id: str
    guest_party_id: str
    action_code: str
    value_gbp: float


@dataclass(frozen=True, slots=True)
class BookingInventoryPlanPayload:
    """Payload for ``booking.inventory-plan.apply``."""

    booking_id: str
    destination_hotel_id: str
    destination_room_type: str


@dataclass(frozen=True, slots=True)
class WorkforceShiftPlanPayload:
    """Payload for ``workforce.shift-plan.apply``."""

    shift_id: str
    destination_hotel_id: str


@dataclass(frozen=True, slots=True)
class FoodBeverageServicePlanPayload:
    """Payload for ``food-beverage.service-plan.apply``."""

    plan_id: str
    covers_prepared: int


@dataclass(frozen=True, slots=True)
class EnergyControlPlanPayload:
    """Payload for ``energy.control-plan.apply``."""

    meter_id: str
    control_action: str  # "reduce-setpoint" | "increase-setpoint" | "reset-normal"
    target_reading_kwh: float


# ---------------------------------------------------------------------------
# Envelope and result/rejection records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    """A fully parsed, typed Hospitality command.

    ``expected_versions`` maps entity ID -> expected current version for
    every mutable entity this command targets (optimistic concurrency).
    """

    command_id: str
    workflow_id: str
    command_type: str
    expected_versions: Mapping[str, int]
    evidence_digest: str
    reason_code: str
    estimated_value_gbp: float
    payload: Any
    approval_ref: str | None = None


@dataclass(frozen=True, slots=True)
class RejectedCommand:
    """A parse-time rejection — malformed programmer input, not a business rule."""

    reason: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Immutable outcome of ``HospitalityWorld.apply_command``."""

    accepted: bool
    reason: str
    command_id: str
    command_type: str
    idempotent_replay: bool
    events: tuple[Any, ...]
    snapshot: dict[str, Any]
    snapshot_digest: str
    details: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Payload parsers — one per exact command type
# ---------------------------------------------------------------------------


def _parse_hotel_recovery_payload(
    payload: Mapping[str, Any],
) -> HotelRecoveryPayload | RejectedCommand:
    unknown = _reject_unknown_keys(payload, _PAYLOAD_ALLOWED_KEYS[CMD_HOTEL_RECOVERY_EXECUTE], "payload")
    if unknown is not None:
        return unknown

    work_order_id = payload.get("work_order_id")
    if not _is_non_empty_str(work_order_id):
        return RejectedCommand("invalid_command_payload", {"field": "work_order_id"})

    rooms_to_restore = _as_str_tuple(payload.get("rooms_to_restore"))
    if rooms_to_restore is None or len(rooms_to_restore) == 0:
        return RejectedCommand("invalid_command_payload", {"field": "rooms_to_restore"})
    if _has_duplicates(rooms_to_restore):
        return RejectedCommand(
            "invalid_command_payload",
            {"field": "rooms_to_restore", "error": "duplicate_ids"},
        )

    raw_relocations = payload.get("relocations")
    if not isinstance(raw_relocations, (list, tuple)):
        return RejectedCommand("invalid_command_payload", {"field": "relocations"})
    relocations: list[HotelRecoveryRelocation] = []
    for item in raw_relocations:
        if not isinstance(item, Mapping):
            return RejectedCommand("invalid_command_payload", {"field": "relocations[]"})
        unknown_item = _reject_unknown_keys(item, _RELOCATION_KEYS, "relocations[]")
        if unknown_item is not None:
            return unknown_item
        booking_id = item.get("booking_id")
        destination_hotel_id = item.get("destination_hotel_id")
        destination_room_type = item.get("destination_room_type")
        if not _is_non_empty_str(booking_id):
            return RejectedCommand("invalid_command_payload", {"field": "relocations[].booking_id"})
        if not _is_non_empty_str(destination_hotel_id):
            return RejectedCommand(
                "invalid_command_payload", {"field": "relocations[].destination_hotel_id"}
            )
        if destination_room_type not in _ROOM_TYPES:
            return RejectedCommand(
                "invalid_command_payload", {"field": "relocations[].destination_room_type"}
            )
        relocations.append(
            HotelRecoveryRelocation(
                booking_id=booking_id,
                destination_hotel_id=destination_hotel_id,
                destination_room_type=destination_room_type,
            )
        )
    relocation_booking_ids = tuple(r.booking_id for r in relocations)
    if _has_duplicates(relocation_booking_ids):
        return RejectedCommand(
            "invalid_command_payload",
            {"field": "relocations[].booking_id", "error": "duplicate_ids"},
        )

    raw_shift_moves = payload.get("shift_moves")
    if not isinstance(raw_shift_moves, (list, tuple)):
        return RejectedCommand("invalid_command_payload", {"field": "shift_moves"})
    shift_moves: list[HotelRecoveryShiftMove] = []
    for item in raw_shift_moves:
        if not isinstance(item, Mapping):
            return RejectedCommand("invalid_command_payload", {"field": "shift_moves[]"})
        unknown_item = _reject_unknown_keys(item, _SHIFT_MOVE_KEYS, "shift_moves[]")
        if unknown_item is not None:
            return unknown_item
        shift_id = item.get("shift_id")
        destination_hotel_id = item.get("destination_hotel_id")
        if not _is_non_empty_str(shift_id):
            return RejectedCommand("invalid_command_payload", {"field": "shift_moves[].shift_id"})
        if not _is_non_empty_str(destination_hotel_id):
            return RejectedCommand(
                "invalid_command_payload", {"field": "shift_moves[].destination_hotel_id"}
            )
        shift_moves.append(
            HotelRecoveryShiftMove(
                shift_id=shift_id, destination_hotel_id=destination_hotel_id
            )
        )
    shift_move_ids = tuple(m.shift_id for m in shift_moves)
    if _has_duplicates(shift_move_ids):
        return RejectedCommand(
            "invalid_command_payload",
            {"field": "shift_moves[].shift_id", "error": "duplicate_ids"},
        )

    guest_communication_actions = _as_str_tuple(payload.get("guest_communication_actions"))
    if guest_communication_actions is None:
        return RejectedCommand(
            "invalid_command_payload", {"field": "guest_communication_actions"}
        )

    return HotelRecoveryPayload(
        work_order_id=work_order_id,
        rooms_to_restore=rooms_to_restore,
        relocations=tuple(relocations),
        shift_moves=tuple(shift_moves),
        guest_communication_actions=guest_communication_actions,
    )


def _parse_room_readiness_plan_payload(
    payload: Mapping[str, Any],
) -> RoomReadinessPlanPayload | RejectedCommand:
    unknown = _reject_unknown_keys(
        payload, _PAYLOAD_ALLOWED_KEYS[CMD_ROOM_READINESS_PLAN_APPLY], "payload"
    )
    if unknown is not None:
        return unknown

    room_ids = _as_str_tuple(payload.get("room_ids"))
    if room_ids is None or len(room_ids) == 0:
        return RejectedCommand("invalid_command_payload", {"field": "room_ids"})
    if _has_duplicates(room_ids):
        return RejectedCommand(
            "invalid_command_payload", {"field": "room_ids", "error": "duplicate_ids"}
        )

    target_status = payload.get("target_status")
    if target_status not in ("available", "not_ready"):
        return RejectedCommand("invalid_command_payload", {"field": "target_status"})

    maintenance_work_order_id = payload.get("maintenance_work_order_id")
    if maintenance_work_order_id is not None and not _is_non_empty_str(maintenance_work_order_id):
        return RejectedCommand(
            "invalid_command_payload", {"field": "maintenance_work_order_id"}
        )

    return RoomReadinessPlanPayload(
        room_ids=room_ids,
        target_status=target_status,
        maintenance_work_order_id=maintenance_work_order_id,
    )


_WORK_ORDER_PRIORITIES = ("critical", "high", "medium", "low")


def _parse_maintenance_work_order_dispatch_payload(
    payload: Mapping[str, Any],
) -> MaintenanceWorkOrderDispatchPayload | RejectedCommand:
    unknown = _reject_unknown_keys(
        payload, _PAYLOAD_ALLOWED_KEYS[CMD_MAINTENANCE_WORK_ORDER_DISPATCH], "payload"
    )
    if unknown is not None:
        return unknown

    work_order_id = payload.get("work_order_id")
    assigned_team_member_id = payload.get("assigned_team_member_id")
    priority = payload.get("priority")
    if not _is_non_empty_str(work_order_id):
        return RejectedCommand("invalid_command_payload", {"field": "work_order_id"})
    if not _is_non_empty_str(assigned_team_member_id):
        return RejectedCommand(
            "invalid_command_payload", {"field": "assigned_team_member_id"}
        )
    if priority not in _WORK_ORDER_PRIORITIES:
        return RejectedCommand("invalid_command_payload", {"field": "priority"})
    return MaintenanceWorkOrderDispatchPayload(
        work_order_id=work_order_id,
        assigned_team_member_id=assigned_team_member_id,
        priority=priority,
    )


_GUEST_RECOVERY_ACTION_CODES = (
    "service-recovery-voucher",
    "room-upgrade",
    "apology-call",
    "complimentary-service-credit",
)


def _parse_guest_recovery_action_payload(
    payload: Mapping[str, Any],
) -> GuestRecoveryActionPayload | RejectedCommand:
    unknown = _reject_unknown_keys(
        payload, _PAYLOAD_ALLOWED_KEYS[CMD_GUEST_RECOVERY_ACTION_ISSUE], "payload"
    )
    if unknown is not None:
        return unknown

    booking_id = payload.get("booking_id")
    guest_party_id = payload.get("guest_party_id")
    action_code = payload.get("action_code")
    value_gbp = payload.get("value_gbp")
    if not _is_non_empty_str(booking_id):
        return RejectedCommand("invalid_command_payload", {"field": "booking_id"})
    if not _is_non_empty_str(guest_party_id):
        return RejectedCommand("invalid_command_payload", {"field": "guest_party_id"})
    if action_code not in _GUEST_RECOVERY_ACTION_CODES:
        return RejectedCommand("invalid_command_payload", {"field": "action_code"})
    if not _is_non_negative_finite(value_gbp):
        return RejectedCommand("invalid_command_payload", {"field": "value_gbp"})
    return GuestRecoveryActionPayload(
        booking_id=booking_id,
        guest_party_id=guest_party_id,
        action_code=action_code,
        value_gbp=float(value_gbp),
    )


def _parse_booking_inventory_plan_payload(
    payload: Mapping[str, Any],
) -> BookingInventoryPlanPayload | RejectedCommand:
    unknown = _reject_unknown_keys(
        payload, _PAYLOAD_ALLOWED_KEYS[CMD_BOOKING_INVENTORY_PLAN_APPLY], "payload"
    )
    if unknown is not None:
        return unknown

    booking_id = payload.get("booking_id")
    destination_hotel_id = payload.get("destination_hotel_id")
    destination_room_type = payload.get("destination_room_type")
    if not _is_non_empty_str(booking_id):
        return RejectedCommand("invalid_command_payload", {"field": "booking_id"})
    if not _is_non_empty_str(destination_hotel_id):
        return RejectedCommand("invalid_command_payload", {"field": "destination_hotel_id"})
    if destination_room_type not in _ROOM_TYPES:
        return RejectedCommand("invalid_command_payload", {"field": "destination_room_type"})
    return BookingInventoryPlanPayload(
        booking_id=booking_id,
        destination_hotel_id=destination_hotel_id,
        destination_room_type=destination_room_type,
    )


def _parse_workforce_shift_plan_payload(
    payload: Mapping[str, Any],
) -> WorkforceShiftPlanPayload | RejectedCommand:
    unknown = _reject_unknown_keys(
        payload, _PAYLOAD_ALLOWED_KEYS[CMD_WORKFORCE_SHIFT_PLAN_APPLY], "payload"
    )
    if unknown is not None:
        return unknown

    shift_id = payload.get("shift_id")
    destination_hotel_id = payload.get("destination_hotel_id")
    if not _is_non_empty_str(shift_id):
        return RejectedCommand("invalid_command_payload", {"field": "shift_id"})
    if not _is_non_empty_str(destination_hotel_id):
        return RejectedCommand("invalid_command_payload", {"field": "destination_hotel_id"})
    return WorkforceShiftPlanPayload(
        shift_id=shift_id, destination_hotel_id=destination_hotel_id
    )


def _parse_food_beverage_service_plan_payload(
    payload: Mapping[str, Any],
) -> FoodBeverageServicePlanPayload | RejectedCommand:
    unknown = _reject_unknown_keys(
        payload, _PAYLOAD_ALLOWED_KEYS[CMD_FOOD_BEVERAGE_SERVICE_PLAN_APPLY], "payload"
    )
    if unknown is not None:
        return unknown

    plan_id = payload.get("plan_id")
    covers_prepared = payload.get("covers_prepared")
    if not _is_non_empty_str(plan_id):
        return RejectedCommand("invalid_command_payload", {"field": "plan_id"})
    if not _is_non_negative_int(covers_prepared):
        return RejectedCommand("invalid_command_payload", {"field": "covers_prepared"})
    return FoodBeverageServicePlanPayload(plan_id=plan_id, covers_prepared=covers_prepared)


_ENERGY_CONTROL_ACTIONS = ("reduce-setpoint", "increase-setpoint", "reset-normal")


def _parse_energy_control_plan_payload(
    payload: Mapping[str, Any],
) -> EnergyControlPlanPayload | RejectedCommand:
    unknown = _reject_unknown_keys(
        payload, _PAYLOAD_ALLOWED_KEYS[CMD_ENERGY_CONTROL_PLAN_APPLY], "payload"
    )
    if unknown is not None:
        return unknown

    meter_id = payload.get("meter_id")
    control_action = payload.get("control_action")
    target_reading_kwh = payload.get("target_reading_kwh")
    if not _is_non_empty_str(meter_id):
        return RejectedCommand("invalid_command_payload", {"field": "meter_id"})
    if control_action not in _ENERGY_CONTROL_ACTIONS:
        return RejectedCommand("invalid_command_payload", {"field": "control_action"})
    if not _is_non_negative_finite(target_reading_kwh):
        return RejectedCommand("invalid_command_payload", {"field": "target_reading_kwh"})
    return EnergyControlPlanPayload(
        meter_id=meter_id,
        control_action=control_action,
        target_reading_kwh=float(target_reading_kwh),
    )


_PAYLOAD_ALLOWED_KEYS: dict[str, frozenset[str]] = {
    CMD_HOTEL_RECOVERY_EXECUTE: frozenset(
        {
            "work_order_id",
            "rooms_to_restore",
            "relocations",
            "shift_moves",
            "guest_communication_actions",
        }
    ),
    CMD_ROOM_READINESS_PLAN_APPLY: frozenset(
        {"room_ids", "target_status", "maintenance_work_order_id"}
    ),
    CMD_MAINTENANCE_WORK_ORDER_DISPATCH: frozenset(
        {"work_order_id", "assigned_team_member_id", "priority"}
    ),
    CMD_GUEST_RECOVERY_ACTION_ISSUE: frozenset(
        {"booking_id", "guest_party_id", "action_code", "value_gbp"}
    ),
    CMD_BOOKING_INVENTORY_PLAN_APPLY: frozenset(
        {"booking_id", "destination_hotel_id", "destination_room_type"}
    ),
    CMD_WORKFORCE_SHIFT_PLAN_APPLY: frozenset({"shift_id", "destination_hotel_id"}),
    CMD_FOOD_BEVERAGE_SERVICE_PLAN_APPLY: frozenset({"plan_id", "covers_prepared"}),
    CMD_ENERGY_CONTROL_PLAN_APPLY: frozenset(
        {"meter_id", "control_action", "target_reading_kwh"}
    ),
}
assert set(_PAYLOAD_ALLOWED_KEYS) == set(COMMAND_TYPES)


# Production command_type -> payload dataclass mapping. Exposed publicly so
# both ``parse_command`` (typed-envelope validation) and tests can assert
# against the single source of truth, rather than a private test-local copy.
COMMAND_PAYLOAD_TYPES: dict[str, type] = {
    CMD_HOTEL_RECOVERY_EXECUTE: HotelRecoveryPayload,
    CMD_ROOM_READINESS_PLAN_APPLY: RoomReadinessPlanPayload,
    CMD_MAINTENANCE_WORK_ORDER_DISPATCH: MaintenanceWorkOrderDispatchPayload,
    CMD_GUEST_RECOVERY_ACTION_ISSUE: GuestRecoveryActionPayload,
    CMD_BOOKING_INVENTORY_PLAN_APPLY: BookingInventoryPlanPayload,
    CMD_WORKFORCE_SHIFT_PLAN_APPLY: WorkforceShiftPlanPayload,
    CMD_FOOD_BEVERAGE_SERVICE_PLAN_APPLY: FoodBeverageServicePlanPayload,
    CMD_ENERGY_CONTROL_PLAN_APPLY: EnergyControlPlanPayload,
}
assert set(COMMAND_PAYLOAD_TYPES) == set(COMMAND_TYPES)
assert len(set(COMMAND_PAYLOAD_TYPES.values())) == 8


# Production command_type -> payload parser mapping. Exposed publicly (see
# ``COMMAND_PAYLOAD_TYPES`` above) for the same reason.
COMMAND_PAYLOAD_PARSERS = {
    CMD_HOTEL_RECOVERY_EXECUTE: _parse_hotel_recovery_payload,
    CMD_ROOM_READINESS_PLAN_APPLY: _parse_room_readiness_plan_payload,
    CMD_MAINTENANCE_WORK_ORDER_DISPATCH: _parse_maintenance_work_order_dispatch_payload,
    CMD_GUEST_RECOVERY_ACTION_ISSUE: _parse_guest_recovery_action_payload,
    CMD_BOOKING_INVENTORY_PLAN_APPLY: _parse_booking_inventory_plan_payload,
    CMD_WORKFORCE_SHIFT_PLAN_APPLY: _parse_workforce_shift_plan_payload,
    CMD_FOOD_BEVERAGE_SERVICE_PLAN_APPLY: _parse_food_beverage_service_plan_payload,
    CMD_ENERGY_CONTROL_PLAN_APPLY: _parse_energy_control_plan_payload,
}
assert set(COMMAND_PAYLOAD_PARSERS) == set(COMMAND_TYPES)
assert len(set(COMMAND_PAYLOAD_PARSERS.values())) == 8


# ---------------------------------------------------------------------------
# Envelope parsing
# ---------------------------------------------------------------------------


def _validate_typed_envelope(envelope: CommandEnvelope) -> CommandEnvelope | RejectedCommand:
    """Validate an already-typed ``CommandEnvelope`` exactly like a mapping.

    A hand-built ``CommandEnvelope`` (e.g. constructed directly by a caller,
    bypassing the mapping parser) must be held to the same field-level
    contract as a raw mapping — non-empty identifiers, non-negative
    versions, a finite non-negative estimated value, and a payload whose
    *exact* runtime type matches the one registered for its command type
    *and* whose field values pass the exact same registered parser as a
    mapping payload would (enum membership, numeric bounds, duplicate-id
    checks, etc.) — a frozen payload dataclass is not, by construction,
    guaranteed to hold business-valid values. Returns the original
    *envelope* instance unchanged when the re-validated payload is
    value-equal to the one supplied (identity preserved for callers such
    as idempotent re-parsing); otherwise returns a new ``CommandEnvelope``
    carrying the freshly parsed/normalized payload.
    """
    if not _is_non_empty_str(envelope.command_id):
        return RejectedCommand("invalid_command_payload", {"field": "command_id"})

    if not _is_non_empty_str(envelope.workflow_id):
        return RejectedCommand("invalid_command_payload", {"field": "workflow_id"})

    if not _is_non_empty_str(envelope.command_type):
        return RejectedCommand("invalid_command_payload", {"field": "command_type"})
    if envelope.command_type not in COMMAND_TYPES:
        return RejectedCommand("unknown_command_type", {"command_type": envelope.command_type})

    raw_expected_versions = envelope.expected_versions
    if not isinstance(raw_expected_versions, Mapping) or len(raw_expected_versions) == 0:
        return RejectedCommand("invalid_command_payload", {"field": "expected_versions"})
    for entity_id, version in raw_expected_versions.items():
        if not _is_non_empty_str(entity_id):
            return RejectedCommand(
                "invalid_command_payload", {"field": "expected_versions.key"}
            )
        if not _is_non_negative_int(version):
            return RejectedCommand(
                "invalid_command_payload", {"field": f"expected_versions[{entity_id}]"}
            )

    if not _is_non_empty_str(envelope.evidence_digest):
        return RejectedCommand("invalid_command_payload", {"field": "evidence_digest"})

    if not _is_non_empty_str(envelope.reason_code):
        return RejectedCommand("invalid_command_payload", {"field": "reason_code"})

    if not _is_non_negative_finite(envelope.estimated_value_gbp):
        return RejectedCommand("invalid_command_payload", {"field": "estimated_value_gbp"})

    if envelope.approval_ref is not None and not _is_non_empty_str(envelope.approval_ref):
        return RejectedCommand("invalid_command_payload", {"field": "approval_ref"})

    expected_payload_type = COMMAND_PAYLOAD_TYPES[envelope.command_type]
    if type(envelope.payload) is not expected_payload_type:
        return RejectedCommand(
            "invalid_command_payload",
            {"field": "payload", "error": "payload_type_mismatch"},
        )

    # Exact-type checking above only proves the payload is *shaped* like
    # the right dataclass — a frozen dataclass instance can still be
    # hand-built with out-of-enum/out-of-bounds field values (e.g.
    # ``target_status="TOTALLY-BOGUS"``) that would never survive the
    # mapping parser. Re-run the payload through the exact same
    # registered parser used for mapping input by serializing it back to
    # a plain mapping first, so both entry points share one validation
    # boundary.
    payload_parser = COMMAND_PAYLOAD_PARSERS[envelope.command_type]
    reparsed_payload = payload_parser(_to_jsonable(envelope.payload))
    if isinstance(reparsed_payload, RejectedCommand):
        return reparsed_payload

    if reparsed_payload == envelope.payload:
        return envelope

    return CommandEnvelope(
        command_id=envelope.command_id,
        workflow_id=envelope.workflow_id,
        command_type=envelope.command_type,
        expected_versions=envelope.expected_versions,
        evidence_digest=envelope.evidence_digest,
        reason_code=envelope.reason_code,
        estimated_value_gbp=float(envelope.estimated_value_gbp),
        payload=reparsed_payload,
        approval_ref=envelope.approval_ref,
    )


def parse_command(command: Any) -> CommandEnvelope | RejectedCommand:
    """Parse and validate a raw command mapping into a typed envelope.

    Validates an already-typed ``CommandEnvelope`` with the exact same
    field-level rules as a raw mapping (see ``_validate_typed_envelope``)
    rather than passing it through unchecked. Never mutates *command*.
    """
    if isinstance(command, CommandEnvelope):
        return _validate_typed_envelope(command)

    if not isinstance(command, Mapping):
        return RejectedCommand("invalid_command_payload", {"field": "command", "error": "not_a_mapping"})

    unknown_envelope_keys = _reject_unknown_keys(command, ENVELOPE_KEYS, "command")
    if unknown_envelope_keys is not None:
        return unknown_envelope_keys

    command_id = command.get("command_id")
    if not _is_non_empty_str(command_id):
        return RejectedCommand("invalid_command_payload", {"field": "command_id"})

    workflow_id = command.get("workflow_id")
    if not _is_non_empty_str(workflow_id):
        return RejectedCommand("invalid_command_payload", {"field": "workflow_id"})

    command_type = command.get("command_type")
    if not _is_non_empty_str(command_type):
        return RejectedCommand("invalid_command_payload", {"field": "command_type"})
    if command_type not in COMMAND_TYPES:
        return RejectedCommand("unknown_command_type", {"command_type": command_type})

    raw_expected_versions = command.get("expected_versions")
    if not isinstance(raw_expected_versions, Mapping) or len(raw_expected_versions) == 0:
        return RejectedCommand("invalid_command_payload", {"field": "expected_versions"})
    expected_versions: dict[str, int] = {}
    for entity_id, version in raw_expected_versions.items():
        if not _is_non_empty_str(entity_id):
            return RejectedCommand(
                "invalid_command_payload", {"field": "expected_versions.key"}
            )
        if not _is_non_negative_int(version):
            return RejectedCommand(
                "invalid_command_payload", {"field": f"expected_versions[{entity_id}]"}
            )
        expected_versions[entity_id] = version

    evidence_digest = command.get("evidence_digest")
    if not _is_non_empty_str(evidence_digest):
        return RejectedCommand("invalid_command_payload", {"field": "evidence_digest"})

    reason_code = command.get("reason_code")
    if not _is_non_empty_str(reason_code):
        return RejectedCommand("invalid_command_payload", {"field": "reason_code"})

    estimated_value_gbp = command.get("estimated_value_gbp")
    if not _is_non_negative_finite(estimated_value_gbp):
        return RejectedCommand("invalid_command_payload", {"field": "estimated_value_gbp"})

    approval_ref = command.get("approval_ref")
    if approval_ref is not None and not _is_non_empty_str(approval_ref):
        return RejectedCommand("invalid_command_payload", {"field": "approval_ref"})

    raw_payload = command.get("payload")
    if not isinstance(raw_payload, Mapping):
        return RejectedCommand("invalid_command_payload", {"field": "payload"})

    payload_parser = COMMAND_PAYLOAD_PARSERS[command_type]
    parsed_payload = payload_parser(raw_payload)
    if isinstance(parsed_payload, RejectedCommand):
        return parsed_payload

    return CommandEnvelope(
        command_id=command_id,
        workflow_id=workflow_id,
        command_type=command_type,
        expected_versions=expected_versions,
        evidence_digest=evidence_digest,
        reason_code=reason_code,
        estimated_value_gbp=float(estimated_value_gbp),
        payload=parsed_payload,
        approval_ref=approval_ref,
    )


# ---------------------------------------------------------------------------
# Idempotency signature
# ---------------------------------------------------------------------------


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _to_jsonable(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    return value


def canonical_signature(envelope: CommandEnvelope) -> str:
    """Return a stable signature capturing every semantically relevant field.

    Two envelopes with the same ``command_id`` and a byte/semantic-equivalent
    payload (list vs tuple, key order) produce the same signature.
    """
    canonical = {
        "command_id": envelope.command_id,
        "workflow_id": envelope.workflow_id,
        "command_type": envelope.command_type,
        "expected_versions": _to_jsonable(dict(envelope.expected_versions)),
        "evidence_digest": envelope.evidence_digest,
        "reason_code": envelope.reason_code,
        "estimated_value_gbp": envelope.estimated_value_gbp,
        "approval_ref": envelope.approval_ref,
        "payload": _to_jsonable(envelope.payload),
    }
    return json.dumps(canonical, sort_keys=True, default=str)
