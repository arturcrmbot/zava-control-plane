"""Phase B tests: _fetch_active_lessons + _prepend_lessons_to_skill_text + _skill_to_domain."""
import pytest
from unittest.mock import patch

from api.functions.graphs.executors.agents._wrapper import (
    _fetch_active_lessons,
    _prepend_lessons_to_skill_text,
    _skill_to_domain,
    _lesson_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    _lesson_cache.clear()
    yield
    _lesson_cache.clear()


@pytest.mark.asyncio
async def test_fetch_returns_slim_items_on_200():
    class _FakeR:
        status_code = 200

        def json(self):
            return {"items": [{"id": "L1", "body": "lesson one"}, {"id": "L2", "body": "lesson two"}]}

    class _FakeC:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **kw):
            return _FakeR()

    with patch("api.functions.graphs.executors.agents._wrapper.httpx.AsyncClient", return_value=_FakeC()):
        out = await _fetch_active_lessons("hiring")
    assert out == [{"id": "L1", "body": "lesson one"}, {"id": "L2", "body": "lesson two"}]


@pytest.mark.asyncio
async def test_fetch_falls_back_to_empty_on_error():
    with patch(
        "api.functions.graphs.executors.agents._wrapper.httpx.AsyncClient",
        side_effect=RuntimeError("boom"),
    ):
        out = await _fetch_active_lessons("hiring")
    assert out == []


@pytest.mark.asyncio
async def test_fetch_caches_within_ttl():
    """Second call within TTL must NOT issue another HTTP request."""
    call_count = {"n": 0}

    class _FakeR:
        status_code = 200

        def json(self):
            return {"items": []}

    class _FakeC:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **kw):
            call_count["n"] += 1
            return _FakeR()

    with patch("api.functions.graphs.executors.agents._wrapper.httpx.AsyncClient", return_value=_FakeC()):
        await _fetch_active_lessons("hiring")
        await _fetch_active_lessons("hiring")
    assert call_count["n"] == 1


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
async def test_recall_top_k_lessons_uses_recall_endpoint_not_active():
    """Phase B regression: agent runtime fetches via /lessons/recall
    (semantic, top-K) and NOT /lessons/active (return-everything)."""
    captured_urls: list[str] = []
    class _FakeR:
        status_code = 200
        def json(self):
            return {"items": [{"id": "L1", "body": "x", "score": 0.9}]}
    class _FakeC:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, *a, **kw):
            captured_urls.append(url)
            return _FakeR()
        async def get(self, url, *a, **kw):
            captured_urls.append(url)
            return _FakeR()
    from api.functions.graphs.executors.agents._wrapper import _fetch_top_k_lessons, _lesson_cache
    _lesson_cache.clear()
    with patch("api.functions.graphs.executors.agents._wrapper.httpx.AsyncClient", return_value=_FakeC()):
        out = await _fetch_top_k_lessons(
            domain="hiring",
            query="senior data engineer USA",
            top_k=3,
        )
    assert any("/api/memory/lessons/recall" in u for u in captured_urls)
    assert not any("/api/memory/lessons/active" in u for u in captured_urls)
    assert out == [{"id": "L1", "body": "x", "score": 0.9}]
