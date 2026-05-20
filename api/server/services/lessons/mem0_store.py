"""Mem0-backed implementation of LessonStore.

Mem0 is the storage tier only. Governance, audit ledger, and Kuzu
provenance are added by LessonGovernor — never call this class directly
from agent code.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from api.server.services.lessons.types import (
    Lesson,
    LessonProvenance,
    LessonScope,
)

_USER_ID = "lesson-store"


def build_default_memory() -> Any:
    """Build a `mem0.Memory` wired to Azure OpenAI + file-backed Chroma.

    - LLM: `azure_openai` pointing at AZURE_OPENAI_DEPLOYMENT (gpt-4o).
      Only invoked if `infer=True`; this store always passes `infer=False`,
      so the LLM client is constructed but never called.
    - Embedder: `azure_openai` pointing at AZURE_OPENAI_EMBED_DEPLOYMENT
      (text-embedding-3-large, 3072 dims).
    - Vector store: `chroma`, persisted to `data/portal/mem0/chroma/` so
      lessons survive `make down && make up`.
    - Auth: when no `*_API_KEY` is set, mem0's Azure client falls back to
      `DefaultAzureCredential` automatically (key-based auth is disabled
      on our Cognitive Services account by tenant policy).

    Raises:
        RuntimeError if AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_EMBED_DEPLOYMENT
        are missing — caller (state.py) catches and falls back to
        InMemoryLessonStore with a loud warning.
    """
    from mem0 import Memory

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    llm_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    embed_deployment = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    if not endpoint:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT not set")
    if not embed_deployment:
        raise RuntimeError("AZURE_OPENAI_EMBED_DEPLOYMENT not set")

    chroma_dir = Path(os.getenv("MEM0_CHROMA_DIR", "data/portal/mem0/chroma"))
    chroma_dir.mkdir(parents=True, exist_ok=True)

    azure_kwargs = {
        "azure_deployment": llm_deployment,
        "azure_endpoint": endpoint,
        "api_version": api_version,
        "api_key": "",
    }
    embed_azure_kwargs = {
        "azure_deployment": embed_deployment,
        "azure_endpoint": endpoint,
        "api_version": api_version,
        "api_key": "",
    }
    config = {
        "llm": {
            "provider": "azure_openai",
            "config": {
                "model": llm_deployment,
                "azure_kwargs": azure_kwargs,
            },
        },
        "embedder": {
            "provider": "azure_openai",
            "config": {
                "model": embed_deployment,
                "embedding_dims": 3072,
                "azure_kwargs": embed_azure_kwargs,
            },
        },
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "lesson_store",
                "path": str(chroma_dir),
            },
        },
    }
    return Memory.from_config(config)


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
    def get_all(
        self,
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
            memory = build_default_memory()
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
        # Mem0.search runs the query through the embedder; Azure OpenAI
        # rejects empty input strings with HTTP 400. Route "list all"
        # calls (query="") through Memory.get_all instead, which does
        # not invoke the embedder. Callers like /api/memory/lessons/active
        # rely on this no-query path; semantic recall passes a real query
        # and uses the normal search path.
        if query.strip():
            results = self._memory.search(
                query=query,
                user_id=_USER_ID,
                filters={"domain": scope.domain},
                limit=top_k,
            )
        else:
            results = self._memory.get_all(
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
