"""Memory-layer read-only endpoints consumed by the portal Memory page
and the constellation viz.

Spec: docs/superpowers/plans/2026-05-20-memory-layer-visualisation.md.
Pulls real data from `app_state.domain_memories` (DomainMemory →
Mem0/FallbackMemory). Frontend hooks (`useDreamPassesRecent`,
`useWorkingNotes`, `useActiveLessons`, `usePerPersonaLessons`) all
expect `{ "items": [...] }`.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter, Query

from api.server.routes.memory_v2 import _dream_history

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory", tags=["memory"])


def _all_domain_memories() -> dict:
    try:
        from api.server.state import app_state
        return app_state.domain_memories or {}
    except Exception:
        return {}


@router.get("/dream-passes/recent")
def dream_passes_recent(
    limit: int = Query(20, ge=1, le=200),
    domain: str | None = Query(None),
) -> dict:
    items = [
        r for r in list(_dream_history)
        if isinstance(r, dict) and (domain is None or r.get("domain") == domain)
    ][:limit]
    return {"items": items}


@router.get("/working-notes")
def working_notes(
    limit: int = Query(50, ge=1, le=500),
    agent_skill: str | None = None,
    domain: str | None = None,
) -> dict:
    """Return non-distilled (working) memory entries.

    Filterable by domain or agent_skill. Sorted by captured_at desc
    when the metadata carries it.
    """
    stores = _all_domain_memories()
    out: list[dict] = []
    for dom, store in stores.items():
        if domain and dom != domain:
            continue
        try:
            entries = store.list_by_kind("working", limit=limit * 4)
        except Exception:
            log.exception("working-notes: list_by_kind failed for %s", dom)
            continue
        for e in entries:
            md = e.get("metadata") or {}
            if agent_skill and md.get("agent_skill") != agent_skill:
                continue
            out.append({
                "id": e.get("id"),
                "domain": dom,
                "memory": e.get("memory"),
                "agent_skill": md.get("agent_skill", ""),
                "workflow_id": md.get("workflow_id", ""),
                "captured_at": md.get("captured_at", ""),
                "metadata": md,
            })
    out.sort(key=lambda r: r.get("captured_at") or "", reverse=True)
    return {"items": out[:limit]}


@router.get("/lessons/active")
def lessons_active(
    domain: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """Return distilled lessons (produced by a dream pass)."""
    stores = _all_domain_memories()
    out: list[dict] = []
    for dom, store in stores.items():
        if domain and dom != domain:
            continue
        try:
            entries = store.list_by_kind("lesson", limit=limit * 4)
        except Exception:
            log.exception("lessons/active: list_by_kind failed for %s", dom)
            continue
        for e in entries:
            md = e.get("metadata") or {}
            out.append({
                "id": e.get("id"),
                "domain": dom,
                "memory": e.get("memory"),
                "consolidated_at": md.get("consolidated_at", ""),
                "source": md.get("source", "dream-consolidation"),
                "metadata": md,
            })
    out.sort(key=lambda r: r.get("consolidated_at") or "", reverse=True)
    return {"items": out[:limit]}


@router.get("/experiments/recent")
def experiments_recent(limit: int = Query(20, ge=1, le=200)) -> dict:
    """Recent dream-pass experiments — currently surfaced via the dream
    history ring; an entry counts as an experiment if it ran a
    consolidation cycle (in/out counts present).
    """
    items = [
        {
            "id": r.get("id") or f"dream-{i}",
            "domain": r.get("domain"),
            "input_count": r.get("input_count", 0),
            "output_count": r.get("output_count", 0),
            "timestamp": r.get("timestamp"),
            "trigger": r.get("trigger", "manual"),
        }
        for i, r in enumerate(list(_dream_history)[:limit])
        if isinstance(r, dict)
    ]
    return {"items": items}


@router.get("/per-persona")
def per_persona() -> dict:
    """Lesson + working counts grouped by persona role, for the
    constellation viz. Returns one row per (domain, persona_role) plus
    a `function_key` join field so the front-end can attach the visual
    to the right planet."""
    stores = _all_domain_memories()
    buckets: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"lessons": 0, "working": 0, "recent_lesson": None}
    )
    for dom, store in stores.items():
        try:
            entries = store.list_all(limit=1000)
        except Exception:
            log.exception("per-persona: list_all failed for %s", dom)
            continue
        for e in entries:
            md = e.get("metadata") or {}
            skill = (md.get("agent_skill") or "").strip()
            persona_role = ""
            if skill.startswith("persona:"):
                persona_role = skill.split(":", 2)[1]
            if not persona_role:
                persona_role = "_unattributed"
            kind = md.get("kind", "working")
            bucket = buckets[(dom, persona_role)]
            if kind == "lesson":
                bucket["lessons"] += 1
                if not bucket["recent_lesson"]:
                    bucket["recent_lesson"] = e.get("memory")
            else:
                bucket["working"] += 1

    # Build a reverse index persona_role -> function_key from FUNCTIONS.
    persona_to_function = _build_persona_to_function_index()

    items = [
        {
            "domain": dom,
            "persona_role": role,
            "function_key": persona_to_function.get(role, ""),
            "lessons": v["lessons"],
            "working": v["working"],
            "recent_lesson": v["recent_lesson"],
        }
        for (dom, role), v in buckets.items()
    ]
    items.sort(key=lambda r: (-r["lessons"], -r["working"]))
    return {"items": items}


def _build_persona_to_function_index() -> dict[str, str]:
    """Walk every FUNCTIONS' persona_hierarchy and emit role → function name.

    Cached at module level on first call. Each role maps to the FIRST
    function whose tree contains it (most roles are unique to a function
    in this repo)."""
    global _persona_to_function_cache
    if _persona_to_function_cache is not None:
        return _persona_to_function_cache
    out: dict[str, str] = {}
    try:
        from api.shared.functions import FUNCTIONS

        def _walk(node, function_name: str) -> None:
            role = getattr(node, "role", None)
            if role and role not in out:
                out[role] = function_name
            for child in getattr(node, "manages", []) or []:
                _walk(child, function_name)

        for name, fn in FUNCTIONS.items():
            if name == "legacy":
                continue
            _walk(fn.persona_hierarchy, name)
    except Exception:
        log.exception("per-persona: failed to build persona_to_function index")
    _persona_to_function_cache = out
    return out


_persona_to_function_cache: dict[str, str] | None = None
