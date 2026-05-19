from __future__ import annotations

import json
from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock

import pytest

from api.server.services.lessons.mem0_store import Mem0LessonStore
from api.server.services.lessons.types import LessonScope


@pytest.fixture
def fake_memory() -> MagicMock:
    return MagicMock(name="mem0.Memory")


def test_add_calls_mem0_with_serialised_lesson(make_lesson, fake_memory) -> None:
    store = Mem0LessonStore(memory=fake_memory)
    lesson = make_lesson()

    store.add(lesson)

    fake_memory.add.assert_called_once()
    _, kwargs = fake_memory.add.call_args
    assert kwargs["user_id"] == "lesson-store"
    assert kwargs["infer"] is False
    metadata = kwargs["metadata"]
    assert metadata["lesson_id"] == lesson.id
    assert metadata["domain"] == "hiring"
    assert "lesson_json" in metadata
    rehydrated = json.loads(metadata["lesson_json"])
    assert rehydrated["body"] == lesson.body


def test_search_passes_scope_into_mem0_filters(make_lesson, fake_memory) -> None:
    store = Mem0LessonStore(memory=fake_memory)
    fake_memory.search.return_value = {"results": []}

    store.search(
        "reference",
        scope=LessonScope(domain="hiring", persona_role="recruiter"),
        top_k=3,
    )

    fake_memory.search.assert_called_once()
    _, kwargs = fake_memory.search.call_args
    assert kwargs["user_id"] == "lesson-store"
    assert kwargs["filters"] == {"domain": "hiring"}
    assert kwargs["limit"] == 3


def test_search_rehydrates_lessons_and_filters_by_scope(
    make_lesson, fake_memory
) -> None:
    in_scope = make_lesson(domain="hiring", persona_role=None)
    narrower = make_lesson(domain="hiring", persona_role="hiring_manager")
    fake_memory.search.return_value = {
        "results": [
            {"metadata": _serialise(in_scope)},
            {"metadata": _serialise(narrower)},
        ]
    }

    store = Mem0LessonStore(memory=fake_memory)
    results = store.search(
        "anything",
        scope=LessonScope(domain="hiring", persona_role="recruiter"),
        top_k=5,
    )

    ids = {lesson.id for lesson in results}
    assert in_scope.id in ids
    assert narrower.id not in ids


def test_search_skips_non_active(make_lesson, fake_memory) -> None:
    active = make_lesson()
    pruned = replace(make_lesson(), status="pruned")
    fake_memory.search.return_value = {
        "results": [
            {"metadata": _serialise(active)},
            {"metadata": _serialise(pruned)},
        ]
    }

    store = Mem0LessonStore(memory=fake_memory)
    results = store.search("x", scope=active.scope, top_k=5)

    ids = {lesson.id for lesson in results}
    assert active.id in ids
    assert pruned.id not in ids


def test_prune_marks_via_mem0_update(make_lesson, fake_memory) -> None:
    store = Mem0LessonStore(memory=fake_memory)
    lesson = make_lesson()
    store.add(lesson)
    fake_memory.reset_mock()

    store.prune(lesson.id, reason="superseded")

    fake_memory.delete.assert_called_once_with(memory_id=lesson.id)


def _serialise(lesson) -> dict[str, Any]:
    from api.server.services.lessons.mem0_store import _serialise_lesson
    return _serialise_lesson(lesson)
