"""precedents_search MCP tool — keyword-bag semantic retrieval over the
synthetic SSC reviewer-precedents corpus.

Dual-surface (plain Python `search()` + SDK-native Tool) per the project's
MCP tool convention."""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Optional

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool

_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "precedents.json"
_records: Optional[list[dict]] = None


def _load() -> list[dict]:
    global _records
    if _records is None:
        if not _PATH.exists():
            raise FileNotFoundError(f"precedents.json not found at {_PATH}")
        _records = json.loads(_PATH.read_text(encoding="utf-8"))
    return _records


def _tokenise(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z0-9§]{3,}", text.lower()) if t}


@traced_tool("precedents.search")
def search(query: str, k: int = 5) -> list[dict]:
    """Return top-k precedents ranked by token-overlap with the query."""
    span = trace.get_current_span()
    span.set_attribute("wpp.mcp.query", query)
    span.set_attribute("wpp.mcp.k", k)
    qt = _tokenise(query)
    if not qt:
        return []
    scored: list[tuple[float, dict]] = []
    for rec in _load():
        haystack = " ".join((
            rec.get("claim_summary", ""),
            rec.get("policy_clause", ""),
            rec.get("rationale", ""),
        ))
        ht = _tokenise(haystack)
        if not ht:
            continue
        overlap = len(qt & ht)
        if overlap == 0:
            continue
        # Jaccard-style score normalised against query token count.
        score = overlap / len(qt)
        scored.append((score, rec))
    scored.sort(key=lambda t: t[0], reverse=True)
    out = [{**rec, "score": float(s)} for s, rec in scored[:k]]
    span.set_attribute("wpp.mcp.result_count", len(out))
    return out


def reset_cache() -> None:
    global _records
    _records = None


class _PrecedentsSearchParams(BaseModel):
    query: str = Field(description="Natural-language query")
    k: int = Field(default=5, description="Top-k precedents to return", ge=1, le=20)


@define_tool(
    name="precedents_search",
    description=(
        "Search ~50 historical SSC reviewer decisions by token overlap. "
        "Returns claim_summary, policy_clause, reviewer_decision (one of "
        "accept-justification / require-repayment / issue-warning / escalate), "
        "rationale, decided_at, and an overlap score."
    ),
)
def precedents_search_tool(params: _PrecedentsSearchParams) -> ToolResult:
    out = search(params.query, params.k)
    return ToolResult(text_result_for_llm=json.dumps(out, ensure_ascii=False))
