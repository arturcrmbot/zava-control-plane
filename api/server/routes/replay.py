"""Time-scrub replay snapshot endpoint (pitch-j4).

Lets the cosmic-lens HUD reconstruct what the org looked like at any
``at`` timestamp in the recent past by reading the in-memory audit
ledger (``api.server.services.audit_logger.AuditLogger``).

This is an *approximation*, not a perfect Kuzu time-travel: we replay
``entity.upserted`` / ``entity.linked`` / ``decision.recorded`` audit
entries up to ``at`` and group by entity id (last write wins). Good
enough for the "leave it 4h and come back" rewind UX without paying for
a temporal store.
"""
from __future__ import annotations

import time as _time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from api.server.state import app_state
from api.server.services.replay.mode import is_replay
from api.server.services.replay.player import current_player

router = APIRouter(prefix="/api/replay")

# Window of audit entries returned in ``recent_events`` — the 60s
# leading up to ``at``. Matches the spec; ``at + small`` clock skew is
# tolerated by the future-timestamp guard below.
_RECENT_EVENTS_WINDOW_S = 60.0
# A small grace so a client clock that's a couple of seconds ahead of
# the server doesn't trigger 400. Anything beyond is rejected as
# "future" because we can't know what the org will look like.
_FUTURE_GRACE_S = 5.0


def _entries_before(at: float) -> list[dict]:
    """Return audit entries whose ``timestamp`` <= ``at``.

    The audit logger is in-memory and append-ordered; we don't bother
    with bisect because the demo ledger is bounded.
    """
    audit = getattr(app_state, "audit", None)
    if audit is None:
        return []
    out: list[dict] = []
    for e in audit.list():
        ts = e.get("timestamp")
        if ts is None:
            continue
        if ts <= at:
            out.append(e)
    return out


def _replay_entities(entries: list[dict]) -> list[dict[str, Any]]:
    """Group ``entity.upserted`` audit entries by id; last write wins."""
    by_id: dict[str, dict[str, Any]] = {}
    for e in entries:
        if e.get("action") != "entity.upserted":
            continue
        details = e.get("details") or {}
        eid = details.get("id")
        if not eid:
            continue
        by_id[eid] = {
            "id": eid,
            "kind": details.get("kind"),
            "workflow_id": details.get("workflow_id"),
            "source_workflows": list(details.get("source_workflows") or []),
            "as_of": e.get("timestamp"),
        }
    return list(by_id.values())


def _replay_in_flight_workflows(entries: list[dict]) -> list[dict[str, Any]]:
    """Best-effort reconstruction of in-flight workflows at ``at``.

    A workflow is "in flight" if we saw audit entries naming its
    ``workflow_id`` and have not seen a terminal ``decision.recorded``
    with a final verdict (``approve``/``reject``) for it. The audit
    ledger doesn't carry full workflow state, so the returned objects
    are deliberately minimal — id, last_action, last_seen.
    """
    last_seen: dict[str, dict[str, Any]] = {}
    terminated: set[str] = set()
    for e in entries:
        details = e.get("details") or {}
        wid = details.get("workflow_id")
        if not wid:
            continue
        last_seen[wid] = {
            "id": wid,
            "last_action": e.get("action"),
            "last_seen": e.get("timestamp"),
        }
        if e.get("action") == "decision.recorded":
            verdict = (details.get("verdict") or "").lower()
            if verdict in ("approve", "reject", "approved", "rejected"):
                terminated.add(wid)
    return [w for wid, w in last_seen.items() if wid not in terminated]


def _recent_events(entries: list[dict], at: float) -> list[dict[str, Any]]:
    """Return audit entries in the ``[at - 60s, at]`` window, projected
    onto the small shape the HUD consumes.
    """
    cutoff = at - _RECENT_EVENTS_WINDOW_S
    out: list[dict[str, Any]] = []
    for e in entries:
        ts = e.get("timestamp")
        if ts is None or ts < cutoff:
            continue
        out.append({
            "type": e.get("action"),
            "at": ts,
            "details": e.get("details") or {},
        })
    return out


def _kpis_at(entities: list[dict[str, Any]],
             in_flight: list[dict[str, Any]],
             recent: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Approximate cosmic-lens KPIs using only the replayed slice.

    Three lightweight gauges so the HUD has *something* to show in
    replay mode without re-running every KPI computation against a
    historical graph that doesn't exist.
    """
    kinds: dict[str, int] = {}
    for ent in entities:
        k = ent.get("kind") or "unknown"
        kinds[k] = kinds.get(k, 0) + 1
    return [
        {"label": "entities", "value": len(entities), "unit": ""},
        {"label": "in_flight_workflows", "value": len(in_flight), "unit": ""},
        {"label": "events_last_60s", "value": len(recent), "unit": ""},
    ]


@router.get("/snapshot")
def replay_snapshot(at: float = Query(..., description="Unix timestamp")) -> dict[str, Any]:
    """Reconstruct the org as it appeared at ``at`` from the audit ledger.

    Returns ``{ at, entities, in_flight_workflows, recent_events,
    kpis_at }``. ``at`` in the future is a 400.
    """
    now = _time.time()
    if at > now + _FUTURE_GRACE_S:
        raise HTTPException(status_code=400, detail="at is in the future")
    entries = _entries_before(at)
    entities = _replay_entities(entries)
    in_flight = _replay_in_flight_workflows(entries)
    recent = _recent_events(entries, at)
    return {
        "at": at,
        "entities": entities,
        "in_flight_workflows": in_flight,
        "recent_events": recent,
        "kpis_at": _kpis_at(entities, in_flight, recent),
    }


@router.get("/meta")
def replay_meta() -> dict[str, Any]:
    """Tell the front-end whether this process is serving live data or a
    replay tape. In replay mode, expose the recording provenance needed
    to distinguish the tape's vertical from the active runtime pack.
    """
    if not is_replay():
        return {"mode": "live"}
    player = current_player()
    if player is None:
        # Replay mode but no player active (boot race / teardown)
        return {"mode": "replay"}
    meta = player.meta
    selected_vertical = getattr(meta, "selected_vertical", None)
    active_vertical = app_state.runtime.pack.name
    return {
        "mode": "replay",
        "tape_id": meta.tape_id,
        "recorded_at": meta.recorded_at,
        "duration_s": meta.duration_s,
        "current_t": player.current_t(),
        "selected_vertical": selected_vertical,
        "active_vertical": active_vertical,
        "pack_matches_tape": (
            selected_vertical == active_vertical
            if selected_vertical is not None
            else None
        ),
    }
