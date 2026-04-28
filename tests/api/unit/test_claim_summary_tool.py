"""Tests for claim_summary MCP tool."""
from __future__ import annotations
import json

import pytest

from api.server.mcp_tools import claim_summary
from api.server.mcp_tools.claim_summary import claim_summary_tool, summarise


def test_summary_includes_amount_category_vendor_market_ems():
    record = summarise("CLM-0000")
    line = record["summary"]
    assert "CLM-0000" in line
    assert record["category"] in line
    assert record["vendor"] in line
    assert record["market"] in line
    assert record["ems_source"] in line


def test_amount_formatting_inr_uses_no_decimals(monkeypatch):
    """INR claims show as integer thousands; not with .00 trailing."""
    monkeypatch.setattr(
        claim_summary,
        "get_structured",
        lambda cid, include_gold=False: {
            "claim_id": cid, "currency": "INR", "amount": 16217.0,
            "category": "accommodation", "vendor": "Hotel X",
            "market": "IN", "ems_source": "workday",
            "submitted_at": "2026-04-01T08:00:00",
        },
    )
    record = summarise("CLM-X")
    assert "INR 16,217" in record["summary"]
    assert ".00" not in record["amount_display"]


def test_amount_formatting_gbp_uses_two_decimals(monkeypatch):
    monkeypatch.setattr(
        claim_summary,
        "get_structured",
        lambda cid, include_gold=False: {
            "claim_id": cid, "currency": "GBP", "amount": 33.81,
            "category": "meals", "vendor": "Côte Brasserie",
            "market": "UK", "ems_source": "concur",
            "submitted_at": "2026-04-01T08:00:00",
        },
    )
    record = summarise("CLM-Y")
    assert "GBP 33.81" in record["summary"]


def test_unknown_claim_raises_via_get_structured():
    with pytest.raises(KeyError):
        summarise("CLM-9999")


def test_tool_returns_summary_json():
    from copilot.tools import ToolInvocation
    import asyncio

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="claim_summary",
        arguments={"claim_id": "CLM-0000"},
    )
    result = asyncio.run(claim_summary_tool.handler(inv))
    assert result.result_type == "success"
    payload = json.loads(result.text_result_for_llm)
    assert payload["claim_id"] == "CLM-0000"
    assert "summary" in payload


def test_tool_failure_for_unknown_claim():
    from copilot.tools import ToolInvocation
    import asyncio

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="claim_summary",
        arguments={"claim_id": "CLM-9999"},
    )
    result = asyncio.run(claim_summary_tool.handler(inv))
    assert result.result_type == "failure"
