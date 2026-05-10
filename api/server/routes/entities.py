"""Read-only HTTP surface for the entity-graph plane (Phase 1 TASK-030..-035).

All five handlers proxy directly to ``app_state.entities`` (the shared
``EntityGraph`` wired in :mod:`api.server.state`). Entity dicts come straight
from Kuzu in snake_case form — they are returned as-is (the camelCase
convention used by ``routes/workflows.py`` is a Pydantic ``by_alias``
artifact and does not apply to raw graph rows). Top-level response keys on
``/_stats`` (``recentLinks``) follow the camelCase convention used in other
routes for response wrapper fields.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.server.state import app_state

router = APIRouter(prefix="/api/entities")

# Canonical kind list — matches ``_NODE_TABLES`` in entity_graph.py. Kept
# inline (rather than re-imported) so this surface stays decoupled from the
# graph module's private constants.
_KINDS: tuple[str, ...] = (
    "Person", "Organisation", "Asset", "Money",
    "Decision", "Place", "Period", "Workflow",
)


@router.get("")
@router.get("/", include_in_schema=False)
async def list_entities(kind: str | None = None, limit: int = 50):
    """List entities, optionally filtered by ``kind``.

    With ``kind`` set: returns up to ``limit`` entities of that kind. An
    invalid kind surfaces as HTTP 400 (``EntityGraph.by_type`` raises
    ``ValueError`` for unknown kinds).

    Without ``kind``: returns up to ``limit`` entities in total, drawn
    round-robin-ish from the eight node tables (each kind contributes until
    the budget is exhausted).
    """
    if kind is not None:
        try:
            rows = app_state.entities.by_type(kind)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return rows[:limit]

    out: list[dict] = []
    for k in _KINDS:
        if len(out) >= limit:
            break
        remaining = limit - len(out)
        out.extend(app_state.entities.by_type(k)[:remaining])
    return out


@router.get("/_stats")
async def entity_stats():
    """Per-kind counts, top-10 most-touched entities, and a recent-links sample.

    Kuzu 0.6.1 caveats:
      * ``size(list)`` works on STRING[] columns, but ``source_workflows`` is
        only declared on five of the eight kinds — hot-list aggregation is
        done in Python over a typed scan rather than via a single label-less
        query so kinds without the column are silently skipped.
      * ``type(r)`` does not exist; ``label(r)`` is the documented
        equivalent (mirrors :meth:`EntityGraph.linked`).
      * No rel table currently declares a ``created_at`` column (see
        ``_REL_TABLES`` in entity_graph.py), so the ``recentLinks`` sample
        is unordered — just the first 20 rels Kuzu returns.
    """
    counts: dict[str, int] = {}
    for k in _KINDS:
        rows = app_state.entities.query(f"MATCH (n:{k}) RETURN count(*) AS c")
        counts[k] = int(rows[0]["c"]) if rows else 0

    # Hot list: only the five kinds that declare source_workflows can
    # participate. Pull each kind's nodes, attach len(source_workflows),
    # sort, take top 10. Dataset is small (hundreds), so the linear scan
    # is fine and dodges Kuzu's per-kind column-presence quirk.
    candidates: list[tuple[int, dict]] = []
    for k in ("Person", "Organisation", "Asset", "Money", "Decision"):
        for n in app_state.entities.by_type(k):
            sw = n.get("source_workflows") or []
            if sw:
                candidates.append((len(sw), n))
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    hot = [n for _, n in candidates[:10]]

    rel_rows = app_state.entities.query(
        "MATCH (a)-[r]->(b) RETURN a, label(r) AS rel, b LIMIT 20"
    )
    recent_links = [
        {"src": row["a"], "rel": row["rel"], "dst": row["b"]}
        for row in rel_rows
    ]

    return {"counts": counts, "hot": hot, "recentLinks": recent_links}


@router.get("/touched-by/{wf_id}")
async def entities_touched_by(wf_id: str):
    """Every entity whose ``source_workflows`` contains ``wf_id``."""
    return app_state.entities.touched_by(wf_id)


@router.get("/by-function/{function_key}")
async def entities_by_function(function_key: str, kind: str | None = None):
    """Org Ops v2 — entities whose source_workflows include any workflow_type
    owned by ``function_key``.

    Replaces the broken hot-list filter the building used at zoom-1: the hot
    list is capped at 10 and dominated by repeatedly-touched ``*-unknown``
    placeholders, so Decisions / Money rows (created once and never re-touched)
    were always counted as 0.

    Returns ``{counts: {kind: count}, sample: [entity, ...]}``. ``sample``
    holds up to 20 entities for the requested ``kind`` (or the first 20 across
    all kinds when no ``kind`` is given) so the frontend can list real
    entities, not just the count.
    """
    try:
        from api.shared.functions import FUNCTIONS
    except Exception:
        raise HTTPException(status_code=500, detail="functions registry unavailable")
    spec = FUNCTIONS.get(function_key)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"unknown function {function_key!r}")
    owned = set(spec.owns_domains or ())
    if not owned:
        return {"counts": {k: 0 for k in _KINDS}, "sample": []}

    # workflow_id prefix → workflow_type lookup so we can filter
    # source_workflows entries (which are workflow_IDs like "VKY-0001") to
    # the owned domains (which are workflow_types like "vendor-kyc").
    try:
        from api.shared import domains as _domains
    except Exception:
        _domains = None

    def _matches_function(source_workflows: list[str]) -> bool:
        for wid in source_workflows or ():
            if not isinstance(wid, str) or "-" not in wid:
                continue
            prefix = wid.split("-", 1)[0]
            if _domains is None:
                continue
            d = _domains.by_prefix(prefix) if hasattr(_domains, "by_prefix") else None
            if d is None:
                # Fallback: try mapping via DOMAINS list scan
                try:
                    for cand in _domains.DOMAINS.values():
                        if cand.workflow_id_prefix == prefix:
                            d = cand
                            break
                except Exception:
                    d = None
            if d is not None and d.workflow_type in owned:
                return True
        return False

    counts: dict[str, int] = {k: 0 for k in _KINDS}
    sample: list[dict] = []
    kinds_to_scan = (kind,) if kind in _KINDS else _KINDS
    for k in kinds_to_scan:
        try:
            rows = app_state.entities.by_type(k)
        except ValueError:
            continue
        for n in rows:
            sw = n.get("source_workflows") or []
            if not _matches_function(sw):
                continue
            counts[k] += 1
            if len(sample) < 20:
                sample.append(n)
    return {"counts": counts, "sample": sample, "function": function_key, "owns": list(owned)}


@router.get("/{id}")
async def get_entity(id: str):
    """Single entity by id; 404 if not found."""
    node = app_state.entities.get(id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"entity {id!r} not found")
    return node


@router.get("/{id}/linked")
async def linked_entities(id: str, rel: str | None = None):
    """Outgoing neighbours of ``id``, optionally filtered by rel type.

    Response shape is ``[{"rel": "<UPPER>", "entity": <node-dict>}]`` —
    the ``EntityGraph.linked`` ``node`` key is renamed to ``entity`` per
    the Phase 1 plan.
    """
    try:
        rows = app_state.entities.linked(id, rel=rel)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return [{"rel": row["rel"], "entity": row["node"]} for row in rows]
