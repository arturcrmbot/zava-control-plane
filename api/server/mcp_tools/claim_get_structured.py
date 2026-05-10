"""claim.getStructured MCP tool — returns a normalised claim record by id.

Exposed two ways:
  - `get_structured(claim_id, include_gold)` — plain Python function.
  - `claim_get_structured_tool` — SDK-native `Tool` registered on a session
    via `tools=[claim_get_structured_tool]`.
"""
from __future__ import annotations
import json
from pathlib import Path

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool

_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"

_GOLD_FIELDS = ("gold_label", "gold_reasoning", "gold_policy_clause")


@traced_tool("claim.getStructured")
def get_structured(claim_id: str, include_gold: bool = False) -> dict:
    """Return claim JSON. By default redacts gold-* fields so the classifier
    cannot accidentally cheat. Tests pass include_gold=True for assertions."""
    trace.get_current_span().set_attribute("zava.claim.id", claim_id)
    path = _CLAIMS_DIR / f"{claim_id}.json"
    if not path.exists():
        raise KeyError(f"claim {claim_id!r} not found")
    claim = json.loads(path.read_text(encoding="utf-8"))
    if not include_gold:
        for f in _GOLD_FIELDS:
            claim.pop(f, None)
    return claim


class _ClaimGetStructuredParams(BaseModel):
    claim_id: str = Field(description="Claim identifier (e.g. CLM-0042)")


@define_tool(
    name="claim_get_structured",
    description=(
        "Fetch a normalised expense claim record by id. Returns category, market, "
        "currency, amount, attendees, vendor, ems_source, and metadata. "
        "Gold-label fields are never exposed."
    ),
)
def claim_get_structured_tool(params: _ClaimGetStructuredParams) -> ToolResult:
    try:
        record = get_structured(params.claim_id, include_gold=False)
    except KeyError as e:
        return ToolResult(
            text_result_for_llm=f"claim not found: {params.claim_id}",
            result_type="failure",
            error=str(e),
        )
    return ToolResult(text_result_for_llm=json.dumps(record, ensure_ascii=False))
