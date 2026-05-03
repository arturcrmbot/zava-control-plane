"""contract_repository MCP tool — read managed-services contract records.

Three operations: get_contract, find_similar, list_amendments. All deterministic
synthetic data keyed on the input(s). No real upstream call. Replace the bodies
with real CLM (contract-lifecycle-management) API calls when wiring to a
production tenant.
"""
from __future__ import annotations
import hashlib
import json

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


_CATEGORIES = [
    "managed-services-it",
    "media-buying",
    "creative-production",
    "data-platform",
    "research-panel",
]
_REGIONS = ["UK", "US", "DE", "FR", "JP"]
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
_COUNTERPARTIES = [
    "GroupM Holdings",
    "Wavemaker UK",
    "Mindshare DACH",
    "Essence US",
    "Hogarth Worldwide",
]
_AMENDMENT_TYPES = [
    "extend-term",
    "expand-scope",
    "add-services",
    "increase-volume",
    "price-adjustment",
    "termination-clause-update",
]


# --------------------------------------------------------------------------
# get_contract
# --------------------------------------------------------------------------


@traced_tool("contract_repository.get_contract")
def get_contract(contract_id: str) -> dict:
    """Read a managed-services contract record — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.contract_repository.contract_id", str(contract_id))
    return _synth_get_contract(contract_id)


def _synth_get_contract(contract_id: str) -> dict:
    """Deterministic synthesis. Same contract_id -> byte-identical record."""
    seed = int(hashlib.sha256(str(contract_id).encode()).hexdigest()[:8], 16)
    base = 250_000 + (seed % 1750) * 1000  # 250k..2.0M
    return {
        "contract_id": contract_id,
        "vendor": _VENDORS[seed % len(_VENDORS)],
        "counterparty": _COUNTERPARTIES[(seed >> 3) % len(_COUNTERPARTIES)],
        "category": _CATEGORIES[(seed >> 6) % len(_CATEGORIES)],
        "region": _REGIONS[(seed >> 9) % len(_REGIONS)],
        "current_annual_value_usd": base,
        "term_years": 1 + (seed >> 12) % 4,  # 1..4 years
        "expires_on": _expiry_iso(seed),
        "owner_employee_id": f"EMP-{(seed >> 15) % 9000 + 1000:04d}",
    }


def _expiry_iso(seed: int) -> str:
    """Synthesise a deterministic expiry date string (YYYY-MM-DD) within
    the next 90 days from a fixed reference epoch (no real time reads)."""
    # Fixed reference base: 2026-06-01. Add seed-derived day offset.
    days = seed % 90
    # Manual date arithmetic against 2026-06-01 (no datetime imports — keep
    # the synth deterministic and call-graph tight).
    months = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]  # 2026 not leap
    year, month, day = 2026, 6, 1 + days
    while day > months[month - 1]:
        day -= months[month - 1]
        month += 1
        if month > 12:
            month = 1
            year += 1
    return f"{year:04d}-{month:02d}-{day:02d}"


class _GetContractParams(BaseModel):
    contract_id: str = Field(description="Contract identifier (e.g. CRN-0042)")


@define_tool(
    name="contract_repository_get_contract",
    description=(
        "Fetch a managed-services contract record by id: vendor, counterparty, "
        "category, region, current annual value (USD), term in years, expiry "
        "date, owner employee id. Use before reasoning about a renewal. "
        "Stub: returns deterministic synthetic data."
    ),
)
def contract_repository_get_contract_tool(params: _GetContractParams) -> ToolResult:
    try:
        result = get_contract(params.contract_id)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))


# --------------------------------------------------------------------------
# find_similar
# --------------------------------------------------------------------------


@traced_tool("contract_repository.find_similar")
def find_similar(
    category: str,
    region: str,
    value_usd_low: float,
    value_usd_high: float,
) -> dict:
    """Return three comparable contracts in the same category + region within
    [value_usd_low, value_usd_high]. Stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.contract_repository.category", str(category))
    span.set_attribute("wpp.contract_repository.region", str(region))
    span.set_attribute("wpp.contract_repository.value_low", float(value_usd_low))
    span.set_attribute("wpp.contract_repository.value_high", float(value_usd_high))
    return _synth_find_similar(category, region, value_usd_low, value_usd_high)


def _synth_find_similar(
    category: str, region: str, value_usd_low: float, value_usd_high: float,
) -> dict:
    """Deterministic synthesis. Same (category, region, low, high) -> same set."""
    key = f"{category}|{region}|{int(value_usd_low)}|{int(value_usd_high)}"
    seed = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
    span = max(value_usd_high - value_usd_low, 1.0)
    contracts = []
    for i in range(3):
        local = (seed >> (i * 4)) & 0xFFFFFFFF
        ratio = (local % 100) / 100.0  # 0.00..0.99
        annual_value = int(value_usd_low + ratio * span)
        contracts.append({
            "contract_id": f"CRN-{1000 + (local % 9000):04d}",
            "vendor": _VENDORS[local % len(_VENDORS)],
            "counterparty": _COUNTERPARTIES[(local >> 3) % len(_COUNTERPARTIES)],
            "category": category,
            "region": region,
            "annual_value_usd": annual_value,
            "term_years": 1 + (local >> 6) % 4,
        })
    return {
        "category": category,
        "region": region,
        "value_usd_low": float(value_usd_low),
        "value_usd_high": float(value_usd_high),
        "comparables": contracts,
    }


class _FindSimilarParams(BaseModel):
    category: str = Field(description="Contract category (e.g. managed-services-it)")
    region: str = Field(description="Region ISO-2 (e.g. UK, US, DE)")
    value_usd_low: float = Field(description="Lower bound of comparable annual value (USD)")
    value_usd_high: float = Field(description="Upper bound of comparable annual value (USD)")


@define_tool(
    name="contract_repository_find_similar",
    description=(
        "Find three comparable managed-services contracts in our portfolio with "
        "the same category and region whose annual value sits inside "
        "[value_usd_low, value_usd_high]. Use to benchmark a renewal against "
        "comparable existing contracts. "
        "Stub: returns deterministic synthetic data."
    ),
)
def contract_repository_find_similar_tool(params: _FindSimilarParams) -> ToolResult:
    try:
        result = find_similar(
            params.category, params.region, params.value_usd_low, params.value_usd_high,
        )
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))


# --------------------------------------------------------------------------
# list_amendments
# --------------------------------------------------------------------------


@traced_tool("contract_repository.list_amendments")
def list_amendments(contract_id: str) -> dict:
    """List the amendment history for a contract — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.contract_repository.contract_id", str(contract_id))
    return _synth_list_amendments(contract_id)


def _synth_list_amendments(contract_id: str) -> dict:
    """Deterministic synthesis. Same contract_id -> same amendment list."""
    seed = int(hashlib.sha256(f"amend|{contract_id}".encode()).hexdigest()[:8], 16)
    count = seed % 5  # 0..4 amendments
    amendments = []
    for i in range(count):
        local = (seed >> (i * 4)) & 0xFFFFFFFF
        amendment_type = _AMENDMENT_TYPES[local % len(_AMENDMENT_TYPES)]
        amendments.append({
            "amendment_id": f"AMD-{contract_id}-{i + 1:02d}",
            "amendment_type": amendment_type,
            "effective_year": 2024 + (local >> 3) % 3,  # 2024..2026
            "delta_value_usd": -50_000 + (local % 200) * 1000,  # -50k..+150k
            "summary": f"{amendment_type.replace('-', ' ')} (synthetic)",
        })
    return {
        "contract_id": contract_id,
        "amendment_count": count,
        "amendments": amendments,
    }


class _ListAmendmentsParams(BaseModel):
    contract_id: str = Field(description="Contract identifier (e.g. CRN-0042)")


@define_tool(
    name="contract_repository_list_amendments",
    description=(
        "Enumerate the amendment history for a contract — amendment id, type, "
        "effective year, delta value (USD), short summary. Use to detect "
        "scope creep before drafting renewal terms. "
        "Stub: returns deterministic synthetic data."
    ),
)
def contract_repository_list_amendments_tool(params: _ListAmendmentsParams) -> ToolResult:
    try:
        result = list_amendments(params.contract_id)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))
