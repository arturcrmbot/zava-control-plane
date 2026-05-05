"""invoice_repository MCP tool — read AP invoice records.

Two operations: get_invoice, find_three_way_match. Deterministic synthetic
data keyed on the invoice_id. No real upstream call. Replace the bodies
with real ERP/AP API calls (e.g. SAP, Oracle, NetSuite) when wiring to a
production tenant.

Used by the AP-invoice fleet domain (api/functions/workflows/fleet_ap_invoice.py).
"""
from __future__ import annotations
import hashlib
import json

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


_VENDORS = [
    "Globex Industries",
    "Acme Holdings",
    "Pinetree Hosting",
    "Stratford Print",
    "Riverside Catering",
    "Northbridge Cloud",
    "Cascade Logistics",
]
_GL_CODES = [
    ("4100", "professional-services"),
    ("4200", "subscriptions"),
    ("4300", "logistics"),
    ("4400", "catering"),
    ("4500", "print-production"),
    ("4600", "cloud-hosting"),
]


# --------------------------------------------------------------------------
# get_invoice
# --------------------------------------------------------------------------


@traced_tool("invoice_repository.get_invoice")
def get_invoice(invoice_id: str) -> dict:
    """Read an AP invoice record — stub. Deterministic on invoice_id."""
    span = trace.get_current_span()
    span.set_attribute("apex.invoice_repository.invoice_id", str(invoice_id))
    return _synth_get_invoice(invoice_id)


def _synth_get_invoice(invoice_id: str) -> dict:
    """Deterministic synthesis. Same invoice_id -> byte-identical record."""
    seed = int(hashlib.sha256(str(invoice_id).encode()).hexdigest()[:8], 16)
    gl = _GL_CODES[seed % len(_GL_CODES)]
    return {
        "invoice_id": invoice_id,
        "vendor": _VENDORS[seed % len(_VENDORS)],
        "amount_gbp": 500 + (seed % 30000),  # 500..30,500
        "currency": "GBP",
        "gl_code": gl[0],
        "gl_category": gl[1],
        "cost_centre": f"CC-{(seed >> 4) % 9000 + 1000:04d}",
        "received_date": _date_iso(seed),
        "due_date": _date_iso(seed + 2592000),  # 30 days later
    }


def _date_iso(seed: int) -> str:
    # Pick a date in 2026; deterministic on seed.
    day_of_year = (seed >> 8) % 365 + 1
    from datetime import date, timedelta
    return (date(2026, 1, 1) + timedelta(days=day_of_year - 1)).isoformat()


# --------------------------------------------------------------------------
# find_three_way_match — confirms PO + GRN exist for an invoice.
# --------------------------------------------------------------------------


@traced_tool("invoice_repository.find_three_way_match")
def find_three_way_match(
    invoice_id: str,
    po_id: str | None = None,
    scenario: str | None = None,
    invoice_amount_gbp: float | None = None,
) -> dict:
    """Three-way match: invoice ↔ PO ↔ goods-receipt note. Deterministic stub.

    When `scenario` is provided, the verdict is fully determined by the
    seed corpus (so matched-clean always matches, amount-mismatch always
    fails on amount, missing-po always fails on PO presence, missing-grn
    always fails on GRN). When `scenario` is None, falls back to a
    sha256-of-invoice_id coin flip so ad-hoc invocations still produce a
    deterministic verdict.
    """
    span = trace.get_current_span()
    span.set_attribute("apex.invoice_repository.invoice_id", str(invoice_id))
    if scenario:
        span.set_attribute("apex.invoice_repository.scenario", str(scenario))

    inv = _synth_get_invoice(invoice_id)
    seed = int(hashlib.sha256(str(invoice_id).encode()).hexdigest()[:8], 16)

    # Scenario-driven path: honour the seed corpus.
    if scenario in {"matched-clean", "matched-controller-band", "matched-cfo-band"}:
        po_present = True
        grn_present = True
        amount_match = True
    elif scenario == "amount-mismatch":
        po_present = True
        grn_present = True
        amount_match = False
    elif scenario == "missing-po":
        po_present = False
        grn_present = False  # no PO ⇒ no GRN can be raised
        amount_match = True
    elif scenario == "missing-grn":
        po_present = True
        grn_present = False
        amount_match = True
    else:
        # Unknown / no scenario: fall back to deterministic coin flip,
        # but if the caller provided an explicit po_id we honour it.
        if po_id is not None:
            po_present = True
        else:
            po_present = (seed % 5) != 0
        grn_present = po_present and ((seed >> 11) % 10) != 0
        amount_match = ((seed >> 17) % 100) >= 15

    # po_id resolution: respect explicit caller, otherwise synth or null.
    if po_id is None and po_present:
        po_id = f"PO-{(seed >> 8) % 99999:05d}"
    elif not po_present:
        po_id = None
    grn_id = f"GRN-{(seed >> 14) % 99999:05d}" if grn_present else None

    # invoice_amount: caller-supplied wins, else synth.
    invoice_amount = (
        int(invoice_amount_gbp) if invoice_amount_gbp is not None
        else inv["amount_gbp"]
    )
    po_amount = invoice_amount if amount_match else int(invoice_amount * 1.15)

    matched = po_present and grn_present and amount_match
    return {
        "matched": matched,
        "invoice_id": invoice_id,
        "po_id": po_id,
        "grn_id": grn_id,
        "invoice_amount_gbp": invoice_amount,
        "po_amount_gbp": po_amount,
        "amount_within_tolerance": amount_match,
        "po_present": po_present,
        "grn_present": grn_present,
        "discrepancies": [
            *( [] if po_present     else ["po-missing"] ),
            *( [] if grn_present    else ["grn-missing"] ),
            *( [] if amount_match   else [f"amount-mismatch:invoice={invoice_amount},po={po_amount}"] ),
        ],
    }


# --------------------------------------------------------------------------
# SDK tool wrappers
# --------------------------------------------------------------------------


class _GetInvoiceParams(BaseModel):
    invoice_id: str = Field(description="Invoice id (e.g. 'INV-2026-00017').")


@define_tool(
    name="invoice_repository_get_invoice",
    description=(
        "Fetch an AP invoice record by id. Returns vendor, amount_gbp, gl_code, "
        "gl_category, cost_centre, received_date, due_date."
    ),
)
def invoice_repository_get_invoice_tool(params: _GetInvoiceParams) -> ToolResult:
    record = get_invoice(params.invoice_id)
    return ToolResult(text_result_for_llm=json.dumps(record, ensure_ascii=False))


class _ThreeWayMatchParams(BaseModel):
    invoice_id: str = Field(description="Invoice id to match.")
    po_id: str | None = Field(
        default=None,
        description="Optional PO id to match against. If omitted, the tool resolves it from the invoice deterministically.",
    )


@define_tool(
    name="invoice_repository_find_three_way_match",
    description=(
        "Run a three-way match on an invoice (invoice ↔ PO ↔ goods-receipt note). "
        "Returns matched=True/False with discrepancies list."
    ),
)
def invoice_repository_find_three_way_match_tool(params: _ThreeWayMatchParams) -> ToolResult:
    result = find_three_way_match(params.invoice_id, params.po_id)
    return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
