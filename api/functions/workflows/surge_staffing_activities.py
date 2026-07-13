"""Surge-staffing decision activity — selects reserve workers for reallocation.

Receives an actor-level observation (queued tickets, reserve workers) and
returns a typed ``reallocate_workers`` command targeting the highest-pressure
workers, or ``None`` if no action is needed.
"""
from __future__ import annotations

import math
from collections import Counter


def surge_staffing_decide_activity(payload: dict) -> dict:
    trace_id = str(payload.get("trace_id") or "unknown")
    observation = payload.get("observation") or {}
    queued = observation.get("queued_tickets") or []
    reserve = observation.get("reserve_workers") or []

    if not queued:
        return {"command": None, "reasoning": "no queued tickets"}
    if not reserve:
        return {"command": None, "reasoning": "no reserve workers"}

    pressure = Counter(ticket.get("required_skill") for ticket in queued)
    ranked = sorted(
        reserve,
        key=lambda worker: (
            -sum(pressure.get(skill, 0) for skill in worker.get("skills", [])),
            worker["id"],
        ),
    )
    count = min(len(ranked), max(1, math.ceil(len(queued) / 20)))
    worker_ids = [worker["id"] for worker in ranked[:count]]
    return {
        "command": {
            "command_id": f"cmd-{trace_id}-staff",
            "trace_id": trace_id,
            "issued_by": "surge_staffing",
            "type": "reallocate_workers",
            "payload": {
                "worker_ids": worker_ids,
                "from_team_id": "TEAM-RESERVE",
                "to_team_id": "TEAM-SUPPORT",
                "duration_minutes": 60,
            },
        },
        "reasoning": (
            f"backlog={len(queued)}; selected {len(worker_ids)} reserve workers "
            f"against skill pressure {dict(pressure)}"
        ),
    }
