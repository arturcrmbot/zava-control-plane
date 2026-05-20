from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from api.server.services.governance.kernel import Decision
from api.server.services.lessons.governor import LessonGovernor
from api.server.services.lessons.store import InMemoryLessonStore
from api.server.services.lessons.lesson_metrics import LessonMetrics
from api.server.services.lessons.lesson_lifecycle import LessonStatus
from api.server.services.lessons.types import Lesson, LessonProvenance, LessonScope


def _make_lesson(lid: str, status: str = "active") -> Lesson:
    return Lesson(
        id=lid,
        body=f"lesson {lid}",
        scope=LessonScope(domain="hiring"),
        provenance=LessonProvenance(
            proposed_by="t", run_ids=(),
            rubric_score_delta=0.1, experiment_n=50,
            promoted_at=datetime.now(timezone.utc),
        ),
        status=status,
    )


def _make_governor(store):
    kernel = MagicMock(name="GovernanceKernel")
    kernel.evaluate_tool_call.return_value = Decision(
        allowed=True, action="allow", reason="ok"
    )
    audit = MagicMock(name="AuditLogger")
    provenance = MagicMock(name="KuzuLessonProvenance")
    return LessonGovernor(
        store=store,
        kernel=lambda: kernel,
        audit=audit,
        provenance=provenance,
        actor="dream-pass:hiring",
    )


def test_apply_lifecycle_demotes_active_lesson_exceeding_override_rate():
    store = InMemoryLessonStore()
    lesson = _make_lesson("L1", status="active")
    store.add(lesson)

    governor = _make_governor(store)

    metrics = MagicMock(spec=LessonMetrics)
    metrics.invocations.return_value = 50
    metrics.hitl_override_count.return_value = 20  # 40% > 20%

    transitions = governor.apply_lifecycle(
        domain="hiring",
        metrics=metrics,
        shadow_invocations_required=50,
        max_override_rate=0.20,
        retire_after_days=30,
    )
    assert transitions == [("L1", LessonStatus.DEMOTED)]


def test_apply_lifecycle_returns_empty_when_nothing_changes():
    store = InMemoryLessonStore()
    store.add(_make_lesson("L1", status="active"))
    governor = _make_governor(store)
    metrics = MagicMock(spec=LessonMetrics)
    metrics.invocations.return_value = 50
    metrics.hitl_override_count.return_value = 1  # 2% << 20%
    transitions = governor.apply_lifecycle(
        domain="hiring", metrics=metrics,
        shadow_invocations_required=50, max_override_rate=0.20,
        retire_after_days=30,
    )
    assert transitions == []
