# src/functions/graphs/executors/agents/agent_creative_stub.py
"""Placeholder agent for the POC3 creative-campaign spine.

Each of the five agentic phases in the creative-campaign orchestrator
(brief_synthesis, insight_audience, concept_fanout, storyboard_render,
package_handoff) wires this agent into its `agent` slot so the workflow
runs end-to-end against canned image fixtures before per-phase skills
land in Phase 4 of plan/feature-poc3-ai-agency-1.md.

Returns a deterministic stub payload tagged with the phase. For
phases that need to surface artefacts to the operator UI (concept
tiles, storyboard strip), the stub reads from
data/synthetic/creative-campaign/cached/<brief-id>/ and returns
canned blob URLs so the WorkflowDetail surface has something to render.

Replaced in Phase 4 by real GHCP-SDK agents loading the per-phase
SKILL.md (creative-briefer, brief-synthesiser, concept-curator,
brand-guardian, storyboard-curator).

Phase-3 swap: when `image_gen.is_configured()` (CREATIVE_REAL_FOUNDRY=1
+ Foundry/Storage env), the concept_fanout and storyboard_render
branches call the `image_gen` MCP tool to render real gpt-image-2
images in parallel via asyncio.gather, falling back to the canned
SVG paths on any failure (RAI rejection, API error, network blip).
The MCP boundary stays clean — image_gen knows nothing about cached
fixtures; the fallback lives here in the caller, exactly the way a
v2 Adobe Firefly / Runway / Veo MCP swap would land.
"""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path

from api.server.mcp_tools import image_gen


# Quality tier for stub-driven renders. Demo default is medium (~$0.04/image,
# 18 images per workflow ⇒ ~$0.75/run at low cache utilisation). Override
# with CREATIVE_IMAGE_QUALITY=low for cheaper / faster dev iteration.
_STUB_QUALITY = os.environ.get("CREATIVE_IMAGE_QUALITY", "medium")
_STUB_SIZE = os.environ.get("CREATIVE_IMAGE_SIZE", "1024x1024")

# Hard cap on simultaneous gpt-image-2 calls per workflow phase. Going wide
# (12 in flight) wedges the Azure Functions Python worker's gRPC heartbeat
# AND blows through the 4-req/min Foundry quota on our demo deployment.
# Default 2 keeps the worker responsive and stays inside the rate limit
# (image_gen handles 429 with retry-after, but minimising 429 hits keeps
# wall time low). Override per environment with CREATIVE_IMAGE_CONCURRENCY.
_STUB_CONCURRENCY = int(os.environ.get("CREATIVE_IMAGE_CONCURRENCY", "2"))

# data/synthetic/creative-campaign/cached/<brief-id>/route-A/{1..4}.svg etc.
_CACHED_ROOT = (
    Path(__file__).resolve().parents[5] / "data" / "synthetic" / "creative-campaign" / "cached"
)


def _cached_urls(brief_id: str, sub: str, count: int, ext: str = "svg") -> list[str]:
    """Return synthetic URLs for cached fixtures. We don't actually serve
    these; they're stable identifiers the Phase-5 UI component will fetch
    from /api/static/creative-campaign/cached/<brief>/<sub>/<n>.svg or
    similar. For Phase 1 stub purposes the path-shaped string is enough
    to render placeholder tiles."""
    out = []
    for i in range(1, count + 1):
        out.append(f"creative-campaign/cached/{brief_id}/{sub}/{i}.{ext}")
    return out


# -------------------------------------------------- Phase-3 real-render hook


def _build_concept_prompt(brief: dict, route_headline: str, route_desc: str, idx: int) -> str:
    """Construct a gpt-image-2 prompt for one concept still. Stub-grade —
    Phase 4's real concept-curator skill will produce richer, art-directed
    prompts via gpt-5.2 + the brand-RAG corpus. For Phase 3 we just need
    something plausible enough to render demo imagery.

    No human faces, no logos, no text — keeps the output RAI-clean and
    aesthetically agency-credible (product-only luxury photography)."""
    brand = brief.get("client_brand", "Solene")
    category = (brief.get("category", "luxury_fragrance")).replace("_", " ")
    audience = brief.get("audience", "European luxury 25-44")
    return (
        f"Editorial product photography for {brand}, a {category} brand. "
        f"Creative route: {route_headline} — {route_desc}. "
        f"Frame {idx} of 4. Audience: {audience}. "
        f"Composition: cinematic, premium, magazine-shoot quality. "
        f"No people, no text, no logos. Natural light. 35mm photographic feel."
    )


def _build_storyboard_prompt(brief: dict, frame_caption: str, idx: int) -> str:
    """One storyboard frame prompt, captioned by intent. Same RAI-clean rules
    as concept stills — product / landscape / craftsmanship subjects only."""
    brand = brief.get("client_brand", "Solene")
    category = (brief.get("category", "luxury_fragrance")).replace("_", " ")
    return (
        f"Storyboard frame {idx} of 6 for a {brand} {category} film. "
        f"Scene: {frame_caption}. "
        f"Style: cinematic still, hand-painted concept-art feel, soft-focus. "
        f"No people in frame, no text overlay, no brand marks rendered."
    )


async def _render_or_fallback(prompt: str, fallback_url: str,
                              sem: asyncio.Semaphore | None = None) -> str:
    """Call image_gen in a thread (it's sync) and return the SAS URL on
    success, or the cached fixture URL on any failure. Failure modes
    include: not configured (canned-fixture path is the dev default),
    content_safety_rejection (RAI flagged the prompt — Phase 4 skill
    rewrites; stub just falls back), api_error (network blip).

    The fall-back behaviour means a partial Foundry outage during a demo
    degrades gracefully to placeholders rather than killing the workflow.

    `sem` bounds in-flight concurrency. None == unbounded (the smoke
    test path); the activity passes a semaphore to keep the Functions
    worker responsive under 12+ parallel renders.
    """
    if not image_gen.is_configured():
        return fallback_url
    async def _run() -> str:
        try:
            result = await asyncio.to_thread(
                image_gen.image_gen,
                prompt=prompt,
                size=_STUB_SIZE,
                quality=_STUB_QUALITY,
            )
        except Exception as ex:  # noqa: BLE001 — never let a render kill the workflow
            print(f"[creative-stub] image_gen raised {ex!r}; using fixture")
            return fallback_url
        if result.result_type == "success" and result.image_url:
            return result.image_url
        print(
            f"[creative-stub] image_gen failed code={result.error_code} "
            f"err={result.error}; using fixture"
        )
        return fallback_url
    if sem is None:
        return await _run()
    async with sem:
        return await _run()


def _load_brief(brief_id: str | None) -> dict:
    """Read one brief from the seed corpus, falling back to a stub. Used by
    brief_synthesis to project the structured brief from the unstructured
    record without calling a real model."""
    if not brief_id:
        return {}
    corpus_path = (
        Path(__file__).resolve().parents[5]
        / "data" / "synthetic" / "creative-campaign" / "briefs.json"
    )
    if not corpus_path.exists():
        return {}
    try:
        records = json.loads(corpus_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    for r in records:
        if r.get("id") == brief_id or r.get("brief_id") == brief_id:
            return r
    return {}


async def execute(input: dict) -> dict:
    """Phase-aware stub. Reads the workflow's brief_id (from payload) and
    the phase tag (set by the orchestrator's checkpoint payload), then
    returns a phase-shaped dict that downstream graphs + the validator
    + the persona responder can all read.
    """
    phase = input.get("phase") or "unknown"
    workflow_id = input.get("workflow_id") or "?"
    brief_id = (
        input.get("brief_id")
        or (input.get("brief") or {}).get("id")
        or (input.get("brief") or {}).get("brief_id")
    )
    brief = _load_brief(brief_id) if brief_id else (input.get("brief") or {})

    if phase in ("Brief Synthesis", "brief_synthesis"):
        # Project the unstructured seed brief into the structured shape the
        # brief_approval gate inspects. Real skill (brief-synthesiser) lands
        # in Phase 4.
        brief_json = {
            "id": brief.get("id") or brief_id or "BRF-?",
            "client_brand": brief.get("client_brand", "Solene"),
            "category": brief.get("category", "luxury_fragrance"),
            "audience": brief.get("audience", "Aspirational European 25-44"),
            "mandatory_messages": brief.get(
                "mandatory_messages",
                ["regenerative provenance", "low-impact craftsmanship"],
            ),
            "channels": brief.get("channels", ["CTV", "OOH", "social"]),
            "kpis": brief.get("kpis", {"awareness": "+15%", "intent": "+8%"}),
            "constraints": brief.get("constraints", []),
            "jurisdictions": brief.get("jurisdictions", ["UK", "FR"]),
        }
        return {
            "phase": phase,
            "workflow_id": workflow_id,
            "brief_json": brief_json,
            "stub": True,
        }

    if phase in ("Insight & Audience", "insight_audience"):
        return {
            "phase": phase,
            "workflow_id": workflow_id,
            "audience_clusters": [
                {"name": "regenerative-converts", "size_pct": 28},
                {"name": "luxury-traditionalists", "size_pct": 41},
                {"name": "aesthetic-experimentalists", "size_pct": 31},
            ],
            "trend_signals": [
                "regenerative provenance now table-stakes for premium",
                "ASMR unboxing dominating TikTok aesthetic-luxury vertical",
            ],
            "brand_recall": {
                "past_campaigns": ["SS24 Solene Renaissance", "AW24 Solene Origin"],
                "guardrails_pulled": 4,
            },
            "stub": True,
        }

    if phase in ("Concept Fan-out", "concept_fanout"):
        # Three strategic routes, each with 4 stills + scores. When
        # CREATIVE_REAL_FOUNDRY=1 the still URLs come from a parallel
        # gpt-image-2 burst (~5-15s for 12 images at medium quality);
        # otherwise we return the canned SVG paths. Either way the UI
        # contract (3 routes × 4 stills + brand_fit + distinctiveness)
        # is identical so the Phase-5 frontend doesn't branch.
        bid = brief.get("id") or brief_id or "BRF-001"
        route_specs = [
            {
                "route_name": "route-A",
                "headline": "Origin",
                "description": (
                    "Cinematic minimalism — single-source botanicals, "
                    "stillness, monochrome typography."
                ),
                "brand_fit": 0.91,
                "distinctiveness": 0.74,
            },
            {
                "route_name": "route-B",
                "headline": "Pulse",
                "description": (
                    "Social-first vibrancy — kinetic close-ups, vivid "
                    "colour blocks, ASMR-led product reveals."
                ),
                "brand_fit": 0.88,
                "distinctiveness": 0.86,
            },
            {
                "route_name": "route-C",
                "headline": "Land",
                "description": (
                    "Provenance-led — landscape vistas, regenerative "
                    "farms, natural light, hand-illustrated supers."
                ),
                "brand_fit": 0.83,
                "distinctiveness": 0.81,
            },
        ]
        # Build the (prompt, fallback_url) pair for every still up-front so
        # we can fire one big asyncio.gather across all 12 in parallel,
        # bounded by a semaphore so a Functions worker doesn't stall on
        # 12 simultaneous in-flight HTTP calls.
        render_jobs: list[tuple[int, int, str, str]] = []
        for r_idx, spec in enumerate(route_specs):
            cached = _cached_urls(bid, spec["route_name"], 4)
            for s_idx in range(4):
                prompt = _build_concept_prompt(
                    brief, spec["headline"], spec["description"], s_idx + 1
                )
                render_jobs.append((r_idx, s_idx, prompt, cached[s_idx]))

        sem = asyncio.Semaphore(_STUB_CONCURRENCY)
        rendered = await asyncio.gather(
            *(_render_or_fallback(p, f, sem) for _, _, p, f in render_jobs)
        )

        # Stitch the flat result list back into 3 routes × 4 stills.
        routes: list[dict] = []
        for r_idx, spec in enumerate(route_specs):
            stills = [
                rendered[i]
                for i, (rr, _, _, _) in enumerate(render_jobs)
                if rr == r_idx
            ]
            routes.append({**spec, "stills": stills})

        return {
            "phase": phase,
            "workflow_id": workflow_id,
            "routes": routes,
            "content_safety_flag": False,
            "image_source": (
                "foundry.gpt-image-2" if image_gen.is_configured() else "fixture"
            ),
            "stub": True,
        }

    if phase in ("Storyboard Render", "storyboard_render"):
        bid = brief.get("id") or brief_id or "BRF-001"
        captions = [
            "Open: regenerative farm at dawn",
            "Cut: hands tending botanicals",
            "Close-up: product reveal",
            "Brand mark: Solene wordmark",
            "Tagline: 'Where it begins'",
            "End frame: package on plinth",
        ]
        cached = _cached_urls(bid, "storyboard", 6)
        sem = asyncio.Semaphore(_STUB_CONCURRENCY)
        rendered = await asyncio.gather(
            *(
                _render_or_fallback(
                    _build_storyboard_prompt(brief, cap, idx + 1),
                    cached[idx],
                    sem,
                )
                for idx, cap in enumerate(captions)
            )
        )
        return {
            "phase": phase,
            "workflow_id": workflow_id,
            "frames": rendered,
            "frame_captions": captions,
            "content_safety_flag": False,
            "image_source": (
                "foundry.gpt-image-2" if image_gen.is_configured() else "fixture"
            ),
            "stub": True,
        }

    if phase in ("Package & Handoff", "package_handoff"):
        bid = brief.get("id") or brief_id or "BRF-001"
        return {
            "phase": phase,
            "workflow_id": workflow_id,
            # Phase 6 MCP (figma.push_asset_bundle) sets this for real.
            "figma_file_url": (
                f"https://www.figma.com/design/DEMO_FILE_KEY/Apex"
                f"?node-id=cmp-{bid}"
            ),
            "deliverables": [
                "brief.json",
                "concept-stills/locked-route/{1..4}.png",
                "storyboard/{1..6}.png",
                "brand-brief.pdf",
            ],
            "stub": True,
        }

    # Default — unknown phase
    return {
        "phase": phase,
        "workflow_id": workflow_id,
        "summary": f"creative-campaign stub agent ran for phase={phase}",
        "stub": True,
    }
