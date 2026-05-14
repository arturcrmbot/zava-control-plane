"""claim_get_receipt MCP tool — returns the receipt PNG (or absence marker)
for a synthetic claim, plus mismatch-flavour metadata.

Exposed two ways:
  - `get_receipt(claim_id)` — plain Python function (used by `agent_receipt_validator`
    to pre-fetch the image before passing it as a session attachment).
  - `claim_get_receipt_tool` — SDK-native `Tool` registered on a session via
    `tools=[claim_get_receipt_tool]`. Returns a JSON summary the model can read
    (filename, size, flavour, absence flag) — but NOT the base64 image, since
    the model can't render binary returned via tool results in this SDK
    version. Vision is delivered via `attachments=` on send_and_wait.
"""
from __future__ import annotations
import base64
import json
from pathlib import Path

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool
from .claim_get_structured import get_structured

_RECEIPTS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "receipts"


@traced_tool("claim.getReceipt")
def get_receipt(claim_id: str) -> dict:
    """Return the receipt for a claim. Zero-byte PNGs (the missing-receipt
    flavour) report `absent=True` and omit `image_b64`."""
    span = trace.get_current_span()
    span.set_attribute("zava.claim.id", claim_id)

    # Pull receipt_filename + flavour from the claim record itself (gold fields
    # like receipt_mismatch_flavour are in there).
    claim = get_structured(claim_id, include_gold=True)
    filename = claim.get("receipt_filename") or f"{claim_id}.png"
    flavour = claim.get("receipt_mismatch_flavour")

    path = _RECEIPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"receipt {filename!r} not found at {_RECEIPTS_DIR}")

    size_bytes = path.stat().st_size
    span.set_attribute("zava.receipt.size_bytes", size_bytes)
    if flavour:
        span.set_attribute("zava.receipt.flavour", flavour)

    if size_bytes == 0:
        # missing-receipt marker — claimant submitted nothing.
        return {
            "claim_id": claim_id,
            "filename": filename,
            "size_bytes": 0,
            "flavour": flavour or "missing-receipt",
            "absent": True,
            "image_b64": None,
        }

    image_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "claim_id": claim_id,
        "filename": filename,
        "size_bytes": size_bytes,
        "flavour": flavour,
        "absent": False,
        "image_b64": image_b64,
    }


class _ClaimGetReceiptParams(BaseModel):
    claim_id: str = Field(description="Claim identifier (e.g. CLM-0042)")


@define_tool(
    name="claim_get_receipt",
    description=(
        "Fetch metadata about an expense claim's receipt: filename, size in "
        "bytes, mismatch flavour if known, and whether the receipt is absent "
        "(zero-byte marker). Use to confirm a receipt exists before commenting "
        "on it. The actual image is delivered to the session via "
        "send_and_wait(attachments=...) by the agent executor — the model "
        "sees the image directly, not via this tool."
    ),
)
def claim_get_receipt_tool(params: _ClaimGetReceiptParams) -> ToolResult:
    try:
        record = get_receipt(params.claim_id)
    except (KeyError, FileNotFoundError) as e:
        return ToolResult(
            text_result_for_llm=f"receipt not found: {params.claim_id}",
            result_type="failure",
            error=str(e),
        )
    # Strip the base64 from the LLM-visible payload (it's noise in tool-call
    # transcripts and the model gets the image via attachments anyway).
    summary = {k: v for k, v in record.items() if k != "image_b64"}
    return ToolResult(text_result_for_llm=json.dumps(summary, ensure_ascii=False))
