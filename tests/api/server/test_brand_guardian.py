"""POC3 Phase 2 — brand-guardian validator unit tests.

Asserts the deterministic brand-guardian implementation produces
sensible scores for each rubric case:
  - On-brand route: high brand_fit, no violations.
  - Off-brand route (uses forbidden lexicon): low brand_fit + violations.
  - Competitor-coded route: low distinctiveness + violations.
  - Mixed route: middle scores.
"""
from __future__ import annotations

import asyncio

import pytest

from api.functions.graphs.executors.validators import validate_brand_guardian
from api.server.mcp_tools import brand_rag


@pytest.fixture(autouse=True)
def _reset():
    brand_rag.reset_cache()
    validate_brand_guardian.reset_lexicon_cache()
    yield
    brand_rag.reset_cache()
    validate_brand_guardian.reset_lexicon_cache()


def _run(input_dict: dict) -> dict:
    return asyncio.run(validate_brand_guardian.execute(input_dict))


def test_on_brand_solene_route_scores_high():
    """A route that uses Solene's preferred lexicon ('regenerative
    provenance', 'single-source', 'Grasse') should score high brand_fit
    and have no forbidden-lexicon violations."""
    out = _run({
        "brief": {"client_brand": "Solene"},
        "routes": [{
            "route_name": "route-on-brand",
            "headline": "Origin",
            "description": (
                "Single-source botanicals from Grasse. Regenerative "
                "provenance, soil-to-stopper craftsmanship. Cinematic "
                "stillness."
            ),
            "tagline": "Cultivated.",
            "stills": [],
        }],
    })
    assert out["ok"] is True
    assert len(out["scored_routes"]) == 1
    s = out["scored_routes"][0]
    assert s["brand_fit"] >= 0.75, f"on-brand route scored {s['brand_fit']}"
    assert s["violations"] == [], f"unexpected violations: {s['violations']}"
    assert out["content_safety_flag"] is False


def test_off_brand_solene_route_scores_low_with_violations():
    """A route with forbidden lexicon ('100% sustainable', 'indulge')
    should score low brand_fit and surface the specific violations."""
    out = _run({
        "brief": {"client_brand": "Solene"},
        "routes": [{
            "route_name": "route-off-brand",
            "headline": "Indulge in 100% sustainable luxury",
            "description": "Best-in-class regenerative fragrance, transformative.",
            "tagline": "Indulge in Provence",
            "stills": [],
        }],
    })
    s = out["scored_routes"][0]
    assert s["brand_fit"] < 0.45, f"off-brand route should score low; got {s['brand_fit']}"
    # At least three forbidden-phrase hits ("100% sustainable", "indulge",
    # "best-in-class", "transformative").
    assert len(s["violations"]) >= 3, f"violations: {s['violations']}"


def test_competitor_coded_solene_route_low_distinctiveness():
    """A route that explicitly references a competitor brand should
    score low distinctiveness AND list the competitor in violations."""
    out = _run({
        "brief": {"client_brand": "Solene"},
        "routes": [{
            "route_name": "route-competitor",
            "headline": "Margiela-coded apothecary aesthetic",
            "description": "Like Le Labo but better. Aesop-style amber.",
            "stills": [],
        }],
    })
    s = out["scored_routes"][0]
    # Distinctiveness should suffer because the route name-checks 3
    # competitors from Solene's distinctiveness benchmark doc.
    assert s["distinctiveness"] < 0.6, (
        f"competitor route should score low distinctiveness; got {s['distinctiveness']}"
    )
    assert any("competitor" in v for v in s["violations"]), s["violations"]


def test_voltari_off_brand_route_flags_tesla_lexicon():
    """Voltari rejects 'Tesla', 'ludicrous', 'revolutionary', 'green'."""
    out = _run({
        "brief": {"client_brand": "Voltari"},
        "routes": [{
            "route_name": "route-off",
            "headline": "Revolutionary Tesla-killer",
            "description": "Ludicrous range. Disruptive. Greener than green.",
            "stills": [],
        }],
    })
    s = out["scored_routes"][0]
    assert s["brand_fit"] < 0.45
    # Must catch at least 'revolutionary', 'ludicrous', 'disruptive'.
    violation_text = " ".join(s["violations"]).lower()
    assert "revolutionary" in violation_text
    assert "ludicrous" in violation_text


def test_three_route_summary_aggregates():
    """When 3 routes are scored, the top-level summary should reflect
    the lowest brand_fit and highest distinctiveness across them."""
    out = _run({
        "brief": {"client_brand": "Solene"},
        "routes": [
            {"route_name": "A", "headline": "Single-source botanicals from Grasse"},
            {"route_name": "B", "headline": "Soil-to-stopper craftsmanship"},
            {"route_name": "C", "headline": "Indulge in 100% sustainable luxury"},
        ],
    })
    assert len(out["scored_routes"]) == 3
    fits = [s["brand_fit"] for s in out["scored_routes"]]
    assert out["lowest_brand_fit"] == round(min(fits), 4)
    dists = [s["distinctiveness"] for s in out["scored_routes"]]
    assert out["highest_distinctiveness"] == round(max(dists), 4)


def test_routes_are_enriched_with_guardian_scores():
    """Brand-guardian must merge brand_fit / distinctiveness onto each
    route IN the returned `routes` list, so the persona's
    decision_policy and the UI's concept_tiles see one coherent shape."""
    out = _run({
        "brief": {"client_brand": "Solene"},
        "routes": [{
            "route_name": "A",
            "headline": "Single-source botanicals from Grasse",
            "stills": ["s1.svg"],
            "brand_fit": 0.55,  # placeholder from agent stub
            "distinctiveness": 0.55,
        }],
    })
    assert "routes" in out
    enriched = out["routes"][0]
    # The original `stills` field passes through.
    assert enriched["stills"] == ["s1.svg"]
    # brand_fit / distinctiveness are overridden with guardian's values.
    assert enriched["brand_fit"] != 0.55  # got rescored
    assert enriched["brand_fit"] == out["scored_routes"][0]["brand_fit"]
    # Rationale bullets are exposed for the operator view.
    assert "brand_guardian_rationale" in enriched


def test_brief_synthesis_brand_path():
    """When the workflow has progressed past brief_synthesis, the brand
    is read from `brief_synthesis.brief_json.client_brand`, not `brief`."""
    out = _run({
        "brief_synthesis": {"brief_json": {"client_brand": "Heritor"}},
        "routes": [{
            "route_name": "A",
            "headline": "150 years in Geneva, hand-finished, edition of 100",
            "stills": [],
        }],
    })
    s = out["scored_routes"][0]
    assert s["brand_fit"] >= 0.75


def test_no_routes_returns_empty_summary():
    out = _run({"brief": {"client_brand": "Solene"}, "routes": []})
    assert out["scored_routes"] == []
    assert out["lowest_brand_fit"] == 0.0
    assert out["highest_distinctiveness"] == 0.0
    assert out["ok"] is True
