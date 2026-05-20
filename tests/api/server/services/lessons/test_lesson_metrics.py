from datetime import datetime, timezone

from api.server.services.lessons.lesson_metrics import LessonMetrics
from api.server.services.lessons.working_memory_store import InMemoryWorkingMemoryStore
from api.server.services.lessons.working_memory_types import WorkingNote


def _wn(*, lesson_id: str, workflow_id: str, kind: str = "lesson_used", body: str | None = None) -> WorkingNote:
    return WorkingNote(
        id=f"WN-{lesson_id}-{workflow_id}",
        workflow_id=workflow_id,
        agent_skill="hiring-segment-b",
        kind=kind,  # type: ignore[arg-type]
        body=body or f"used {lesson_id}: …",
    )


def test_invocations_counts_lesson_used_notes_for_a_lesson():
    store = InMemoryWorkingMemoryStore()
    store._by_id["a"] = _wn(lesson_id="L1", workflow_id="WF-1")
    store._by_id["b"] = _wn(lesson_id="L1", workflow_id="WF-2")
    store._by_id["c"] = _wn(lesson_id="L2", workflow_id="WF-1")
    m = LessonMetrics(working_memory_store=store, exceptions_provider=lambda: [])
    assert m.invocations("L1") == 2
    assert m.invocations("L2") == 1
    assert m.invocations("UNKNOWN") == 0


def test_hitl_override_count_intersects_used_workflows_with_open_exceptions():
    store = InMemoryWorkingMemoryStore()
    store._by_id["a"] = _wn(lesson_id="L1", workflow_id="WF-1")
    store._by_id["b"] = _wn(lesson_id="L1", workflow_id="WF-2")
    exceptions = [{"workflow_id": "WF-2", "resolved": False}]
    m = LessonMetrics(working_memory_store=store, exceptions_provider=lambda: exceptions)
    assert m.hitl_override_count("L1") == 1
