from __future__ import annotations
from fastapi import APIRouter
from src.server.state import app_state

router = APIRouter(prefix="/api/audit")


@router.get("/")
async def list_audit():
    return app_state.audit.list()
