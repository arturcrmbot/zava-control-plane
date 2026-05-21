"""learning_catalogue MCP tool — match a training request against the L&D
course catalogue and reserve seats on matched courses.

Stub. Returns deterministic synthetic data keyed on the input(s). No real
upstream call, no network, no filesystem read, no clock read. Same
inputs -> byte-identical outputs. Replace the bodies of
`match_course` / `reserve_seat` with real LMS calls when wiring to a
production tenant.
"""
from __future__ import annotations
import hashlib
import json

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


_VENDORS = [
    "GroupM Academy",
    "Wavemaker Learning",
    "Mindshare Open",
    "Essence Skills",
    "Hogarth Studio",
]
_TOPIC_TO_PREFIX = {
    "leadership": "LDR",
    "data": "DAT",
    "creative": "CRE",
    "engineering": "ENG",
    "compliance": "CMP",
    "client": "CLT",
    "media": "MED",
}


def _seed(*parts: str) -> int:
    payload = "|".join(parts)
    return int(hashlib.sha256(payload.encode()).hexdigest()[:8], 16)


def _course_prefix(topic: str) -> str:
    key = (topic or "").strip().lower()
    for needle, prefix in _TOPIC_TO_PREFIX.items():
        if needle in key:
            return prefix
    return "GEN"


@traced_tool("learning_catalogue.match_course")
def match_course(
    topic: str,
    requested_title: str,
    target_start_date: str,
) -> dict:
    """Resolve a training request against the catalogue — stub.

    Returns a structured match with `match_quality` ∈ {exact, closest,
    none}. When the deterministic seed lands on `none`, a
    `closest_alternative` block is included so the caller can still
    propose a substitute course.
    """
    span = trace.get_current_span()
    span.set_attribute("zava.learning_catalogue.topic", str(topic))
    span.set_attribute("zava.learning_catalogue.requested_title", str(requested_title))
    return _synth_match_course(topic, requested_title, target_start_date)


def _synth_match_course(
    topic: str, requested_title: str, target_start_date: str,
) -> dict:
    seed = _seed(str(topic), str(requested_title), str(target_start_date))
    prefix = _course_prefix(topic)
    course_num = (seed % 900) + 100
    course_id = f"{prefix}-{course_num:04d}"
    vendor = _VENDORS[(seed >> 5) % len(_VENDORS)]
    confirmed_cost_gbp = float(((seed >> 11) % 25 + 1) * 50)
    course_start_date = str(target_start_date or "2026-09-01")

    bucket = seed % 10
    if bucket < 6:
        match_quality = "exact"
        alternative = None
    elif bucket < 9:
        match_quality = "closest"
        alternative = None
    else:
        match_quality = "none"
        alt_seed = _seed("alt", str(topic), str(requested_title))
        alt_num = (alt_seed % 900) + 100
        alternative = {
            "course_id": f"{prefix}-{alt_num:04d}",
            "vendor": _VENDORS[(alt_seed >> 5) % len(_VENDORS)],
            "confirmed_cost_gbp": float(((alt_seed >> 11) % 25 + 1) * 50),
            "course_start_date": course_start_date,
        }

    return {
        "course_id": course_id,
        "vendor": vendor,
        "confirmed_cost_gbp": confirmed_cost_gbp,
        "course_start_date": course_start_date,
        "match_quality": match_quality,
        "closest_alternative": alternative,
    }


@traced_tool("learning_catalogue.reserve_seat")
def reserve_seat(course_id: str, employee_id: str, course_start_date: str) -> dict:
    """Reserve a seat for an employee on a matched course — stub.

    Returns a deterministic booking record. Same `(course_id, employee_id,
    course_start_date)` triple -> byte-identical booking_id.
    """
    span = trace.get_current_span()
    span.set_attribute("zava.learning_catalogue.course_id", str(course_id))
    span.set_attribute("zava.learning_catalogue.employee_id", str(employee_id))
    return _synth_reserve_seat(course_id, employee_id, course_start_date)


def _synth_reserve_seat(
    course_id: str, employee_id: str, course_start_date: str,
) -> dict:
    seed = _seed(str(course_id), str(employee_id), str(course_start_date))
    booking_id = f"BKG-{seed % 1_000_000:06d}"
    seat_no = (seed >> 7) % 40 + 1
    return {
        "booking_id": booking_id,
        "course_id": course_id,
        "employee_id": employee_id,
        "course_start_date": course_start_date,
        "seat_no": seat_no,
        "status": "reserved",
    }


class _MatchCourseParams(BaseModel):
    topic: str = Field(description="High-level training topic (e.g. 'leadership', 'data', 'compliance').")
    requested_title: str = Field(description="The course title the employee asked for verbatim.")
    target_start_date: str = Field(description="Requested course start date (ISO YYYY-MM-DD).")


@define_tool(
    name="learning_catalogue_match_course",
    description=(
        "Resolve a training request against the L&D learning catalogue. Returns "
        "the matched course_id, vendor, confirmed_cost_gbp, course_start_date and "
        "a match_quality flag. When match_quality is 'none', a closest_alternative "
        "block is included so the caller can propose a substitute. Stub: returns "
        "deterministic synthetic data keyed on the inputs."
    ),
)
def learning_catalogue_match_course_tool(params: _MatchCourseParams) -> ToolResult:
    try:
        result = match_course(
            params.topic, params.requested_title, params.target_start_date,
        )
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))


class _ReserveSeatParams(BaseModel):
    course_id: str = Field(description="Catalogue course id, as returned by match_course.")
    employee_id: str = Field(description="Employee identifier the seat is being reserved for.")
    course_start_date: str = Field(description="Confirmed course start date (ISO YYYY-MM-DD).")


@define_tool(
    name="learning_catalogue_reserve_seat",
    description=(
        "Reserve a seat for an employee on a matched catalogue course. Returns a "
        "deterministic booking_id and seat_no. Stub: same input triple yields "
        "byte-identical booking record."
    ),
)
def learning_catalogue_reserve_seat_tool(params: _ReserveSeatParams) -> ToolResult:
    try:
        result = reserve_seat(
            params.course_id, params.employee_id, params.course_start_date,
        )
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))
