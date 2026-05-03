"""feedback_collector MCP tool — collect 360-degree peer reviews + OKR results.

Two operations: list_360, get_okr_results. All deterministic synthetic data
keyed on the input(s). No real upstream call. Replace the bodies with real
feedback-platform API calls (e.g. Lattice, Culture Amp) when wiring to a
production tenant.
"""
from __future__ import annotations
import hashlib
import json

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


_RELATIONSHIPS = ["peer", "manager", "report", "cross-functional"]
_SENTIMENTS = ["positive", "constructive", "mixed"]
_OKR_STATUSES = ["achieved", "partial", "missed"]
_PEER_NAMES = [
    "EMP-2014",
    "EMP-3041",
    "EMP-4188",
    "EMP-5022",
    "EMP-5567",
    "EMP-6109",
    "EMP-6602",
    "EMP-7733",
    "EMP-8204",
]


# --------------------------------------------------------------------------
# list_360
# --------------------------------------------------------------------------


@traced_tool("feedback_collector.list_360")
def list_360(employee_id: str, cycle: str) -> dict:
    """List 360-degree peer reviews for (employee_id, cycle) — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.feedback_collector.employee_id", str(employee_id))
    span.set_attribute("wpp.feedback_collector.cycle", str(cycle))
    return _synth_list_360(employee_id, cycle)


def _synth_list_360(employee_id: str, cycle: str) -> dict:
    """Deterministic synthesis. Same (employee_id, cycle) -> same review set."""
    seed = int(hashlib.sha256(f"360|{employee_id}|{cycle}".encode()).hexdigest()[:8], 16)
    count = 2 + (seed % 5)  # 2..6 reviews — straddles the HR persona's >=3 threshold
    reviews = []
    for i in range(count):
        local = (seed >> (i * 4)) & 0xFFFFFFFF
        reviewer_id = _PEER_NAMES[local % len(_PEER_NAMES)]
        relationship = _RELATIONSHIPS[(local >> 3) % len(_RELATIONSHIPS)]
        sentiment = _SENTIMENTS[(local >> 6) % len(_SENTIMENTS)]
        score = 1 + (local >> 9) % 5  # 1..5 stars
        reviews.append({
            "review_id": f"REV-{employee_id}-{cycle}-{i + 1:02d}",
            "reviewer_id": reviewer_id,
            "relationship": relationship,
            "sentiment": sentiment,
            "score_out_of_5": score,
            "summary": f"{relationship} review, {sentiment} sentiment (synthetic)",
        })
    return {
        "employee_id": employee_id,
        "cycle": cycle,
        "review_count": count,
        "reviews": reviews,
    }


class _List360Params(BaseModel):
    employee_id: str = Field(description="Reviewee employee identifier (e.g. EMP-0042)")
    cycle: str = Field(description="Performance cycle label (e.g. 2026-H1)")


@define_tool(
    name="feedback_collector_list_360",
    description=(
        "Collect 360-degree peer reviews submitted for a given (employee_id, cycle): "
        "review id, reviewer id, relationship (peer / manager / report / "
        "cross-functional), sentiment, score out of 5, short summary. Use to "
        "aggregate peer feedback before drafting a calibration. "
        "Stub: returns deterministic synthetic data."
    ),
)
def feedback_collector_list_360_tool(params: _List360Params) -> ToolResult:
    try:
        result = list_360(params.employee_id, params.cycle)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))


# --------------------------------------------------------------------------
# get_okr_results
# --------------------------------------------------------------------------


@traced_tool("feedback_collector.get_okr_results")
def get_okr_results(employee_id: str, cycle: str) -> dict:
    """Return OKR results for (employee_id, cycle) — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.feedback_collector.employee_id", str(employee_id))
    span.set_attribute("wpp.feedback_collector.cycle", str(cycle))
    return _synth_get_okr_results(employee_id, cycle)


def _synth_get_okr_results(employee_id: str, cycle: str) -> dict:
    """Deterministic synthesis. Same (employee_id, cycle) -> same OKR result."""
    seed = int(hashlib.sha256(f"okr|{employee_id}|{cycle}".encode()).hexdigest()[:8], 16)
    total = 3 + (seed % 4)  # 3..6 OKRs
    objectives = []
    achieved = 0
    partial = 0
    missed = 0
    for i in range(total):
        local = (seed >> (i * 4)) & 0xFFFFFFFF
        status = _OKR_STATUSES[local % len(_OKR_STATUSES)]
        if status == "achieved":
            achievement_pct = 90 + (local >> 3) % 20  # 90..109
            achieved += 1
        elif status == "partial":
            achievement_pct = 50 + (local >> 3) % 35  # 50..84
            partial += 1
        else:
            achievement_pct = (local >> 3) % 45  # 0..44
            missed += 1
        objectives.append({
            "objective_id": f"OKR-{employee_id}-{cycle}-{i + 1:02d}",
            "title": f"Objective {i + 1} (synthetic)",
            "status": status,
            "achievement_pct": achievement_pct,
            "key_results_count": 2 + (local >> 6) % 3,  # 2..4 KRs each
        })
    overall_pct = round(sum(o["achievement_pct"] for o in objectives) / total, 1)
    return {
        "employee_id": employee_id,
        "cycle": cycle,
        "objective_count": total,
        "achieved_count": achieved,
        "partial_count": partial,
        "missed_count": missed,
        "overall_achievement_pct": overall_pct,
        "objectives": objectives,
    }


class _GetOkrResultsParams(BaseModel):
    employee_id: str = Field(description="Reviewee employee identifier (e.g. EMP-0042)")
    cycle: str = Field(description="Performance cycle label (e.g. 2026-H1)")


@define_tool(
    name="feedback_collector_get_okr_results",
    description=(
        "Fetch OKR results for a given (employee_id, cycle): per-objective "
        "status (achieved / partial / missed), achievement percent, key-result "
        "count, plus rolled-up counts and overall achievement percent. Use to "
        "ground the calibration drafter in measured outcomes for the cycle. "
        "Stub: returns deterministic synthetic data."
    ),
)
def feedback_collector_get_okr_results_tool(params: _GetOkrResultsParams) -> ToolResult:
    try:
        result = get_okr_results(params.employee_id, params.cycle)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))
