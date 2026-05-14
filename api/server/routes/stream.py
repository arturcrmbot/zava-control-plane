from __future__ import annotations
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from api.server.state import app_state

router = APIRouter(prefix="/api/stream")


@router.get("/fleet")
async def stream_fleet(request: Request):
    return EventSourceResponse(app_state.hub.stream("fleet", request))


@router.get("/fleet-manager")
async def stream_fleet_manager(request: Request):
    return EventSourceResponse(app_state.hub.stream("fleet-manager", request))


@router.get("/orchestration")
async def stream_orchestration(request: Request):
    return EventSourceResponse(app_state.hub.stream("orchestration", request))
