from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.server.services.lessons.working_memory_store import (
    InMemoryWorkingMemoryStore,
    Mem0WorkingMemoryStore,
    _serialise_note,
    _user_id_for,
)
from api.server.services.lessons.working_memory_types import WorkingNote


def _note(
    note_id: str = "WN-1",
    workflow_id: str = "WF-1",
    agent_skill: str = "interview-recommender",
) -> WorkingNote:
    return WorkingNote(
        id=note_id,
        workflow_id=workflow_id,
        agent_skill=agent_skill,
        kind="observation",
        body="screening flagged employment-date inconsistency",
    )


def test_user_id_isolation_per_workflow() -> None:
    a = _user_id_for("WF-1")
    b = _user_id_for("WF-2")
    assert a != b
    assert a.startswith("working-memory:")


def test_in_memory_add_then_list() -> None:
    store = InMemoryWorkingMemoryStore()
    note = _note()
    store.add(note)
    notes = store.list_for_workflow(workflow_id="WF-1")
    assert notes == [note]


def test_in_memory_list_skips_consumed() -> None:
    store = InMemoryWorkingMemoryStore()
    n = _note()
    store.add(n)
    store.mark_consumed(note_id=n.id, dream_pass_id="DP-1")
    assert store.list_for_workflow(workflow_id="WF-1") == []


def test_in_memory_list_recent_across_workflows() -> None:
    store = InMemoryWorkingMemoryStore()
    store.add(_note())
    store.add(_note(note_id="WN-2", workflow_id="WF-2", agent_skill="other"))
    notes = store.list_recent_unconsumed(
        domain_agents=("interview-recommender", "other"), limit=10
    )
    assert {n.id for n in notes} == {"WN-1", "WN-2"}


def test_in_memory_list_recent_filters_unknown_agent() -> None:
    store = InMemoryWorkingMemoryStore()
    store.add(_note())
    notes = store.list_recent_unconsumed(domain_agents=("other",), limit=10)
    assert notes == []


def test_mem0_add_uses_workflow_scoped_user_id_and_infer_false() -> None:
    fake = MagicMock()
    store = Mem0WorkingMemoryStore(memory=fake)
    note = _note(workflow_id="WF-7")

    store.add(note)

    fake.add.assert_called_once()
    _, kwargs = fake.add.call_args
    assert kwargs["user_id"] == _user_id_for("WF-7")
    assert kwargs["infer"] is False
    assert kwargs["metadata"]["agent_skill"] == "interview-recommender"
    assert kwargs["metadata"]["kind"] == "observation"


def test_mem0_list_recent_filters_consumed_in_memory() -> None:
    fake = MagicMock()
    consumed = _note(note_id="WN-CONS").mark_consumed(dream_pass_id="DP-X")
    fake.get_all.return_value = {
        "results": [
            {"metadata": _serialise_note(_note())},
            {"metadata": _serialise_note(consumed)},
        ]
    }
    store = Mem0WorkingMemoryStore(memory=fake)

    notes = store.list_recent_unconsumed(domain_agents=("interview-recommender",), limit=10)

    assert [n.id for n in notes] == ["WN-1"]
    _, kwargs = fake.get_all.call_args
    assert kwargs["filters"] == {"agent_skill": ["interview-recommender"]}
    assert kwargs["limit"] == 10


def test_mem0_mark_consumed_deletes() -> None:
    fake = MagicMock()
    store = Mem0WorkingMemoryStore(memory=fake)

    store.mark_consumed(note_id="WN-1", dream_pass_id="DP-1")

    fake.delete.assert_called_once_with(memory_id="WN-1")
