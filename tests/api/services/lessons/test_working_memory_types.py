from __future__ import annotations

import pytest

from api.server.services.lessons.working_memory_types import WorkingNote


def test_working_note_minimal() -> None:
    note = WorkingNote(
        id="WN-1",
        workflow_id="WF-1",
        agent_skill="interview-recommender",
        kind="observation",
        body="screening flagged employment-date inconsistency",
    )
    assert note.workflow_id == "WF-1"
    assert note.kind == "observation"
    assert note.consumed_by_dream_pass is None


def test_working_note_kind_alphabet_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        WorkingNote(
            id="WN-1",
            workflow_id="WF-1",
            agent_skill="x",
            kind="bogus",  # type: ignore[arg-type]
            body="x",
        )


def test_working_note_mark_consumed_returns_new_instance() -> None:
    note = WorkingNote(
        id="WN-1",
        workflow_id="WF-1",
        agent_skill="x",
        kind="observation",
        body="x",
    )
    consumed = note.mark_consumed(dream_pass_id="DP-1")
    assert consumed.consumed_by_dream_pass == "DP-1"
    assert note.consumed_by_dream_pass is None
