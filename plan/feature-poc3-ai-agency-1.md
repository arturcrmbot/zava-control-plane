---
goal: Compose POC3 (creative campaign workflow for the AI-agency demo) on the existing eight-domain substrate by adding one new domain — `creative-campaign` — that takes a multi-party voice brief, fans out across specialist agents (insight, audience, brand-guardian, concept-curator), generates concept stills + storyboard via Foundry `gpt-image-2`, gates four HITL approvals through our Control Plane, and federates the final asset bundle to Figma as the agency's existing design surface. No video generation in v1 (Sora-2 is preview / Limited Access; storyboard hand-off to humans is the agency-truthful endpoint). No Cowork in v1 (M365 Frontier dependency adds risk, voice intake to our Control Plane is sufficient). All four HITL gates from the original storyboard land in our Control Plane (the supervisor surface, the hero of the demo), with Figma federation surfacing as a one-click "send to design team" action — not a competing canvas.
version: 1.0
date_created: 2026-05-05
last_updated: 2026-05-05
owner: Zava Control Plane POC1 — substrate
status: 'Planned'
tags: [feature, poc3, creative-agency, figma, foundry, image-generation]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Sister POC to POC1 (finance / [docs/poc1-brief.md](../docs/poc1-brief.md))
and POC2 (hiring / [docs/poc2-status.md](../docs/poc2-status.md)). Driven
by the storyboard at
[docs/AI-Agency-Demo-Storyboard.pptx](../docs/AI-Agency-Demo-Storyboard.pptx)
(prepared for James MacGregor — Sr Dir Industry Advisory IBB), with two
deliberate scope cuts vs. the storyboard:

1. **No video generation in v1.** Sora-2 is Foundry's only video model,
   in Preview, gated by Limited Access (verified — current subscription
   `MCAPS-Hybrid-REQ-67826-2023-arzielinski` returns empty when
   listing eastus2 SKUs filtered for `sora`), with 1–5 minute latency
   per render and 2-job concurrency cap. Betting a live demo on
   Sora-2 is operationally unsafe. The storyboard's "hero video" beat
   becomes a **storyboard hand-off**: agents produce 6 storyboard
   frames + brand brief, and the workflow's Stage-12 deliverable is the
   asset bundle handed to the agency's video team in their existing
   tools (Frame.io, Premiere). Sora-2 / Runway / Veo are narrated as v2
   plug-ins via the same MCP shape — that's exactly what the substrate
   is for.
2. **No Microsoft 365 Cowork integration in v1.** Cowork is M365
   Frontier preview; voice intake using the existing
   [`voice-screener`](../api/server/skills/voice-screener/SKILL.md)
   mechanic from POC2 lands the same beat with zero Frontier dependency.
   Cowork remains a v2 federation surface (custom skills in OneDrive
   call our MCP plugin) once the voice → control plane → image fan-out
   loop is solid.

The thesis from [docs/blueprint.md](../docs/blueprint.md) holds verbatim:
the **Control Plane is the hero**. The supervisor watching 300
campaigns concurrently, governing cost, exception, autonomy, audit, and
HITL across all of them — that's the demo's centre of gravity. The
agency keeps Figma. We add the layer above it.

**Cast (mapped from storyboard slide 1.3):**
- **Creative Director** (London) — submits brief via voice; reviews concept routes + storyboard in our Control Plane workflow detail; approves at 4 HITL gates; opens Figma when they want to take assets further.
- **Strategist + Brand Manager** — joins the voice brief alongside the CD (multi-party WebRTC, gpt-realtime-1.5).
- **Producer** (shared services) — sees workflow on the existing operator surface; resolves brand/safety exceptions only.
- **Fleet Supervisor** — watches 30–50 concurrent campaigns from the existing Control Plane fleet view (filter chip: "Creative Campaigns").

**Six phases** mapped to storyboard stages 01–08 (compressed; storyboard
stages 6 video-gen + 7 exception become a single phase in v1 since the
exception pipeline is reusing the existing `triage` + `exception_factory`
substrate):

| # | Phase | What an agent does | HITL gate | Tools borrowed |
|---|---|---|---|---|
| 1 | `brief_capture` | `creative-briefer` skill listens to multi-party WebRTC call (gpt-realtime-1.5), prompts for missing fields | Strategist confirms objective | Existing `voice-screener` mechanic from POC2; new rubric only |
| 2 | `brief_synthesis` | `brief-synthesiser` skill turns transcript → structured JSON brief; Control Plane renders it as AG-UI scorecard inline in WorkflowDetail | **◆1** CD approves brief | Reuse `BulkHitlModal` |
| 3 | `insight_audience` | 3 agents fan out: `audience-clusterer`, `trend-scanner`, `brand-knowledge` — last one queries the brand-RAG corpus | none — supervisor watches | New `brand-rag` MCP server (Phase 2 below) |
| 4 | `concept_fanout` | `concept-curator` generates 3 routes; `gpt-image-2` renders 4 stills per route in parallel; **brand-guardian** scores brand-fit + distinctiveness; Control Plane shows 12 stills as 3-route concept tiles | **◆2** CD picks route | Foundry `gpt-image-2`; brand-RAG |
| 5 | `storyboard_render` | Chosen route → `storyboard-curator` generates 6 storyboard frame prompts; `gpt-image-2` renders all 6; brand-guardian validates each | **◆3** CD approves storyboard | Foundry `gpt-image-2` |
| 6 | `package_handoff` | Package: brief JSON, concept stills, storyboard frames, brand brief PDF; **push asset bundle to Figma file** as concept page (federation, not canvas); cost ledger + audit blob entry | **◆4** Producer signs off bundle, then activates Figma push | Figma MCP (one push; not the canvas) |

The four HITL gates from storyboard slide 14 land 1:1, all in our
Control Plane. Storyboard Stage 7 ("control plane becomes the hero" —
exception handling) is **not a new phase**; it's the existing
`exception_factory` + `triage` pipeline firing on brand-distinctiveness
flags, content-safety rejections from `gpt-image-2`, and cost-budget
breaches. Free.

**The brief subject for the demo scenario** is a **sustainable luxury
fragrance launch** — product-only (no human faces, RAI-clean for
`gpt-image-2`), credible for an agency audience, gives a wide visual
range from cinematic minimalism to social-first vibrancy, and aligns
with the blueprint's "regenerative production" framing. Worked example
prompts pre-baked in `data/synthetic/creative-campaign/briefs.json`.

## 1. Requirements & Constraints

- **REQ-001**: Add `creative-campaign` to the eight-domain substrate via [`api/shared/domains.py`](../api/shared/domains.py). Per-domain phase ribbon, FM skill text, blueprint inventory entry, simulator spawner all light up automatically (Phase 1 of [feature-fleet-domain-substrate-1.md](archive/feature-fleet-domain-substrate-1.md) made this a config change). Workflow-id prefix `CMP-`.
- **REQ-002**: A creative director joins a multi-party voice call (themselves + strategist + brand manager + AI), structures a brief in 3–5 minutes, and the workflow registers in our Control Plane within 2 seconds of `voice_complete`. Brief deck does NOT go to Word — it renders as an AG-UI scorecard inline in `WorkflowDetail.tsx`.
- **REQ-003**: After ◆1 brief approval, three insight agents fan out in parallel; supervisor watches them on the workflow detail with the existing `AgentReasoningTimeline` component.
- **REQ-004**: After insight phase, `concept-curator` produces 3 strategic routes; `gpt-image-2` renders 4 stills per route (12 stills total) in parallel; the 12 stills surface in WorkflowDetail as 3 concept-tile cards (4 stills each, brand-fit score, route name) with a "Lock route" button per card. Picking a route raises the `concept_locked` external event and the workflow advances to Phase 5.
- **REQ-005**: Storyboard phase generates 6 storyboard frame prompts and renders 6 stills via `gpt-image-2`; CD reviews them in the Control Plane (no Figma round-trip needed yet); ◆3 approves.
- **REQ-006**: After ◆4 final sign-off, the asset bundle (brief JSON, 4 chosen concept stills, 6 storyboard frames, brand brief PDF) is pushed to a single shared demo Figma file as a new page named `[CMP-NNNN] <campaign-name>`. Figma comment containing `@apex archive` on that page raises an `asset_archived` event (not used in v1; reserved for v2).
- **REQ-007**: 30 concurrent campaign workflows can run on the same FastAPI process. `gpt-image-2` calls run with no concurrency cap (model permits it).
- **REQ-008**: The fleet view (`web/client/routes/Fleet.tsx`) gains a "Creative Campaigns" filter chip alongside the existing chips. WorkflowDetail extends with a new `CreativeCampaignArtefacts` component that renders the AG-UI brief scorecard, the 3 concept tiles, and the storyboard strip. **No new pages, no parallel UI** — extend WorkflowDetail the same way POC2 extended it for the recruiter view.
- **REQ-009**: One pre-built demo brief seeds reproducibly; demo run takes ≤ 6 minutes end-to-end with no live edits required (image generation is fast — ~10s per still; 12 stills ≈ 60s parallel).
- **SEC-001**: `gpt-image-2` RAI filter blocks human faces, public figures, copyrighted content. The pre-baked brief subject (sustainable luxury fragrance) and prompt library are RAI-clean. Fail-safely: if `gpt-image-2` rejects a prompt, the orchestrator emits an exception with `category=content_safety_rejection` → FM picks it up via existing triage. **This is the Stage 7 demo beat, intentional.**
- **SEC-002**: Figma personal access token in `.env` (gitignored), never `.env.example`. Single-team scope.
- **CON-001**: Single operator. Three-week implementation window post-Friday demo (target 2026-05-29). No agent-runtime migration, no orchestrator-spine rewrite.
- **CON-002**: Reuse [`api/functions/workflows/expense_claim.py`](../api/functions/workflows/expense_claim.py)-shape Durable orchestrator generator; reuse [`api/functions/graphs/_tracked_executor.py`](../api/functions/graphs/_tracked_executor.py); reuse [`api/server/services/persona_responder.py`](../api/server/services/persona_responder.py) `escalate` verdict; reuse [`api/server/services/audit_logger.py`](../api/server/services/audit_logger.py) append-blob ledger from [feature-foundry-credibility-friday-1.md](feature-foundry-credibility-friday-1.md) Phase 4. **Zero substrate changes.**
- **CON-003**: Frontend additions are **strictly additive extensions** to existing components, not net-new pages. Specifically: one new component `CreativeCampaignArtefacts.tsx` mounted inside `WorkflowDetail.tsx`; one new filter chip in `Fleet.tsx`; one new domain-aware label in `PhaseRibbon.tsx` (already domain-aware via the registry).
- **CON-004**: **No video generation.** Sora-2 / Runway / Veo / Kling all narrated as v2 follow-ons via the same MCP shape. The storyboard delivery is the v1 endpoint.
- **CON-005**: **No Cowork integration.** Voice intake uses our existing WebRTC stack. Cowork narrated as v2 surface ("the same MCP shape lets a creative director author this from inside Cowork").
- **CON-006**: **No Adobe integration.** Frame.io, Workfront, Firefly, GenStudio narrated only. Figma is the agency-truthful concession; no further external creative-tool integration in v1.
- **CON-007**: Mock-first. Phase 2 ships canned image fixtures + a `gpt-image-2` MCP that returns blob URLs from `data/synthetic/creative-campaign/cached/`. Phase 3 connects to real Foundry behind a `CREATIVE_REAL_FOUNDRY=1` env flag (same pattern as POC2's `VOICE_TRANSPORT=canned`). All Phase 1 + Phase 2 work uses canned data so the substrate is end-to-end demoable before any Foundry call lands.
- **GUD-001**: Every per-campaign artefact (concept-tile JSON, storyboard URLs, Figma file URL) lives in `Workflow.payload` — no schema change. Same blob pattern as `Workflow.metadata.attachments`.
- **GUD-002**: All four new skills (`creative-briefer`, `brief-synthesiser`, `concept-curator`, `brand-guardian`) carry the same OTEL semantic-convention attributes as existing skills (`gen_ai.system=github_copilot`, `gen_ai.agent.name=creative-agent`, `zava.skill=<label>`) so spans appear in Foundry Tracing without per-skill wiring. Inherits from [feature-foundry-credibility-friday-1.md](feature-foundry-credibility-friday-1.md) Phase 1.
- **PAT-001**: Voice brief reuses [voice.py](../api/functions/graphs/voice.py) graph + [voice-screener](../api/server/skills/voice-screener/SKILL.md) mechanic — magic-link issuance, ephemeral key proxy at `/api/portal/voice/{session,rtc}`, `voice_complete` external event. New skill `creative-briefer` swaps the rubric (creative brief structure vs. candidate screening). Multi-party (≥2 humans + AI on one call): gpt-realtime-1.5 already diarises; we set `participants=[strategist,brand_manager,creative_director]` on the magic link payload and the rubric prompts the AI to address each by role.
- **PAT-002**: `gpt-image-2` MCP follows the existing sync-call pattern (no async polling — image gen is sub-30s per call). Cost ledger entry per call. Same shape as the existing `recall_similar_hires` MCP from POC2.
- **PAT-003**: Brand-RAG MCP wraps a 30–50 doc corpus (brand guidelines, past campaign briefs, distinctiveness benchmarks) in a single Foundry-deployed `text-embedding-3-large` index. Retrieval-only; one tool, `query_brand_corpus(brand, query, k=5)`. Hosted in-process via `chromadb` or similar (already a transitive dep). Corpus seed is committed; embeddings re-built at boot time.
- **PAT-004**: Figma push uses the official Figma REST API (`POST /v1/files/:key/comments`, `POST /v2/webhooks` for approval comment receipt) for the v1 federation push. **Not** the Figma MCP for write-to-canvas (that's beta + rate-limited; the v1 push is a single image-fill batch into a new page, no live canvas mutation).

## 2. Implementation Steps

Recommended worktree: `../zava-control-plane-poc3-ai-agency` on a new
branch `feat/poc3-ai-agency` based on `origin/main` after wave-2
hand-graduated fleet domains land. Phase 1 is fully reversible config;
Phase 6 is recording-only and last.

### Implementation Phase 1 — Domain registry + orchestrator skeleton (canned end-to-end)

- GOAL-001: `creative-campaign` is a first-class domain in [`api/shared/domains.py`](../api/shared/domains.py) with 6 phases, 4 HITL gates, 4 declared skills, prefix `CMP-`. Spawning `POST /api/simulator/creative-campaign` registers a workflow that completes end-to-end in ~15 seconds with stub agents and canned image URLs from `data/synthetic/creative-campaign/cached/`. Per-domain phase ribbon, blueprint observatory tile, FM skill catalogue light up automatically.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-001 | Add `Domain(workflow_type="creative-campaign", display_name="Creative Campaign", workflow_id_prefix="CMP-", orchestrator_name="CreativeCampaignOrchestrator", operator_surface="producer-queue", phases=(brief_capture, brief_synthesis, insight_audience, concept_fanout, storyboard_render, package_handoff), hitl_gates=(brief_approval, concept_lock, storyboard_approval, final_signoff), skills=("creative-briefer", "brief-synthesiser", "concept-curator", "brand-guardian"))` to `DOMAINS` in `api/shared/domains.py`. | | |
| TASK-002 | Widen `Workflow.type` literal in `api/shared/types.py` to include `"creative-campaign"`. | | |
| TASK-003 | Create `api/functions/workflows/creative_campaign.py` — Durable orchestrator generator with the 6 phases and 4 HITL waits. Each phase calls a stub graph that sleeps 2s and emits `step.completed`. | | |
| TASK-004 | Create `api/functions/graphs/{creative_brief,concept_fanout,storyboard_render,package_handoff}.py` — each a `_tracked_executor` shell that calls `agent_creative_stub.execute` + `validate_creative_stub.execute`. Real agents land in Phase 4. | | |
| TASK-005 | Create `creative-director` persona under `api/server/personae/creative-director/SKILL.md` with `decision_policy` block. v1 logic: `approve` on `brand_fit > 0.8 AND distinctiveness > 0.7`; `escalate` on `content_safety_flag == true`; otherwise leave open. Reuses `_DECISION_BUILTINS` sandbox. Opt into `PERSONA_AUTO_CLOSE` env list for the demo so the four gates close themselves on the autonomous loop. | | |
| TASK-006 | Add `spawn_creative_campaign_workflow(brief_id, scenario)` to `api/server/services/simulator_orchestrator.py`. Wire the simulator ramp loop to occasionally inject one (weight 0.05; the 8 existing domains keep their current weights). | | |
| TASK-007 | Pre-seed corpus at `data/synthetic/creative-campaign/briefs.json` with 12 demo briefs (variety: fragrance launch, EV reveal, regenerative skincare, watch reveal, premium spirits — all product/landscape, no humans, RAI-clean). Each brief carries `id`, `client_brand`, `category`, `audience`, `mandatory_messages[]`, `channels[]`, `kpis`, `scenario` (clean / amber / escalated). | | |
| TASK-008 | Pre-seed canned image fixtures at `data/synthetic/creative-campaign/cached/<brief-id>/{route-A,route-B,route-C}/{1,2,3,4}.png` and `data/synthetic/creative-campaign/cached/<brief-id>/storyboard/{1..6}.png`. Three full sets covering the three pre-baked demo briefs. Generate offline with personal `gpt-image-2` access; commit. | | |
| TASK-009 | Verify: `make up`, then `curl -X POST localhost:3101/api/simulator/creative-campaign -d '{"brief_id":"BRF-001"}'`, then check workflow appears in fleet view with 6 phases, completes in ~15s with stubs, all 4 HITL gates auto-close via `PERSONA_AUTO_CLOSE`. Tile shows the canned images. | | |

### Implementation Phase 2 — Brand-RAG MCP + brand-guardian skill (real corpus)

- GOAL-002: A real ~40-document brand corpus indexed in `chromadb`, queryable via a new MCP tool, consumed by `brand-guardian` to score every concept still + storyboard frame on brand-fit and distinctiveness. This is the agency-credibility moment — not the AI generating art, but the AI knowing what's *on-brand*.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-010 | Curate the brand corpus at `data/synthetic/creative-campaign/brand-corpus/` — 40 markdown documents across 4 fictional brand families: `Solene` (sustainable luxury fragrance, 12 docs), `Voltari` (EV reveal, 10 docs), `Verdaire` (regenerative skincare, 8 docs), `Heritor` (heritage watches, 10 docs). Each doc covers brand voice / visual codes / mandatory phrases / forbidden treatments / past campaign learnings. Use `gpt-5.4` to generate the corpus offline; review by hand. | | |
| TASK-011 | `api/server/mcp_tools/brand_rag.py` — exposes `query_brand_corpus(brand: str, query: str, k: int = 5) -> list[Chunk]`. Builds a `chromadb` index at startup using `text-embedding-3-large` (existing Foundry deployment). Persists to `azurite-data/brand-rag/` to avoid re-embedding on restart. | | |
| TASK-012 | `api/server/skills/brand-guardian/SKILL.md` — `gpt-4.1-mini` (cheap); takes `(image_url, brief_json)` → calls `query_brand_corpus(brief.client_brand, "visual codes")` → returns `{brand_fit: 0..1, distinctiveness: 0..1, violations: [...]}`. Wired as a validator in the `concept_fanout` and `storyboard_render` graphs. | | |
| TASK-013 | Add `BrandFitAccuracy` evaluator in `api/server/eval/custom_evaluators.py` — checks `brand-guardian`'s scores against ground truth in `data/synthetic/creative-campaign/labels.csv`. Wire into `_PER_AGENT` in `evaluator_set.py` (extending [feature-foundry-credibility-friday-1.md](feature-foundry-credibility-friday-1.md) Phase 3). | | |
| TASK-014 | Verify: spawn 3 workflows (one per brand). Inspect `brand-guardian` outputs; assert each route gets a `brand_fit` score, the brand corpus query span shows in Foundry Tracing with `tool.server.brand_rag`, and one deliberately-off-brand fixture triggers a `violations` non-empty array → orchestrator emits exception → FM picks up. | | |

### Implementation Phase 3 — Real Foundry `gpt-image-2` MCP

- GOAL-003: One MCP server (`api/server/mcp_tools/image_gen.py`) calls the real `gpt-image-2` model on the existing Foundry resource, writes outputs to blob, returns URLs, emits cost ledger entries. Available to skills via the existing in-process MCP pattern. Behind a `CREATIVE_REAL_FOUNDRY=1` env flag — defaults off so the Phase 1 canned path remains the dev default.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-015 | Verify `gpt-image-2` deployment exists on `arzie-mm4okigm-canadacentral` (or whichever Foundry resource is active). If not, deploy via `az cognitiveservices account deployment create --model-name gpt-image-2 --model-version <latest> --sku-name GlobalStandard`. Add `AZURE_OPENAI_IMAGE_DEPLOYMENT` + `AZURE_OPENAI_IMAGE_ENDPOINT` to `.env.example`. | | |
| TASK-016 | `api/server/mcp_tools/image_gen.py` — exposes `generate_concept_stills(prompt: str, style_directives: dict, count: int = 4, size: str = "1280x720") -> list[str]` returning a list of blob URLs (Azurite locally, real blob in deploy). Calls `client.images.generate(model="gpt-image-2", prompt=..., n=count, size=size, quality="high")`. Cost ledger row per call (`gpt-image-2` per-image rate from [Foundry pricing](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/)). | | |
| TASK-017 | Both `concept-curator` and `storyboard-curator` skills swap their canned-fixture call for `image_gen.generate_concept_stills(...)` when `CREATIVE_REAL_FOUNDRY=1`; otherwise fall through to the cached fixtures from Phase 1. Single code path, env flag at the boundary. | | |
| TASK-018 | Add content-safety rejection path: when `client.images.generate(...)` raises `BadRequestError` with `code=content_filter`, raise `ContentSafetyRejection` exception → orchestrator catches → emits `workflow.exception.created` with `category=content_safety_rejection` → FM picks up via existing triage. **This is the Stage 7 demo beat, deliberate.** | | |
| TASK-019 | The MCP emits OTEL spans `tool.server.image_gen` with `tool.cost.usd` attribute, picked up by [feature-foundry-credibility-friday-1.md](feature-foundry-credibility-friday-1.md) Phase 2 economics path with no extra wiring. | | |
| TASK-020 | Verify with `CREATIVE_REAL_FOUNDRY=1`: spawn one workflow, watch 12 concept stills + 6 storyboard frames land in Azurite, watch cost ledger row populate (~$0.50/workflow). Watch one deliberately-bad prompt trigger a content_safety exception in the FM queue. Spans visible in Foundry Tracing. | | |

### Implementation Phase 4 — Real skills (creative-briefer, brief-synthesiser, concept-curator, storyboard-curator)

- GOAL-004: Five real `SKILL.md` files in `api/server/skills/` replace the stubs from Phase 1. Each carries OTEL attrs, declared tool list, model choice. The voice intake reuses POC2's voice-screener mechanic verbatim with a swapped rubric.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-021 | `api/server/skills/creative-briefer/SKILL.md` — `gpt-realtime-1.5`; rubric: campaign objective, audience, mandatory messages, channels, KPIs, constraints, jurisdictions, brand selection from corpus. Multi-party prompt: addresses participants by role (strategist / brand-manager / creative-director). Reuses `voice.py` graph from POC2 verbatim. | | |
| TASK-022 | Drop `data/synthetic/creative-campaign/brief.schema.json` — JSON schema for the structured brief. | | |
| TASK-023 | `api/server/skills/brief-synthesiser/SKILL.md` — `gpt-5.4`; turns transcript JSON → structured brief JSON conforming to the schema; emits `brief_structured` event with the JSON in payload. | | |
| TASK-024 | `api/server/skills/concept-curator/SKILL.md` — `gpt-5.4`; takes brief JSON; for each of 3 strategic routes calls `image_gen.generate_concept_stills(...)` 1×; declares tools allow-list `[image_gen, brand_rag, recall_similar_campaigns]`. | | |
| TASK-025 | `api/server/skills/storyboard-curator/SKILL.md` — `gpt-5.4`; takes locked route + brief; generates 6 storyboard frame prompts; calls `image_gen.generate_concept_stills(prompt=<frame_prompt>, count=1)` × 6. | | |
| TASK-026 | Reuse [`api/server/mcp_tools/recall_similar_hires.py`](../api/server/mcp_tools/recall_similar_hires.py) pattern → new `api/server/mcp_tools/recall_similar_campaigns.py` keyed on `(brand_family, category)`. Returns past brief JSONs from `data/synthetic/creative-campaign/past-campaigns/` (10 fixtures). | | |
| TASK-027 | Per-agent evaluator entries for the four new skills in `api/server/eval/evaluator_set.py` `_PER_AGENT` (extending Friday Phase 3). Add: `BriefFieldExtractionAccuracy` (vs labels.csv), `RouteDistinctivenessScore`, `StoryboardCoherenceScore`. | | |
| TASK-028 | Verify: spawn one workflow with `CREATIVE_REAL_FOUNDRY=1`, watch real images land for the real route names; watch evaluator scores populate in `Evaluations.tsx`. | | |

### Implementation Phase 5 — Frontend extension (WorkflowDetail + Fleet filter chip)

- GOAL-005: Creative-campaign workflows render in WorkflowDetail with the AG-UI brief scorecard, 3 concept tiles (4 stills each, brand-fit score, "Lock route" button), storyboard strip (6 frames), and asset bundle download. Fleet view gains a "Creative Campaigns" filter chip. **No new pages.** Per [`docs/poc2-status.md`](../docs/poc2-status.md) the AG-UI primitive `AgentDrivenComponent.tsx` already exists; this phase only adds creative-campaign-shaped specs to it.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-029 | Extend `web/client/components/AgentDrivenComponent.tsx` with three new spec kinds: `brief_scorecard`, `concept_tiles`, `storyboard_strip`. Each has minimal styling (Tailwind, matches existing surface). Concept tiles include a "Lock route" button that POSTs `/api/workflows/<id>/resolve?gate=concept_lock&route=<route>` reusing existing resolve route. | | |
| TASK-030 | New component `web/client/components/apex/CreativeCampaignArtefacts.tsx` — mounted inside `WorkflowDetail.tsx` when `workflow.type === "creative-campaign"`. Reads `workflow.payload.{briefJson, conceptRoutes, storyboardFrames, figmaFileUrl}` and dispatches to the AG-UI primitives. | | |
| TASK-031 | Extend `web/client/routes/Fleet.tsx` to add a "Creative Campaigns" filter chip alongside existing chips. Filter logic uses `workflow.type === "creative-campaign"`. No new state — chips already drive the existing query param. | | |
| TASK-032 | Verify in browser: spawn 3 workflows, check filter chip toggles correctly; click into one, check brief scorecard renders, check 3 concept tiles render with images, click Lock route on one tile → workflow advances to storyboard, check storyboard strip renders. | | |

### Implementation Phase 6 — Figma federation push (final asset bundle)

- GOAL-006: After ◆4 final sign-off, the asset bundle is pushed to a single shared demo Figma file as a new page named `[CMP-NNNN] <campaign-name>` containing the brief summary frame + 4 chosen concept stills + 6 storyboard frames. Designer opens Figma later and sees the bundle waiting. This is the **federation moment** — the agency's existing tool, untouched, gets the substrate's output natively.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-033 | Register Figma personal access token; create one demo team file. Add `FIGMA_TOKEN` + `FIGMA_DEMO_FILE_KEY` to `.env.example`. Free-plan account is sufficient for v1. | | |
| TASK-034 | `api/server/mcp_tools/figma.py` — exposes `push_asset_bundle(workflow_id: str, brief_summary: str, concept_image_urls: list[str], storyboard_image_urls: list[str], campaign_name: str) -> str` returning the Figma page URL. Implementation: single REST call sequence — `POST /v1/files/:key/images` to upload images; create new page via `POST /v1/files/:key/nodes` (or via the desktop MCP if available); place images in auto-layout frames; post one comment `Asset bundle pushed by APEX [CMP-NNNN]` for traceability. | | |
| TASK-035 | New phase `package_handoff` in `creative_campaign.py` orchestrator: after ◆4 fires, calls `figma.push_asset_bundle(...)`, stamps `figmaFileUrl` into `workflow.payload`, and the `CreativeCampaignArtefacts` component renders an "Open in Figma →" link in the WorkflowDetail. | | |
| TASK-036 | Optional: `api/server/routes/figma.py` → `POST /api/figma/webhook` receives `FILE_COMMENT` events. Parses `@apex archive` from comment text → raises `asset_archived` event on the matching workflow. Reserved for v2 (close-the-loop), not used by v1 demo flow. | | |
| TASK-037 | Verify: spawn one full workflow end-to-end, check Figma page is created with the right images and the demo team can open it. The demo runbook narrates this as "and your design team picks it up from here, in the tool they already use". | | |

### Implementation Phase 7 — Demo wiring + recording

- GOAL-007: A repeatable 6-minute demo runbook in `docs/poc3-DEMO.md` that walks the storyboard slide 5–12 beats end-to-end against live Foundry + Figma, with one deliberately-bad scenario for the Stage 7 exception beat.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-038 | Author `docs/poc3-DEMO.md` mirroring [docs/poc2-DEMO.md](../docs/poc2-DEMO.md) shape: prerequisites, ramp boot, three demo scenarios (clean / amber / exception), tab-switch beats (Voice intake → Control Plane fleet view → workflow detail with concepts → exception in FM queue → Figma push → Foundry Tracing), expected outputs at each step. | | |
| TASK-039 | Pre-bake one "happy path" brief (Solene fragrance — RAI-safe) and one "Stage 7" brief (deliberately ambiguous prompt that triggers content_filter or brand-distinctiveness flag) in `briefs.json`. | | |
| TASK-040 | Update [README.md](../README.md) eight-domain table to include creative-campaign; update [docs/blueprint.md](../docs/blueprint.md) to reference POC3 in the "dozens of agents" line. | | |
| TASK-041 | Record 6-minute Loom of demo flow against live stack; post to `docs/recordings/poc3-walkthrough.mp4` (or link out per existing convention). | | |
| TASK-042 | Update the v2 narration script in `docs/poc3-DEMO.md` "What's next" section: Sora-2 / Runway / Veo (video-gen MCPs same shape), Cowork (custom skill in OneDrive calling our plugin), Frame.io / Workfront (federation MCPs), Adobe Firefly (image-gen MCP swap). One sentence each. | | |

## 3. Alternatives

- **ALT-001** — *Build a creative workbench in `web/portal/`*: rejected. Agencies use Figma, Adobe CC, Frame.io. Building a parallel surface is a fiction. The blueprint thesis is that we govern across the working tools, not replace them.
- **ALT-002** — *Sora-2 in v1 for video generation*: rejected. Preview, gated by Limited Access (verified empty SKU on current subscription), 1–5 min latency, 2-job concurrency cap, RAI surprises, force-upgradable preview lifecycle. Storyboard hand-off is agency-truthful and demo-safe.
- **ALT-003** — *Runway / Veo / Kling for video instead*: rejected for v1 same reason as Sora-2 (latency, RAI risk, mid-demo failure surface). Plus none are native to Foundry, weakening the all-Microsoft-substrate story.
- **ALT-004** — *Microsoft 365 Cowork integration in v1*: rejected. M365 Frontier preview adds a tenant-state dependency we can't control mid-demo. Voice intake → Control Plane via existing voice-screener mechanic lands the same beat with zero Frontier risk. Cowork narrated as v2.
- **ALT-005** — *Build the concept-card / storyboard surface in Figma, with our Control Plane just driving it*: rejected. The storyboard explicitly positions the Control Plane as the hero ("split screen: storyboard on left, video on right, control plane behind"). Pushing the canvas to Figma weakens the supervisor narrative for the IBB audience. Figma is the federation endpoint, not the canvas.
- **ALT-006** — *Adobe-first integration (Frame.io, Workfront, Firefly)*: rejected for v1, narrated only. More agency-truthful but less Microsoft-optical for IBB. Figma is the agency-truthful concession; Adobe MCPs are v2 follow-ons.
- **ALT-007** — *Use Microsoft Designer (the M365 image-gen surface) instead of `gpt-image-2` direct*: rejected. Designer is built on `gpt-image-2`/`gpt-image-1.5` anyway — same model under the hood, less control over prompt + output blob lifecycle, harder to attribute cost. Direct Foundry call is simpler and cheaper.
- **ALT-008** — *Don't reuse the voice-screener mechanic; build new multi-party WebRTC stack*: rejected. POC2 voice-screener is single-candidate but the underlying mechanic (magic link, ephemeral key, transcript → external event) is the same. Multi-party means up to ~3 participants on one WebRTC call — gpt-realtime-1.5 already diarises. Swap the rubric, not the plumbing.
- **ALT-009** — *Skip brand-RAG, fake brand-fit scores*: rejected. The brand-RAG corpus is the agency-credibility moment — proves the AI knows what's *on-brand*, not just that it can render images. Without it the demo reads as "ChatGPT image generator with a UI". With it the demo reads as "your brand library, your distinctiveness benchmarks, your past campaign learnings — all of it now operating on every concept."

## 4. Dependencies

- **DEP-001**: Foundry resource with `gpt-image-2` deployment (region: any global standard). Likely existing `arzie-mm4okigm-canadacentral` works; verify in TASK-015.
- **DEP-002**: Figma personal access token; one demo team + one demo file with API access enabled. Free plan sufficient.
- **DEP-003**: Existing substrate features from prior plans:
  - [feature-fleet-domain-substrate-1.md](archive/feature-fleet-domain-substrate-1.md) Phases 1–6 (registry, generalised payload, FM domain awareness, persona escalate verdict).
  - [feature-foundry-credibility-friday-1.md](feature-foundry-credibility-friday-1.md) Phase 1 (Foundry tracing live), Phase 2 (real cost from real tokens), Phase 4 (audit append-blob).
  - Wave-2 fleet domains (PO / contract-review / DPIA / treasury-fx) committed to `origin/main` before worktree branches.
- **DEP-004**: GHCP SDK Python (already a dep) for skill execution; `agent-framework` for graph wiring (already a dep); `azure-storage-blob` for image staging (already transitively); `chromadb` for brand-RAG (verify in TASK-011, may need explicit add to `pyproject.toml`).

## 5. Files

- `api/shared/domains.py` — extend `DOMAINS` registry (TASK-001)
- `api/shared/types.py` — widen `Workflow.type` literal (TASK-002)
- `api/functions/workflows/creative_campaign.py` — new orchestrator (TASK-003)
- `api/functions/graphs/{creative_brief,concept_fanout,storyboard_render,package_handoff}.py` — new graphs (TASK-004)
- `api/server/services/simulator_orchestrator.py` — `spawn_creative_campaign_workflow` + ramp loop wire-up (TASK-006)
- `api/server/mcp_tools/{image_gen,brand_rag,figma,recall_similar_campaigns}.py` — four new MCP servers (TASK-011, TASK-016, TASK-026, TASK-034)
- `api/server/skills/{creative-briefer,brief-synthesiser,concept-curator,brand-guardian,storyboard-curator}/SKILL.md` — five new skill files (TASK-012, TASK-021, TASK-023, TASK-024, TASK-025)
- `api/server/personae/creative-director/SKILL.md` — new persona (TASK-005)
- `api/server/eval/evaluator_set.py` + `custom_evaluators.py` — per-agent evaluators + `BrandFitAccuracy`, `BriefFieldExtractionAccuracy`, `RouteDistinctivenessScore`, `StoryboardCoherenceScore` (TASK-013, TASK-027)
- `api/server/routes/figma.py` — webhook receiver (TASK-036, optional)
- `data/synthetic/creative-campaign/{briefs.json,brief.schema.json,labels.csv}` — seed corpus (TASK-007, TASK-022)
- `data/synthetic/creative-campaign/cached/<brief-id>/...` — canned image fixtures (TASK-008)
- `data/synthetic/creative-campaign/brand-corpus/<brand>/...` — 40-doc brand RAG corpus (TASK-010)
- `data/synthetic/creative-campaign/past-campaigns/...` — 10 past-campaign JSON fixtures (TASK-026)
- `web/client/components/AgentDrivenComponent.tsx` — extend with 3 new spec kinds (TASK-029)
- `web/client/components/apex/CreativeCampaignArtefacts.tsx` — new component (TASK-030)
- `web/client/routes/Fleet.tsx` — add filter chip (TASK-031)
- `docs/poc3-DEMO.md` — runbook (TASK-038)
- `README.md`, `docs/blueprint.md` — eight → nine domain table updates (TASK-040)

## 6. Testing

- **TEST-001**: `tests/api/shared/test_domains_registry.py` extended — assert `creative-campaign` entry exists, has 6 phases, 4 HITL gates, `creative-director` persona declared.
- **TEST-002**: `tests/api/server/test_creative_campaign_workflow.py` (new) — spawn one stub workflow, assert it completes through 6 phases with auto-closed HITL gates; assert `Workflow.payload` contains `briefJson`, `conceptRoutes`, `storyboardFrames`, `figmaFileUrl` after Phase 6.
- **TEST-003**: `tests/api/server/test_image_gen_mcp.py` (new) — record-replay tests against canned `gpt-image-2` responses (use `respx`). Assert cost ledger entries created with non-zero USD; assert content_filter exception path raises `ContentSafetyRejection`.
- **TEST-004**: `tests/api/server/test_brand_rag_mcp.py` (new) — assert `query_brand_corpus("Solene", "visual codes", k=5)` returns 5 chunks from the Solene corpus only.
- **TEST-005**: `tests/api/server/test_brand_guardian_skill.py` (new) — assert on-brand fixture scores `brand_fit > 0.8`; off-brand fixture scores `brand_fit < 0.5` and produces non-empty `violations`.
- **TEST-006**: `tests/api/server/test_persona_creative_director.py` (new) — test the `decision_policy` block: `brand_fit=0.9 distinctiveness=0.8` → approve; `content_safety_flag=true` → escalate; ambiguous → leave open.
- **TEST-007**: `tests/api/server/test_figma_push.py` (new) — record-replay against canned Figma REST responses; assert `push_asset_bundle` returns a URL and posts the traceability comment.
- **TEST-008**: `tests/e2e/test_creative_campaign_e2e.py` (Playwright, optional) — spawn workflow via simulator, click "Creative Campaigns" filter chip, assert workflow appears, click in, assert concept tiles render.
- **TEST-009**: Foundry Tracing manual check — after one live demo run with `CREATIVE_REAL_FOUNDRY=1`, click the workflow in https://ai.azure.com Tracing tab, assert all 5 new skill spans visible with token counts and `zava.skill` labels; assert `tool.server.image_gen` and `tool.server.brand_rag` spans present.

## 7. Risks & Assumptions

- **RISK-001**: `gpt-image-2` RAI rejects the demo prompt mid-recording. Mitigation: pre-bake all demo prompts offline, verify each renders RAI-clean before the demo, keep canned fixtures as fallback. The sustainable luxury fragrance subject is product/landscape-only so the surface area is small.
- **RISK-002**: `gpt-image-2` quality variability across 12 concept stills + 6 storyboard frames could undermine the "this is real creative" beat. Mitigation: pre-render 3 well-curated demo briefs offline; live demo references one of them as the happy-path. The substrate runs whether the artwork is brilliant or workmanlike — we're demonstrating governance, not virtuosity.
- **RISK-003**: Figma push API surface (image upload + frame creation) may rate-limit or fail mid-demo. Mitigation: Phase 6 is the last phase; if it fails, demo still tells a complete story (stop at "asset bundle ready, push to Figma"). The Figma push is narrated as "and the bundle goes to your design team" — even a successful POST without immediate UI verification is enough.
- **RISK-004**: Brand-RAG corpus quality matters — if `brand-guardian` produces nonsense scores, the agency-credibility beat collapses. Mitigation: TASK-010 includes hand-review of every doc before commit; TEST-005 asserts known on-brand vs off-brand fixtures score correctly.
- **RISK-005**: Voice intake multi-party (3 humans on one WebRTC call) is harder than POC2 single-candidate. gpt-realtime-1.5 diarises but the rubric needs to handle turn-taking. Mitigation: Phase 1 stubs the voice phase entirely; Phase 4 lights it up; demo can fall back to a 2-person call (CD + AI) if 3-person turn-taking is fragile.
- **RISK-006**: The agency-truthful framing (we don't replace Figma) might confuse an IBB audience expecting a Microsoft-only story. Mitigation: open the demo with the blueprint thesis ("we govern across the stack, supervisor watches 300 campaigns concurrently") not the storyboard thesis ("we generated a video"). Lead with substrate, not artwork. Figma surface is one slide, narrated as "the agency keeps Figma; we add the layer above".
- **RISK-007**: Adobe absence is conspicuous to anyone who knows the agency stack. Mitigation: ALT-006 — narrate Frame.io / Workfront / Firefly as v2 follow-ons with same MCP shape. One sentence, then move on.
- **RISK-008**: Wave-2 hand-graduated fleet domains uncommitted on `main` at plan-write time. Mitigation: worktree branches off `origin/main` *after* wave-2 is committed and pushed (DEP-003). Don't start Phase 1 until wave-2 is on `origin/main`.
- **ASSUMPTION-001**: Demo brief subject is sustainable luxury fragrance launch — product-only, RAI-clean, agency-credible. Locked.
- **ASSUMPTION-002**: `gpt-image-2` deployment exists or is trivially deployable on the existing Foundry resource. Verified in TASK-015.
- **ASSUMPTION-003**: Figma free plan + personal access token sufficient for the demo file.
- **ASSUMPTION-004**: ~3 weeks of focused single-operator work post the 2026-05-08 Friday demo. Phase 1 first (config-only, low-risk, fully canned); Phase 7 is recording-only and last. Phases 2–6 can interleave.
- **ASSUMPTION-005**: Cost is negligible — `gpt-image-2` at ~$0.04/image × 18 images per workflow = ~$0.72/workflow; 100 dev runs ≈ $72; full 3-week build ≈ $150 max. Out-of-pocket negligible. No Foundry PTU, no Figma paid plan, no Cowork licensing needed for v1.

## 8. Related Specifications / Further Reading

- [docs/AI-Agency-Demo-Storyboard.pptx](../docs/AI-Agency-Demo-Storyboard.pptx) — original storyboard; this plan re-scopes Stages 6 (video gen → storyboard hand-off), 7 (exception → reuses existing pipeline), and surfaces (Cowork → voice-to-Control-Plane direct, Figma → federation push not canvas)
- [docs/blueprint.md](../docs/blueprint.md) — the press / manuscript thesis this POC operationalises in a creative domain
- [docs/poc1-brief.md](../docs/poc1-brief.md) — POC1 (finance) brief shape; per-section anchors borrowed
- [docs/poc2-status.md](../docs/poc2-status.md) — POC2 (hiring) status format mirrored here; voice-screener mechanic reused verbatim
- [plan/archive/feature-fleet-domain-substrate-1.md](archive/feature-fleet-domain-substrate-1.md) — substrate parity work this plan inherits (registry, payload, FM domain awareness, persona escalate verdict)
- [plan/feature-foundry-credibility-friday-1.md](feature-foundry-credibility-friday-1.md) — Foundry tracing + real cost + audit-blob work this plan inherits
- [Figma REST API](https://developers.figma.com/docs/rest-api/) — comments, webhooks, image upload endpoints used in Phase 6
- [Foundry image generation models](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure#image-generation-models) — `gpt-image-2` GA, `gpt-image-1.5`, `gpt-image-1`
- [Foundry video generation (Sora-2 — out of v1 scope)](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/video-generation) — narrated as v2 plug-in
- [Microsoft 365 Cowork (out of v1 scope)](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/) — narrated as v2 federation surface
