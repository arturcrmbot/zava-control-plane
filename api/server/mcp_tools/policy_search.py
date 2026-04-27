"""policy.search MCP tool — in-memory chunked retriever over the synthetic
T&E policy. Foundry IQ swap-in is a later detail; this is the demo-grade
implementation."""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from opentelemetry import trace
from sentence_transformers import SentenceTransformer

from ._otel import traced_tool

_POLICY_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "policy.md"


@dataclass
class _Chunk:
    section: str
    text: str
    embedding: "np.ndarray"


_index_cache: Optional[list[_Chunk]] = None
_model_cache: Optional[SentenceTransformer] = None


def _load_model() -> SentenceTransformer:
    global _model_cache
    if _model_cache is None:
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
    expanded: list[tuple[str, str]] = []
    for label, body in chunks:
        if len(body) > 600:
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
