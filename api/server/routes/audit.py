from __future__ import annotations
from fastapi import APIRouter
from api.server.state import app_state

router = APIRouter(prefix="/api/audit")


@router.get("")
async def list_audit():
    return app_state.audit.list()
