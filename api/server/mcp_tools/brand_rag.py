"""brand_rag MCP tool — query the per-brand corpus for relevant chunks.

POC3 Phase 2. The corpus lives at:
  data/synthetic/creative-campaign/brand-corpus/<Brand>/<doc>.md

Each markdown doc carries YAML frontmatter (`brand`, `doc_kind`, `title`).
We chunk every doc into ~500-char windows with 100-char overlap, embed
each chunk, and serve `query_brand_corpus(brand, query, k)` as the
public tool surface.

Embedding strategy — env-gated:
  - `BRAND_RAG_REAL_EMBEDDINGS=1`: use Foundry text-embedding-3-large
    (cosine similarity over the embedding vectors).
  - default: deterministic bag-of-words TF over normalised tokens. No
    network, no Foundry quota. Good enough for ranking docs in tests
    and demos without a live model.

Both modes use the same chunk store + result shape, so the brand-guardian
skill doesn't need to know which is active. `Phase 3` of the plan flips
the env flag for the demo build; CI runs against the deterministic
fallback.

The tool returns `BrandQueryResult.chunks: list[Chunk]` where each chunk
carries the source doc kind + title + the chunk text. The brand-guardian
skill's prompt formats these into the system prompt for the gpt-4.1-mini
call (in Phase 4).
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from copilot.tools import ToolResult, define_tool
from pydantic import BaseModel, Field

from ._otel import traced_tool


# --------------------------------------------------------------------------
# Public surface (Pydantic shapes the brand-guardian skill reads).
# --------------------------------------------------------------------------


class Chunk(BaseModel):
    brand: str
    doc_kind: str
    doc_title: str
    text: str
    score: float = Field(ge=0.0, le=1.0)


class BrandQueryResult(BaseModel):
    brand: str
    query: str
    k: int
    chunks: list[Chunk] = Field(default_factory=list)
    embedding_mode: str  # "real-foundry" | "deterministic-bow"


# --------------------------------------------------------------------------
# Corpus loading + chunking.
# --------------------------------------------------------------------------

_CORPUS_ROOT = (
    Path(__file__).resolve().parents[3]
    / "data" / "synthetic" / "creative-campaign" / "brand-corpus"
)

# Tokeniser — alphanumeric runs, lowercased. Drops markdown punctuation
# but keeps numbers (which matter for the brand corpus, e.g. "550",
# "1875", "100% sustainable").
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

# Chunking parameters — tuned to fit a few brand-RAG hits in a typical
# gpt-4.1-mini system prompt without dominating the token budget.
_CHUNK_CHARS = 600
_CHUNK_OVERLAP = 120


def _real_embeddings_enabled() -> bool:
    return os.environ.get("BRAND_RAG_REAL_EMBEDDINGS", "").strip() == "1"


@dataclass(frozen=True)
class _StoredChunk:
    """In-memory chunk record. Either `bow` (deterministic) or `vec`
    (Foundry embeddings) is populated, not both — chosen at boot time
    by the embedding-mode flag."""
    brand: str
    doc_kind: str
    doc_title: str
    text: str
    bow: Counter[str] | None
    vec: list[float] | None


def _tokenise(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]


def _bag_of_words(text: str) -> Counter[str]:
    return Counter(_tokenise(text))


def _split_frontmatter(raw: str) -> tuple[dict, str]:
    """Cheap YAML-front-matter splitter (no PyYAML for the simple case).
    Returns ({}, raw) when the file has no frontmatter block."""
    if not raw.startswith("---"):
        return {}, raw
    lines = raw.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, raw
    fm: dict[str, str] = {}
    for ln in lines[1:end]:
        if ":" not in ln:
            continue
        k, _, v = ln.partition(":")
        fm[k.strip()] = v.strip()
    return fm, "\n".join(lines[end + 1 :])


def _chunk_text(text: str, chunk_size: int = _CHUNK_CHARS,
                overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """Window the text into ~chunk_size-char slices with `overlap`-char
    overlap. Splits prefer paragraph boundaries when one falls inside
    the window."""
    text = text.strip()
    if len(text) <= chunk_size:
        return [text] if text else []
    out: list[str] = []
    i = 0
    while i < len(text):
        end = min(i + chunk_size, len(text))
        # Prefer to end at the last paragraph break inside the window.
        if end < len(text):
            para = text.rfind("\n\n", i + chunk_size // 2, end)
            if para > i:
                end = para
        chunk = text[i:end].strip()
        if chunk:
            out.append(chunk)
        i = max(end - overlap, i + 1)
    return out


@lru_cache(maxsize=1)
def _load_store() -> tuple[list[_StoredChunk], str]:
    """Load + chunk + (optionally) embed the entire brand corpus.
    Cached per process — first call costs O(corpus); subsequent calls
    are free.

    Returns (chunks, mode) where mode is "real-foundry" or
    "deterministic-bow"."""
    chunks: list[_StoredChunk] = []
    if not _CORPUS_ROOT.exists():
        return [], "deterministic-bow"

    # Walk every brand subdir.
    for brand_dir in sorted(p for p in _CORPUS_ROOT.iterdir() if p.is_dir()):
        for md in sorted(brand_dir.glob("*.md")):
            try:
                raw = md.read_text(encoding="utf-8")
            except OSError:
                continue
            fm, body = _split_frontmatter(raw)
            brand = fm.get("brand") or brand_dir.name
            doc_kind = fm.get("doc_kind") or "unspecified"
            doc_title = fm.get("title") or md.stem
            for piece in _chunk_text(body):
                chunks.append(_StoredChunk(
                    brand=brand,
                    doc_kind=doc_kind,
                    doc_title=doc_title,
                    text=piece,
                    bow=_bag_of_words(piece),
                    vec=None,
                ))

    if not _real_embeddings_enabled():
        return chunks, "deterministic-bow"

    # Real embeddings path. Lazy-import the Foundry client so the
    # deterministic path stays import-free.
    try:
        vecs = _embed_real([c.text for c in chunks])
    except Exception as ex:
        print(f"[brand_rag] real embedding failed ({ex}); falling back to BoW")
        return chunks, "deterministic-bow"

    enriched: list[_StoredChunk] = []
    for c, v in zip(chunks, vecs):
        enriched.append(_StoredChunk(
            brand=c.brand,
            doc_kind=c.doc_kind,
            doc_title=c.doc_title,
            text=c.text,
            bow=None,
            vec=v,
        ))
    return enriched, "real-foundry"


def _embed_real(texts: list[str]) -> list[list[float]]:
    """Foundry text-embedding-3-large path. Lazy-imported."""
    from openai import OpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    base_url = os.environ.get("AZURE_OPENAI_EMBEDDING_ENDPOINT")
    deployment = os.environ.get(
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"
    )
    if not base_url:
        raise RuntimeError("AZURE_OPENAI_EMBEDDING_ENDPOINT not set")

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://ai.azure.com/.default"
    )
    client = OpenAI(base_url=base_url.rstrip("/") + "/openai/v1/", api_key=token_provider)
    out: list[list[float]] = []
    # Batch in groups of 100 for embeddings API friendliness.
    for i in range(0, len(texts), 100):
        batch = texts[i : i + 100]
        resp = client.embeddings.create(model=deployment, input=batch)
        out.extend([d.embedding for d in resp.data])
    return out


# --------------------------------------------------------------------------
# Scoring.
# --------------------------------------------------------------------------


def _bow_similarity(query_bow: Counter[str], chunk_bow: Counter[str]) -> float:
    """Cosine similarity over normalised bag-of-words. Returns [0, 1]."""
    if not query_bow or not chunk_bow:
        return 0.0
    common = set(query_bow) & set(chunk_bow)
    if not common:
        return 0.0
    dot = sum(query_bow[t] * chunk_bow[t] for t in common)
    nq = math.sqrt(sum(v * v for v in query_bow.values()))
    nc = math.sqrt(sum(v * v for v in chunk_bow.values()))
    return dot / (nq * nc) if nq and nc else 0.0


def _vec_similarity(qv: list[float], cv: list[float]) -> float:
    """Cosine similarity over embedding vectors. Returns [0, 1] — the
    OpenAI embeddings are L2-normalised so dot product == cosine."""
    if not qv or not cv:
        return 0.0
    return max(0.0, sum(a * b for a, b in zip(qv, cv)))


# --------------------------------------------------------------------------
# Public Python entry — also exposed as @define_tool below for skills.
# --------------------------------------------------------------------------


def query_brand_corpus_impl(
    brand: str, query: str, k: int = 5,
) -> BrandQueryResult:
    """Return the top-k most relevant chunks from the named brand's corpus.

    Mode is auto-detected at first call; deterministic by default,
    real-Foundry when `BRAND_RAG_REAL_EMBEDDINGS=1` and the env vars are
    set.

    `brand` is matched case-insensitively against the directory name +
    the YAML frontmatter `brand:` field. `query` is whatever free text
    the brand-guardian skill builds (typically: route headline +
    tagline + a few mandatory-message keywords).
    """
    chunks, mode = _load_store()
    if not chunks:
        return BrandQueryResult(brand=brand, query=query, k=k,
                                chunks=[], embedding_mode=mode)

    brand_norm = brand.strip().lower()
    candidates = [c for c in chunks if c.brand.lower() == brand_norm]
    if not candidates:
        return BrandQueryResult(brand=brand, query=query, k=k,
                                chunks=[], embedding_mode=mode)

    if mode == "real-foundry":
        # Embed the query once; score against pre-embedded chunks.
        try:
            qv = _embed_real([query])[0]
        except Exception as ex:
            print(f"[brand_rag] query embedding failed ({ex}); BoW for this call only")
            qbow = _bag_of_words(query)
            scored = [(c, _bow_similarity(qbow, c.bow or Counter())) for c in candidates]
        else:
            scored = [(c, _vec_similarity(qv, c.vec or [])) for c in candidates]
    else:
        qbow = _bag_of_words(query)
        scored = [(c, _bow_similarity(qbow, c.bow or Counter())) for c in candidates]

    scored.sort(key=lambda pair: pair[1], reverse=True)
    top = scored[: max(1, k)]
    return BrandQueryResult(
        brand=brand,
        query=query,
        k=k,
        embedding_mode=mode,
        chunks=[
            Chunk(
                brand=c.brand, doc_kind=c.doc_kind, doc_title=c.doc_title,
                text=c.text, score=round(min(1.0, max(0.0, s)), 4),
            )
            for c, s in top
        ],
    )


def reset_cache() -> None:
    """Test helper — invalidate the chunk-store cache so a test can
    flip BRAND_RAG_REAL_EMBEDDINGS or modify the corpus on disk."""
    _load_store.cache_clear()


# --------------------------------------------------------------------------
# GHCP SDK tool registration.
# --------------------------------------------------------------------------


@define_tool(name="query_brand_corpus", description=(
    "Retrieve the top-k most relevant chunks from a brand's curated corpus "
    "(brand voice, visual codes, mandatory phrases, distinctiveness "
    "benchmark, past campaigns, forbidden treatments). Use this to "
    "ground a brand-fit / distinctiveness verdict before scoring a "
    "creative concept."
))
@traced_tool("brand_rag")
def query_brand_corpus(brand: str, query: str, k: int = 5) -> ToolResult:
    """Tool entry — wraps query_brand_corpus_impl in a ToolResult."""
    out = query_brand_corpus_impl(brand=brand, query=query, k=k)
    return ToolResult(
        result_type="success",
        content=out.model_dump_json(),
    )
