"""workday_hr.employee MCP tool — read an employee's grade + cost-centre.

Stub. Returns deterministic synthetic data keyed on the input(s). No real
upstream call. Replace the body of `get_employee` with a real Workday HR
HCM call when wiring to a production tenant.
"""
from __future__ import annotations
import hashlib

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


_GRADES = ["G1", "G2", "G3", "G4", "G5", "G6", "G7"]
_AGENCIES = ["GroupM", "Wavemaker", "Mindshare", "Essence", "Hogarth"]
_MARKETS = ["UK", "US", "DE", "FR", "JP"]
_COST_CENTRES = ["CC-1001", "CC-1042", "CC-1099", "CC-2300", "CC-2401", "CC-3122"]


@traced_tool("workday_hr.employee.get_employee")
def get_employee(employee_id: str) -> dict:
    """Read an employee's grade, cost-centre, agency and home market — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.workday_hr.employee_id", str(employee_id))
    return _synth_get_employee(employee_id)


def _synth_get_employee(employee_id: str) -> dict:
    """Deterministic synthesis. Same employee_id -> byte-identical record."""
    seed = int(hashlib.sha256(str(employee_id).encode()).hexdigest()[:8], 16)
    return {
        "employee_id": employee_id,
        "grade": _GRADES[seed % len(_GRADES)],
        "cost_centre": _COST_CENTRES[(seed >> 3) % len(_COST_CENTRES)],
        "agency": _AGENCIES[(seed >> 6) % len(_AGENCIES)],
        "home_market": _MARKETS[(seed >> 9) % len(_MARKETS)],
        "manager_id": f"EMP-{(seed >> 12) % 9000 + 1000:04d}",
    }


class _GetEmployeeParams(BaseModel):
    employee_id: str = Field(description="Employee identifier (e.g. EMP-0042)")


@define_tool(
    name="workday_hr_employee_get_employee",
    description=(
        "Fetch an employee's grade, cost-centre, agency and home market from Workday HR. "
        "Use when a workflow needs to know an employee's organisational context "
        "before applying a grade-banded policy. "
        "Stub: returns deterministic synthetic data."
    ),
)
def workday_hr_employee_get_employee_tool(params: _GetEmployeeParams) -> ToolResult:
    try:
        result = get_employee(params.employee_id)
        return ToolResult(success=True, content=result)
    except Exception as ex:
        return ToolResult(success=False, error=str(ex))
