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
