"""Mem0-backed implementation of LessonStore.

Mem0 is the storage tier only. Governance, audit ledger, and Kuzu
provenance are added by LessonGovernor — never call this class directly
from agent code.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any, Protocol

from api.server.services.lessons.types import (
    Lesson,
    LessonProvenance,
    LessonScope,
)

_USER_ID = "lesson-store"


class _MemoryLike(Protocol):
    def add(
        self,
        messages: str,
        *,
        user_id: str,
        metadata: dict[str, Any],
        infer: bool = ...,
    ) -> Any: ...
    def search(
        self,
        query: str,
        *,
        user_id: str,
        filters: dict[str, Any],
        limit: int,
    ) -> Any: ...
    def delete(self, *, memory_id: str) -> Any: ...


class Mem0LessonStore:
    """Lesson store backed by mem0.Memory.

    Memories are scoped by `user_id="lesson-store"` and filtered by
    `domain` at search time. The full Lesson is serialised into metadata
    so we can rehydrate on read; this keeps Mem0 as a pure storage tier.
    """

    def __init__(self, *, memory: _MemoryLike | None = None) -> None:
        if memory is None:
            from mem0 import Memory
            memory = Memory()
        self._memory = memory

    def add(self, lesson: Lesson) -> None:
        self._memory.add(
            messages=lesson.body,
            user_id=_USER_ID,
            metadata=_serialise_lesson(lesson),
            # infer=False skips mem0's LLM entity-extraction step. Our
            # body is already a curated lesson; we don't want mem0 to
            # rewrite it.
            infer=False,
        )

    def get(self, lesson_id: str) -> Lesson | None:
        results = self._memory.search(
            query=lesson_id,
            user_id=_USER_ID,
            filters={"lesson_id": lesson_id},
            limit=1,
        )
        for result in (results or {}).get("results", []):
            return _deserialise_lesson(result["metadata"])
        return None

    def search(
        self,
        query: str,
        *,
        scope: LessonScope,
        top_k: int = 5,
    ) -> list[Lesson]:
        results = self._memory.search(
            query=query,
            user_id=_USER_ID,
            filters={"domain": scope.domain},
            limit=top_k,
        )
        lessons: list[Lesson] = []
        for result in (results or {}).get("results", []):
            metadata = result.get("metadata") or {}
            try:
                lesson = _deserialise_lesson(metadata)
            except (KeyError, json.JSONDecodeError):
                continue
            if lesson.status != "active":
                continue
            if not lesson.scope.matches(scope):
                continue
            lessons.append(lesson)
        return lessons

    def prune(self, lesson_id: str, *, reason: str) -> None:
        del reason
        self._memory.delete(memory_id=lesson_id)


def _serialise_lesson(lesson: Lesson) -> dict[str, Any]:
    payload = asdict(lesson)
    payload["provenance"]["promoted_at"] = lesson.provenance.promoted_at.isoformat()
    return {
        "lesson_id": lesson.id,
        "domain": lesson.scope.domain,
        "persona_role": lesson.scope.persona_role or "",
        "market": lesson.scope.market or "",
        "status": lesson.status,
        "lesson_json": json.dumps(payload),
    }


def _deserialise_lesson(metadata: dict[str, Any]) -> Lesson:
    raw = json.loads(metadata["lesson_json"])
    scope = LessonScope(**raw["scope"])
    prov_raw = raw["provenance"]
    provenance = LessonProvenance(
        proposed_by=prov_raw["proposed_by"],
        run_ids=tuple(prov_raw["run_ids"]),
        rubric_score_delta=prov_raw["rubric_score_delta"],
        experiment_n=prov_raw["experiment_n"],
        promoted_at=datetime.fromisoformat(prov_raw["promoted_at"]),
    )
    return Lesson(
        id=raw["id"],
        body=raw["body"],
        scope=scope,
        provenance=provenance,
        status=raw["status"],
        supersedes=raw.get("supersedes"),
    )
