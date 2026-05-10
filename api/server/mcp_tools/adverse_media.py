"""adverse_media.search MCP tool — adverse-media sweep for a (name, country) pair.

Stub. Returns deterministic synthetic data keyed on the input(s). No real
upstream call. Replace the body of `search` with a real adverse-media
provider call (Refinitiv World-Check, LexisNexis, Dow Jones Risk &
Compliance) when wiring to a production system.
"""
from __future__ import annotations
import hashlib
import json

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


_SOURCES = ["Reuters", "FT", "WSJ", "Bloomberg", "BBC", "Le Monde", "Handelsblatt"]
_HEADLINE_TEMPLATES = [
    "{name} named in tax probe by {country} authority",
    "{name} faces money-laundering allegations in {country}",
    "{name} subject of bribery investigation in {country}",
    "{name} linked to sanctions-evasion scheme in {country}",
    "{name} fined by {country} regulator over disclosure failures",
]


@traced_tool("adverse_media.search")
def search(name: str, country: str) -> dict:
    """Run an adverse-media sweep on a (name, country) pair — stub."""
    span = trace.get_current_span()
    span.set_attribute("zava.adverse_media.name", str(name))
    span.set_attribute("zava.adverse_media.country", str(country))
    return _synth_search(name, country)


def _synth_search(name: str, country: str) -> dict:
    """Deterministic synthesis. Same (name, country) -> byte-identical sweep.

    Hit policy: roughly 1 in 8 (name, country) pairs returns a hit. Hits
    carry a synthesised headline, source, and published date — all derived
    from the seed so two runs against the same input return identical text."""
    key = f"{name}|{country}".encode()
    seed = int(hashlib.sha256(key).hexdigest()[:8], 16)
    is_hit = (seed % 8) == 0
    matches = []
    if is_hit:
        template = _HEADLINE_TEMPLATES[(seed >> 4) % len(_HEADLINE_TEMPLATES)]
        source = _SOURCES[(seed >> 8) % len(_SOURCES)]
        # Spread published dates across 2024-2026 deterministically.
        year = 2024 + ((seed >> 12) % 3)
        month = 1 + ((seed >> 16) % 12)
        day = 1 + ((seed >> 20) % 28)
        matches.append({
            "headline": template.format(name=name, country=country),
            "source": source,
            "published": f"{year:04d}-{month:02d}-{day:02d}",
            "summary": (
                f"Stub adverse-media match for {name} ({country}). Replace with "
                f"a real provider feed in production."
            ),
        })
    return {
        "searched_name": name,
        "searched_country": country,
        "matches": matches,
        "match_count": len(matches),
    }


class _SearchParams(BaseModel):
    name: str = Field(description="Person or entity name to sweep")
    country: str = Field(description="Country of association, ISO-2 (e.g. GB, US, DE)")


@define_tool(
    name="adverse_media_search",
    description=(
        "Run an adverse-media sweep on a (name, country) pair. Returns a "
        "`matches` list (empty when clean) where each match carries headline, "
        "source, published date, and a one-sentence summary. Use only on the "
        "top three UBOs by ownership percentage — the sweep is rate-limited "
        "in production and not cheap to fan out widely. "
        "Stub: returns deterministic synthetic data."
    ),
)
def adverse_media_search_tool(params: _SearchParams) -> ToolResult:
    try:
        result = search(params.name, params.country)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))
