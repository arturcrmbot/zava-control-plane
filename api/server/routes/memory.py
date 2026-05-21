"""Memory-layer read-only endpoints consumed by the portal Memory page.

Spec: docs/superpowers/plans/2026-05-20-memory-layer-visualisation.md.
Stub returns empty envelopes — backing Kuzu queries are not yet wired.
Frontend hooks (`useDreamPassesRecent`, `useWorkingNotes`,
`useActiveLessons`) all expect `{ "items": [...] }`.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from api.server.routes.memory_v2 import _dream_history

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/dream-passes/recent")
def dream_passes_recent(limit: int = Query(20, ge=1, le=200)) -> dict:
    items = [r for r in list(_dream_history) if isinstance(r, dict) and r.get("id")][:limit]
    return {"items": items}


@router.get("/working-notes")
def working_notes(
    limit: int = Query(50, ge=1, le=500),
    agent_skill: str | None = None,
) -> dict:
    return {"items": []}


@router.get("/lessons/active")
def lessons_active(domain: str | None = None) -> dict:
    return {"items": []}


@router.get("/experiments/recent")
def experiments_recent(limit: int = Query(20, ge=1, le=200)) -> dict:
    return {"items": []}
