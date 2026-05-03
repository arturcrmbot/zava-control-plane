"""performance_norms MCP tool — read grade-band rating distributions and
calibration history.

Two operations: get_grade_distribution, get_calibration_history. All
deterministic synthetic data keyed on the input(s). No real upstream call.
Replace the bodies with real Workday HCM / talent-platform API calls when
wiring to a production tenant.
"""
from __future__ import annotations
import hashlib
import json

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


_RATINGS = [
    "below-expectations",
    "meets-expectations",
    "exceeds-expectations",
    "outstanding",
]


# --------------------------------------------------------------------------
# get_grade_distribution
# --------------------------------------------------------------------------


@traced_tool("performance_norms.get_grade_distribution")
def get_grade_distribution(grade: str, cycle: str) -> dict:
    """Return the rating distribution norm for (grade, cycle) — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.performance_norms.grade", str(grade))
    span.set_attribute("wpp.performance_norms.cycle", str(cycle))
    return _synth_get_grade_distribution(grade, cycle)


def _synth_get_grade_distribution(grade: str, cycle: str) -> dict:
    """Deterministic synthesis. Same (grade, cycle) -> same distribution."""
    seed = int(hashlib.sha256(f"dist|{grade}|{cycle}".encode()).hexdigest()[:8], 16)
    # Synthesise a target percent per rating. Sum constrained to 100.
    below_pct = 5 + (seed % 6)              # 5..10
    outstanding_pct = 5 + ((seed >> 3) % 6)  # 5..10
    exceeds_pct = 20 + ((seed >> 6) % 11)    # 20..30
    meets_pct = 100 - below_pct - outstanding_pct - exceeds_pct
    cohort_size = 80 + (seed >> 9) % 220     # 80..299
    return {
        "grade": grade,
        "cycle": cycle,
        "cohort_size": cohort_size,
        "target_distribution_pct": {
            "below-expectations": below_pct,
            "meets-expectations": meets_pct,
            "exceeds-expectations": exceeds_pct,
            "outstanding": outstanding_pct,
        },
        "current_distribution_pct": {
            "below-expectations": max(0, below_pct + ((seed >> 12) % 5) - 2),
            "meets-expectations": max(0, meets_pct + ((seed >> 15) % 7) - 3),
            "exceeds-expectations": max(0, exceeds_pct + ((seed >> 18) % 7) - 3),
            "outstanding": max(0, outstanding_pct + ((seed >> 21) % 5) - 2),
        },
        "headroom": {
            # Slots remaining at each rating before the cohort goes over its
            # target percent. Derived deterministically; used by the
            # calibration drafter to reason about distribution_fit.
            "exceeds-expectations": max(0, 6 - ((seed >> 24) % 8)),
            "outstanding": max(0, 3 - ((seed >> 27) % 4)),
        },
    }


class _GetGradeDistributionParams(BaseModel):
    grade: str = Field(description="Employee grade band (e.g. G3)")
    cycle: str = Field(description="Performance cycle label (e.g. 2026-H1)")


@define_tool(
    name="performance_norms_get_grade_distribution",
    description=(
        "Fetch the rating distribution norm for a given (grade, cycle): cohort "
        "size, target distribution percent per rating "
        "(below / meets / exceeds / outstanding), current distribution percent "
        "(what's already been calibrated this cycle), and headroom (slots "
        "remaining at each top rating before the cohort overshoots its "
        "target). Use to ground a calibration draft so we don't cluster too "
        "many high ratings in one grade band. "
        "Stub: returns deterministic synthetic data."
    ),
)
def performance_norms_get_grade_distribution_tool(params: _GetGradeDistributionParams) -> ToolResult:
    try:
        result = get_grade_distribution(params.grade, params.cycle)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))


# --------------------------------------------------------------------------
# get_calibration_history
# --------------------------------------------------------------------------


@traced_tool("performance_norms.get_calibration_history")
def get_calibration_history(employee_id: str) -> dict:
    """Return the prior calibration history for an employee — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.performance_norms.employee_id", str(employee_id))
    return _synth_get_calibration_history(employee_id)


def _synth_get_calibration_history(employee_id: str) -> dict:
    """Deterministic synthesis. Same employee_id -> same history."""
    seed = int(hashlib.sha256(f"hist|{employee_id}".encode()).hexdigest()[:8], 16)
    count = 1 + (seed % 4)  # 1..4 prior cycles
    history = []
    for i in range(count):
        local = (seed >> (i * 4)) & 0xFFFFFFFF
        rating = _RATINGS[local % len(_RATINGS)]
        cycle_year = 2024 + i
        cycle_half = "H1" if (local >> 3) & 1 else "H2"
        history.append({
            "cycle": f"{cycle_year}-{cycle_half}",
            "rating": rating,
            "calibration_changed": bool((local >> 6) & 1),
            "manager_id": f"EMP-{(local >> 9) % 9000 + 1000:04d}",
        })
    return {
        "employee_id": employee_id,
        "cycle_count": count,
        "history": history,
    }


class _GetCalibrationHistoryParams(BaseModel):
    employee_id: str = Field(description="Reviewee employee identifier (e.g. EMP-0042)")


@define_tool(
    name="performance_norms_get_calibration_history",
    description=(
        "Fetch an employee's prior calibration history: per-cycle rating, "
        "whether the rating was changed at calibration, and the manager id "
        "of record. Use to spot trajectory (e.g. consistent meets, recent "
        "exceeds upgrade) when drafting this cycle's calibration. "
        "Stub: returns deterministic synthetic data."
    ),
)
def performance_norms_get_calibration_history_tool(params: _GetCalibrationHistoryParams) -> ToolResult:
    try:
        result = get_calibration_history(params.employee_id)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))
