"""claim.lookup MCP tool — dispatch a claim id to the appropriate EMS mock.

Bridges the Python orchestrator world to the Node EMS-mock world. Reads the
synthetic claim JSON to auto-detect `ems_source` when the caller doesn't
supply one. The HTTP target ports come from `WORKDAY_MCP_PORT` /
`CONCUR_MCP_PORT` env vars (defaults 4101 / 4102).

The two EMSs use different terminology — Workday's `getExpenseClaim` returns
the claim record verbatim; Concur's `getExpenseLine` returns a re-shaped view
with the original record under `_normalised`. This adapter normalises both
into the same shape (the synthetic claim record) before returning.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

import httpx
from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool

_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"


def _resolve_ems(claim_id: str) -> str:
    path = _CLAIMS_DIR / f"{claim_id}.json"
    if not path.exists():
        raise KeyError(f"claim {claim_id!r} not found in synthetic corpus")
    record = json.loads(path.read_text(encoding="utf-8"))
    ems = record.get("ems_source")
    if ems not in {"workday", "concur"}:
        raise KeyError(f"claim {claim_id!r} has unknown ems_source {ems!r}")
    return ems


@traced_tool("claim.lookup")
def lookup(claim_id: str, ems_source: str | None = None) -> dict:
    """Fetch a claim record from the EMS named in ems_source (or auto-detect).

    Both EMSs return the same normalised claim record shape — Workday returns
    it directly, Concur returns it under `_normalised` and we unwrap.
    """
    span = trace.get_current_span()
    span.set_attribute("wpp.claim.id", claim_id)
    ems = ems_source or _resolve_ems(claim_id)
    span.set_attribute("wpp.ems.source", ems)

    if ems == "concur":
        port = int(os.environ.get("CONCUR_MCP_PORT", "4102"))
        url = f"http://127.0.0.1:{port}/mcp/call/getExpenseLine"
        # Concur enforces an OAuth bearer; the mock accepts any non-empty token.
        headers = {"Authorization": "Bearer concur-mock-dev-token"}
        resp = httpx.post(url, json={"reportItemId": claim_id}, headers=headers, timeout=5.0)
        if resp.status_code == 404:
            raise KeyError(f"claim {claim_id!r} not found at concur mock")
        resp.raise_for_status()
        body = resp.json()
        # Concur wraps the original synthetic record under `_normalised`.
        return body.get("_normalised") or body

    # workday
    port = int(os.environ.get("WORKDAY_MCP_PORT", "4101"))
    url = f"http://127.0.0.1:{port}/mcp/call/getExpenseClaim"
    resp = httpx.post(url, json={"claimId": claim_id}, timeout=5.0)
    if resp.status_code == 404:
        raise KeyError(f"claim {claim_id!r} not found at workday mock")
    resp.raise_for_status()
    return resp.json()


class _ClaimLookupParams(BaseModel):
    claim_id: str = Field(description="Claim identifier (e.g. CLM-0042)")
    ems_source: str | None = Field(
        default=None,
        description="Optional EMS override: 'workday' or 'concur'. Auto-detected from the claim record if omitted.",
    )


@define_tool(
    name="claim_lookup",
    description=(
        "Fetch a claim record from the upstream EMS (Workday or Concur) by id. "
        "Use when you need EMS-side metadata that isn't in the structured claim JSON."
    ),
)
def claim_lookup_tool(params: _ClaimLookupParams) -> ToolResult:
    try:
        record = lookup(params.claim_id, params.ems_source)
    except KeyError as e:
        return ToolResult(text_result_for_llm=f"claim not found: {params.claim_id}",
                          result_type="failure", error=str(e))
    return ToolResult(text_result_for_llm=json.dumps(record, ensure_ascii=False))
