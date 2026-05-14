from __future__ import annotations
import json

import pytest

from api.server.mcp_tools import precedents_search
from api.server.mcp_tools.precedents_search import precedents_search_tool, search


def test_returns_top_k_for_meals_query():
    out = search("UK meals client dinner alcohol", k=3)
    assert isinstance(out, list)
    assert 1 <= len(out) <= 3
    for r in out:
        assert {"id", "claim_summary", "policy_clause", "reviewer_decision", "rationale", "decided_at", "score"} <= set(r)


def test_score_descending():
    out = search("alcohol prohibited", k=5)
    scores = [r["score"] for r in out]
    assert scores == sorted(scores, reverse=True)


def test_returns_empty_for_garbage():
    out = search("xyzqwertynonsense", k=3)
    assert isinstance(out, list)


def test_tool_returns_json_payload():
    from copilot.tools import ToolInvocation
    import asyncio

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="precedents_search",
        arguments={"query": "alcohol", "k": 3},
    )
    result = asyncio.run(precedents_search_tool.handler(inv))
    assert result.result_type == "success"
    payload = json.loads(result.text_result_for_llm)
    assert isinstance(payload, list)
