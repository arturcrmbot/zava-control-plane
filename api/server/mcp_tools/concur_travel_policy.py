"""concur_travel.policy.get_policy MCP tool — retrieve travel policy clauses
for a (grade, market) pair.

Stub. Returns deterministic synthetic data keyed on the input(s). No real
upstream call. Replace the body of `get_policy` with a real SAP Concur
Policy API call when wiring to a production tenant.
"""
from __future__ import annotations
import hashlib

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


# Per-grade fare class allow-list. Higher grades unlock more cabins.
_CABIN_BY_GRADE: dict[str, list[str]] = {
    "G1": ["economy"],
    "G2": ["economy"],
    "G3": ["economy", "premium_economy"],
    "G4": ["economy", "premium_economy"],
    "G5": ["economy", "premium_economy", "business"],
    "G6": ["economy", "premium_economy", "business"],
    "G7": ["economy", "premium_economy", "business", "first"],
}


# Per-market max-spend per night for hotels (in USD-equivalent).
_MAX_HOTEL_USD_BY_MARKET: dict[str, int] = {
    "UK": 280,
    "US": 350,
    "DE": 240,
    "FR": 260,
    "JP": 400,
}


@traced_tool("concur_travel.policy.get_policy")
def get_policy(grade: str, market: str) -> dict:
    """Return the travel-policy slice that applies to (grade, market) — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.concur_travel.grade", str(grade))
    span.set_attribute("wpp.concur_travel.market", str(market))
    return _synth_get_policy(grade, market)


def _synth_get_policy(grade: str, market: str) -> dict:
    """Deterministic synthesis. Same (grade, market) -> byte-identical clause set."""
    seed = int(hashlib.sha256(f"{grade}|{market}".encode()).hexdigest()[:8], 16)
    cabins = _CABIN_BY_GRADE.get(grade, ["economy"])
    max_hotel = _MAX_HOTEL_USD_BY_MARKET.get(market, 250)
    advance_days = 7 + (seed % 7)  # 7..13 days advance booking required
    return {
        "policy_version": "2026-Q1",
        "grade": grade,
        "market": market,
        "clauses": {
            "allowed_cabins": cabins,
            "max_hotel_per_night_usd": max_hotel,
            "min_advance_booking_days": advance_days,
            "refundable_required_above_usd": 1500,
            "preferred_vendor_carriers": ["BA", "LH", "AF"],
        },
        "bands_usd": {
            "low": [0, 750],
            "mid": [750, 2000],
            "high": [2000, 100000],
        },
    }


class _GetPolicyParams(BaseModel):
    grade: str = Field(description="Employee grade (e.g. G3)")
    market: str = Field(description="Destination market ISO-2 (e.g. UK, US)")


@define_tool(
    name="concur_travel_policy_get_policy",
    description=(
        "Retrieve the travel-policy slice that applies to a given (grade, market) pair: "
        "allowed cabins, hotel cap, advance-booking requirement, vendor preferences, "
        "and the cost-band thresholds (low/mid/high in USD). Use before reasoning "
        "about whether a proposed trip is in-policy. "
        "Stub: returns deterministic synthetic data."
    ),
)
def concur_travel_policy_get_policy_tool(params: _GetPolicyParams) -> ToolResult:
    try:
        result = get_policy(params.grade, params.market)
        return ToolResult(success=True, content=result)
    except Exception as ex:
        return ToolResult(success=False, error=str(ex))
