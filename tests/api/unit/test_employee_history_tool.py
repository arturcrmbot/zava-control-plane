"""Tests for employee_history MCP tool."""
from __future__ import annotations
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from api.server.mcp_tools import employee_history
from api.server.mcp_tools.employee_history import (
    employee_history_tool, get_history,
)


def test_returns_repeat_offender_breaches():
    record = get_history("EMP-0001", lookback_days=None)
    assert record["employee_id"] == "EMP-0001"
    # EMP-0001 is a seeded repeat offender per the synthetic fixtures.
    assert record["breach_count"] >= 2
    for b in record["breach_history"]:
        assert {"date", "category", "tier"} <= set(b)
        assert b["tier"] in {"warning", "escalation", "major-violation"}


def test_lookback_days_filters_old_breaches(tmp_path, monkeypatch):
    fake_path = tmp_path / "employees.json"
    today = date.today()
    fake_path.write_text(json.dumps([
        {"id": "EMP-X", "name": "Test", "market": "UK", "department": "Account",
         "agency": "Test Agency", "breach_history": [
            {"date": (today - timedelta(days=30)).isoformat(), "category": "meals", "tier": "warning"},
            {"date": (today - timedelta(days=120)).isoformat(), "category": "travel", "tier": "warning"},
        ]},
    ]), encoding="utf-8")
    monkeypatch.setattr(employee_history, "_EMPLOYEES_PATH", fake_path)

    record_90 = get_history("EMP-X", lookback_days=90)
    assert record_90["breach_count"] == 1  # only the 30-day-old breach

    record_full = get_history("EMP-X", lookback_days=None)
    assert record_full["breach_count"] == 2  # no filter


def test_unknown_employee_raises_key_error():
    with pytest.raises(KeyError):
        get_history("EMP-NOPE", lookback_days=None)


def test_tool_returns_json_payload():
    from copilot.tools import ToolInvocation
    import asyncio

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="employee_history",
        arguments={"employee_id": "EMP-0001", "lookback_days": None},
    )
    result = asyncio.run(employee_history_tool.handler(inv))
    assert result.result_type == "success"
    payload = json.loads(result.text_result_for_llm)
    assert payload["employee_id"] == "EMP-0001"
    assert "breach_history" in payload


def test_tool_reports_failure_for_unknown_employee():
    from copilot.tools import ToolInvocation
    import asyncio

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="employee_history",
        arguments={"employee_id": "EMP-NOPE", "lookback_days": 90},
    )
    result = asyncio.run(employee_history_tool.handler(inv))
    assert result.result_type == "failure"
