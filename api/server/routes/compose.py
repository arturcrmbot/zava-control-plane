"""Visual Domain Composer HTTP surface (Phase 1: create + SSE stream).

LOCALHOST-ONLY: this endpoint drives a coding agent that edits the repo. It
refuses non-loopback callers. Phase 2 adds the `.poc-safety` marker check,
document intake (PDF/docx), and the answer/brief/permission/ignite endpoints.
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Form, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from api.server.services.compose import registry
from api.server.services.compose.bridge import ComposeBridge
from api.server.services.compose.session import ComposeSession

router = APIRouter()

_COPILOT_CMD_OVERRIDE: list[str] | None = None

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def set_copilot_cmd_for_tests(cmd: list[str] | None) -> None:
    """Test seam: inject the fake ACP agent command."""
    global _COPILOT_CMD_OVERRIDE
    _COPILOT_CMD_OVERRIDE = cmd


def _is_loopback(request: Request) -> bool:
    # Any forwarding header means a proxy/non-local caller -> reject.
    if request.headers.get("x-forwarded-for"):
        return False
    host = request.client.host if request.client else ""
    if host == "testclient" and _COPILOT_CMD_OVERRIDE is not None:
        return True
    return host in _LOOPBACK


@router.post("/api/compose/session")
async def create_session(
    request: Request,
    text: str | None = Form(default=None),
    file: UploadFile | None = None,
):
    if not _is_loopback(request):
        return JSONResponse({"error": "forbidden: localhost only"}, status_code=403)

    document_text = text or ""
    if file is not None:
        document_text = (await file.read()).decode("utf-8", "ignore")
    if not document_text.strip():
        return JSONResponse({"error": "empty document"}, status_code=422)

    cid = uuid.uuid4().hex
    session = ComposeSession(cid)
    bridge = ComposeBridge(session, document_text, copilot_cmd=_COPILOT_CMD_OVERRIDE)
    try:
        await bridge.start()
    except Exception as ex:
        return JSONResponse({"error": f"failed to start compose agent: {ex}"}, status_code=500)
    registry.register(session)
    return {"compose_id": cid}


@router.get("/api/compose/{cid}/stream")
async def stream(cid: str):
    session = registry.get(cid)
    if session is None:
        return JSONResponse({"error": "not found"}, status_code=404)

    async def gen():
        q = session.subscribe()
        try:
            while True:
                event = await q.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "error" or (
                    event.get("type") == "stage" and event.get("stage") == "ready"
                ):
                    break
        finally:
            session.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/api/compose/{cid}")
async def get_session(cid: str):
    session = registry.get(cid)
    if session is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"compose_id": cid, "stage": session.stage,
            "done": session.done, "events": session.events}
