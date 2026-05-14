"""brand-guardian deterministic validator (POC3 Phase 2).

Phase 2 ships a deterministic implementation of brand-guardian that
reads the brand corpus directly (via api.server.mcp_tools.brand_rag),
extracts the lexicon (preferred / forbidden), and scores each concept
route against the rubric in api/server/skills/brand-guardian/SKILL.md.

Phase 4 will swap this for a real gpt-4.1-mini call against the same
SKILL.md. The output JSON shape is identical so downstream consumers
(persona decision_policy, UI) don't need to change.

Strategy:
  - Pull lexicon from the corpus by parsing the markdown for known
    section headings ("Lexicon — preferred", "Lexicon — forbidden",
    "Mandatory in-frame", etc.).
  - For each route, build a single text blob (headline + description +
    tagline) and search for forbidden / preferred terms + competitor
    names.
  - Score brand_fit + distinctiveness deterministically per the rubric.
  - Surface violations as a list of short strings.

Wired as the agent step in `concept_fanout` graph (Phase 2 task).
Phase 1 stub (`agent_creative_stub`) returns the routes with hardcoded
brand_fit; this validator overlays its scores on top.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from api.server.mcp_tools.brand_rag import (
    Chunk,
    BrandQueryResult,
    query_brand_corpus_impl,
)


# Cached per-brand lexicon, parsed once from the corpus.
_LEXICON_CACHE: dict[str, dict] = {}


_HEADING_TO_FIELD = {
    "lexicon — preferred": "preferred",
    "lexicon — forbidden": "forbidden",
    "mandatory in-frame": "mandatory",
    "mandatory in-frame phrases (rotate at least one)": "mandatory",
    # "Avoid (read as competitor)" lives in markdown tables; we parse
    # those separately as `competitor_codes` below.
}

_TOKEN_RE = re.compile(r"[A-Za-z0-9%]+")


def _normalise(s: str) -> str:
    return s.lower().strip()


def _extract_bullets_after_heading(md: str, headings: list[str]) -> list[str]:
    """Return all bullet items that follow any of the given heading
    strings (case-insensitive substring match) up to the next markdown
    heading (`#`-prefixed line) or end-of-file.

    Handles two bullet shapes:
      - simple:        `- "phrase" (parenthetical reason)`
      - multi-phrase:  `- "a", "b", "c" — long explanation`
      - bold-emphasis: `- **Item** — explanation`
    Returns each phrase as a separate string with quotes/markers stripped.
    """
    found: list[str] = []
    headings_lc = [h.lower() for h in headings]
    in_block = False
    for line in md.splitlines():
        s = line.strip()
        sl = s.lower()
        # A new heading (any level) terminates the previous block and
        # may start a new one.
        if sl.startswith("#"):
            in_block = any(h in sl for h in headings_lc)
            continue
        if not (in_block and s.startswith("- ")):
            continue
        body = s[2:].strip()
        # Drop trailing parenthetical reasons "(legal)".
        body = re.sub(r"\s*\([^)]*\)\s*", " ", body)
        # Drop trailing em-dash explanation: "X — long explanation".
        body = re.split(r"\s+\u2014\s+", body, maxsplit=1)[0].strip()
        # Drop trailing en-dash explanation too: "X – explanation".
        body = re.split(r"\s+\u2013\s+", body, maxsplit=1)[0].strip()
        # Quoted multi-item: "a", "b", "c" — split on quote-comma-space.
        if '"' in body:
            phrases = re.findall(r'"([^"]+)"', body)
            if phrases:
                for p in phrases:
                    p2 = p.strip()
                    if p2:
                        found.append(p2)
                continue
        # Bold-emphasis form: "**Item** ..." — strip emphasis markers.
        m = re.match(r"^\*\*([^*]+)\*\*", body)
        if m:
            item = m.group(1).strip()
            if item:
                found.append(item)
            continue
        # Plain text bullet — strip surrounding backticks/quotes.
        item = body.strip("`").strip('"').strip("'").strip()
        if item:
            found.append(item)
    return found


def _load_lexicon(brand: str) -> dict:
    """Parse the brand's corpus directory once and extract:
      - preferred: list[str]
      - forbidden: list[str]
      - mandatory: list[str]
      - competitors: list[str] (from distinctiveness benchmark tables)
    Cached per process."""
    cached = _LEXICON_CACHE.get(brand.lower())
    if cached:
        return cached

    corpus_root = (
        Path(__file__).resolve().parents[5]
        / "data" / "synthetic" / "creative-campaign" / "brand-corpus"
    )
    brand_dir = None
    for p in corpus_root.iterdir() if corpus_root.exists() else []:
        if p.is_dir() and p.name.lower() == brand.lower():
            brand_dir = p
            break
    if not brand_dir:
        out = {"preferred": [], "forbidden": [], "mandatory": [], "competitors": []}
        _LEXICON_CACHE[brand.lower()] = out
        return out

    preferred: list[str] = []
    forbidden: list[str] = []
    mandatory: list[str] = []
    competitors: list[str] = []

    for md in sorted(brand_dir.glob("*.md")):
        raw = md.read_text(encoding="utf-8")
        preferred += _extract_bullets_after_heading(raw, ["lexicon — preferred"])
        forbidden += _extract_bullets_after_heading(raw, ["lexicon — forbidden"])
        # Mandatory phrases live under several heading variants.
        mandatory += _extract_bullets_after_heading(raw, [
            "mandatory in-frame",
            "mandatory phrases",
        ])
        # Competitive set lives as bullets right after "## Competitive set"
        # or "## Category competitive set". The bullet extractor already
        # strips the bold marker + em-dash trailer, so we just take what
        # comes back.
        competitors += _extract_bullets_after_heading(raw, [
            "competitive set",
            "category competitive set",
        ])

    # Dedupe + lowercase for matching.
    out = {
        "preferred": sorted({_normalise(x) for x in preferred if x}),
        "forbidden": sorted({_normalise(x) for x in forbidden if x}),
        "mandatory": sorted({_normalise(x) for x in mandatory if x}),
        "competitors": sorted({_normalise(x) for x in competitors if x}),
    }
    _LEXICON_CACHE[brand.lower()] = out
    return out


def reset_lexicon_cache() -> None:
    """Test helper."""
    _LEXICON_CACHE.clear()


def _route_text(route: dict) -> str:
    """Concatenate all the strings on a route into one search blob."""
    parts: list[str] = []
    for k in ("headline", "description", "tagline"):
        v = route.get(k)
        if isinstance(v, str):
            parts.append(v)
    # Stills carry path strings; not useful for text scoring but harmless.
    return " ".join(parts)


def _has_phrase(text: str, phrase: str) -> bool:
    """Match phrase in text (case-insensitive substring). Fast and good
    enough for the lexicon shapes our corpus uses."""
    if not phrase:
        return False
    return phrase.lower() in text.lower()


def _score_route(route: dict, lexicon: dict, rag_chunks: list[Chunk]) -> dict:
    """Apply the rubric in api/server/skills/brand-guardian/SKILL.md.
    Returns a dict matching the SKILL.md output schema for one route."""
    text = _route_text(route)
    text_lc = text.lower()

    # ---- forbidden hits drive brand_fit down hard ----
    forbidden_hits = [f for f in lexicon["forbidden"] if _has_phrase(text_lc, f)]
    preferred_hits = [p for p in lexicon["preferred"] if _has_phrase(text_lc, p)]
    mandatory_hits = [m for m in lexicon["mandatory"] if _has_phrase(text_lc, m)]
    competitor_hits = [c for c in lexicon["competitors"] if _has_phrase(text_lc, c)]

    # brand_fit baseline ~ 0.65 for a route that's neither distinctly
    # on- nor off-brand. Each preferred / mandatory phrase nudges up;
    # each forbidden phrase pushes down sharply.
    brand_fit = 0.65
    brand_fit += min(len(preferred_hits), 3) * 0.08
    brand_fit += min(len(mandatory_hits), 2) * 0.06
    brand_fit -= len(forbidden_hits) * 0.20
    brand_fit = max(0.0, min(1.0, brand_fit))

    # distinctiveness: down for competitor name hits, up for brand-RAG
    # density (more on-brand chunks score above 0.5 means the route's
    # text leans into the brand's owned codes).
    avg_chunk_score = (
        sum(c.score for c in rag_chunks) / len(rag_chunks)
        if rag_chunks else 0.0
    )
    distinctiveness = 0.55 + 0.6 * avg_chunk_score
    distinctiveness -= len(competitor_hits) * 0.15
    distinctiveness = max(0.0, min(1.0, distinctiveness))

    violations: list[str] = []
    for f in forbidden_hits:
        violations.append(f"uses forbidden phrase '{f[:60]}'")
    for c in competitor_hits:
        violations.append(f"reads competitor-coded ({c[:40]})")

    rationale: list[str] = []
    if preferred_hits:
        rationale.append(
            f"on-brand phrases present: {', '.join(preferred_hits[:3])[:60]}"
        )
    if mandatory_hits:
        rationale.append(
            f"mandatory codes present: {', '.join(mandatory_hits[:2])[:60]}"
        )
    if not preferred_hits and not mandatory_hits:
        rationale.append("no preferred or mandatory lexicon detected")
    if forbidden_hits:
        rationale.append(f"{len(forbidden_hits)} forbidden lexicon hit(s)")
    if competitor_hits:
        rationale.append(f"{len(competitor_hits)} competitor cue(s)")
    if rag_chunks:
        rationale.append(
            f"top brand-RAG chunk score: {rag_chunks[0].score:.2f}"
            f" ({rag_chunks[0].doc_kind})"
        )

    return {
        "route_name": route.get("route_name", "?"),
        "brand_fit": round(brand_fit, 4),
        "distinctiveness": round(distinctiveness, 4),
        "violations": violations,
        "content_safety_flag": False,  # Phase 2 deterministic doesn't trip this
        "rationale_bullets": rationale[:5],
    }


async def execute(input: dict) -> dict:
    """Validator entry point. Reads `concept_fanout.routes` (or
    `routes` directly when called inside a graph that already
    extracted them) from the input, scores each, and returns a
    payload conforming to the brand-guardian SKILL.md schema.

    Crucially, the returned dict carries BOTH the original `routes`
    list (with brand-guardian's brand_fit / distinctiveness /
    violations merged ONTO each route entry) AND the standalone
    `scored_routes` list. The orchestrator's `_publish_phase_output`
    stamps this onto `workflow.payload.concept_fanout`, so the UI's
    CreativeCampaignArtefacts component still sees `routes[].brand_fit`
    where it expects, and the persona's decision_policy reads
    `routes[].brand_fit` consistently.
    """
    workflow_id = input.get("workflow_id") or "?"
    phase = input.get("phase") or "brand_guardian"

    # Find the brand. Either nested under `brief` (early phases) or
    # `brief_synthesis.brief_json` (post-Phase-2 of the workflow).
    brief = (
        (input.get("brief_synthesis") or {}).get("brief_json")
        or input.get("brief")
        or {}
    )
    brand = brief.get("client_brand") or "Solene"

    # Find the routes. Either passed directly via the merged payload
    # from the upstream concept-curator stub (`routes`) or nested
    # under `concept_fanout.routes` if the orchestrator stitched it.
    routes = input.get("routes") or (input.get("concept_fanout") or {}).get("routes") or []

    lexicon = _load_lexicon(brand)

    scored_routes: list[dict] = []
    enriched_routes: list[dict] = []
    for r in routes:
        text = _route_text(r)
        # One brand-RAG query per route — gives us a freshness signal
        # for the scoring below.
        rag = query_brand_corpus_impl(brand=brand, query=text or brand, k=5)
        scored = _score_route(r, lexicon, rag.chunks)
        scored_routes.append(scored)
        # Merge guardian's scores ONTO the route so the UI + persona
        # decision_policy see a unified shape.
        merged = dict(r)
        merged["brand_fit"] = scored["brand_fit"]
        merged["distinctiveness"] = scored["distinctiveness"]
        merged["violations"] = scored["violations"]
        merged["brand_guardian_rationale"] = scored["rationale_bullets"]
        enriched_routes.append(merged)

    if scored_routes:
        lowest_brand_fit = min(s["brand_fit"] for s in scored_routes)
        highest_distinctiveness = max(s["distinctiveness"] for s in scored_routes)
    else:
        lowest_brand_fit = 0.0
        highest_distinctiveness = 0.0

    return {
        "phase": phase,
        "workflow_id": workflow_id,
        # Merged routes (with brand_fit / distinctiveness from guardian)
        # — the persona's decision_policy reads this directly.
        "routes": enriched_routes,
        # Standalone scored summary — surfaced on the UI as a "guardian
        # called out the following violations" panel (Phase 4 / 5
        # follow-up).
        "scored_routes": scored_routes,
        "content_safety_flag": any(
            s["content_safety_flag"] for s in scored_routes
        ),
        "lowest_brand_fit": round(lowest_brand_fit, 4),
        "highest_distinctiveness": round(highest_distinctiveness, 4),
        # ok flag for the graph validator contract; brand-guardian is
        # informative-only — it doesn't block the graph, it surfaces
        # scores the persona reads.
        "ok": True,
    }
