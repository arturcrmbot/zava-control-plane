# api/server/routes/fleet.py
from __future__ import annotations
from fastapi import APIRouter
from api.server.state import app_state
from api.server.services import economics

router = APIRouter(prefix="/api/fleet")


@router.get("/economics")
async def fleet_economics():
    active_states = {"in_progress", "awaiting_hitl"}
    workflows = list(app_state.store.list_workflows())
    active_count = sum(1 for w in workflows if w.status in active_states)
    totals = {"cost": 0.0, "model": 0, "tool": 0}
    for w in workflows:
        eco = economics.compute(
            w,
            spans=app_state.store.get_spans(w.id),
            mcp_calls=app_state.store.get_mcp_calls(w.id),
        )
        totals["cost"] += eco["computeCostUsd"]
        totals["model"] += eco["modelCalls"]
        totals["tool"] += eco["toolCalls"]
    n = max(1, len(workflows))
    return {
        "activeWorkflowCount": active_count,
        "totalWorkflowCount": len(workflows),
        # 4dp so the UI's 3dp display isn't truncated to $0.000 for
        # sub-cent per-workflow averages.
        "totalComputeCostUsd": round(totals["cost"], 4),
        "totalModelCalls": totals["model"],
        "totalToolCalls": totals["tool"],
        "averageCostPerWorkflow": round(totals["cost"] / n, 4),
    }
