from __future__ import annotations
from fastapi import APIRouter
from api.server.state import app_state

router = APIRouter(prefix="/api/audit")


@router.get("")
@router.get("/", include_in_schema=False)
async def list_audit():
    return app_state.audit.list()
