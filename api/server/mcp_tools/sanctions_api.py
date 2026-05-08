"""sanctions_api.screen_entity MCP tool — screen a (name, country) pair against
sanctions lists.

Stub. Returns deterministic synthetic data keyed on the input(s). No real
upstream call. Replace the body of `screen_entity` with a real sanctions
screening API call (OFAC, UN, EU consolidated, HMT) when wiring to a
production system.
"""
from __future__ import annotations
import hashlib
import json

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


_SANCTIONS_LISTS = ["OFAC-SDN", "UN-CONSOLIDATED", "EU-CONSOLIDATED", "HMT-CONSOLIDATED"]


@traced_tool("sanctions_api.screen_entity")
def screen_entity(name: str, country: str) -> dict:
    """Screen a (name, country) pair against sanctions lists — stub."""
    span = trace.get_current_span()
    span.set_attribute("zava.sanctions_api.name", str(name))
    span.set_attribute("zava.sanctions_api.country", str(country))
    return _synth_screen_entity(name, country)


def _synth_screen_entity(name: str, country: str) -> dict:
    """Deterministic synthesis. Same (name, country) -> byte-identical verdict.

    Hit policy: roughly 1 in 12 (name, country) pairs returns a hit, derived
    from the seed modulus. Hits carry the matching list name, the matched
    name, the country, and a similarity score in [0.80, 0.99]."""
    key = f"{name}|{country}".encode()
    seed = int(hashlib.sha256(key).hexdigest()[:8], 16)
    is_hit = (seed % 12) == 0
    hits = []
    if is_hit:
        list_name = _SANCTIONS_LISTS[(seed >> 4) % len(_SANCTIONS_LISTS)]
        score = 0.80 + ((seed >> 8) % 20) / 100.0
        hits.append({
            "list": list_name,
            "matched_name": name,
            "country": country,
            "score": round(score, 2),
        })
    return {
        "screened_name": name,
        "screened_country": country,
        "lists_consulted": _SANCTIONS_LISTS,
        "hits": hits,
        "hit_count": len(hits),
    }


class _ScreenEntityParams(BaseModel):
    name: str = Field(description="Legal entity or natural-person name to screen")
    country: str = Field(description="Country of association, ISO-2 (e.g. GB, US, DE)")


@define_tool(
    name="sanctions_api_screen_entity",
    description=(
        "Screen a (name, country) pair against the major sanctions lists "
        "(OFAC-SDN, UN-CONSOLIDATED, EU-CONSOLIDATED, HMT-CONSOLIDATED). "
        "Returns the lists consulted plus a `hits` list (empty when clean). "
        "Use once per legal entity AND once per ultimate beneficial owner; "
        "also call once per additional country surfaced by the registry "
        "filings beyond the country of incorporation. "
        "Stub: returns deterministic synthetic data."
    ),
)
def sanctions_api_screen_entity_tool(params: _ScreenEntityParams) -> ToolResult:
    try:
        result = screen_entity(params.name, params.country)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))
