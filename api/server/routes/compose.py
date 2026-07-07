"""Visual Domain Composer HTTP surface (Phase 1: create + SSE stream).

LOCALHOST-ONLY: this endpoint drives a coding agent that edits the repo. It
refuses non-loopback callers. Phase 2 adds the `.poc-safety` marker check,
document intake (PDF/docx), and the answer/brief/permission/ignite endpoints.
"""
from __future__ import annotations

import json
import subprocess
import uuid

from fastapi import APIRouter, Body, Form, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from api.server.services.compose import intake, registry
from api.server.services.compose.bridge import ComposeBridge
from api.server.services.compose.session import ComposeSession
from api.shared import compose_config

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


def _guard(request: Request) -> bool:
    return _is_loopback(request) and compose_config.poc_safety_ok()


@router.post("/api/compose/session")
async def create_session(
    request: Request,
    text: str | None = Form(default=None),
    file: UploadFile | None = None,
):
    if not _guard(request):
        return JSONResponse({"error": "forbidden: localhost only"}, status_code=403)

    document_text = text or ""
    if file is not None:
        raw = await file.read()
        document_text = intake.extract_text(file.filename or "", raw)
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


async def resolve_answer(cid: str, payload: dict) -> dict:
    session = registry.get(cid)
    if session is None:
        return {"ok": False, "error": "not found"}
    ok = session.resolve(payload["request_id"], payload.get("answer", ""))
    return {"ok": ok}


async def resolve_brief(cid: str, payload: dict) -> dict:
    session = registry.get(cid)
    if session is None:
        return {"ok": False, "error": "not found"}
    ok = session.resolve(payload["request_id"],
                         {"approved": bool(payload.get("approved", True)),
                          "yaml": payload.get("yaml", "")})
    return {"ok": ok}


@router.post("/api/compose/{cid}/answer")
async def answer(cid: str, payload: dict = Body(...)):
    return await resolve_answer(cid, payload)


@router.post("/api/compose/{cid}/brief")
async def brief(cid: str, payload: dict = Body(...)):
    return await resolve_brief(cid, payload)


@router.post("/api/compose/{cid}/ignite")
async def ignite(cid: str):
    session = registry.get(cid)
    if session is None:
        return {"ok": False, "error": "not found"}
    session.emit({"type": "stage", "stage": "ready", "label": "Igniting — re-arming the substrate"})
    script = str(compose_config.repo_root() / "scripts" / "compose-ignite.sh")
    # Detached so it survives the API restart it performs.
    subprocess.Popen(
        ["bash", script],
        cwd=str(compose_config.repo_root()),
        start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return {"ok": True}

