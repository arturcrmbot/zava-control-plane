"""policy.search MCP tool — in-memory chunked retriever over the synthetic
T&E policy. Exposed two ways:

  - `search(query, k)` — plain Python function (used by tests and any
    direct-call paths like the accuracy harness's retrieval-only flow).
  - `policy_search_tool` — SDK-native `Tool` registered on a session via
    `tools=[policy_search_tool]`; the model invokes it autonomously when
    a skill's `allowed-tools` lists `policy.search`.

Foundry IQ swap-in is a later detail; this is the demo-grade implementation."""
from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool

# Heavy ML deps (sentence_transformers pulls torch + transformers, ~2GB in memory
# and ~90s to import). Lazy-load inside _load_model so Azure Functions worker
# startup stays under the 60s WorkerMetadataRequest timeout — otherwise the host
# abandons worker init and the Functions host never reaches "Job host started".
if TYPE_CHECKING:
    import numpy as np
    from sentence_transformers import SentenceTransformer

_POLICY_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "policy.md"


@dataclass
class _Chunk:
    section: str
    text: str
    embedding: "np.ndarray"


_index_cache: Optional[list[_Chunk]] = None
_model_cache: Optional[SentenceTransformer] = None


def _load_model() -> "SentenceTransformer":
    global _model_cache
    if _model_cache is None:
        from sentence_transformers import SentenceTransformer
        _model_cache = SentenceTransformer("all-MiniLM-L6-v2")
    return _model_cache


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown by ##/### headers, retaining the section label."""
    chunks: list[tuple[str, str]] = []
    current_label = "§0 Preamble"
    current: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^#+\s+(.*)$", line)
        if m:
            if current:
                chunks.append((current_label, "\n".join(current).strip()))
                current = []
            heading = m.group(1).strip()
            num = re.match(r"^([\d.]+)\s+(.*)", heading)
            current_label = f"§{num.group(1)} {num.group(2)}" if num else f"§ {heading}"
        else:
            current.append(line)
    if current:
        chunks.append((current_label, "\n".join(current).strip()))
    return [(label, body) for label, body in chunks if body]


def _ensure_index() -> list[_Chunk]:
    global _index_cache
    if _index_cache is not None:
        return _index_cache
    if not _POLICY_PATH.exists():
        raise FileNotFoundError(f"policy.md not found at {_POLICY_PATH}")
    text = _POLICY_PATH.read_text(encoding="utf-8")
    chunks = _split_into_sections(text)
    # Keep §3.X rule sections whole so the rate table stays adjacent to its rule
    # body (otherwise retrieval can return the rule prose without the threshold
    # numbers). Only split sections that are truly large (>2000 chars).
    expanded: list[tuple[str, str]] = []
    for label, body in chunks:
        if len(body) > 2000:
            paras = [p.strip() for p in body.split("\n\n") if p.strip()]
            for para in paras:
                expanded.append((label, para))
        else:
            expanded.append((label, body))
    model = _load_model()
    # Prepend the section label so the title (Meals/Travel/...) informs the cosine
    # match and shows up in returned chunk text.
    embed_inputs = [f"{label}\n{body}" for label, body in expanded]
    embeddings = model.encode(
        embed_inputs, convert_to_numpy=True, normalize_embeddings=True,
    )
    _index_cache = [
        _Chunk(section=label, text=f"{label}\n{body}", embedding=emb)
        for (label, body), emb in zip(expanded, embeddings)
    ]
    return _index_cache


def reset_cache() -> None:
    """Invalidate the index — call when policy.md is edited at runtime."""
    global _index_cache
    _index_cache = None


@traced_tool("policy.search")
def search(query: str, k: int = 5) -> list[dict]:
    """Return top-k policy chunks ranked by cosine similarity to query."""
    import numpy as np
    span = trace.get_current_span()
    span.set_attribute("wpp.mcp.query", query)
    span.set_attribute("wpp.mcp.k", k)
    chunks = _ensure_index()
    model = _load_model()
    q_emb = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]
    scored = [(float(np.dot(q_emb, c.embedding)), c) for c in chunks]
    scored.sort(key=lambda t: t[0], reverse=True)
    out = [
        {"section": c.section, "text": c.text, "score": s}
        for s, c in scored[:k]
    ]
    span.set_attribute("wpp.mcp.result_count", len(out))
    return out


class _PolicySearchParams(BaseModel):
    query: str = Field(description="Natural-language query about the WPP T&E policy")
    k: int = Field(default=5, description="Number of top chunks to return", ge=1, le=20)


@define_tool(
    name="policy_search",
    description=(
        "Search the WPP T&E policy markdown by semantic similarity. Returns the "
        "top-k matching chunks (each with section label and similarity score). "
        "Use to ground R/A/G classification and arbitration in policy text."
    ),
)
def policy_search_tool(params: _PolicySearchParams) -> ToolResult:
    out = search(params.query, params.k)
    return ToolResult(text_result_for_llm=json.dumps(out, ensure_ascii=False))
