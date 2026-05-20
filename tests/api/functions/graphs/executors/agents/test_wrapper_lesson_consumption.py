"""Phase B tests: _fetch_top_k_lessons + _prepend_lessons_to_skill_text + _skill_to_domain."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from api.functions.graphs.executors.agents._wrapper import (
    _lesson_cache,
    _prepend_lessons_to_skill_text,
    _skill_to_domain,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    _lesson_cache.clear()
    yield
    _lesson_cache.clear()


def test_prepend_with_lessons_includes_header_and_bullets():
    skill = "You are the receipt validator."
    out = _prepend_lessons_to_skill_text(skill, [
        {"id": "L1", "body": "first lesson body"},
        {"id": "L2", "body": "second lesson body"},
    ])
    assert "## Past lessons" in out
    assert "- first lesson body" in out
    assert "- second lesson body" in out
    assert out.endswith(skill)


def test_prepend_with_empty_lessons_returns_skill_unchanged():
    skill = "You are the receipt validator."
    assert _prepend_lessons_to_skill_text(skill, []) == skill


def test_prepend_with_none_skill_and_lessons_yields_header_only():
    out = _prepend_lessons_to_skill_text(None, [{"id": "L1", "body": "x"}])
    assert "## Past lessons" in out
    assert "- x" in out


def test_skill_to_domain_returns_hiring_for_hiring_skills():
    assert _skill_to_domain("cv-crystalliser", None) == "hiring"
    assert _skill_to_domain(None, "interview-recommender") == "hiring"


def test_skill_to_domain_returns_none_for_unknown_skill():
    assert _skill_to_domain("anomaly-flagger", None) is None
    assert _skill_to_domain(None, None) is None


@pytest.mark.asyncio
async def test_fetch_memories_uses_v2_recall_endpoint():
    captured_urls: list[str] = []

    class _FakeR:
        status_code = 200

        def json(self):
            return {"memories": [{"id": "m1", "memory": "x", "score": 0.9}]}

    class _FakeC:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, *a, **kw):
            captured_urls.append(url)
            return _FakeR()

    from api.functions.graphs.executors.agents._wrapper import _fetch_memories

    _lesson_cache.clear()
    with patch("api.functions.graphs.executors.agents._wrapper.httpx.AsyncClient", return_value=_FakeC()):
        out = await _fetch_memories(
            domain="hiring",
            query="senior data engineer USA",
            top_k=5,
        )

    assert any("/api/memory/v2/recall" in u for u in captured_urls)
    assert out == [{"id": "m1", "memory": "x", "score": 0.9}]


@pytest.mark.asyncio
async def test_run_agent_session_prepends_recalled_memories(monkeypatch):
    class _FakeRuntime:
        def __init__(self):
            self.calls = []

        async def run_session(self, **kwargs):
            self.calls.append(kwargs)
            from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult

            return LLMRuntimeResult(text='{"ok": true}', tool_calls=[])

    fake_runtime = _FakeRuntime()
    monkeypatch.setattr(
        "api.functions.graphs.executors.agents._wrapper._get_runtime",
        lambda: fake_runtime,
    )
    monkeypatch.setattr(
        "api.functions.graphs.executors.agents._wrapper._load_skill",
        lambda skill_dir: "You are the receipt validator.",
    )
    monkeypatch.setattr(
        "api.functions.graphs.executors.agents._wrapper._fetch_memories",
        AsyncMock(return_value=[{"id": "m1", "memory": "Prefer evidence over volume"}]),
    )

    from api.functions.graphs.executors.agents._wrapper import run_agent_session

    out = await run_agent_session(
        prompt="screen these candidates",
        tools=[],
        skill_dir=Path("api/server/skills/unused-skill-dir"),
        skill_label="cv-crystalliser",
        workflow_id="WF-TEST-2",
    )

    assert out == {"ok": True}
    assert fake_runtime.calls
    assert "## Relevant memories from prior cases" in fake_runtime.calls[0]["system_message"]
    assert "- Prefer evidence over volume" in fake_runtime.calls[0]["system_message"]
