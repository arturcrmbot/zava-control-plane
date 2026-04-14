from __future__ import annotations
from fastapi import APIRouter, HTTPException
from src.server.state import app_state

router = APIRouter(prefix="/api/workflows")


@router.get("/{id}/orchestration")
async def get_orchestration(id: str):
    w = app_state.store.get_workflow(id)
    if not w:
        raise HTTPException(404)
    history = app_state.orchestration_history.get(id, [])
    return {
        "instance_id": w.orchestration_instance_id,
        "status": w.status,
        "history": history,
    }
