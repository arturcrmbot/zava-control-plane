from __future__ import annotations
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from src.server.state import app_state

router = APIRouter(prefix="/api/stream")


@router.get("/fleet")
async def stream_fleet():
    return EventSourceResponse(app_state.hub.stream("fleet"))


@router.get("/fleet-manager")
async def stream_fleet_manager():
    return EventSourceResponse(app_state.hub.stream("fleet-manager"))


@router.get("/orchestration")
async def stream_orchestration():
    return EventSourceResponse(app_state.hub.stream("orchestration"))
