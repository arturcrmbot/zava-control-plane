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
"""
from __future__ import annotations
import json
from pathlib import Path

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
        # Three strategic routes, each with 4 cached stills + scores.
        # Real concept-curator skill lands in Phase 4; image_gen MCP in
        # Phase 3 swaps the cached URLs for live gpt-image-2 outputs.
        bid = brief.get("id") or brief_id or "BRF-001"
        routes = [
            {
                "route_name": "route-A",
                "headline": "Origin",
                "description": (
                    "Cinematic minimalism — single-source botanicals, "
                    "stillness, monochrome typography."
                ),
                "stills": _cached_urls(bid, "route-A", 4),
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
                "stills": _cached_urls(bid, "route-B", 4),
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
                "stills": _cached_urls(bid, "route-C", 4),
                "brand_fit": 0.83,
                "distinctiveness": 0.81,
            },
        ]
        return {
            "phase": phase,
            "workflow_id": workflow_id,
            "routes": routes,
            "content_safety_flag": False,
            "stub": True,
        }

    if phase in ("Storyboard Render", "storyboard_render"):
        bid = brief.get("id") or brief_id or "BRF-001"
        return {
            "phase": phase,
            "workflow_id": workflow_id,
            "frames": _cached_urls(bid, "storyboard", 6),
            "frame_captions": [
                "Open: regenerative farm at dawn",
                "Cut: hands tending botanicals",
                "Close-up: product reveal",
                "Brand mark: Solene wordmark",
                "Tagline: 'Where it begins'",
                "End frame: package on plinth",
            ],
            "content_safety_flag": False,
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
