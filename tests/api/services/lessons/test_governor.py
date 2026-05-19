from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.server.services.governance.kernel import Decision, GovernanceDenied
from api.server.services.lessons.governor import LessonGovernor
from api.server.services.lessons.store import InMemoryLessonStore


@pytest.fixture
def fake_kernel() -> MagicMock:
    return MagicMock(name="GovernanceKernel")


@pytest.fixture
def fake_audit() -> MagicMock:
    return MagicMock(name="AuditLogger")


@pytest.fixture
def fake_provenance() -> MagicMock:
    return MagicMock(name="KuzuLessonProvenance")


def _governor(store, fake_kernel, fake_audit, fake_provenance) -> LessonGovernor:
    return LessonGovernor(
        store=store,
        kernel=lambda: fake_kernel,
        audit=fake_audit,
        provenance=fake_provenance,
        actor="dream-pass:hiring",
    )


def test_write_calls_kernel_then_store_then_audit(
    make_lesson, fake_kernel, fake_audit, fake_provenance
) -> None:
    fake_kernel.evaluate_tool_call.return_value = Decision(
        allowed=True, action="allow", reason="ok"
    )
    store = InMemoryLessonStore()
    governor = _governor(store, fake_kernel, fake_audit, fake_provenance)
    lesson = make_lesson()

    governor.write(lesson)

    fake_kernel.evaluate_tool_call.assert_called_once()
    _, kwargs = fake_kernel.evaluate_tool_call.call_args
    assert kwargs["actor"] == "dream-pass:hiring"
    assert kwargs["tool"] == "lesson.write"
    assert kwargs["args"]["lesson_id"] == lesson.id
    assert store.get(lesson.id) == lesson
    fake_provenance.record.assert_called_once_with(lesson)
    fake_audit.log.assert_called_once()
    action_arg, details = fake_audit.log.call_args[0]
    assert action_arg == "lesson.write"
    assert details["lesson_id"] == lesson.id
    assert details["governance_action"] == "allow"


def test_write_denied_in_enforce_mode_raises_and_skips_store(
    make_lesson, fake_kernel, fake_audit, fake_provenance
) -> None:
    fake_kernel.evaluate_tool_call.return_value = Decision(
        allowed=False,
        action="deny",
        reason="capability missing",
        enforcement_mode="enforce",
    )
    store = InMemoryLessonStore()
    governor = _governor(store, fake_kernel, fake_audit, fake_provenance)
    lesson = make_lesson()

    with pytest.raises(GovernanceDenied):
        governor.write(lesson)

    assert store.get(lesson.id) is None
    fake_provenance.record.assert_not_called()
    # No ledger entry on enforced deny — the raise carries the Decision.
    fake_audit.log.assert_not_called()


def test_write_denied_in_log_only_records_deny_but_skips_store(
    make_lesson, fake_kernel, fake_audit, fake_provenance
) -> None:
    fake_kernel.evaluate_tool_call.return_value = Decision(
        allowed=False,
        action="deny",
        reason="capability missing",
        enforcement_mode="log_only",
    )
    store = InMemoryLessonStore()
    governor = _governor(store, fake_kernel, fake_audit, fake_provenance)
    lesson = make_lesson()

    governor.write(lesson)

    # Phase 2 log_only: no raise, write proceeds, ledger records deny.
    # Phase 6 will flip this — same call will raise GovernanceDenied.
    assert store.get(lesson.id) == lesson
    fake_provenance.record.assert_called_once_with(lesson)
    action_arg, details = fake_audit.log.call_args[0]
    assert action_arg == "lesson.write"
    assert details["governance_action"] == "deny"
    assert details["enforcement_mode"] == "log_only"


def test_prune_records_in_ledger_with_reason(
    make_lesson, fake_kernel, fake_audit, fake_provenance
) -> None:
    fake_kernel.evaluate_tool_call.return_value = Decision(
        allowed=True, action="allow", reason="ok"
    )
    store = InMemoryLessonStore()
    lesson = make_lesson()
    store.add(lesson)
    governor = _governor(store, fake_kernel, fake_audit, fake_provenance)

    governor.prune(lesson.id, reason="superseded by stronger evidence")

    action_arg, details = fake_audit.log.call_args[0]
    assert action_arg == "lesson.prune"
    assert details["reason"] == "superseded by stronger evidence"
    fake_provenance.mark_pruned.assert_called_once_with(
        lesson.id, reason="superseded by stronger evidence"
    )



def test_write_denied_by_kernel_in_enforce_mode_with_real_registry_gate(
    make_lesson, monkeypatch
) -> None:
    from api.server.services.governance import kernel

    monkeypatch.setenv('AGT_ENFORCE', '1')
    store = InMemoryLessonStore()
    governor = LessonGovernor(
        store=store,
        kernel=kernel,
        audit=MagicMock(name='AuditLogger'),
        provenance=MagicMock(name='KuzuLessonProvenance'),
        actor='interview-recommender',
    )

    with pytest.raises(GovernanceDenied):
        governor.write(make_lesson())
