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

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from api.server.state import app_state
from api.server.services.read_route_auth import (
    Actor,
    project_for_role,
    require_actor,
)

router = APIRouter(prefix="/api/entities")
log = logging.getLogger(__name__)

# Canonical kind list — matches ``_NODE_TABLES`` in entity_graph.py. Kept
# inline (rather than re-imported) so this surface stays decoupled from the
# graph module's private constants.
_KINDS: tuple[str, ...] = (
    "Person", "Organisation", "Asset", "Money",
    "Decision", "Place", "Period", "Workflow",
    # pitch-e1: agency-domain kinds
    "Brand", "Campaign", "Pitch", "MediaPlan", "Subsidiary",
    # Phase 2: accounts substrate
    "Account", "CostCentre",
    # autonomous-domain-insights v1: persona-emitted insight kind
    "Insight",
)

# Always-relevant keys carried on every projected entity dict regardless
# of kind. ``_label`` / ``_id`` are Kuzu-injected; ``first_seen_at`` /
# ``last_seen_at`` are written by EntityGraph.upsert; ``source_workflows``
# / ``attributes`` are present on most kinds and harmless when absent.
_COMMON_FIELDS: frozenset[str] = frozenset({
    "id", "_label", "_id",
    "source_workflows", "attributes",
    "first_seen_at", "last_seen_at",
})

# Per-kind allow-list of payload columns. Hand-mirrored from
# ``_NODE_TABLES`` in api/server/services/entity_graph.py — when a new
# column lands on a node table, add it here too. Kuzu's label-less
# ``MATCH (n {id: $id}) RETURN n`` returns the union of every kind's
# columns, with NULLs for the other kinds; this map is the route-layer
# filter that drops the noise so a Period node no longer comes back
# carrying NULL ``email`` / ``role`` / ``employed_from`` / etc.
_PROJECT_FIELDS_BY_KIND: dict[str, frozenset[str]] = {
    "Person": frozenset({
        "name", "email", "role", "market", "department",
        "employed_from", "employed_to",
    }),
    "Organisation": frozenset({
        "name", "kind", "country", "jurisdiction", "risk_band",
    }),
    "Asset": frozenset({
        "kind", "identifier", "status", "acquired_at", "retired_at",
    }),
    "Money": frozenset({
        "amount", "currency", "kind", "period",
    }),
    "Decision": frozenset({
        "workflow_id", "phase", "persona_role",
        "verdict", "reason", "decided_at", "source_event",
        # Phase 4 Task 4.3: first-class Decision columns
        "amount_gbp", "currency_pair", "notional_gbp", "vendor_id", "client_brand",
    }),
    "Place": frozenset({
        "kind", "name", "parent_id",
    }),
    "Period": frozenset({
        "kind", "starts", "ends", "label",
    }),
    "Workflow": frozenset({
        "workflow_type", "status", "started_at", "completed_at",
    }),
    "Account": frozenset({
        "code", "name", "type", "currency",
    }),
    "CostCentre": frozenset({
        "name", "subsidiary_id", "owner_role",
    }),
    "Insight": frozenset({
        "role", "scope", "decided_at", "headline", "body",
        "kpis", "proposed_actions", "fingerprint",
    }),
}


def _project_entity(node: dict) -> dict:
    """Drop NULL union-noise columns from a Kuzu-returned entity dict.

    Keeps the always-relevant common fields plus the columns declared on
    the node's ``_label`` kind. Unknown/extra labels pass through
    unchanged so this filter never accidentally hides a new kind's
    payload before the allow-list is updated.
    """
    if not isinstance(node, dict):
        return node
    label = node.get("_label")
    kind_fields = _PROJECT_FIELDS_BY_KIND.get(label) if isinstance(label, str) else None
    if kind_fields is None:
        return node
    allowed = _COMMON_FIELDS | kind_fields
    return {k: v for k, v in node.items() if k in allowed}


@router.get("")
@router.get("/", include_in_schema=False)
async def list_entities(
    kind: str | None = None,
    limit: int = 50,
    order: str | None = None,
    actor: Actor = Depends(require_actor),
):
    """List entities, optionally filtered by ``kind``.

    With ``kind`` set: returns up to ``limit`` entities of that kind. An
    invalid kind surfaces as HTTP 400 (``EntityGraph.by_type`` raises
    ``ValueError`` for unknown kinds). ``order=recent`` sorts by
    ``last_seen_at`` (falling back to ``decided_at``) DESC.

    Without ``kind``: returns up to ``limit`` entities in total, drawn
    round-robin-ish from the eight node tables (each kind contributes until
    the budget is exhausted).
    """
    if kind is not None:
        try:
            rows = app_state.entities.by_type(kind)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if order == "recent":
            def _ts(row: dict) -> float:
                v = row.get("last_seen_at") or row.get("decided_at")
                if v is None:
                    return 0.0
                try:
                    return v.timestamp() if hasattr(v, "timestamp") else float(v)
                except Exception:
                    return 0.0
            rows = sorted(rows, key=_ts, reverse=True)
        return project_for_role(rows[:limit], actor.role)

    out: list[dict] = []
    for k in _KINDS:
        if len(out) >= limit:
            break
        remaining = limit - len(out)
        out.extend(app_state.entities.by_type(k)[:remaining])
    return project_for_role(out, actor.role)


@router.get("/_stats")
async def entity_stats(actor: Actor = Depends(require_actor)):
    """Per-kind counts, top-10 most-touched entities, and a recent-links sample.

    Kuzu 0.6.1 caveats:
      * ``size(list)`` works on STRING[] columns, but ``source_workflows`` is
        only declared on five of the eight kinds — hot-list aggregation is
        done in Python over a typed scan rather than via a single label-less
        query so kinds without the column are silently skipped.
      * ``type(r)`` does not exist; ``label(r)`` is the documented
        equivalent (mirrors :meth:`EntityGraph.linked`).
      * Every rel table now declares ``decided_at TIMESTAMP`` (Phase 4 Task
        4.2), so ``recentLinks`` is ordered by it. Old graph files with
        unstamped rels will sort NULL-last per Kuzu's default.
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
        "MATCH (a)-[r]->(b) "
        "RETURN a, label(r) AS rel, b, r.decided_at AS decided_at "
        "ORDER BY decided_at DESC LIMIT 20"
    )
    recent_links = [
        {"src": row["a"], "rel": row["rel"], "dst": row["b"],
         "decided_at": row["decided_at"]}
        for row in rel_rows
    ]

    return project_for_role(
        {"counts": counts, "hot": hot, "recentLinks": recent_links},
        actor.role,
    )


@router.get("/touched-by/{wf_id}")
async def entities_touched_by(wf_id: str, actor: Actor = Depends(require_actor)):
    """Every entity whose ``source_workflows`` contains ``wf_id``."""
    return project_for_role(app_state.entities.touched_by(wf_id), actor.role)


@router.get("/by-function/{function_key}")
async def entities_by_function(
    function_key: str,
    kind: str | None = None,
    actor: Actor = Depends(require_actor),
):
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
    except ImportError:
        log.warning("entities_by_function: functions registry unimportable", exc_info=True)
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
    except ImportError:
        log.warning("entities_by_function: domains module unimportable", exc_info=True)
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
                except (AttributeError, KeyError):
                    # _domains shape may diverge across generated registries;
                    # missing DOMAINS / non-dict shape is fine — fall through
                    # to "no match for this workflow_id".
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
    return project_for_role(
        {"counts": counts, "sample": sample, "function": function_key, "owns": list(owned)},
        actor.role,
    )


import time as _time
_PULSE_BASELINE: dict[str, tuple[float, int]] = {"prev": (0.0, 0)}


@router.get("/_pulse")
async def entities_pulse(actor: Actor = Depends(require_actor)):
    """Snapshot of substrate knowledge growth + activity rates."""
    counts = app_state.entities.count_by_kind()
    total = sum(counts.values())
    now = _time.time()
    prev_ts, prev_total = _PULSE_BASELINE["prev"]
    growth_60s = 0
    if prev_ts > 0 and now - prev_ts < 90:
        growth_60s = max(0, total - prev_total)
    if now - prev_ts > 60:
        _PULSE_BASELINE["prev"] = (now, total)
    decisions_rate = 0.0
    links_rate = 0.0
    try:
        from api.server.services.entity_graph import DECIDED_REL_NAMES

        decisions_rate = float(app_state.entities.recent_activity_per_min("Decision"))
        # DECIDED_<KIND> shards (DECIDED_PERSON, DECIDED_MONEY, …) are
        # imported from the writer's canonical list so this aggregate
        # stays in sync as new shards are added.
        link_rels = (
            "EMPLOYED_BY", "MANAGES", "OWNS", "TRANSACTS", "BELONGS_TO",
            "LOCATED_IN", "PRECEDENT_OF", "TOUCHED", "SUB_WORKFLOW_OF",
            *DECIDED_REL_NAMES,
        )
        links_rate = sum(
            float(app_state.entities.recent_activity_per_min(r))
            for r in link_rels
        )
    except Exception:
        pass
    try:
        cross = app_state.entities.cross_domain_top(limit=5)
    except Exception:
        cross = []
    return {
        "total": total,
        "growth_60s": growth_60s,
        "decisions_per_min": round(decisions_rate, 2),
        "links_per_min": round(links_rate, 2),
        "cross_domain_top": cross,
    }


@router.get("/_kinds")
async def entity_kinds_summary(actor: Actor = Depends(require_actor)):
    """Per-kind statistics for the "Org X-ray" panel (pitch-a7).

    Returns ``{kinds: [{kind, count, sample_ids, recent_link_count}, ...]}``.

    * ``count`` comes from :meth:`EntityGraph.count_by_kind` (cheap aggregate).
    * ``sample_ids`` is up to three ids drawn straight from Kuzu via an
      inline-LIMIT scan (Kuzu 0.6.1 does not parameterise ``LIMIT``).
    * ``recent_link_count`` is the total edge count where either end is
      of this kind — the per-hour fallback the plan calls out, since no
      rel table currently declares a ``created_at`` column (see
      ``_REL_TABLES`` in entity_graph.py).
    """
    counts = app_state.entities.count_by_kind()
    out: list[dict] = []
    for k in _KINDS:
        try:
            sample_rows = app_state.entities.query(
                f"MATCH (n:{k}) RETURN n.id AS id LIMIT 3"
            )
        except Exception:
            sample_rows = []
        sample_ids = [
            row["id"] for row in sample_rows
            if isinstance(row.get("id"), str)
        ]
        try:
            link_rows = app_state.entities.query(
                f"MATCH (n:{k})-[r]-() RETURN count(r) AS c"
            )
            recent_link_count = int(link_rows[0]["c"]) if link_rows else 0
        except Exception:
            recent_link_count = 0
        out.append({
            "kind": k,
            "count": int(counts.get(k, 0)),
            "sample_ids": sample_ids,
            "recent_link_count": recent_link_count,
        })
    return project_for_role({"kinds": out}, actor.role)


@router.get("/{id}")
async def get_entity(id: str, actor: Actor = Depends(require_actor)):
    """Single entity by id; 404 if not found."""
    node = app_state.entities.get(id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"entity {id!r} not found")
    return project_for_role(_project_entity(node), actor.role)


@router.get("/{id}/linked")
async def linked_entities(
    id: str,
    response: Response,
    rel: str | None = None,
    direction: str = "both",
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    actor: Actor = Depends(require_actor),
):
    """Neighbours of ``id``, optionally filtered by rel type and direction.

    Response shape is
    ``[{"rel": "<UPPER>", "direction": "out|in", "entity": <node-dict>}]``.

    ``direction`` defaults to ``"both"`` (union of incoming + outgoing).
    The schema is directional, so many useful kinds (``Period``, ``Place``,
    ``Money``, ``Organisation``) appear orphan if you only follow outgoing
    edges. Pass ``direction=out`` or ``direction=in`` to restrict.

    Pagination: ``limit`` (default 50, clamped 1–500) and ``offset``
    (default 0) page through the result set in stable insertion order
    (Kuzu returns out-edges before in-edges, both in storage order). The
    total unpaginated count is returned in the ``X-Total-Count`` response
    header so callers can render "showing 50 of 312" without changing the
    array-shaped JSON body that today's frontend already consumes
    (``WorkflowDrawer.tsx`` does ``r.json()`` and treats the value as an
    array).
    """
    try:
        rows = app_state.entities.linked(id, rel=rel, direction=direction)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    total = len(rows)
    page = rows[offset : offset + limit]
    response.headers["X-Total-Count"] = str(total)
    return project_for_role(
        [
            {
                "rel": row["rel"],
                "direction": row["direction"],
                "entity": row["node"],
            }
            for row in page
        ],
        actor.role,
    )


@router.get("/{id}/precedents")
async def precedents(id: str, actor: Actor = Depends(require_actor)) -> dict:
    """Phase 4 Task 4.4: precedent chain for a Decision (up to 3 hops, top 10 by recency)."""
    g = app_state.entities
    rows = g.query(
        """
        MATCH (d:Decision {id: $id})-[:PRECEDENT_OF*1..3]->(p:Decision)
        RETURN p.id AS id, p.workflow_id AS workflow_id, p.phase AS phase,
               p.verdict AS verdict, p.reason AS reason, p.decided_at AS decided_at
        ORDER BY decided_at DESC LIMIT 10
        """,
        {"id": id},
    )
    out = {"precedents": [
        {"id": r["id"], "workflow_id": r["workflow_id"], "phase": r["phase"],
         "verdict": r["verdict"], "reason": r["reason"],
         "decided_at": r["decided_at"]}
        for r in rows
    ]}
    return project_for_role(out, actor.role)


def _summarise_audit_entry(entry: dict) -> str:
    """Render a one-line human summary for a timeline row.

    Falls back to ``"<action>"`` when the details blob doesn't carry
    enough context to be more specific. Kept local to the entities
    route — the audit ledger itself stores raw details and intentionally
    has no opinion on how they read.
    """
    action = str(entry.get("action") or "event")
    details = entry.get("details")
    if not isinstance(details, dict):
        return action
    bits: list[str] = [action]
    verdict = details.get("verdict")
    if isinstance(verdict, str) and verdict:
        bits.append(verdict)
    persona = details.get("persona_role") or details.get("agent_id")
    if isinstance(persona, str) and persona:
        bits.append(f"by {persona}")
    target = details.get("entity_id") or details.get("workflow_id") or details.get("id")
    if isinstance(target, str) and target:
        bits.append(f"on {target}")
    return " ".join(bits)


@router.get("/{id}/timeline")
async def entity_timeline(
    id: str,
    limit: int = Query(100, ge=1, le=500),
    before_ts: float | None = None,
    actor: Actor = Depends(require_actor),
):
    """Chronological audit-ledger view for everything that touched ``id``.

    Aggregates entries whose ``details`` reference the id under any of the
    well-known keys (``id``, ``entity_id``, ``workflow_id``, ``decision_id``,
    plus the nested ``governance.decision_id``). Newest first; cursor
    via ``before_ts`` (unix seconds, exclusive).
    """
    entries = app_state.audit.entries_for_id(id, limit=limit, before_ts=before_ts)
    rows = [
        {
            "timestamp": e.get("timestamp"),
            "action": e.get("action"),
            "summary": _summarise_audit_entry(e),
            "raw_details": e.get("details"),
        }
        for e in entries
    ]
    return project_for_role(rows, actor.role)
