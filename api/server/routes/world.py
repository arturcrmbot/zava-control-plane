"""Internal control + observability for the world simulator (JSON only — not UX).

Two endpoints, in the spirit of the existing internal/demo routes
(``routes/demo_triggers.py``, ``routes/internal_durable_event.py``):

  GET  /api/world/state        — snapshot of live world state (stocks, resources,
                                 signals, inputs) + the last Durable responder run.
  POST /api/world/inject/{name}— inject a named perturbation into the running world.

These exist so a proof driver (or an operator) can drive and observe the world
engine that runs inside the FastAPI process. No frontend, no rendering.
"""
from __future__ import annotations

from fastapi import APIRouter

from api.server.state import app_state

router = APIRouter(prefix="/api/world", tags=["world"])


@router.get("/state")
async def world_state() -> dict:
    engine = getattr(app_state, "world_engine", None)
    if engine is None:
        return {"enabled": False}
    st = engine.state
    return {
        "enabled": True,
        "pack": engine.pack.name,
        "stocks": {k: round(v, 3) for k, v in st.stocks.items()},
        "resources": {k: round(v, 3) for k, v in st.resources.items()},
        "signals": {k: round(v, 4) for k, v in st.signals.items()},
        "inputs": {k: round(v, 3) for k, v in st.inputs.items()},
        "last_response": getattr(app_state, "world_last_response", None),
    }


@router.post("/inject/{name}")
async def world_inject(name: str) -> dict:
    engine = getattr(app_state, "world_engine", None)
    if engine is None:
        return {"ok": False, "error": "world engine not enabled (set ZAVA_WORLD)"}
    engine.inject(name)
    return {"ok": True, "injected": name}
