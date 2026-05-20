"""Dream-pass kill switch.

POST /api/dream-pass/pause?domain=X       — add domain to paused set
DELETE /api/dream-pass/pause?domain=X     — remove from paused set
GET /api/dream-pass/pause                  — list paused domains

Paused domains: dream-pass.run, dream-pass cadence, and dream-storm
all refuse with 423 Locked. Returns immediately so the cadence
doesn't have to know — it imports is_paused() before each pass.
"""
from __future__ import annotations

import threading

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/dream-pass", tags=["dream-pass"])

_lock = threading.Lock()
_paused_domains: set[str] = set()


def is_paused(domain: str) -> bool:
    with _lock:
        return domain in _paused_domains


@router.post("/pause")
def pause(domain: str = Query(...)) -> dict:
    with _lock:
        _paused_domains.add(domain)
        return {"ok": True, "paused": sorted(_paused_domains)}


@router.delete("/pause")
def unpause(domain: str = Query(...)) -> dict:
    with _lock:
        _paused_domains.discard(domain)
        return {"ok": True, "paused": sorted(_paused_domains)}


@router.get("/pause")
def list_paused() -> dict:
    with _lock:
        return {"paused": sorted(_paused_domains)}
