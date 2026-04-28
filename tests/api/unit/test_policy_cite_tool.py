"""Tests for policy_cite MCP tool."""
from __future__ import annotations
import json

import pytest

from api.server.mcp_tools import policy_cite
from api.server.mcp_tools.policy_cite import cite, policy_cite_tool


def test_section_id_extraction():
    assert policy_cite._section_id("§3.1 Meals — UK per-attendee cap") == "3.1"
    assert policy_cite._section_id("§3.3.1 — Tier 1 hotels") == "3.3.1"
    assert policy_cite._section_id("Meals UK no marker") is None


def test_cite_resolves_section_3_1_meals():
    """Exact §3.1 lookup should hit the policy index without falling back."""
    policy_cite._ensure_index.__globals__["_index_cache"] = None  # reset
    record = cite("§3.1 Meals — UK per-attendee cap GBP 75")
    assert record["section"].startswith("§3.1")
    assert "Meals" in record["section"]
    assert record["source"] == "exact-section-match"
    assert "GBP" in record["quote"] or "meal" in record["quote"].lower()


def test_cite_falls_back_to_semantic_search():
    """A clause that doesn't include a §-tag triggers the semantic fallback."""
    record = cite("UK alcohol prohibited at non-client meals")
    assert record["source"] == "semantic-fallback"
    assert record["section"]
    assert record["quote"]


def test_cite_raises_when_index_empty(tmp_path, monkeypatch):
    """If no chunk matches and the index is empty, raise KeyError."""
    monkeypatch.setattr(policy_cite, "_ensure_index", lambda: [])
    monkeypatch.setattr(policy_cite, "search", lambda q, k: [])
    with pytest.raises(KeyError):
        cite("§99 nonexistent")


def test_tool_returns_section_quote_payload():
    from copilot.tools import ToolInvocation
    import asyncio

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="policy_cite",
        arguments={"clause": "§3.3 Accommodation"},
    )
    result = asyncio.run(policy_cite_tool.handler(inv))
    assert result.result_type == "success"
    payload = json.loads(result.text_result_for_llm)
    assert payload["section"].startswith("§3.3")
