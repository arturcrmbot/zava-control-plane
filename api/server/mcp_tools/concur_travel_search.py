"""concur_travel.search.search_options MCP tool — retrieve booking options
for a (origin, destination, dates) tuple.

Stub. Returns deterministic synthetic data keyed on the input(s). No real
upstream call. Replace the body of `search_options` with a real SAP Concur
Travel search API call when wiring to a production tenant.
"""
from __future__ import annotations
import hashlib
import json

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


_CARRIERS = ["BA", "LH", "AF", "UA", "DL", "AA", "JL"]
_HOTELS = ["Marriott Courtyard", "Hilton Garden Inn", "Sofitel", "Park Plaza", "ibis Styles"]


@traced_tool("concur_travel.search.search_options")
def search_options(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str,
) -> dict:
    """Return a deterministic shortlist of flight + hotel options — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.concur_travel.origin", str(origin))
    span.set_attribute("wpp.concur_travel.destination", str(destination))
    return _synth_search_options(origin, destination, depart_date, return_date)


def _synth_search_options(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str,
) -> dict:
    """Deterministic synthesis. Same query -> byte-identical shortlist."""
    key = f"{origin}|{destination}|{depart_date}|{return_date}".encode()
    seed = int(hashlib.sha256(key).hexdigest()[:8], 16)

    # Three flight options: cheapest economy, mid-tier premium economy, business
    base_econ = 320 + (seed % 280)               # 320..599
    base_prem = base_econ * 2 + (seed % 200)
    base_biz = base_econ * 5 + (seed % 500)

    flight_options = [
        {
            "carrier": _CARRIERS[seed % len(_CARRIERS)],
            "cabin": "economy",
            "price_usd": base_econ,
            "refundable": False,
            "stopovers": 0 if seed % 2 == 0 else 1,
        },
        {
            "carrier": _CARRIERS[(seed >> 3) % len(_CARRIERS)],
            "cabin": "premium_economy",
            "price_usd": base_prem,
            "refundable": False,
            "stopovers": 0,
        },
        {
            "carrier": _CARRIERS[(seed >> 6) % len(_CARRIERS)],
            "cabin": "business",
            "price_usd": base_biz,
            "refundable": True,
            "stopovers": 0,
        },
    ]

    nights = 2 + (seed % 4)                       # 2..5 nights
    hotel_per_night = 140 + (seed % 220)          # 140..359
    hotel_option = {
        "name": _HOTELS[(seed >> 9) % len(_HOTELS)],
        "nights": nights,
        "rate_per_night_usd": hotel_per_night,
        "subtotal_usd": hotel_per_night * nights,
        "refundable": True,
    }

    return {
        "origin": origin,
        "destination": destination,
        "depart_date": depart_date,
        "return_date": return_date,
        "flights": flight_options,
        "hotel": hotel_option,
        "cheapest_option_total_usd": flight_options[0]["price_usd"] + hotel_option["subtotal_usd"],
    }


class _SearchOptionsParams(BaseModel):
    origin: str = Field(description="Origin IATA airport code (e.g. LHR)")
    destination: str = Field(description="Destination IATA airport code (e.g. JFK)")
    depart_date: str = Field(description="Outbound date, ISO-8601 (e.g. 2026-06-12)")
    return_date: str = Field(description="Return date, ISO-8601 (e.g. 2026-06-15)")


@define_tool(
    name="concur_travel_search_search_options",
    description=(
        "Search for flight + hotel options for a trip. Returns three flight options "
        "(economy / premium_economy / business) and one hotel option, with prices in "
        "USD. Use to ground cost-band reasoning in concrete options rather than "
        "guesses. "
        "Stub: returns deterministic synthetic data."
    ),
)
def concur_travel_search_search_options_tool(params: _SearchOptionsParams) -> ToolResult:
    try:
        result = search_options(
            params.origin,
            params.destination,
            params.depart_date,
            params.return_date,
        )
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))
