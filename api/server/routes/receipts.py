"""Static receipt PNG endpoint for the UI.

Demo-grade: serves files from data/synthetic/receipts/ directly.
A zero-byte PNG (the "missing receipt" mismatch flavour) returns 204
so the UI can render a "missing" placeholder.
"""
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/receipts")

_RECEIPTS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "receipts"


@router.get("/{claim_id}.png")
async def get_receipt(claim_id: str):
    if not claim_id.startswith("CLM-") or "/" in claim_id or "\\" in claim_id:
        raise HTTPException(400, "invalid claim_id")
    path = _RECEIPTS_DIR / f"{claim_id}.png"
    if not path.exists():
        raise HTTPException(404, f"receipt for {claim_id} not found")
    if path.stat().st_size == 0:
        # missing-receipt marker: claimant submitted nothing
        return Response(status_code=204)
    return FileResponse(path, media_type="image/png")
