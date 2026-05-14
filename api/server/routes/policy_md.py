"""GET/POST endpoints for the synthetic T&E policy markdown.

The autonomy-policy route at /api/policy is a different domain (governance
sliders / change requests). This route serves data/synthetic/policy.md — the
single source of truth grounding rag_classifier and the gold labels.

POST /api/policy-md/save invalidates the policy_search cache so the next
classifier run reflects the edited policy. This is the AC #4 demo path:
classifier code unchanged, only policy text edited, accuracy shifts.
"""
from __future__ import annotations
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.server.mcp_tools import policy_search

router = APIRouter(prefix="/api/policy-md", tags=["policy-md"])

_POLICY_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "policy.md"


class SaveBody(BaseModel):
    content: str


@router.get("/content")
async def get_content():
    if not _POLICY_PATH.exists():
        raise HTTPException(404, "policy.md not found")
    return {"content": _POLICY_PATH.read_text(encoding="utf-8")}


@router.post("/save")
async def save_content(body: SaveBody):
    _POLICY_PATH.write_text(body.content, encoding="utf-8")
    policy_search.reset_cache()
    return {"ok": True, "bytes": len(body.content.encode("utf-8"))}
