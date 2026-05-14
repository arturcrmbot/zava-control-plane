"""Read-only HTTP surface for the accounts substrate (Phase 2)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from api.server.state import app_state
from api.server.services.read_route_auth import (
    Actor, project_for_role, require_actor,
)

router = APIRouter(prefix="/api/accounts")


@router.get("/summary")
async def summary(
    group_by: str | None = Query(None, pattern="^(period|cost_centre|none)?$"),
    cost_centre: str | None = None,
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    g = app_state.entities

    # Kuzu 0.6.1 has no pattern-comprehension subqueries; express the
    # cost-centre filter as an extra MATCH leg instead.
    base_match = (
        "MATCH (m:Money)-[:BOOKED_AGAINST]->(a:Account)"
    )
    cc_clause = ""
    params: dict[str, Any] = {}
    if cost_centre:
        base_match += ", (m)-[:COSTED_TO]->(:CostCentre {id: $cc})"
        params["cc"] = cost_centre

    rows = g.query(
        f"""
        {base_match}
        OPTIONAL MATCH (m)-[:COSTED_TO]->(c:CostCentre)
        RETURN a.id AS account_id, a.code AS code, a.name AS name,
               a.type AS type, sum(m.amount) AS total_gbp,
               count(DISTINCT m) AS row_count,
               collect(DISTINCT c.id) AS cost_centres
        """,
        params,
    )
    out = {
        "accounts": [
            {
                "id": r["account_id"],
                "code": r["code"],
                "name": r["name"],
                "type": r["type"],
                "total_gbp": float(r["total_gbp"] or 0),
                "row_count": int(r["row_count"]),
                "cost_centres": [c for c in (r["cost_centres"] or []) if c],
            }
            for r in rows
        ],
    }
    if group_by == "period":
        period_rows = g.query(
            """
            MATCH (m:Money)-[:BOOKED_AGAINST]->(a:Account)
            OPTIONAL MATCH (m)-[:BELONGS_TO]->(p:Period)
            RETURN p.id AS period_id, p.label AS label,
                   a.id AS account_id, sum(m.amount) AS total
            """
        )
        out["by_period"] = [
            {"period_id": r["period_id"], "label": r["label"],
             "account_id": r["account_id"], "total_gbp": float(r["total"] or 0)}
            for r in period_rows
        ]
    return project_for_role(out, actor.role)


@router.get("/by-brand")
async def by_brand(actor: Actor = Depends(require_actor)) -> dict[str, Any]:
    g = app_state.entities
    rows = g.query(
        """
        MATCH (m:Money)-[:COSTED_TO_BRAND]->(b:Brand)
        OPTIONAL MATCH (b)-[:BRAND_OF]->(o:Organisation)
        RETURN b.id AS brand_id, b.name AS brand_name,
               o.name AS client_name, sum(m.amount) AS total_gbp,
               count(DISTINCT m) AS row_count
        ORDER BY total_gbp DESC
        """
    )
    out = {
        "brands": [
            {
                "brand_id": r["brand_id"],
                "brand_name": r["brand_name"],
                "client_name": r["client_name"],
                "total_gbp": float(r["total_gbp"] or 0),
                "row_count": int(r["row_count"]),
            }
            for r in rows
        ],
    }
    return project_for_role(out, actor.role)
