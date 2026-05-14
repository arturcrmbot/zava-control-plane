"""Live decision/insight ticker — autonomous-domain-insights v1.1 Phase D1.

Two endpoints powering the bottom-strip live feed on the constellation HUD
(spec §9 polish item (c)):

  GET /api/ticker/recent  — REST snapshot of the last N Decisions + Insights
  GET /api/ticker/stream  — SSE stream of new Decisions + Insights

The stream subscribes to ``app_state.bus`` and filters for the two events
that signal a fresh write:

  * ``decision.recorded``                (emitted by EntityGraph.record_decision)
  * ``entity.upserted`` with kind=Insight (emitted by EntityGraph.upsert)

The bus-subscription approach is chosen over polling because the substrate
already emits these events in-process — no extra Cypher pressure, sub-ms
latency, and the per-connection pattern mirrors ``routes/blueprint.py``.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse

from api.server.state import app_state
from api.shared.events import FleetEvent

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ticker")


# Decided-on traversal walks every DECIDED_<KIND> shard. Mirrors the
# routing table in entity_graph._DECIDED_REL_BY_KIND but kept local so the
# ticker doesn't import a private symbol.
_DECIDED_RELS: tuple[str, ...] = (
    "DECIDED_PERSON", "DECIDED_MONEY", "DECIDED_ASSET", "DECIDED_ORG",
    "DECIDED_PERIOD", "DECIDED_PLACE", "DECIDED_BRAND", "DECIDED_CAMPAIGN",
    "DECIDED_PITCH", "DECIDED_MEDIAPLAN", "DECIDED_SUBSIDIARY",
)


def _iso(ts: Any) -> Any:
    return ts.isoformat() if hasattr(ts, "isoformat") else ts


def _decided_on_for(decision_id: str) -> list[str]:
    """Best-effort lookup of the target ids linked to a Decision.

    Walks each DECIDED_<KIND> shard and concatenates the resolved ids.
    Tolerant: any rel-table that doesn't exist on this graph (older
    fixtures) is silently skipped so the ticker never 500s on a partial
    schema.
    """
    out: list[str] = []
    g = app_state.entities
    for rel in _DECIDED_RELS:
        try:
            rows = g.query(
                f"MATCH (d:Decision {{id: $id}})-[:{rel}]->(n) "
                "RETURN n.id AS id",
                {"id": decision_id},
            )
        except Exception:
            continue
        for r in rows:
            tid = r.get("id")
            if tid:
                out.append(tid)
    return out


def _decision_to_item(row: dict[str, Any]) -> dict[str, Any]:
    decision_id = row.get("id")
    return {
        "kind": "Decision",
        "id": decision_id,
        "persona_role": row.get("persona_role"),
        "verdict": row.get("verdict"),
        "reason": row.get("reason"),
        "decided_at": _iso(row.get("decided_at")),
        "workflow_id": row.get("workflow_id"),
        "decided_on": _decided_on_for(decision_id) if decision_id else [],
    }


def _insight_to_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "Insight",
        "id": row.get("id"),
        "role": row.get("role"),
        "scope": row.get("scope"),
        "decided_at": _iso(row.get("decided_at")),
        "headline": row.get("headline") or "",
        "fingerprint": row.get("fingerprint") or "",
    }


def _fetch_recent(limit: int) -> list[dict[str, Any]]:
    """Return the last ``limit`` Decision + Insight items, decided_at desc.

    Two queries (one per kind), each capped at ``limit``, then merged and
    re-sorted. Cap-then-merge avoids walking every Decision in the graph
    just to find the top N when the two streams have wildly different
    cardinalities.
    """
    g = getattr(app_state, "entities", None)
    if g is None:
        return []
    lim = max(1, int(limit))
    decisions: list[dict[str, Any]] = []
    insights: list[dict[str, Any]] = []
    try:
        d_rows = g.query(
            "MATCH (d:Decision) "
            "RETURN d.id AS id, d.persona_role AS persona_role, "
            "       d.verdict AS verdict, d.reason AS reason, "
            "       d.decided_at AS decided_at, d.workflow_id AS workflow_id "
            f"ORDER BY d.decided_at DESC LIMIT {lim}",
        )
        decisions = [_decision_to_item(r) for r in d_rows]
    except Exception:
        log.exception("ticker: Decision fetch failed")
    try:
        i_rows = g.query(
            "MATCH (i:Insight) "
            "RETURN i.id AS id, i.role AS role, i.scope AS scope, "
            "       i.decided_at AS decided_at, i.headline AS headline, "
            "       i.fingerprint AS fingerprint "
            f"ORDER BY i.decided_at DESC LIMIT {lim}",
        )
        insights = [_insight_to_item(r) for r in i_rows]
    except Exception:
        log.exception("ticker: Insight fetch failed")

    merged = decisions + insights
    # Sort by decided_at desc; missing/None timestamps sink to the end.
    merged.sort(key=lambda it: (it.get("decided_at") or ""), reverse=True)
    return merged[:limit]


@router.get("/recent")
async def recent(
    limit: int = Query(25, ge=1, le=200),
) -> dict[str, Any]:
    """Snapshot of the last ``limit`` Decisions + Insights, newest first."""
    return {"ticker": _fetch_recent(limit)}


def _fetch_decision_by_id(decision_id: str) -> dict[str, Any] | None:
    g = getattr(app_state, "entities", None)
    if g is None:
        return None
    try:
        rows = g.query(
            "MATCH (d:Decision {id: $id}) "
            "RETURN d.id AS id, d.persona_role AS persona_role, "
            "       d.verdict AS verdict, d.reason AS reason, "
            "       d.decided_at AS decided_at, d.workflow_id AS workflow_id "
            "LIMIT 1",
            {"id": decision_id},
        )
    except Exception:
        log.exception("ticker: Decision lookup failed (id=%s)", decision_id)
        return None
    if not rows:
        return None
    return _decision_to_item(rows[0])


def _fetch_insight_by_id(insight_id: str) -> dict[str, Any] | None:
    g = getattr(app_state, "entities", None)
    if g is None:
        return None
    try:
        rows = g.query(
            "MATCH (i:Insight {id: $id}) "
            "RETURN i.id AS id, i.role AS role, i.scope AS scope, "
            "       i.decided_at AS decided_at, i.headline AS headline, "
            "       i.fingerprint AS fingerprint LIMIT 1",
            {"id": insight_id},
        )
    except Exception:
        log.exception("ticker: Insight lookup failed (id=%s)", insight_id)
        return None
    if not rows:
        return None
    return _insight_to_item(rows[0])


def _event_to_item(event: FleetEvent) -> dict[str, Any] | None:
    """Translate a bus event into a ticker item, or None to skip.

    Only ``decision.recorded`` and ``entity.upserted{kind=Insight}`` produce
    items; every other event type is dropped silently so the ticker never
    leaks unrelated bus chatter to the HUD.
    """
    etype = event.type
    payload = event.model_dump()
    if etype == "decision.recorded":
        did = payload.get("decision_id")
        if not did:
            return None
        return _fetch_decision_by_id(did)
    if etype == "entity.upserted" and payload.get("kind") == "Insight":
        eid = payload.get("entity_id")
        if not eid:
            return None
        return _fetch_insight_by_id(eid)
    return None


@router.get("/stream")
async def stream(request: Request) -> EventSourceResponse:
    """SSE stream of new Decisions + Insights.

    Per-connection asyncio.Queue + bus subscription; mirrors the
    blueprint observatory pattern. ``loop.call_soon_threadsafe`` is used
    because bus emits may originate from any thread (Decision writes from
    durable orchestration workers run off the event loop).
    """
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
    loop = asyncio.get_running_loop()

    def _on_event(event: FleetEvent) -> None:
        # The graph lookup is CPU-bound + holds the Kuzu conn lock; do it
        # on the bus-emit thread so the queue carries already-rendered
        # items and the event-loop side stays purely I/O.
        try:
            item = _event_to_item(event)
        except Exception:
            log.exception("ticker: event translation failed")
            return
        if item is None:
            return
        try:
            loop.call_soon_threadsafe(queue.put_nowait, item)
        except (RuntimeError, asyncio.QueueFull):
            pass

    unsubscribe = app_state.bus.on_any(_on_event)

    async def _gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {"event": "ticker", "data": json.dumps(item)}
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": "{}"}
        finally:
            try:
                unsubscribe()
            except Exception:
                pass

    return EventSourceResponse(_gen())
