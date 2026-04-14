from __future__ import annotations
from fastapi import APIRouter, HTTPException
from src.server.state import app_state

router = APIRouter(prefix="/api/workflows")


@router.get("/")
async def list_workflows(status: str | None = None, phase: str | None = None,
                         agency: str | None = None, has_exception: bool | None = None):
    items = app_state.store.list_workflows(status=status, phase=phase, agency=agency, has_exception=has_exception)
    return [w.model_dump() for w in items]


@router.get("/{id}")
async def get_workflow(id: str):
    w = app_state.store.get_workflow(id)
    if not w:
        raise HTTPException(404)
    active = app_state.store.get_exception(w.active_exception_id) if w.active_exception_id else None
    return {
        "workflow": w.model_dump(),
        "phases": [p.model_dump() for p in app_state.store.get_phases(id)],
        "spans": [s.model_dump() for s in app_state.store.get_spans(id)],
        "amplifications": [a.model_dump() for a in app_state.store.get_amplifications(id)],
        "active_exception": active.model_dump() if active else None,
    }
