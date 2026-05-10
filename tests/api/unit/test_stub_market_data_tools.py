"""Tests for the deterministic stub MCP tools that screen / sweep / quote.

These three tools share the same shape: a hash-seeded synthesiser that returns
byte-identical output for the same input, with a small fraction of inputs
producing "hits" / quotes. We exercise:

- determinism (same input → same output)
- both empty and non-empty branches of the synthesiser
- shape of returned dict
- error-wrapping behaviour of the public Tool wrapper
"""
from __future__ import annotations

import json

import pytest

from api.server.mcp_tools import adverse_media, sanctions_api, market_pricing


# ---------------------------------------------------------------------------
# adverse_media.search
# ---------------------------------------------------------------------------


class TestAdverseMediaSearch:
    def test_determinism_same_inputs_same_output(self):
        a = adverse_media.search("Acme Ltd", "GB")
        b = adverse_media.search("Acme Ltd", "GB")
        assert a == b

    def test_returns_searched_inputs_in_envelope(self):
        out = adverse_media.search("Foo Corp", "DE")
        assert out["searched_name"] == "Foo Corp"
        assert out["searched_country"] == "DE"
        assert out["match_count"] == len(out["matches"])

    def test_finds_clean_input(self):
        # A name we know does NOT trigger the 1-in-8 hit branch (seed % 8 != 0).
        # We brute-force-find one rather than hard-code seeds.
        for n in range(200):
            r = adverse_media.search(f"clean-{n}", "GB")
            if not r["matches"]:
                assert r["match_count"] == 0
                assert r["matches"] == []
                return
        pytest.fail("expected at least one clean adverse-media result among 200 seeds")

    def test_finds_hit_input(self):
        # Brute-force a hit input and assert the hit shape.
        for n in range(200):
            r = adverse_media.search(f"target-{n}", "DE")
            if r["matches"]:
                m = r["matches"][0]
                assert set(m.keys()) == {"headline", "source", "published", "summary"}
                # Headline should mention both the searched name and country.
                assert f"target-{n}" in m["headline"]
                assert "DE" in m["headline"]
                # Date is yyyy-mm-dd in 2024..2026.
                year = int(m["published"][:4])
                assert 2024 <= year <= 2026
                return
        pytest.fail("expected at least one adverse-media hit among 200 seeds")

    def test_tool_wrapper_returns_serialised_json(self):
        import asyncio
        from copilot.tools import ToolInvocation

        inv = ToolInvocation(
            session_id="t", tool_call_id="t", tool_name="adverse_media_search",
            arguments={"name": "Acme", "country": "GB"},
        )
        result = asyncio.run(adverse_media.adverse_media_search_tool.handler(inv))
        decoded = json.loads(result.text_result_for_llm)
        assert decoded == adverse_media.search("Acme", "GB")


# ---------------------------------------------------------------------------
# sanctions_api.screen_entity
# ---------------------------------------------------------------------------


class TestSanctionsApiScreenEntity:
    def test_determinism_same_inputs_same_output(self):
        a = sanctions_api.screen_entity("Acme Ltd", "GB")
        b = sanctions_api.screen_entity("Acme Ltd", "GB")
        assert a == b

    def test_lists_consulted_always_present_and_complete(self):
        out = sanctions_api.screen_entity("Foo", "US")
        assert out["lists_consulted"] == [
            "OFAC-SDN",
            "UN-CONSOLIDATED",
            "EU-CONSOLIDATED",
            "HMT-CONSOLIDATED",
        ]
        assert out["screened_name"] == "Foo"
        assert out["screened_country"] == "US"
        assert out["hit_count"] == len(out["hits"])

    def test_clean_input_returns_empty_hits(self):
        for n in range(200):
            r = sanctions_api.screen_entity(f"clean-sanc-{n}", "GB")
            if not r["hits"]:
                assert r["hit_count"] == 0
                return
        pytest.fail("expected a clean sanctions input among 200 seeds")

    def test_hit_input_returns_typed_match(self):
        for n in range(400):
            r = sanctions_api.screen_entity(f"hit-sanc-{n}", "DE")
            if r["hits"]:
                hit = r["hits"][0]
                assert hit["list"] in {
                    "OFAC-SDN",
                    "UN-CONSOLIDATED",
                    "EU-CONSOLIDATED",
                    "HMT-CONSOLIDATED",
                }
                assert hit["matched_name"] == f"hit-sanc-{n}"
                assert hit["country"] == "DE"
                assert 0.80 <= hit["score"] <= 0.99
                return
        pytest.fail("expected a sanctions hit among 400 seeds")

    def test_tool_wrapper_returns_serialised_json(self):
        import asyncio
        from copilot.tools import ToolInvocation

        inv = ToolInvocation(
            session_id="t", tool_call_id="t", tool_name="sanctions_api_screen_entity",
            arguments={"name": "Acme", "country": "GB"},
        )
        result = asyncio.run(sanctions_api.sanctions_api_screen_entity_tool.handler(inv))
        decoded = json.loads(result.text_result_for_llm)
        assert decoded == sanctions_api.screen_entity("Acme", "GB")


# ---------------------------------------------------------------------------
# market_pricing.get_quotes
# ---------------------------------------------------------------------------


class TestMarketPricingGetQuotes:
    def test_determinism(self):
        a = market_pricing.get_quotes("managed-services-it", "UK")
        b = market_pricing.get_quotes("managed-services-it", "UK")
        assert a == b

    def test_returns_three_quotes_with_required_fields(self):
        out = market_pricing.get_quotes("creative-design", "US")
        assert out["category"] == "creative-design"
        assert out["region"] == "US"
        assert out["quote_count"] == 3
        assert len(out["quotes"]) == 3
        for q in out["quotes"]:
            assert q["vendor"] in market_pricing._VENDORS
            assert isinstance(q["annual_value_usd"], int)
            assert q["annual_value_usd"] > 0
            assert 1 <= q["term_years"] <= 4
            assert 30 <= q["valid_for_days"] <= 60
            assert q["incentives"] in {"1-month free transition", "none"}

    def test_different_inputs_produce_different_quotes(self):
        a = market_pricing.get_quotes("managed-services-it", "UK")
        b = market_pricing.get_quotes("managed-services-it", "US")
        # Same category, different region — quote sets should differ.
        assert a["quotes"] != b["quotes"]

    def test_tool_wrapper_returns_serialised_json(self):
        import asyncio
        from copilot.tools import ToolInvocation

        inv = ToolInvocation(
            session_id="t", tool_call_id="t", tool_name="market_pricing_get_quotes",
            arguments={"category": "managed-services-it", "region": "UK"},
        )
        result = asyncio.run(market_pricing.market_pricing_get_quotes_tool.handler(inv))
        decoded = json.loads(result.text_result_for_llm)
        assert decoded == market_pricing.get_quotes("managed-services-it", "UK")
