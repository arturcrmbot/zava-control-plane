from __future__ import annotations

from api.server.services.lessons.store import InMemoryLessonStore
from api.server.services.lessons.types import LessonScope


def test_add_then_get(make_lesson) -> None:
    store = InMemoryLessonStore()
    lesson = make_lesson()
    store.add(lesson)
    assert store.get(lesson.id) == lesson


def test_search_returns_in_scope_lessons(make_lesson) -> None:
    store = InMemoryLessonStore()
    hire = make_lesson(domain="hiring")
    kyc = make_lesson(domain="vendor_kyc")
    store.add(hire)
    store.add(kyc)

    results = store.search("reference checks", scope=LessonScope(domain="hiring"), top_k=5)

    assert hire in results
    assert kyc not in results


def test_search_respects_broader_lesson_scope(make_lesson) -> None:
    store = InMemoryLessonStore()
    broad = make_lesson(domain="hiring", persona_role=None)
    store.add(broad)

    results = store.search(
        "anything",
        scope=LessonScope(domain="hiring", persona_role="recruiter"),
        top_k=5,
    )

    assert broad in results


def test_search_does_not_return_pruned(make_lesson) -> None:
    store = InMemoryLessonStore()
    lesson = make_lesson()
    store.add(lesson)
    store.prune(lesson.id, reason="superseded by stronger evidence")

    results = store.search("anything", scope=lesson.scope, top_k=5)

    assert results == []


def test_prune_marks_status(make_lesson) -> None:
    store = InMemoryLessonStore()
    lesson = make_lesson()
    store.add(lesson)
    store.prune(lesson.id, reason="superseded by stronger evidence")

    stored = store.get(lesson.id)
    assert stored is not None
    assert stored.status == "pruned"
