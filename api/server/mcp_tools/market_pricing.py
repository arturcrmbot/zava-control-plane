"""market_pricing MCP tool — fetch fresh market quotes for a category + region.

Single operation: get_quotes. Returns three deterministic synthetic quotes
keyed on (category, region). No real upstream call. Replace the body of
`get_quotes` with a real market-pricing API call when wiring to a production
tenant.
"""
from __future__ import annotations
import hashlib
import json

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


_VENDORS = [
    "Acme MSP",
    "Northwind Data",
    "Helios Creative",
    "Polaris Research",
    "Atlas Media",
    "Boreal Cloud",
    "Cygnus Analytics",
    "Drachen Studio",
]


@traced_tool("market_pricing.get_quotes")
def get_quotes(category: str, region: str) -> dict:
    """Return three fresh market quotes for (category, region) — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.market_pricing.category", str(category))
    span.set_attribute("wpp.market_pricing.region", str(region))
    return _synth_get_quotes(category, region)


def _synth_get_quotes(category: str, region: str) -> dict:
    """Deterministic synthesis. Same (category, region) -> same quote set."""
    seed = int(hashlib.sha256(f"{category}|{region}".encode()).hexdigest()[:8], 16)
    base = 200_000 + (seed % 1500) * 1000  # 200k..1.7M
    quotes = []
    for i in range(3):
        local = (seed >> (i * 4)) & 0xFFFFFFFF
        spread_pct = -10 + (local % 25)  # -10%..+15% off the base
        annual_value = int(base * (100 + spread_pct) / 100)
        validity_days = 30 + (local >> 6) % 31  # 30..60 days
        quotes.append({
            "vendor": _VENDORS[local % len(_VENDORS)],
            "annual_value_usd": annual_value,
            "term_years": 1 + (local >> 3) % 4,
            "valid_for_days": validity_days,
            "incentives": "1-month free transition" if (local & 0x1) else "none",
        })
    return {
        "category": category,
        "region": region,
        "quote_count": len(quotes),
        "quotes": quotes,
    }


class _GetQuotesParams(BaseModel):
    category: str = Field(description="Contract category (e.g. managed-services-it)")
    region: str = Field(description="Region ISO-2 (e.g. UK, US, DE)")


@define_tool(
    name="market_pricing_get_quotes",
    description=(
        "Fetch fresh market quotes (typically three vendors) for a (category, "
        "region) pair: vendor, annual value (USD), term years, validity window, "
        "incentives. Use to benchmark a renewal against current market pricing. "
        "Stub: returns deterministic synthetic data."
    ),
)
def market_pricing_get_quotes_tool(params: _GetQuotesParams) -> ToolResult:
    try:
        result = get_quotes(params.category, params.region)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))
