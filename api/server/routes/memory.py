"""Domain-generic memory layer surface.

Four read-only endpoints back the Fleet UI Memory page:
  GET /api/memory/working-notes?agent_skill=&workflow_id=&limit=
  GET /api/memory/lessons/active?domain=
  GET /api/memory/dream-passes/recent?limit=
  GET /api/memory/experiments/recent?dream_pass_id=&limit=

All reads go through app_state singletons constructed in state.py
(lesson_store, working_memory_store) and the live entity graph for
DreamPass / Experiment nodes. No writes — the only writers are the
dream-pass loop itself and persona_responder's working-memory capture.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from api.server.services.lessons.working_memory_store import (
    InMemoryWorkingMemoryStore,
)
from api.server.state import app_state

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory", tags=["memory"])


def _graph():
    return getattr(app_state, "entities", None) if getattr(app_state, "_entity_plane_enabled", False) else None


# ---------------------------------------------------------------------
# Working notes
# ---------------------------------------------------------------------

@router.get("/working-notes")
def working_notes(
    agent_skill: str | None = Query(None),
    workflow_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, list[dict[str, Any]]]:
    """Most recent WorkingNotes captured during persona decisions.

    Optional filters narrow on agent_skill or workflow_id; with neither,
    the most recent ``limit`` notes across every skill are returned
    (newest first).
    """
    store = app_state.working_memory_store
    if not isinstance(store, InMemoryWorkingMemoryStore):
        return {"items": []}
    # Intentional read of the private _by_id dict — the route shares the
    # singleton with the orchestrator's governor and needs a "list all"
    # view the public API doesn't expose. See state.py for the sharing
    # rationale.
    notes = list(store._by_id.values())  # type: ignore[attr-defined]
    if agent_skill:
        notes = [n for n in notes if n.agent_skill == agent_skill]
    if workflow_id:
        notes = [n for n in notes if n.workflow_id == workflow_id]
    notes.sort(key=lambda n: n.captured_at, reverse=True)
    notes = notes[:limit]
    return {"items": [_note_to_dict(n) for n in notes]}


# ---------------------------------------------------------------------
# Active lessons
# ---------------------------------------------------------------------

@router.get("/lessons/active")
def lessons_active(
    domain: str | None = Query(None),
) -> dict[str, list[dict[str, Any]]]:
    """Currently active (un-pruned) lessons.

    Backed by LessonStore.search so it works against both
    InMemoryLessonStore and Mem0LessonStore — the route is storage-
    agnostic. A domain filter narrows the LessonScope; without one,
    we fan out over the set of known dream-pass domains (today: just
    'hiring', read from api/server/skills/dream-passes/).
    """
    from api.server.services.lessons.types import LessonScope
    store = app_state.lesson_store
    if domain:
        domains = [domain]
    else:
        from pathlib import Path as _Path
        dream_passes_dir = _Path(__file__).resolve().parents[1] / "skills" / "dream-passes"
        domains = (
            [p.name for p in dream_passes_dir.iterdir() if p.is_dir()]
            if dream_passes_dir.exists()
            else ["hiring"]
        )
    items: list[dict[str, Any]] = []
    for d in domains:
        try:
            lessons = store.search(query="", scope=LessonScope(domain=d), top_k=200)
        except Exception:
            log.exception("memory: lessons_active search failed for domain=%s", d)
            continue
        items.extend(_lesson_to_dict(l) for l in lessons)
    return {"items": items}


# ---------------------------------------------------------------------
# Lesson recall (semantic top-K)
# ---------------------------------------------------------------------

class _RecallBody(BaseModel):
    domain: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)


@router.post("/lessons/recall")
def lessons_recall(body: _RecallBody) -> dict[str, list[dict[str, Any]]]:
    """Top-K relevant lessons for a query string. Backs the Functions-
    process agent runtime: every LLM agent call POSTs the candidate
    context (role title + jurisdiction + skill name + workflow id) as
    `query`, gets the top 3 semantically-relevant lessons, and
    prepends them as natural-language guidance to its prompt. This
    replaces the prepend-everything pattern."""
    from api.server.services.lessons.types import LessonScope
    store = app_state.lesson_store
    scope = LessonScope(domain=body.domain)
    try:
        ranked = store.search_ranked(query=body.query, scope=scope, top_k=body.top_k)
    except Exception:
        log.exception("memory: lessons_recall search failed")
        return {"items": []}
    items = []
    for l, score in ranked:
        d = _lesson_to_dict(l)
        d["score"] = float(score)
        items.append(d)
    return {"items": items}


# ---------------------------------------------------------------------
# Dream passes & experiments (Kuzu-backed)
# ---------------------------------------------------------------------

@router.get("/dream-passes/recent")
def dream_passes_recent(
    limit: int = Query(20, ge=1, le=200),
) -> dict[str, list[dict[str, Any]]]:
    """Recent DreamPass nodes, newest first."""
    g = _graph()
    if g is None:
        return {"items": []}
    try:
        rows = g.query(
            "MATCH (d:DreamPass) "
            "RETURN d.id AS id, d.domain AS domain, "
            "       d.skill_version AS skill_version, "
            "       d.started_at AS started_at, "
            "       d.completed_at AS completed_at, "
            "       d.status AS status, "
            "       d.candidates_proposed AS candidates_proposed, "
            "       d.candidates_promoted AS candidates_promoted "
            f"ORDER BY d.started_at DESC LIMIT {int(limit)}",
        )
    except Exception:
        log.exception("memory: dream-passes query failed")
        return {"items": []}
    return {"items": [_iso_keys(r, ('started_at', 'completed_at')) for r in rows]}


@router.get("/experiments/recent")
def experiments_recent(
    dream_pass_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, list[dict[str, Any]]]:
    """Recent Experiment nodes, optionally scoped to one dream pass."""
    g = _graph()
    if g is None:
        return {"items": []}
    where = "WHERE e.dream_pass_id = $dp" if dream_pass_id else ""
    params: dict[str, Any] = {"dp": dream_pass_id} if dream_pass_id else {}
    try:
        rows = g.query(
            "MATCH (e:Experiment) "
            f"{where} "
            "RETURN e.id AS id, e.dream_pass_id AS dream_pass_id, "
            "       e.candidate_lesson_id AS candidate_lesson_id, "
            "       e.control_score AS control_score, "
            "       e.treatment_score AS treatment_score, "
            "       e.delta AS delta, e.n_samples AS n_samples, "
            "       e.verdict AS verdict, e.run_at AS run_at "
            f"ORDER BY e.run_at DESC LIMIT {int(limit)}",
            params,
        )
    except Exception:
        log.exception("memory: experiments query failed")
        return {"items": []}
    return {"items": [_iso_keys(r, ('run_at',)) for r in rows]}


# ---------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------

def _note_to_dict(n: Any) -> dict[str, Any]:
    return {
        "id": getattr(n, "id", None),
        "workflow_id": getattr(n, "workflow_id", None),
        "agent_skill": getattr(n, "agent_skill", None),
        "kind": getattr(n, "kind", None),
        "body": getattr(n, "body", None),
        "captured_at": _iso(getattr(n, "captured_at", None)),
        "consumed_by_dream_pass": getattr(n, "consumed_by_dream_pass", None),
    }


def _lesson_to_dict(l: Any) -> dict[str, Any]:
    return {
        "id": getattr(l, "id", None),
        "body": getattr(l, "body", None),
        "domain": getattr(getattr(l, "scope", None), "domain", None),
        "persona_role": getattr(getattr(l, "scope", None), "persona_role", None),
        "promoted_at": _iso(getattr(getattr(l, "provenance", None), "promoted_at", None)),
        "rubric_score_delta": getattr(getattr(l, "provenance", None), "rubric_score_delta", None),
        "experiment_n": getattr(getattr(l, "provenance", None), "experiment_n", None),
        "proposed_by": getattr(getattr(l, "provenance", None), "proposed_by", None),
        "status": getattr(l, "status", None),
    }


def _iso(ts: Any) -> Any:
    return ts.isoformat() if hasattr(ts, "isoformat") else ts


def _iso_keys(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {**row, **{k: _iso(row.get(k)) for k in keys}}
