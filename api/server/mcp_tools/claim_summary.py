"""claim_summary MCP tool — terse one-liner describing a claim, suitable for
embedding in an Adaptive Card / email subject / SMS.

Two surfaces (plain Python + @define_tool wrapper).
"""
from __future__ import annotations
import json

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool
from .claim_get_structured import get_structured


def _format_amount(currency: str, amount: float) -> str:
    """Currency-aware amount formatting. Whole-number for INR-style; two
    decimals for GBP/USD/EUR."""
    if currency == "INR":
        return f"{currency} {int(round(amount)):,}"
    return f"{currency} {amount:,.2f}"


@traced_tool("claim.summary")
def summarise(claim_id: str) -> dict:
    """Return a terse single-line summary plus the structured fields used to
    build it. The line is composed for human consumption (no JSON syntax)."""
    span = trace.get_current_span()
    span.set_attribute("zava.claim.id", claim_id)

    claim = get_structured(claim_id, include_gold=False)
    amount_str = _format_amount(claim["currency"], claim["amount"])
    line = (
        f"{claim['claim_id']}: {amount_str} {claim['category']} "
        f"at {claim['vendor']} ({claim['market']}, {claim['ems_source']}) — "
        f"submitted {claim.get('submitted_at', '')[:10]}"
    )
    span.set_attribute("zava.claim.summary_chars", len(line))
    return {
        "claim_id": claim["claim_id"],
        "summary": line,
        "amount_display": amount_str,
        "category": claim["category"],
        "vendor": claim["vendor"],
        "market": claim["market"],
        "ems_source": claim["ems_source"],
        "submitted_at": claim.get("submitted_at"),
    }


class _ClaimSummaryParams(BaseModel):
    claim_id: str = Field(description="Claim identifier (e.g. CLM-0042)")


@define_tool(
    name="claim_summary",
    description=(
        "Return a one-line human-readable summary of an expense claim "
        "(amount, category, vendor, market, EMS, submission date). Use to "
        "embed in notification bodies, Adaptive Cards, or audit narratives."
    ),
)
def claim_summary_tool(params: _ClaimSummaryParams) -> ToolResult:
    try:
        record = summarise(params.claim_id)
    except KeyError as e:
        return ToolResult(
            text_result_for_llm=f"claim not found: {params.claim_id}",
            result_type="failure",
            error=str(e),
        )
    return ToolResult(text_result_for_llm=json.dumps(record, ensure_ascii=False))
