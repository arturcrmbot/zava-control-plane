from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.server.services.governance.kernel import Decision
from api.server.services.lessons.governor import LessonGovernor
from api.server.services.lessons.store import InMemoryLessonStore
from api.server.services.lessons.types import (
    Lesson,
    LessonCandidate,
    LessonProvenance,
    LessonScope,
)


def _allow_kernel() -> MagicMock:
    return MagicMock(
        evaluate_tool_call=MagicMock(
            return_value=Decision(allowed=True, action="allow", reason="ok")
        )
    )


def _candidate() -> LessonCandidate:
    return LessonCandidate(
        id="L-FLAGGED-1",
        body="lessons in this domain should escalate to vendor review",
        scope=LessonScope(domain="hiring"),
        proposed_by="dream-pass:hiring",
        rationale="observed pattern",
    )


def _governor(store, audit, provenance, actor="dream-pass:hiring") -> LessonGovernor:
    return LessonGovernor(
        store=store,
        kernel=lambda: _allow_kernel(),
        audit=audit,
        provenance=provenance,
        actor=actor,
    )


def test_write_flagged_candidate_records_status_candidate() -> None:
    store = InMemoryLessonStore()
    audit = MagicMock()
    provenance = MagicMock()
    governor = _governor(store, audit, provenance)

    governor.write_flagged_candidate(
        candidate=_candidate(),
        experiment_id="EXP-1",
        delta=0.07,
        n=40,
        flag_reason="implausible_delta",
    )

    provenance.record_candidate.assert_called_once()
    _, kwargs = provenance.record_candidate.call_args
    assert kwargs["flag_reason"] == "implausible_delta"
    assert kwargs["experiment_id"] == "EXP-1"
    assert kwargs["body"] == _candidate().body

    action_arg, details = audit.log.call_args[0]
    assert action_arg == "lesson.flag_candidate"
    assert details["flag_reason"] == "implausible_delta"
    assert details["delta"] == 0.07
    # Flagged candidates should NOT be added to the active store.
    assert store.get("L-FLAGGED-1") is None


def test_approve_flagged_promotes_via_existing_write() -> None:
    store = InMemoryLessonStore()
    audit = MagicMock()
    provenance = MagicMock()
    candidate_lesson = Lesson(
        id="L-FLAGGED-1",
        body="lessons in this domain should escalate to vendor review",
        scope=LessonScope(domain="hiring"),
        provenance=LessonProvenance(
            proposed_by="dream-pass:hiring",
            run_ids=(),
            rubric_score_delta=0.07,
            experiment_n=40,
        ),
        status="candidate",
    )
    provenance.fetch_candidate.return_value = candidate_lesson
    governor = _governor(store, audit, provenance, actor="operator:human")

    governor.approve_flagged(lesson_id="L-FLAGGED-1", approver="alice@example.com")

    # Re-recorded as status=active in Kuzu and added to the store.
    provenance.record.assert_called_once()
    promoted = provenance.record.call_args[0][0]
    assert promoted.status == "active"
    assert store.get("L-FLAGGED-1") is not None
    assert store.get("L-FLAGGED-1").status == "active"

    action_arg, details = audit.log.call_args[0]
    assert action_arg == "lesson.approve_flagged"
    assert details["approver"] == "alice@example.com"


def test_approve_flagged_raises_when_candidate_missing() -> None:
    store = InMemoryLessonStore()
    audit = MagicMock()
    provenance = MagicMock()
    provenance.fetch_candidate.return_value = None
    governor = _governor(store, audit, provenance, actor="operator:human")

    with pytest.raises(LookupError):
        governor.approve_flagged(lesson_id="nope", approver="alice@example.com")


def test_reject_flagged_marks_pruned_with_reason() -> None:
    store = InMemoryLessonStore()
    audit = MagicMock()
    provenance = MagicMock()
    governor = _governor(store, audit, provenance, actor="operator:human")

    governor.reject_flagged(
        lesson_id="L-FLAGGED-1",
        reviewer="alice@example.com",
        reason="contradicts policy",
    )

    provenance.mark_pruned.assert_called_once_with(
        "L-FLAGGED-1", reason="rejected_by_review: contradicts policy"
    )
    action_arg, details = audit.log.call_args[0]
    assert action_arg == "lesson.reject_flagged"
    assert details["reviewer"] == "alice@example.com"
    assert details["reason"] == "contradicts policy"
