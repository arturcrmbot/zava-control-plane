"""HTTP surface for the Threadlight SME-interview accelerator (§4.14).

The Threadlight React route at `/threadlight` calls these endpoints; the
right-rail SKILL.md preview reads `skill_md_draft` after each SME turn.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.server.services.threadlight_service import threadlight

router = APIRouter(prefix="/api/threadlight")


class StartRequest(BaseModel):
    skill_target_name: str


class TurnRequest(BaseModel):
    text: str


@router.post("/sessions")
async def start_session(req: StartRequest):
    s = await threadlight.start_session(skill_target_name=req.skill_target_name)
    return {
        "session_id": s.session_id,
        "skill_target_name": s.skill_target_name,
        "transcript": [t.__dict__ for t in s.transcript],
        "skill_md_draft": s.skill_md_draft,
    }


@router.post("/sessions/{session_id}/turn")
async def append_turn(session_id: str, req: TurnRequest):
    if threadlight.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    s = await threadlight.append_sme_turn(session_id, req.text)
    return {
        "session_id": s.session_id,
        "transcript": [t.__dict__ for t in s.transcript],
        "skill_md_draft": s.skill_md_draft,
    }


@router.post("/sessions/{session_id}/finalise")
async def finalise(session_id: str):
    if threadlight.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    path = await threadlight.finalise(session_id)
    return {"ok": True, "skill_path": str(path)}
