"""LessonStore Protocol + a deterministic in-memory implementation for tests."""
from __future__ import annotations

from dataclasses import replace
from typing import Protocol, runtime_checkable

from api.server.services.lessons.types import Lesson, LessonScope


@runtime_checkable
class LessonStore(Protocol):
    """Pluggable backend for the lesson tier.

    Implementations: InMemoryLessonStore (tests), Mem0LessonStore (default).
    Future: AzureSearchLessonStore, PgVectorLessonStore.

    Implementations MUST be storage-only. Governance, ledger writes, and
    Kuzu provenance are added by LessonGovernor in governor.py.
    """

    def add(self, lesson: Lesson) -> None: ...

    def get(self, lesson_id: str) -> Lesson | None: ...

    def search(
        self,
        query: str,
        *,
        scope: LessonScope,
        top_k: int = 5,
    ) -> list[Lesson]: ...

    def search_ranked(
        self,
        query: str,
        *,
        scope: LessonScope,
        top_k: int = 5,
    ) -> list[tuple[Lesson, float]]: ...

    def prune(self, lesson_id: str, *, reason: str) -> None: ...


class InMemoryLessonStore:
    """Deterministic in-memory store. NOT for production — substring match only."""

    def __init__(self) -> None:
        self._by_id: dict[str, Lesson] = {}

    def add(self, lesson: Lesson) -> None:
        self._by_id[lesson.id] = lesson

    def get(self, lesson_id: str) -> Lesson | None:
        return self._by_id.get(lesson_id)

    def search(
        self,
        query: str,
        *,
        scope: LessonScope,
        top_k: int = 5,
    ) -> list[Lesson]:
        del query
        results = [
            lesson
            for lesson in self._by_id.values()
            if lesson.status == "active" and lesson.scope.matches(scope)
        ]
        return results[:top_k]

    def search_ranked(
        self,
        query: str,
        *,
        scope: LessonScope,
        top_k: int = 5,
    ) -> list[tuple[Lesson, float]]:
        return [(l, 1.0) for l in self.search(query, scope=scope, top_k=top_k)]

    def prune(self, lesson_id: str, *, reason: str) -> None:
        del reason
        existing = self._by_id.get(lesson_id)
        if existing is None:
            return
        self._by_id[lesson_id] = replace(existing, status="pruned")
