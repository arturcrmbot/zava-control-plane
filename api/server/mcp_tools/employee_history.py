"""employee_history MCP tool — return an employee's prior breach history.

Reads from `data/synthetic/employees.json`. Drives the escalation-advisor
skill (Day 9) — the more prior breaches in the recent window, the higher
the enforcement tier.

Two surfaces:
  - `get_history(employee_id, lookback_days?)` — plain Python.
  - `employee_history_tool` — SDK-native @define_tool wrapper.
"""
from __future__ import annotations
import json
from datetime import date, timedelta
from pathlib import Path

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool

_EMPLOYEES_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "employees.json"


def _load_employees() -> list[dict]:
    if not _EMPLOYEES_PATH.exists():
        raise FileNotFoundError(f"employees.json not found at {_EMPLOYEES_PATH}")
    return json.loads(_EMPLOYEES_PATH.read_text(encoding="utf-8"))


@traced_tool("employee.history")
def get_history(employee_id: str, lookback_days: int | None = 90) -> dict:
    """Return employee profile + recent breach history within `lookback_days`.

    Setting `lookback_days=None` returns the full breach_history without
    filtering — useful for the audit phase. Default 90 days matches the
    policy's progressive-enforcement window.
    """
    span = trace.get_current_span()
    span.set_attribute("zava.employee.id", employee_id)
    if lookback_days is not None:
        span.set_attribute("zava.employee.lookback_days", lookback_days)

    employees = _load_employees()
    emp = next((e for e in employees if e["id"] == employee_id), None)
    if emp is None:
        raise KeyError(f"employee {employee_id!r} not found")

    history = list(emp.get("breach_history", []))
    if lookback_days is not None:
        cutoff = date.today() - timedelta(days=lookback_days)
        filtered: list[dict] = []
        for entry in history:
            try:
                entry_date = date.fromisoformat(entry["date"])
            except (KeyError, ValueError):
                continue
            if entry_date >= cutoff:
                filtered.append(entry)
        history = filtered

    span.set_attribute("zava.employee.breach_count", len(history))
    return {
        "employee_id": emp["id"],
        "name": emp.get("name"),
        "market": emp.get("market"),
        "department": emp.get("department"),
        "agency": emp.get("agency"),
        "lookback_days": lookback_days,
        "breach_count": len(history),
        "breach_history": history,
    }


class _EmployeeHistoryParams(BaseModel):
    employee_id: str = Field(description="Employee identifier (e.g. EMP-0001)")
    lookback_days: int | None = Field(
        default=90,
        description="Filter breaches to those within the last N days. Pass null for the full history.",
        ge=0,
    )


@define_tool(
    name="employee_history",
    description=(
        "Fetch an employee's prior breach history (date, category, tier) and "
        "profile (market, department, agency). Use to inform progressive "
        "enforcement decisions: warning -> escalation -> major-violation."
    ),
)
def employee_history_tool(params: _EmployeeHistoryParams) -> ToolResult:
    try:
        record = get_history(params.employee_id, params.lookback_days)
    except KeyError as e:
        return ToolResult(
            text_result_for_llm=f"employee not found: {params.employee_id}",
            result_type="failure",
            error=str(e),
        )
    return ToolResult(text_result_for_llm=json.dumps(record, ensure_ascii=False))
