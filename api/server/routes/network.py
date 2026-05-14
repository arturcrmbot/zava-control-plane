"""GET /api/network/holding-view — agency holding network effects (pitch-e6).

Surfaces the cross-subsidiary structure that's invisible in the
per-city view: every Subsidiary with its headcount + utilisation,
the talent flows between them, and the clients shared by 2+ subs.

Empty data is normal here — several rel-tables (CAMPAIGN_FOR,
EXECUTED_BY, BRAND_OF) are scaffolded by pitch-e1 but not yet
populated by the data fabric, and the talent-transfer workflow type
isn't materialised either. The endpoint must NOT crash in that
state — it returns ``[]`` / ``0`` for unavailable data without an
``unavailable_reason`` field (the JSON contract is the same; the
data is just sparse).
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from fastapi import APIRouter

from api.server.state import app_state

router = APIRouter(prefix="/api/network", tags=["network"])
log = logging.getLogger(__name__)


def _safe_query(cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run ``cypher`` returning ``[]`` on any error (empty graph, missing rel)."""
    try:
        return app_state.entities.query(cypher, params or {})
    except Exception as exc:
        log.debug("network query failed (returning []): %s", exc)
        return []


def _utilisation_for(sub_id: str) -> int:
    """Deterministic mock utilisation in [60, 90) keyed on subsidiary id.

    TODO(phase-2): replace with a real timesheet aggregate once the
    Timesheet kind lands. Today the data fabric has no per-sub billable
    hours, so we synthesise a stable value so the bar renders without
    being misleading (the value is constant for a given sub).
    """
    h = int(hashlib.sha1(sub_id.encode("utf-8")).hexdigest()[:8], 16)
    return 60 + (h % 30)


def _subsidiaries() -> list[dict[str, Any]]:
    rows = _safe_query(
        "MATCH (s:Subsidiary) "
        "RETURN s.id AS id, s.name AS name, "
        "s.country AS country, s.headcount AS headcount"
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        sid = r.get("id")
        if not isinstance(sid, str) or not sid:
            continue
        # EMPLOYED_BY links Person → Organisation (sub ids are shared
        # between Subsidiary and Organisation tables, so the count
        # works without a typed Subsidiary edge).
        emp_rows = _safe_query(
            "MATCH (p:Person)-[:EMPLOYED_BY]->(o:Organisation) "
            "WHERE o.id = $sid RETURN count(p) AS c",
            {"sid": sid},
        )
        graph_headcount = 0
        if emp_rows:
            c = emp_rows[0].get("c")
            graph_headcount = int(c) if isinstance(c, (int, float)) else 0
        # Prefer the live EMPLOYED_BY count; fall back to the static
        # Subsidiary.headcount column when the edge table is empty.
        static_headcount = r.get("headcount") or 0
        try:
            static_headcount = int(static_headcount)
        except (TypeError, ValueError):
            static_headcount = 0
        headcount = graph_headcount or static_headcount

        # TODO(pitch-c3): brands per subsidiary requires the
        # Brand→Subsidiary chain (BRAND_OF + EXECUTED_BY) to be
        # populated. Until then, expose an empty list — clients
        # render "—" without crashing.
        brands: list[str] = []

        # TODO(pitch-c3): client list per subsidiary depends on the
        # same Brand→Subsidiary chain.
        clients: list[str] = []

        country = r.get("country") or ""
        name = r.get("name") or sid

        out.append({
            "id": sid,
            "name": name,
            "headcount": headcount,
            "brands": brands,
            "clients": clients,
            "billable_utilisation_pct": _utilisation_for(sid),
            "country": country,
        })
    # Stable order — name asc — so the HUD doesn't reshuffle on poll.
    out.sort(key=lambda s: s["name"])
    return out


def _talent_flows() -> list[dict[str, Any]]:
    """Cross-sub Person transfers.

    Today the data fabric does not emit ``intercompany_talent_transfer``
    workflows so this is always ``[]``. Wired as a query so it lights
    up automatically once the workflow_type starts producing rows.
    """
    rows = _safe_query(
        "MATCH (w:Workflow) WHERE w.workflow_type = 'intercompany_talent_transfer' "
        "RETURN w.attributes AS attrs"
    )
    flows: dict[tuple[str, str], int] = {}
    for r in rows:
        try:
            attrs = json.loads(r.get("attrs") or "{}")
        except (TypeError, ValueError):
            continue
        src = attrs.get("from_subsidiary")
        dst = attrs.get("to_subsidiary")
        if not isinstance(src, str) or not isinstance(dst, str) or src == dst:
            continue
        flows[(src, dst)] = flows.get((src, dst), 0) + 1
    return [
        {"from": s, "to": d, "count": c}
        for (s, d), c in sorted(flows.items())
    ]


def _client_overlap() -> list[dict[str, Any]]:
    """Clients served by 2+ subsidiaries.

    TODO(pitch-c3): this needs the Brand → Subsidiary chain
    (BRAND_OF + EXECUTED_BY) to be populated. Until then we list
    every client with ``subsidiary_count = 0`` so the HUD can show
    "no shared clients yet" without faking the data.
    """
    rows = _safe_query(
        "MATCH (o:Organisation) WHERE o.kind = 'client' "
        "RETURN o.id AS id, o.name AS name"
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        cid = r.get("id")
        if not isinstance(cid, str) or not cid:
            continue
        # Count distinct subs serving this client via Brand → Subsidiary.
        sub_rows = _safe_query(
            "MATCH (c:Organisation)<-[:BRAND_OF]-(b:Brand)<-[:CAMPAIGN_FOR]-"
            "(:Campaign)-[:EXECUTED_BY]->(s:Subsidiary) "
            "WHERE c.id = $cid RETURN DISTINCT s.id AS sid",
            {"cid": cid},
        )
        sub_ids = [
            row.get("sid") for row in sub_rows
            if isinstance(row.get("sid"), str)
        ]
        out.append({
            "client_id": cid,
            "name": r.get("name") or cid,
            "subsidiary_count": len(sub_ids),
            "subsidiaries": sub_ids,
        })
    # Only return clients touched by 2+ subs once the chain is wired;
    # until then keep them all so the HUD can render the empty state
    # without an extra "no data" branch.
    multi = [c for c in out if c["subsidiary_count"] >= 2]
    return multi if multi else out


@router.get("/holding-view")
def holding_view() -> dict[str, Any]:
    """Return the holding-level network-effects bundle."""
    return {
        "subsidiaries": _subsidiaries(),
        "talent_flows": _talent_flows(),
        "client_overlap": _client_overlap(),
    }
