"""Static creative-campaign asset endpoint for the UI.

POC3 Phase 5 — serves the canned SVG fixtures under
data/synthetic/creative-campaign/cached/ so the WorkflowDetail
CreativeCampaignArtefacts component can render concept tiles +
storyboard frames.

Phase 3 swaps these for real Foundry gpt-image-2 outputs (writing PNGs
to Azurite blob); the URLs returned by the image_gen MCP will continue
to flow through this same path shape so the UI doesn't change.
"""
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/static/creative-campaign")

_CACHED_DIR = (
    Path(__file__).resolve().parents[3]
    / "data" / "synthetic" / "creative-campaign" / "cached"
)


def _safe(s: str) -> str:
    """Reject anything that could escape the fixtures dir."""
    if "/" in s or "\\" in s or s.startswith(".") or s == "":
        raise HTTPException(400, "invalid path component")
    return s


@router.get("/cached/{brief_id}/{sub}/{n}.svg")
async def get_cached_still(brief_id: str, sub: str, n: str):
    """Concept routes (route-A/B/C) + storyboard frames (storyboard).

    Path shape matches what agent_creative_stub returns in
    api/functions/graphs/executors/agents/agent_creative_stub.py.
    """
    brief_id = _safe(brief_id)
    sub = _safe(sub)
    n = _safe(n)
    path = _CACHED_DIR / brief_id / sub / f"{n}.svg"
    if not path.exists():
        raise HTTPException(404, f"asset {brief_id}/{sub}/{n}.svg not found")
    return FileResponse(path, media_type="image/svg+xml")
