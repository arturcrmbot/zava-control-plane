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


def test_build_default_memory_raises_when_endpoint_missing(monkeypatch) -> None:
    """When AZURE_OPENAI_ENDPOINT is unset, build_default_memory raises
    RuntimeError. state.py catches and falls back to InMemoryLessonStore
    so the substrate boots without persistence rather than crashing."""
    from api.server.services.lessons.mem0_store import build_default_memory

    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-3-large")
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_ENDPOINT"):
        build_default_memory()


def test_build_default_memory_raises_when_embed_deployment_missing(monkeypatch) -> None:
    from api.server.services.lessons.mem0_store import build_default_memory

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.delenv("AZURE_OPENAI_EMBED_DEPLOYMENT", raising=False)
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_EMBED_DEPLOYMENT"):
        build_default_memory()


def test_build_default_memory_assembles_azure_chroma_config(monkeypatch, tmp_path) -> None:
    """The default Mem0 config wires Azure OpenAI for LLM + embedder and
    file-backed Chroma for the vector store under data/portal/mem0/chroma/
    (overridable via MEM0_CHROMA_DIR). We assert the dict shape passed to
    Memory.from_config instead of constructing a real Memory — that needs
    az login and is covered by the @pytest.mark.foundry integration test."""
    from api.server.services.lessons import mem0_store

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    monkeypatch.setenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-3-large")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    monkeypatch.setenv("MEM0_CHROMA_DIR", str(tmp_path / "chroma"))

    captured: dict[str, Any] = {}

    class _FakeMemory:
        @classmethod
        def from_config(cls, config):
            captured["config"] = config
            return MagicMock(name="FakeMemory")

    monkeypatch.setattr("mem0.Memory", _FakeMemory)

    mem0_store.build_default_memory()

    config = captured["config"]
    assert config["llm"]["provider"] == "azure_openai"
    assert config["llm"]["config"]["model"] == "gpt-4o"
    assert config["llm"]["config"]["azure_kwargs"]["azure_deployment"] == "gpt-4o"
    assert config["llm"]["config"]["azure_kwargs"]["azure_endpoint"] == (
        "https://example.openai.azure.com"
    )

    assert config["embedder"]["provider"] == "azure_openai"
    assert config["embedder"]["config"]["model"] == "text-embedding-3-large"
    assert config["embedder"]["config"]["embedding_dims"] == 3072
    assert config["embedder"]["config"]["azure_kwargs"]["azure_deployment"] == (
        "text-embedding-3-large"
    )

    assert config["vector_store"]["provider"] == "chroma"
    assert config["vector_store"]["config"]["collection_name"] == "lesson_store"
    assert config["vector_store"]["config"]["path"] == str(tmp_path / "chroma")
    # Directory should be created eagerly so a fresh checkout boots without
    # needing the operator to mkdir first.
    assert (tmp_path / "chroma").exists()
