"""claim.getStructured MCP tool — returns a normalised claim record by id."""
from __future__ import annotations
import json
from pathlib import Path

from opentelemetry import trace

from ._otel import traced_tool

_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"

_GOLD_FIELDS = ("gold_label", "gold_reasoning", "gold_policy_clause")


@traced_tool("claim.getStructured")
def get_structured(claim_id: str, include_gold: bool = False) -> dict:
    """Return claim JSON. By default redacts gold-* fields so the classifier
    cannot accidentally cheat. Tests pass include_gold=True for assertions."""
    trace.get_current_span().set_attribute("wpp.claim.id", claim_id)
    path = _CLAIMS_DIR / f"{claim_id}.json"
    if not path.exists():
        raise KeyError(f"claim {claim_id!r} not found")
    claim = json.loads(path.read_text(encoding="utf-8"))
    if not include_gold:
        for f in _GOLD_FIELDS:
            claim.pop(f, None)
    return claim
