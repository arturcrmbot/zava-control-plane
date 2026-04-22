from __future__ import annotations
from fastapi import APIRouter, HTTPException
from api.server.state import app_state

router = APIRouter(prefix="/api/workflows")


@router.get("/")
async def list_workflows(status: str | None = None, phase: str | None = None,
                         agency: str | None = None, has_exception: bool | None = None):
    items = app_state.store.list_workflows(status=status, phase=phase, agency=agency, has_exception=has_exception)
    return [w.model_dump(by_alias=True) for w in items]  # camelCase for UI


@router.get("/{id}")
async def get_workflow(id: str):
    w = app_state.store.get_workflow(id)
    if not w:
        raise HTTPException(404)
    active = app_state.store.get_exception(w.active_exception_id) if w.active_exception_id else None
    return {
        "workflow": w.model_dump(by_alias=True),
        "phases": [p.model_dump(by_alias=True) for p in app_state.store.get_phases(id)],
        "spans": [s.model_dump(by_alias=True) for s in app_state.store.get_spans(id)],
        "amplifications": [a.model_dump(by_alias=True) for a in app_state.store.get_amplifications(id)],
        "activeException": active.model_dump(by_alias=True) if active else None,
    }
