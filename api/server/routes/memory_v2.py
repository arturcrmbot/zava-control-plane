"""Memory layer v2 — Anthropic-style two-tier architecture.

POST /api/memory/v2/recall    — semantic search for agent runtime
GET  /api/memory/v2/memories  — list all for UI / dream input
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from api.server.state import app_state

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory/v2", tags=["memory-v2"])


class _RecallBody(BaseModel):
    domain: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


@router.post("/recall")
def recall(body: _RecallBody) -> dict:
    store = app_state.domain_memories.get(body.domain)
    if not store:
        return {"memories": [], "error": f"unknown domain: {body.domain}"}
    try:
        memories = store.recall(query=body.query, top_k=body.top_k)
    except Exception:
        log.exception("memory recall failed for domain=%s", body.domain)
        memories = []
    return {"memories": memories}


@router.get("/memories")
def list_memories(domain: str = Query(..., min_length=1)) -> dict:
    store = app_state.domain_memories.get(domain)
    if not store:
        return {"memories": [], "count": 0, "error": f"unknown domain: {domain}"}
    try:
        memories = store.list_all(limit=200)
        count = len(memories)
    except Exception:
        log.exception("memory list failed for domain=%s", domain)
        memories, count = [], 0
    return {"memories": memories, "count": count}
