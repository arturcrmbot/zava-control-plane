"""Network-incident decision activity — greedily reroutes degraded sessions.

Receives an actor-level observation (the failed site, its healthy neighbours
with spare capacity, and the affected/degraded sessions) and returns a typed
``reroute_sessions`` command that moves each session to a real neighbour site
with room, or ``None`` if nothing can be done. Voice sessions are placed first
(call continuity), then deterministically by session ID; each session goes to
the healthiest neighbour (most spare capacity) that can still hold it.

FastAPI's world bridge validates and applies the command to the real session
actors — this activity never mutates the world itself.
"""
from __future__ import annotations


def network_incident_decide_activity(payload: dict) -> dict:
    trace_id = str(payload.get("trace_id") or "unknown")
    observation = payload.get("observation") or {}
    incident = observation.get("incident_site") or {}
    incident_id = incident.get("id")
    neighbors = observation.get("neighbor_sites") or []
    affected = observation.get("affected_sessions") or []

    if not incident_id:
        return {"command": None, "reasoning": "no incident site in observation"}
    if not affected:
        return {"command": None, "reasoning": "no affected sessions to reroute"}

    spare: dict[str, float] = {}
    for neighbor in neighbors:
        if neighbor.get("status") != "healthy":
            continue
        site_id = neighbor.get("id")
        headroom = float(neighbor.get("spare_mbps", 0.0))
        if site_id and headroom > 0:
            spare[site_id] = headroom
    if not spare:
        return {"command": None, "reasoning": "no healthy neighbour capacity available"}

    # Voice first (call continuity), then deterministic by session ID.
    ordered = sorted(
        affected,
        key=lambda s: (0 if s.get("kind") == "voice" else 1, str(s.get("id"))),
    )

    assignments: list[dict[str, str]] = []
    dropped = 0
    for session in ordered:
        demand = float(session.get("demand_mbps", 0.0))
        candidates = sorted(
            (site_id for site_id, room in spare.items() if room + 1e-6 >= demand),
            key=lambda site_id: (-spare[site_id], site_id),
        )
        if not candidates:
            dropped += 1
            continue
        target = candidates[0]
        spare[target] = round(spare[target] - demand, 6)
        assignments.append({"session_id": str(session["id"]), "to_site_id": target})

    if not assignments:
        return {"command": None, "reasoning": "no neighbour has capacity for any session"}

    voice = sum(1 for s in ordered if s.get("kind") == "voice")
    return {
        "command": {
            "command_id": f"cmd-{trace_id}-reroute",
            "trace_id": trace_id,
            "issued_by": "network_incident",
            "type": "reroute_sessions",
            "payload": {
                "incident_site_id": incident_id,
                "assignments": assignments,
            },
        },
        "reasoning": (
            f"incident at {incident_id}: rerouted {len(assignments)}/{len(affected)} "
            f"sessions ({voice} voice prioritised) across {len(spare)} neighbours"
            + (f"; {dropped} dropped (no capacity)" if dropped else "")
        ),
    }
