"""vendor_registry MCP tool — vendor lookup, filings list, and UBO list.

Stub. Returns deterministic synthetic data keyed on the input(s). No real
upstream call. Replace the bodies of `lookup_vendor`, `list_filings` and
`list_ubos` with real registry API calls (Companies House, OpenCorporates,
etc.) when wiring to a production system.
"""
from __future__ import annotations
import hashlib
import json

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


_LEGAL_FORMS = ["Ltd", "LLC", "GmbH", "S.A.", "Pty Ltd", "AG", "BV"]
_FILING_TYPES = [
    "annual_accounts",
    "confirmation_statement",
    "officer_change",
    "share_capital_change",
    "registered_address_change",
]
_UBO_FIRST = ["Jane", "Marco", "Yuki", "Aisha", "Lukas", "Priya", "Olu", "Ines"]
_UBO_LAST = ["Doe", "Rossi", "Tanaka", "Khan", "Weber", "Sharma", "Adeyemi", "Costa"]
# A small allow-list of countries the synth picks from for filings + UBOs;
# kept short so the agent's per-country screening fan-out stays bounded.
_COUNTRIES = ["GB", "US", "DE", "FR", "JP", "AE", "SG", "CH"]


# --------------------------------------------------------------------------
# lookup_vendor
# --------------------------------------------------------------------------


@traced_tool("vendor_registry.lookup_vendor")
def lookup_vendor(vendor_name: str, country: str) -> dict:
    """Return the registry record for a (vendor_name, country) pair — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.vendor_registry.vendor_name", str(vendor_name))
    span.set_attribute("wpp.vendor_registry.country", str(country))
    return _synth_lookup_vendor(vendor_name, country)


def _synth_lookup_vendor(vendor_name: str, country: str) -> dict:
    """Deterministic synthesis. Same (vendor_name, country) -> byte-identical record."""
    key = f"{vendor_name}|{country}".encode()
    seed = int(hashlib.sha256(key).hexdigest()[:8], 16)
    legal_form = _LEGAL_FORMS[seed % len(_LEGAL_FORMS)]
    registry_id = f"VR-{seed % 1_000_000:06d}"
    street_no = 1 + (seed % 999)
    return {
        "registry_id": registry_id,
        "vendor_name": vendor_name,
        "country": country,
        "legal_form": legal_form,
        "registered_address": f"{street_no} High Street, {country}",
        "incorporation_year": 1990 + (seed % 36),
        "status": "active",
    }


class _LookupVendorParams(BaseModel):
    vendor_name: str = Field(description="Legal name of the vendor as proposed")
    country: str = Field(description="Country of incorporation, ISO-2 (e.g. GB, US, DE)")


@define_tool(
    name="vendor_registry_lookup_vendor",
    description=(
        "Look the proposed vendor up in the corporate registry by (legal name, country). "
        "Returns registry_id, legal_form, registered_address, incorporation_year, status. "
        "Use as the first call when running KYC on a new vendor — the registry_id keys "
        "every other registry call. "
        "Stub: returns deterministic synthetic data."
    ),
)
def vendor_registry_lookup_vendor_tool(params: _LookupVendorParams) -> ToolResult:
    try:
        result = lookup_vendor(params.vendor_name, params.country)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))


# --------------------------------------------------------------------------
# list_filings
# --------------------------------------------------------------------------


@traced_tool("vendor_registry.list_filings")
def list_filings(registry_id: str, months: int = 24) -> dict:
    """Return the regulatory filings for a registry_id over the last N months — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.vendor_registry.registry_id", str(registry_id))
    span.set_attribute("wpp.vendor_registry.months", int(months))
    return _synth_list_filings(registry_id, months)


def _synth_list_filings(registry_id: str, months: int) -> dict:
    """Deterministic synthesis. Same (registry_id, months) -> byte-identical filings."""
    key = f"{registry_id}|{months}".encode()
    seed = int(hashlib.sha256(key).hexdigest()[:8], 16)
    n_filings = 1 + (seed % 6)  # 1..6 filings
    filings = []
    for i in range(n_filings):
        sub_seed = (seed >> (i * 3)) & 0xFFFF
        ftype = _FILING_TYPES[sub_seed % len(_FILING_TYPES)]
        country = _COUNTRIES[sub_seed % len(_COUNTRIES)]
        # Spread filings across the window deterministically.
        month_offset = sub_seed % max(months, 1)
        year = 2024 + (month_offset // 12)
        month = 1 + (month_offset % 12)
        filings.append({
            "filing_id": f"F-{sub_seed:04d}",
            "filing_type": ftype,
            "filed_in_country": country,
            "filed_date": f"{year:04d}-{month:02d}-15",
        })
    return {
        "registry_id": registry_id,
        "months_window": months,
        "filings_count": n_filings,
        "filings": filings,
    }


class _ListFilingsParams(BaseModel):
    registry_id: str = Field(description="Registry id from lookup_vendor (e.g. VR-123456)")
    months: int = Field(default=24, description="Window size in months (default 24)")


@define_tool(
    name="vendor_registry_list_filings",
    description=(
        "List the regulatory filings for a vendor over the last N months. "
        "Each filing carries filing_type, filed_in_country, filed_date. Use after "
        "lookup_vendor to surface any country the vendor has filed in beyond its "
        "country of incorporation — those countries also need sanctions screening. "
        "Stub: returns deterministic synthetic data."
    ),
)
def vendor_registry_list_filings_tool(params: _ListFilingsParams) -> ToolResult:
    try:
        result = list_filings(params.registry_id, params.months)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))


# --------------------------------------------------------------------------
# list_ubos
# --------------------------------------------------------------------------


@traced_tool("vendor_registry.list_ubos")
def list_ubos(registry_id: str) -> dict:
    """Return the ultimate beneficial owners for a registry_id — stub."""
    span = trace.get_current_span()
    span.set_attribute("wpp.vendor_registry.registry_id", str(registry_id))
    return _synth_list_ubos(registry_id)


def _synth_list_ubos(registry_id: str) -> dict:
    """Deterministic synthesis. Same registry_id -> byte-identical UBO list.

    UBO ownership percentages sum to 100 across the returned list (the
    leftover after the first N-1 deterministic slices is assigned to the
    last owner so the totals always reconcile)."""
    seed = int(hashlib.sha256(str(registry_id).encode()).hexdigest()[:8], 16)
    n_ubos = 2 + (seed % 5)  # 2..6 UBOs
    ubos = []
    remaining = 100
    for i in range(n_ubos):
        sub_seed = (seed >> (i * 5)) & 0xFFFF
        first = _UBO_FIRST[sub_seed % len(_UBO_FIRST)]
        last = _UBO_LAST[(sub_seed >> 4) % len(_UBO_LAST)]
        country = _COUNTRIES[(sub_seed >> 8) % len(_COUNTRIES)]
        if i == n_ubos - 1:
            pct = remaining
        else:
            # 5..min(40, remaining-5*(remaining_owners))
            owners_left = n_ubos - 1 - i
            max_take = max(5, remaining - 5 * owners_left)
            pct = 5 + (sub_seed % max(1, max_take - 5))
            pct = min(pct, remaining - 5 * owners_left)
            pct = max(pct, 5)
        remaining -= pct
        ubos.append({
            "name": f"{first} {last}",
            "country": country,
            "ownership_pct": float(pct),
        })
    return {
        "registry_id": registry_id,
        "ubos_count": n_ubos,
        "ubos": ubos,
    }


class _ListUbosParams(BaseModel):
    registry_id: str = Field(description="Registry id from lookup_vendor (e.g. VR-123456)")


@define_tool(
    name="vendor_registry_list_ubos",
    description=(
        "Enumerate the ultimate beneficial owners (UBOs) for a registered vendor. "
        "Each UBO carries name, country, ownership_pct. Percentages sum to 100. "
        "Use to drive per-UBO sanctions screening and the adverse-media sweep on "
        "the top three by ownership. "
        "Stub: returns deterministic synthetic data."
    ),
)
def vendor_registry_list_ubos_tool(params: _ListUbosParams) -> ToolResult:
    try:
        result = list_ubos(params.registry_id)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))
