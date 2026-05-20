"""Per-lesson outcome metrics.

A lesson's outcome is measured by:
  - invocations: how many times it was in an agent's prompt
    (counted from kind="lesson_used" working notes)
  - hitl_override_count: how many of those invocations led to a
    workflow that the operator subsequently overrode at a HITL gate.
    Proxy for "the lesson did not improve the decision."

The intersection between (workflows where lesson_used) and (workflows
with open/resolved-by-operator exceptions) is the override rate. Not
perfect — operator overrides happen for many reasons — but it's the
strongest signal available without a labeled ground truth.
"""
from __future__ import annotations

from typing import Callable, Iterable

from api.server.services.lessons.working_memory_store import WorkingMemoryStore


def _lesson_id_from_body(body: str | None) -> str | None:
    """lesson_used note body format: 'used <id>: <preview>'."""
    if not body or not body.startswith("used "):
        return None
    rest = body[len("used "):]
    sep = rest.find(":")
    if sep <= 0:
        return None
    return rest[:sep].strip()


class LessonMetrics:
    def __init__(
        self,
        *,
        working_memory_store: WorkingMemoryStore,
        exceptions_provider: Callable[[], Iterable[dict]],
    ) -> None:
        self._wms = working_memory_store
        self._exceptions = exceptions_provider

    def _used_notes_for(self, lesson_id: str) -> list:
        store = self._wms
        if not hasattr(store, "_by_id"):
            return []
        return [
            n for n in store._by_id.values()
            if getattr(n, "kind", None) == "lesson_used"
            and _lesson_id_from_body(getattr(n, "body", None)) == lesson_id
        ]

    def invocations(self, lesson_id: str) -> int:
        return len(self._used_notes_for(lesson_id))

    def hitl_override_count(self, lesson_id: str) -> int:
        used_workflows = {
            getattr(n, "workflow_id", None) for n in self._used_notes_for(lesson_id)
        } - {None}
        overridden = {
            e.get("workflow_id") for e in self._exceptions() if e.get("workflow_id")
        }
        return len(used_workflows & overridden)
