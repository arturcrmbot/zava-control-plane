"""Graph-shape adapter for the fleet-employee-onboarding-induction-planner validator.

In-graph validators return `{"ok": bool, ...}` so TrackedExecutor can emit
`validator.blocked` cleanly. Mirrors validate_classification_schema_node.py.
"""
from __future__ import annotations


_ALLOWED_VERDICT = {"booked", "unbookable"}


async def execute(input: dict) -> dict:
    payload = input.get("induction_planner") or {}

    verdict = payload.get("verdict")
    if verdict not in _ALLOWED_VERDICT:
        return {
            "ok": False,
            "blocked_reason": f"verdict must be one of {sorted(_ALLOWED_VERDICT)}; got {verdict!r}",
            "induction_planner": payload,
        }

    slot = payload.get("slot")
    if not isinstance(slot, dict):
        return {
            "ok": False,
            "blocked_reason": "slot must be a dict with start + end ISO timestamps",
            "induction_planner": payload,
        }
    if not (isinstance(slot.get("start"), str) and isinstance(slot.get("end"), str)):
        return {
            "ok": False,
            "blocked_reason": "slot.start and slot.end must be ISO-8601 strings",
            "induction_planner": payload,
        }

    attendees = payload.get("attendees")
    if not isinstance(attendees, list) or len(attendees) < 1:
        return {
            "ok": False,
            "blocked_reason": "attendees must be a non-empty list of employee_id strings",
            "induction_planner": payload,
        }

    room_id = payload.get("room_id")
    event_id = payload.get("event_id")

    # Cross-field invariant: booked iff non-empty event_id AND non-empty room_id.
    is_booked = bool(event_id) and bool(room_id)
    if (verdict == "booked") != is_booked:
        return {
            "ok": False,
            "blocked_reason": (
                f"verdict/event_id inconsistent: verdict={verdict!r} but "
                f"room_id={room_id!r} event_id={event_id!r}"
            ),
            "induction_planner": payload,
        }

    return {
        "ok": True,
        "induction_planner": payload,
        "verdict": verdict,
    }
