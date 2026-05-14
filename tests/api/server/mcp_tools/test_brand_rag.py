"""POC3 Phase 2 — brand_rag MCP tool unit tests.

Asserts:
  1. Corpus loads and chunks all 4 brands (Solene/Voltari/Verdaire/Heritor).
  2. query_brand_corpus_impl returns chunks ranked by relevance for
     well-known brand-specific terms.
  3. The deterministic-bow mode is used by default (no Foundry deps).
  4. Cross-brand queries don't leak across brands.
"""
from __future__ import annotations

import pytest

from api.server.mcp_tools.brand_rag import (
    BrandQueryResult,
    query_brand_corpus_impl,
    reset_cache,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_cache()
    yield
    reset_cache()


def test_corpus_loads_for_all_four_brands():
    """Each of the 4 brands has at least one chunk indexed."""
    for brand in ("Solene", "Voltari", "Verdaire", "Heritor"):
        r = query_brand_corpus_impl(brand=brand, query=brand, k=3)
        assert r.chunks, f"{brand}: no chunks returned"
        assert all(c.brand.lower() == brand.lower() for c in r.chunks), (
            f"{brand}: cross-brand leak in results"
        )


def test_default_mode_is_deterministic_bow():
    """No env flag => no Foundry network — the deterministic BoW path
    is the CI / dev default."""
    r = query_brand_corpus_impl(brand="Solene", query="botanical Provence", k=3)
    assert r.embedding_mode == "deterministic-bow"


def test_solene_query_matches_brand_voice():
    """Querying Solene-specific terms should surface chunks from the
    brand-voice or visual-codes docs at the top."""
    r = query_brand_corpus_impl(
        brand="Solene",
        query="regenerative provenance soil-to-stopper Grasse",
        k=3,
    )
    assert r.chunks
    top_kinds = {c.doc_kind for c in r.chunks}
    # The corpus has multiple docs that mention these phrases — at least
    # one of brand_voice / mandatory_phrases / messaging_pillars should hit.
    assert top_kinds & {
        "brand_voice", "mandatory_phrases", "messaging_pillars",
        "tagline_archive",
    }, f"unexpected top kinds: {top_kinds}"


def test_voltari_query_finds_carbon_negative():
    """Voltari's signature claim should land near the top."""
    r = query_brand_corpus_impl(
        brand="Voltari",
        query="carbon-negative manufacture 550 mile range Munich",
        k=3,
    )
    assert r.chunks
    # At least one of the top chunks should mention "carbon-negative".
    text_combined = " ".join(c.text.lower() for c in r.chunks)
    assert "carbon-negative" in text_combined or "carbon negative" in text_combined


def test_verdaire_query_finds_soil_to_skin():
    r = query_brand_corpus_impl(
        brand="Verdaire",
        query="soil-to-skin Hampshire farm regenerative",
        k=3,
    )
    assert r.chunks
    text_combined = " ".join(c.text.lower() for c in r.chunks)
    assert "soil-to-skin" in text_combined or "hampshire" in text_combined


def test_heritor_query_finds_geneva_heritage():
    r = query_brand_corpus_impl(
        brand="Heritor",
        query="Geneva 1875 Reference 414 hand-finished",
        k=3,
    )
    assert r.chunks
    text_combined = " ".join(c.text.lower() for c in r.chunks)
    assert "geneva" in text_combined or "1875" in text_combined


def test_unknown_brand_returns_empty():
    r = query_brand_corpus_impl(brand="NotAReal", query="anything", k=3)
    assert r.chunks == []


def test_brand_match_is_case_insensitive():
    r1 = query_brand_corpus_impl(brand="Solene", query="botanical", k=3)
    r2 = query_brand_corpus_impl(brand="solene", query="botanical", k=3)
    r3 = query_brand_corpus_impl(brand="SOLENE", query="botanical", k=3)
    assert len(r1.chunks) == len(r2.chunks) == len(r3.chunks)


def test_k_bounds_results():
    r = query_brand_corpus_impl(brand="Solene", query="brand", k=2)
    assert len(r.chunks) <= 2


def test_chunks_carry_metadata():
    r = query_brand_corpus_impl(brand="Solene", query="Grasse", k=1)
    assert r.chunks
    c = r.chunks[0]
    assert c.brand
    assert c.doc_kind
    assert c.doc_title
    assert c.text
    assert 0.0 <= c.score <= 1.0
