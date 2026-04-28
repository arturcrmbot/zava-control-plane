"""claim.lookup MCP tool — dispatch a claim id to the appropriate EMS mock.

Bridges the Python orchestrator world to the Node EMS-mock world. Reads the
synthetic claim JSON to auto-detect `ems_source` when the caller doesn't
supply one. The HTTP target ports come from `WORKDAY_MCP_PORT` /
`CONCUR_MCP_PORT` env vars (defaults 4101 / 4102).

Concur dispatch is reserved for Day 8 — currently raises NotImplementedError.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

import httpx
from opentelemetry import trace

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
    """Fetch a claim record from the EMS named in ems_source (or auto-detect)."""
    span = trace.get_current_span()
    span.set_attribute("wpp.claim.id", claim_id)
    ems = ems_source or _resolve_ems(claim_id)
    span.set_attribute("wpp.ems.source", ems)

    if ems == "concur":
        # Day 8 will wire the Concur mock; for Day 6 this is a hard branch.
        raise NotImplementedError("concur dispatch — Day 8")

    # workday
    port = int(os.environ.get("WORKDAY_MCP_PORT", "4101"))
    url = f"http://127.0.0.1:{port}/mcp/call/getExpenseClaim"
    resp = httpx.post(url, json={"claimId": claim_id}, timeout=5.0)
    if resp.status_code == 404:
        raise KeyError(f"claim {claim_id!r} not found at workday mock")
    resp.raise_for_status()
    return resp.json()
