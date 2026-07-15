"""Network-incident deterministic decision activities.

The network-incident responder turns a live cell-site failure into a typed
``reroute_sessions`` command across two REAL deterministic boundaries so the
orchestration checkpoints match the actual phases the operator surfaces render:

  1. :func:`network_incident_impact_activity` — **Impact Diagnosis**. Reads the
     failed site, its healthy neighbours (with spare capacity) and the affected
     sessions, and diagnoses the blast radius: which neighbours can absorb load
     and the deterministic order in which sessions should be moved (voice first
     for call continuity, then by session id). No mutation, no reasoning model —
     pure gather + ordering.
  2. :func:`network_incident_reroute_activity` — **Reroute Planning**. Greedily
     plans each diagnosed session's assignment to the healthiest neighbour that
     still fits and emits a typed ``reroute_sessions`` command, or ``None`` when
     nothing can be done. FastAPI's world bridge validates and applies the
     command to the real session actors — this activity never mutates the world
     itself.

Both steps are deterministic (no agent / GHCP call); the split exists so the
orchestration emits truthful ``step.started`` / ``step.completed`` checkpoints
for the two boundaries rather than one opaque combined activity.
"""
from __future__ import annotations


def network_incident_impact_activity(payload: dict) -> dict:
    """Diagnose the incident blast radius (deterministic; no mutation).

    Returns ``{"diagnosis": {...}, "reasoning": None}`` on success or
    ``{"diagnosis": None, "reasoning": "<why nothing can be done>"}`` for the
    explicit no-op cases (no incident site, no affected sessions, no healthy
    neighbour capacity). ``diagnosis`` carries the incident id, the healthy
    neighbours' spare-capacity map, the deterministically ordered affected
    sessions, and the affected total — everything the reroute step needs.
    """
    observation = payload.get("observation") or {}
    incident = observation.get("incident_site") or {}
    incident_id = incident.get("id")
    neighbors = observation.get("neighbor_sites") or []
    affected = observation.get("affected_sessions") or []

    if not incident_id:
        return {"diagnosis": None, "reasoning": "no incident site in observation"}
    if not affected:
        return {"diagnosis": None, "reasoning": "no affected sessions to reroute"}

    spare: dict[str, float] = {}
    for neighbor in neighbors:
        if neighbor.get("status") != "healthy":
            continue
        site_id = neighbor.get("id")
        headroom = float(neighbor.get("spare_mbps", 0.0))
        if site_id and headroom > 0:
            spare[site_id] = headroom
    if not spare:
        return {"diagnosis": None, "reasoning": "no healthy neighbour capacity available"}

    # Voice first (call continuity), then deterministic by session ID.
    ordered = sorted(
        affected,
        key=lambda s: (0 if s.get("kind") == "voice" else 1, str(s.get("id"))),
    )

    return {
        "diagnosis": {
            "incident_site_id": incident_id,
            "spare_capacity": spare,
            "affected_sessions": ordered,
            "affected_total": len(affected),
        },
        "reasoning": None,
    }


def network_incident_reroute_activity(payload: dict) -> dict:
    """Plan the reroute assignments and emit a typed ``reroute_sessions`` command.

    Consumes the :func:`network_incident_impact_activity` diagnosis (under
    ``payload["diagnosis"]``) plus the trace id. Greedily plans each session's
    assignment to the healthiest neighbour that still fits; returns
    ``{"command": None, "reasoning": ...}`` when the diagnosis was a no-op or
    no neighbour can hold any session.
    """
    trace_id = str(payload.get("trace_id") or "unknown")
    diagnosis = payload.get("diagnosis")
    if not diagnosis:
        # Impact diagnosis found nothing to do; carry its reason forward.
        return {
            "command": None,
            "reasoning": payload.get("diagnosis_reasoning")
            or "no reroute diagnosis available",
        }

    incident_id = diagnosis.get("incident_site_id")
    spare: dict[str, float] = dict(diagnosis.get("spare_capacity") or {})
    ordered = diagnosis.get("affected_sessions") or []
    neighbour_count = len(spare)

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
    assignment_word = "assignment" if len(assignments) == 1 else "assignments"
    neighbour_word = "neighbour" if neighbour_count == 1 else "neighbours"
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
            f"incident at {incident_id}: planned {len(assignments)} session "
            f"{assignment_word} across {neighbour_count} {neighbour_word}"
            + (f" ({voice} voice prioritised)" if voice else "")
            + (f"; {dropped} unassigned (no capacity)" if dropped else "")
        ),
    }
