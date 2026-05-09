"""HTTP surface for the FUNCTIONS registry — Phase 3 IP7 (TASK-039).

Two endpoints:

* ``GET /api/functions`` — list every non-legacy ``Function`` as JSON.
* ``GET /api/functions/{name}/sse`` — proxy for the per-function FM
  SSE topic registered by ``AppState.init_function_fms``.

The blueprint ``/functions`` page (``FunctionsPage.tsx``) consumes both.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from api.server.state import app_state
from api.shared.functions import FUNCTIONS, PersonaTree

router = APIRouter(prefix="/api/functions")


def _persona_tree_to_dict(node: PersonaTree) -> dict:
    """Recursively convert a PersonaTree into a JSON-serialisable dict."""
    return {
        "role": node.role,
        "manages": [_persona_tree_to_dict(child) for child in node.manages],
    }


@router.get("")
@router.get("/")
def list_functions() -> list[dict]:
    """Return the FUNCTIONS registry as JSON; the legacy entry is excluded."""
    return [
        {
            "name": fn.name,
            "display": fn.display,
            "operatorSurface": fn.operator_surface,
            "ownsDomains": list(fn.owns_domains),
            "ambientAgents": list(fn.ambient_agents),
            "kpis": list(fn.kpis),
            "personaHierarchy": _persona_tree_to_dict(fn.persona_hierarchy),
        }
        for name, fn in FUNCTIONS.items()
        if name != "legacy"
    ]


@router.get("/{name}/sse")
async def function_sse(name: str, request: Request):
    """Proxy the per-function FM SSE topic. 404 for legacy / unknown."""
    if name == "legacy" or name not in FUNCTIONS:
        raise HTTPException(status_code=404, detail=f"unknown function: {name}")
    return EventSourceResponse(
        app_state.hub.stream(f"fleet-manager.{name}", request)
    )


@router.get("/{name}/kpis-latest")
def function_kpis_latest(name: str) -> dict:
    """The Org Building (IP1, TASK-003) — latest KPI snapshot per metric.

    Returns ``{metrics: {<metric>: {value, period, captured_at}}, since}``
    for every metric declared on ``FUNCTIONS[name].kpis``. Reduces the raw
    KPI snapshot ledger (append-only, multiple rows per metric) to the
    single most recent row per metric (max ``captured_at``). Metrics with
    no published snapshot are omitted; the front-end renders ``"—"`` in
    their place.

    404 for ``legacy`` / unknown function. Returns an empty ``metrics``
    dict — not 404 — when the kpi store is disabled (entity plane off) or
    has no rows yet.
    """
    if name == "legacy" or name not in FUNCTIONS:
        raise HTTPException(status_code=404, detail=f"unknown function: {name}")

    declared = set(FUNCTIONS[name].kpis)
    store = getattr(app_state, "kpi_store", None)
    if store is None or not declared:
        return {"metrics": {}, "since": None}

    rows = store.query(function=name)
    latest_per_metric: dict[str, dict] = {}
    for row in rows:
        metric = row["metric"]
        if metric not in declared:
            continue
        prev = latest_per_metric.get(metric)
        if prev is None or row["captured_at"] > prev["captured_at"]:
            latest_per_metric[metric] = {
                "value": row["value"],
                "period": row["period"],
                "captured_at": row["captured_at"],
            }

    since = (
        min(v["captured_at"] for v in latest_per_metric.values())
        if latest_per_metric
        else None
    )
    return {"metrics": latest_per_metric, "since": since}
