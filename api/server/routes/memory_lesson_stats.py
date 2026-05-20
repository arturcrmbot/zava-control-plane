"""Per-lesson observability surface.

GET /api/memory/lessons/{id}/stats — invocation count, HITL override
count, override rate, first+last used timestamps. Powers the Dashboard
"Lessons used (1h)" tile and the per-lesson drill-down on the Memory
page.
"""
from __future__ import annotations

from fastapi import APIRouter

from api.server.state import app_state
from api.server.services.lessons.lesson_metrics import LessonMetrics, _lesson_id_from_body


router = APIRouter(prefix="/api/memory/lessons", tags=["memory"])


@router.get("/{lesson_id}/stats")
def lesson_stats(lesson_id: str) -> dict:
    metrics = LessonMetrics(
        working_memory_store=app_state.working_memory_store,
        exceptions_provider=lambda: [],  # TODO wire app_state.store.list_open_exceptions
    )
    inv = metrics.invocations(lesson_id)
    override = metrics.hitl_override_count(lesson_id)
    rate = (override / inv) if inv > 0 else 0.0

    store = app_state.working_memory_store
    notes = []
    if hasattr(store, "_by_id"):
        for n in store._by_id.values():
            if getattr(n, "kind", None) == "lesson_used" and _lesson_id_from_body(getattr(n, "body", None)) == lesson_id:
                notes.append(n)
    notes.sort(key=lambda n: n.captured_at)
    first_at = notes[0].captured_at.isoformat() if notes else None
    last_at = notes[-1].captured_at.isoformat() if notes else None

    return {
        "lesson_id": lesson_id,
        "invocations": inv,
        "hitl_override_count": override,
        "override_rate": round(rate, 3),
        "first_used_at": first_at,
        "last_used_at": last_at,
    }
