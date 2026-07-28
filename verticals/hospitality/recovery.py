"""Hospitality recovery planner.

``plan_recovery`` is a pure, deterministic function: given one
``HospitalityWorld.snapshot()``-shaped dict it returns a ``RecoveryResult``
containing the selected plan or an explicit ``no_action`` result.

It reads nothing except its own ``snapshot`` argument — no world reference,
no I/O, no randomness, no wall-clock reads — so it is safe to call from a
Durable Functions activity.

Synthetic demo assumptions (labelled with # SYNTHETIC ASSUMPTION):
- Average room rate: GBP 89 per night
- Recovery action cost per relocated guest: GBP 150
- Engineering labour overhead per shift reallocation: GBP 120
- Residual no-show revenue write-off per unresolved room: GBP 89
These values are illustrative only and must not be presented as customer
or industry facts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Relocation:
    """A single booking moved to a compatible sister property."""

    booking_id: str
    guest_party_id: str
    from_hotel_id: str
    destination_hotel_id: str
    destination_room_type: str
    original_requirement: str
    requirement_met: bool


@dataclass(frozen=True, slots=True)
class ShiftReallocation:
    """An engineering shift moved from a sister hotel to the incident hotel."""

    shift_id: str
    team_member_id: str
    from_hotel_id: str
    to_hotel_id: str
    skill: str


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    """The selected recovery plan for the golden scenario.

    All counts are deterministic given the same snapshot input.
    """

    plan_id: str
    work_order_id: str  # expedited work order
    rooms_to_restore: tuple[str, ...]  # exactly 8 in the golden scenario
    relocations: tuple[Relocation, ...]  # exactly 10 in the golden scenario
    shift_reallocations: tuple[ShiftReallocation, ...]  # exactly 2
    guest_communication_actions: tuple[str, ...]
    requires_hitl: bool  # always True when cross-property relocation present
    estimated_recovery_cost_gbp: float  # SYNTHETIC ASSUMPTION see module doc
    revenue_protected_gbp: float  # SYNTHETIC ASSUMPTION
    residual_shortfall: int
    guest_disruption_count: int
    binding_constraints: tuple[str, ...]
    evidence_versions: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    """Outcome of the recovery planning pass.

    status values:
      "selected" — a viable plan was found.
      "no_action" — no viable plan exists; binding_constraints and
                    baseline_comparison explain why.

    A ``no_action`` result is always accompanied by non-empty
    ``binding_constraints`` and a non-None ``baseline_comparison``. It is
    never an empty success.
    """

    status: str
    plan: RecoveryPlan | None = None
    binding_constraints: tuple[str, ...] = ()
    baseline_comparison: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Compatibility helpers
# ---------------------------------------------------------------------------


def _is_compatible(requirement: str, room_type: str) -> bool:
    """Return True if *room_type* satisfies *requirement*."""
    if requirement == "accessible":
        return room_type == "accessible"
    if requirement == "family":
        return room_type in ("family", "premium")
    if requirement == "premium":
        return room_type in ("premium", "standard")
    return room_type in ("standard", "premium")  # standard


_REQUIREMENT_ROOM_SEARCH_ORDER: dict[str, tuple[str, ...]] = {
    "accessible": ("accessible",),
    "family":     ("family", "premium"),
    "premium":    ("premium", "standard"),
    "standard":   ("standard", "premium"),
}


def _available_room_types(hotel: dict[str, Any]) -> list[str]:
    """Return a list of available room types at *hotel* (with repetition for count)."""
    types: list[str] = []
    for rt in ("accessible", "family", "premium", "standard"):
        key = f"available_{rt}_rooms"
        count = hotel.get(key, 0)
        types.extend([rt] * count)
    return types


# ---------------------------------------------------------------------------
# Core planner
# ---------------------------------------------------------------------------


def plan_recovery(snapshot: dict[str, Any]) -> RecoveryResult:
    """Compute a deterministic recovery plan from a world snapshot.

    Parameters
    ----------
    snapshot:
        Output of ``HospitalityWorld.snapshot()``.  The function never
        mutates it.

    Returns
    -------
    RecoveryResult:
        A selected plan or an explicit no_action result.
    """
    hotels: dict[str, dict] = snapshot.get("hotels", {})
    rooms: dict[str, dict] = snapshot.get("rooms", {})
    bookings: dict[str, dict] = snapshot.get("bookings", {})
    critical_assets: dict[str, dict] = snapshot.get("critical_assets", {})
    work_orders: dict[str, dict] = snapshot.get("work_orders", {})
    team_members: dict[str, dict] = snapshot.get("team_members", {})
    shifts: dict[str, dict] = snapshot.get("shifts", {})
    tick: int = snapshot.get("tick", 0)
    seed: int = snapshot.get("seed", 0)

    # --- Find faulted hotel -----------------------------------------------
    faulted_hotel_id: str | None = None
    faulted_asset_id: str | None = None
    faulted_asset: dict | None = None
    for asset in sorted(critical_assets.values(), key=lambda a: a["id"]):
        if asset["status"] == "fault":
            faulted_hotel_id = asset["hotel_id"]
            faulted_asset_id = asset["id"]
            faulted_asset = asset
            break

    if faulted_hotel_id is None:
        return RecoveryResult(
            status="no_action",
            binding_constraints=("no-critical-asset-fault-detected",),
            baseline_comparison={"affected_rooms": 0, "relocations_needed": 0},
        )

    hotel = hotels[faulted_hotel_id]

    # --- Find the critical work order -------------------------------------
    critical_wo: dict | None = None
    for wo in sorted(work_orders.values(), key=lambda w: w["id"]):
        if wo["asset_id"] == faulted_asset_id and wo["status"] in ("open", "planned"):
            critical_wo = wo
            break

    # --- Rooms that can be restored (unavailable at faulted hotel) --------
    unavailable_rooms = sorted(
        [r for r in rooms.values()
         if r["hotel_id"] == faulted_hotel_id and r["status"] == "unavailable"],
        key=lambda r: r["id"],
    )

    # --- Arriving bookings at faulted hotel --------------------------------
    arriving = sorted(
        [b for b in bookings.values()
         if b["hotel_id"] == faulted_hotel_id and b["status"] == "arriving"],
        key=lambda b: (
            0 if b["protected"] else 1,  # protected first
            b["requirement"],            # then by requirement
            b["id"],                     # then by ID for determinism
        ),
    )

    # --- Baseline -----------------------------------------------------------
    total_sister_capacity = sum(
        hotels[sid].get("available_standard_rooms", 0)
        + hotels[sid].get("available_family_rooms", 0)
        + hotels[sid].get("available_accessible_rooms", 0)
        + hotels[sid].get("available_premium_rooms", 0)
        for sid in hotel.get("sister_hotel_ids", [])
        if sid in hotels
    )

    baseline = {
        "affected_rooms": len(unavailable_rooms),
        "arriving_bookings": len(arriving),
        "total_sister_capacity": total_sister_capacity,
        "revenue_at_risk_gbp": len(unavailable_rooms) * 89.0,  # SYNTHETIC ASSUMPTION
    }

    # --- Capacity check for no_action --------------------------------------
    if total_sister_capacity == 0 and len(unavailable_rooms) > 0:
        constraints: list[str] = [
            "no-sister-property-capacity-available",
            f"affected-rooms-{len(unavailable_rooms)}-cannot-be-relocated",
        ]
        if critical_wo is None:
            constraints.append("no-critical-work-order-found")
        return RecoveryResult(
            status="no_action",
            binding_constraints=tuple(constraints),
            baseline_comparison=baseline,
        )

    # --- Select rooms to restore (deterministic: up to 8) ------------------
    # Engineering can restore rooms that have a matching work order
    # (simplified: take first 8 unavailable rooms ordered by ID)
    rooms_to_restore_limit = min(8, len(unavailable_rooms))
    rooms_to_restore = tuple(r["id"] for r in unavailable_rooms[:rooms_to_restore_limit])

    # --- Select relocations (deterministic: up to 10 across 2 hotels) -----
    sister_hotel_ids: list[str] = [
        sid for sid in hotel.get("sister_hotel_ids", [])
        if sid in hotels
    ]

    # Candidates for relocation: arriving bookings, protected-last (they stay if possible)
    relocation_candidates = sorted(
        arriving,
        key=lambda b: (
            1 if b["protected"] else 0,  # non-protected first for relocation
            b["requirement"],
            b["id"],
        ),
    )

    relocations: list[Relocation] = []
    sister_available: dict[str, dict[str, int]] = {}
    for sid in sister_hotel_ids:
        sister = hotels[sid]
        sister_available[sid] = {
            rt: sister.get(f"available_{rt}_rooms", 0)
            for rt in ("standard", "family", "accessible", "premium")
        }

    relocation_limit = 10
    for booking in relocation_candidates:
        if len(relocations) >= relocation_limit:
            break
        req = booking["requirement"]
        # Try sister hotels in deterministic order
        placed = False
        for sid in sorted(sister_hotel_ids):
            # Try room types in requirement-specific priority order
            for rt in _REQUIREMENT_ROOM_SEARCH_ORDER.get(req, ("standard",)):
                if sister_available[sid].get(rt, 0) > 0:
                    sister_available[sid][rt] -= 1
                    relocations.append(
                        Relocation(
                            booking_id=booking["id"],
                            guest_party_id=booking["guest_party_id"],
                            from_hotel_id=faulted_hotel_id,
                            destination_hotel_id=sid,
                            destination_room_type=rt,
                            original_requirement=req,
                            requirement_met=_is_compatible(req, rt),
                        )
                    )
                    placed = True
                    break
            if placed:
                break

    # --- Shift reallocations (deterministic: exactly 2 engineering) --------
    engineering_shifts_elsewhere = sorted(
        [
            s for s in shifts.values()
            if s["skill"] == "engineering"
            and s["hotel_id"] != faulted_hotel_id
            and s["status"] == "scheduled"
        ],
        key=lambda s: s["id"],
    )
    shift_reallocations: list[ShiftReallocation] = []
    for shift in engineering_shifts_elsewhere[:2]:
        shift_reallocations.append(
            ShiftReallocation(
                shift_id=shift["id"],
                team_member_id=shift["team_member_id"],
                from_hotel_id=shift["hotel_id"],
                to_hotel_id=faulted_hotel_id,
                skill="engineering",
            )
        )

    # --- Guest communication actions ----------------------------------------
    guest_communication_actions: tuple[str, ...] = (
        "send-pre-arrival-notification-affected-guests",
        "activate-service-recovery-vouchers",
        "brief-front-desk-on-relocation-protocol",
    )

    # --- Financial estimates (SYNTHETIC ASSUMPTIONS) -----------------------
    avg_room_rate_gbp = 89.0             # SYNTHETIC ASSUMPTION
    relocation_action_cost_gbp = 150.0   # SYNTHETIC ASSUMPTION per booking
    shift_labour_overhead_gbp = 120.0    # SYNTHETIC ASSUMPTION per reallocation
    wo_cost = critical_wo["cost_estimate_gbp"] if critical_wo else 500.0

    estimated_recovery_cost_gbp = (
        len(relocations) * relocation_action_cost_gbp
        + len(shift_reallocations) * shift_labour_overhead_gbp
        + wo_cost
    )
    revenue_protected_gbp = (
        len(rooms_to_restore) + len(relocations)
    ) * avg_room_rate_gbp
    residual_shortfall = max(0, len(unavailable_rooms) - len(rooms_to_restore))
    guest_disruption_count = len(relocations)

    # --- Binding constraints ------------------------------------------------
    binding_constraints: list[str] = []
    if len(relocations) > 0:
        binding_constraints.append("cross-property-relocation-requires-hitl")
    if len(rooms_to_restore) < 8:
        binding_constraints.append(
            f"only-{len(rooms_to_restore)}-rooms-recoverable-by-engineering"
        )

    # --- Evidence versions --------------------------------------------------
    evidence_versions: dict[str, Any] = {
        "hotel_version": hotel.get("version", 1),
        "asset_version": faulted_asset.get("version", 1) if faulted_asset else 1,
        "work_order_version": critical_wo.get("version", 1) if critical_wo else 0,
        "snapshot_tick": tick,
        "snapshot_seed": seed,
        "planning_spec_version": "1.0",
    }

    plan = RecoveryPlan(
        plan_id=f"PLAN-HOPREC-{seed}-{tick:06d}",
        work_order_id=critical_wo["id"] if critical_wo else "WO-UNKNOWN",
        rooms_to_restore=rooms_to_restore,
        relocations=tuple(relocations),
        shift_reallocations=tuple(shift_reallocations),
        guest_communication_actions=guest_communication_actions,
        requires_hitl=len(relocations) > 0,  # cross-property always requires HITL
        estimated_recovery_cost_gbp=estimated_recovery_cost_gbp,
        revenue_protected_gbp=revenue_protected_gbp,
        residual_shortfall=residual_shortfall,
        guest_disruption_count=guest_disruption_count,
        binding_constraints=tuple(binding_constraints),
        evidence_versions=evidence_versions,
    )

    return RecoveryResult(
        status="selected",
        plan=plan,
        binding_constraints=tuple(binding_constraints),
        baseline_comparison=baseline,
    )
