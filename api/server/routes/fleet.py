# api/server/routes/fleet.py
from __future__ import annotations
from fastapi import APIRouter
from api.server.state import app_state
from api.server.services import economics

router = APIRouter(prefix="/api/fleet")


@router.get("/economics")
async def fleet_economics():
    active_states = {"in_progress", "awaiting_hitl"}
    active = [w for w in app_state.store.list_workflows()
              if w.status in active_states]
    totals = {"cost": 0.0, "model": 0, "tool": 0}
    for w in active:
        eco = economics.compute(
            w,
            spans=app_state.store.get_spans(w.id),
            mcp_calls=app_state.store.get_mcp_calls(w.id),
        )
        totals["cost"] += eco["computeCostUsd"]
        totals["model"] += eco["modelCalls"]
        totals["tool"] += eco["toolCalls"]
    n = max(1, len(active))
    return {
        "activeWorkflowCount": len(active),
        "totalComputeCostUsd": round(totals["cost"], 2),
        "totalModelCalls": totals["model"],
        "totalToolCalls": totals["tool"],
        "averageCostPerWorkflow": round(totals["cost"] / n, 2),
    }
