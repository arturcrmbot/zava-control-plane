# POC2 Frontier Demo — Runbook

30-minute walkthrough across all 22 capabilities from [spec.md](../spec.md)
§4.1–4.22, applied to the POC2 HR Talent Lifecycle. Every beat below is
either **live** (runs against the local stack) or **narrated** (described
against the cloud-target architecture in
[poc2-architecture.svg](poc2-architecture.svg)).

This is the sister doc to [poc1-DEMO.md](poc1-DEMO.md). The POC1 demo runs
verbatim — POC2 layers on the hiring orchestration, not replaces it.

---

## 0. Pre-flight (5 min before demo start)

```bash
# Terminal 1 — Functions host (Durable + activities)
func start

# Terminal 2 — FastAPI control plane
uvicorn api.server.main:app --reload --port 8000

# Terminal 3 — POC2 mocks (ports 4201–4207)
npm run dev:mcp:poc2

# Terminal 4 — POC1 mocks (ports 4101–4103, optional but keeps POC1 alive)
npm run dev:mcp

# Terminal 5 — admin UI (Control Plane)
npm run dev:client

# Terminal 6 — candidate portal Vite app
npm run dev:portal
```

The voice screen runs natively inside the portal — no separate accelerator
process. `/screen?token=xxx` opens a real WebRTC peer connection to Azure
GPT-Realtime through `/api/portal/voice/{session,rtc}` (the FastAPI
control plane proxies the SDP exchange). Set `VOICE_TRANSPORT=canned`
(or `VITE_VOICE_TRANSPORT=canned` for the portal-side branch) to short-circuit
to a one-button canned-transcript path if mic / Azure access isn't available.

Open http://localhost:5173. The Fleet Dashboard should show zero workflows.
Generate the synthetic corpus once if it doesn't exist:

```bash
python data/synthetic/hiring/generate_hiring.py
```

Pre-render the demo onboarding videos so Phase 10 returns instantly from
the Azure Blob cache rather than re-rendering on the live demo run
(2-3 min wall-clock per render):

```bash
# Requires AZURE_SPEECH_REGION + AZURE_STORAGE_CONNECTION_STRING in env.
uv run python scripts/prewarm_avatar.py
```

---

## 1. The 22-capability walkthrough

Below: each row is one demo beat. Live beats name the simulator command and
the surface to look at. Narrated beats reference the architecture diagram
and the SKILL.md / MCP-tool that *would* run the capability live.

| § | Capability | Mode | Beat |
|---|---|---|---|
| 4.1 | Multi-agent orchestration | live | `POST /api/simulator/hire {}` — open the resulting `HIRE-NNNN` and watch the 10-phase ribbon advance from Budget → Onboarding. |
| 4.2 | System integration & auth | live | Inspect the spans on Phase 3 (Sourcing): `linkedin_search` + `greenhouse_post` fire in parallel against `mocks/linkedin-mcp` + `mocks/greenhouse-mcp`. |
| 4.3 | HITL + bulk action | live | Phase 1 (Budget) suspends; the Adaptive Card payload is in the orchestration history. POST the Finance BP webhook to unblock: `POST /api/webhooks/finance-bp/HIRE-NNNN?decision=approve`. Bulk = the existing BulkHitlModal works on hiring workflows verbatim. |
| 4.4 | Exception handling & self-healing | live | Inject `scenario="rtw-unknown"` and watch Phase 8 raise `right_to_work_unverified` to the exception queue; resolve it via the queue. |
| 4.5 | Voice + avatar | live | Phase 6 issues a `screen`-scope magic link, emails the candidate, and suspends on the `voice_complete` external event raced against a 24h timer. The candidate opens `/screen?token=xxx` which iframes the firstcentral voice-direct accelerator (browser WebRTC + GPT-Realtime); on call-end the transcript posts to `/api/portal/voice/{cid}/transcript` and the orchestration resumes. `VITE_VOICE_TRANSPORT=canned` falls back to the existing `acs-mcp` canned transcript via a one-button surface for demo robustness. Phase 10 calls `avatar_render` against Azure AI Speech batch synthesis (cached mp4 SAS URL surfaced on the candidate portal). `AVATAR_TRANSPORT=mock` falls back to `mocks/heygen-mcp` for offline runs. Both surfaced in the Execution Timeline. |
| 4.6 | Multi-surface convergence | mixed | Live: Finance BP card webhook (Phase 1), ServiceNow IT-Ops webhook (Phase 10), Hiring Manager surface at `/hiring-manager/HIRE-NNNN`, Candidate at the A2A boundary `/api/a2a/inbound`. Narrated: Teams deep-link, real Outlook Adaptive Card. |
| 4.7 | Episodic memory | live | Open the workflow detail; the `recall_similar_hires` MCP tool surfaces past hires of the same `(role_family, jurisdiction)`. |
| 4.8 | Crystallisation pipeline | live | Phase 4 runs `cv-crystalliser` against the synthetic CV (PDF + LinkedIn JSON merge); inconsistencies surfaced in the workflow detail. |
| 4.9 | Synthetic CV gym | live | `data/synthetic/hiring/generate_hiring.py` produces 50 CVs across 5 roles × 2 jurisdictions; ground-truth labels in `labels.csv`. |
| 4.10 | Compliance + jurisdiction switch | live | Run two hires back-to-back: `candidate_id=C-SE-USA-00` (no BetrVG step) vs `C-SE-DE-00` (Phase 8 grows BetrVG §99 notification step). Same code path. |
| 4.11 | Tiered model usage | narrated | Phase 5 (auto-shortlister) uses gpt-4.1-mini (cheap screen); Phase 4 (cv-crystalliser, multimodal) uses gpt-4.1 frontier. Skill `model:` frontmatter drives the choice. |
| 4.12 | Skill library + APIOps gate | narrated | All 11 hiring SKILL.md files under `api/server/skills/`; cloud target publishes via API Center governance with a CI gate. |
| 4.13 | Hooks for non-revocable sends | live | Phase 9 (Offer) drafts the offer letter; the `graph_mail` send is gated by `onPreToolUse` hook. Phase 10 ServiceNow JML same pattern. Logged in the action ledger. |
| 4.15 | Entra Agent ID | narrated | `hiring-agent@wpp` is the workload identity in the cloud target. Local demo uses the gh CLI token. |
| 4.16 | Audit + reporting | live | Workflow detail → Audit tab. Same ledger as POC1, partition key extends to `(jurisdiction, hire_id)`. |
| 4.17 | Cost-per-hire | live | Fleet Manager rail: `report.cost_per_task` returns the per-hire average; `query_economics` aggregates over the hiring fleet. POC1's economics service is domain-neutral — the label rebinds to "per hire" automatically based on workflow type. |
| 4.18 | Process evolution | live | After 50+ "approved-with-RTW-unverified-overridden" decisions, Fleet Manager proposes auto-approving that path via `propose_skill_amp`; surfaces in the policy panel. |
| 4.19 | A2A boundary | live | `POST /api/a2a/inbound {workflow_id, from_pa, intent: "availability_propose", body: {...}}` — the message lands in the workflow ledger and the Execution Timeline shows the cross-boundary call. |
| 4.20 | Drift detection | live | Spot-check 10% of auto-shortlisted candidates: Fleet Manager skill emits `compose_exception` with severity `info` listing the spot-check diff. |
| 4.21 | AG-UI dynamic components | live | Workflow detail surfaces the Triage agent's emitted component spec — Senior Data Engineer gets `skill_chips` + `fact_grid`; Creative Director gets `portfolio_gallery`. Same surface, different layouts. |
| 4.22 | Region failover + jurisdiction routing | mixed | Live: `POST /api/simulator/region-failure` with 15 in-flight hires; the Functions host stop / restart replays from Durable state with no data loss. Narrated: APIM jurisdiction-aware routing config. |
| Bonus | Hiring evaluator coverage | live (2026-05-05) | Open `/evaluations` → *Hiring (POC2)* table. Three deterministic evaluators (`cv_field_extraction_accuracy`, `shortlist_decision_match`, `jurisdiction_routing_correctness`) join the `data/synthetic/hiring/labels.csv` ground truth; LLM-judges (`groundedness`, `relevance`, `coherence`) score `voice-screener` / `interview-recommender` / `offer-personaliser`. All seven hiring agents have evaluator coverage. |
| Bonus | Foundry Tracing tab — hiring spans | live (2026-05-05) | Open https://ai.azure.com → project `azureai_swedencentral_arzielinski` → *Tracing*. Filter by `cloud_RoleName == "control-plane-functions"` and 1h. The hiring orchestrator's `gen_ai.generate_content` spans appear with `gen_ai.agent.name=hiring-agent`, `wpp.skill=cv-crystalliser` / `auto-shortlister` / etc., token counts, response content, and `tool.server.*` children. Same App Insights resource the engagement POC will use; same OTEL semantic conventions Microsoft Agent Framework / Semantic Kernel / OpenAI Agents SDK / GHCP SDK all share. |
| Bonus | Real cost-per-hire | live (2026-05-05) | The `Cost` tile on Workflow detail now reads `modelCostUsd` derived from real `gen_ai.usage.*` span attributes × published Azure per-million-token rates ([`model_pricing.py`](../api/server/services/model_pricing.py)). No synthetic constants. Same number Foundry's monitoring dashboard shows. |

---

## 2. The "wow" beats (the 8-minute compressed version)

If time gets cut, lead with these:

1. **Multi-surface convergence** (§4.6) — one hire walks all five surfaces in
   12 minutes (compressed from the real 12 weeks).
2. **Jurisdiction switching live** (§4.10) — flip the country flag USA → DE
   on the next spawn; watch the workflow grow a Compliance step *without
   any code change*.
3. **A2A boundary** (§4.19) — POST to `/api/a2a/inbound` from a stand-in
   "candidate's PA"; the inbound message threads into the same
   orchestration without breaking identity.

---

## 3. Failure surfaces (when the demo flakes)

| Symptom | Cause | Fallback |
|---|---|---|
| `acs-mcp` 500 on dial | Mock not booted | Skip to recorded clip; restart `npm run dev:mcp:poc2`. |
| HeyGen avatar 404 | Render id collision | Switch to fallback `welcome-default`. |
| Avatar render fails / times out | Real Azure Speech API issue (region down, role missing, quota) | Set `AVATAR_TRANSPORT=mock`; the `mocks/heygen-mcp` canned mp4 plays instead. Pre-warmed cache (`scripts/prewarm_avatar.py`) means re-renders shouldn't fire during a live demo anyway. |
| Functions host won't replay after region-failure simulation | Azurite tablestore write race | Stop everything, `rm -rf azurite-data/`, restart. |
| BetrVG step doesn't fire on DE hire | Wrong `jurisdiction_target` on the synthetic CV | Pick a `C-*-DE-NN` candidate explicitly: `POST /api/simulator/hire {"candidate_id": "C-SE-DE-00"}`. |
| `/screen?token=xxx` fails to start the call | `AZURE_GPT_REALTIME_URL` / `WEBRTC_URL` not set, or `az login` token expired | Set `VITE_VOICE_TRANSPORT=canned` (rebuild portal or set in `.env`), reload `/screen?token=xxx` — single button replays the canned transcript via `/api/portal/voice/{cid}/canned` and the orchestration resumes through the same `voice_complete` callback. Long-term: confirm the realtime env vars are set + `az login` is fresh. |

---

## 4. What's left after the demo

POC2 starting tag for the demo is `v1.0-poc2-spine` (this branch). The
12-week sprint outlined in [poc2-status.md](poc2-status.md) §5 lands the
remaining per-track polish (real cloud ACS / HeyGen, real APIM jurisdiction
routing, full 200-CV corpus, Fabric IQ episodic memory).
