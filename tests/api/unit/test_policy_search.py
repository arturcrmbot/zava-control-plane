"""policy.search MCP tool tests."""
from __future__ import annotations
from pathlib import Path
import pytest

from api.server.mcp_tools import policy_search

POLICY = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "policy.md"


def test_search_returns_top_k_chunks():
    policy_search.reset_cache()
    results = policy_search.search("UK meals per attendee cap", k=3)
    assert isinstance(results, list)
    assert 1 <= len(results) <= 3
    for r in results:
        assert {"text", "section", "score"} <= set(r), r
        assert isinstance(r["score"], float)
        assert r["section"].startswith("§"), r["section"]


def test_search_finds_meal_clause_first():
    policy_search.reset_cache()
    results = policy_search.search("UK meals per attendee cap GBP 75", k=5)
    top_text = results[0]["text"].lower()
    assert "meal" in top_text and ("75" in top_text or "per-attendee" in top_text or "per attendee" in top_text)


def test_search_finds_alcohol_rule():
    policy_search.reset_cache()
    results = policy_search.search("alcohol prohibited Germany", k=5)
    assert any("alcohol" in r["text"].lower() for r in results)


def test_search_handles_missing_policy_gracefully(tmp_path, monkeypatch):
    monkeypatch.setattr(policy_search, "_POLICY_PATH", tmp_path / "missing.md")
    monkeypatch.setattr(policy_search, "_index_cache", None)
    with pytest.raises(FileNotFoundError):
        policy_search.search("anything", k=3)
