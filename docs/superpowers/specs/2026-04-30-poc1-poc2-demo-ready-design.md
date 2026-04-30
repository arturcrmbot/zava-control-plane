# Master spec — POC1 + POC2 demo-ready by end of next week

**Date:** 2026-04-30
**Target:** Friday 2026-05-08 (with weekend buffer)
**Audience:** WPP evaluators, live, ~60+ minutes, open format

## 1. Goal + constraints

Both POC1 (Finance Expense Compliance) and POC2 (HR Talent Lifecycle) must be demonstrable end-to-end against WPP evaluators next Friday. Open format — we drive — so the through-line is ours to choose, but every published capability claim must back to something live (or knowingly narrated) on screen.

Constraints:

- **No full Azure deployment of the app itself** — Functions / FastAPI / mocks / UI keep running on a laptop. Saves the 2-3 days that "lift everything to ACA" would cost.
- **Azure *services* are fair game** — ACS, ACS Email, Storage, Foundry, Document Intelligence (already wired). The user has authorised standing up new resources where needed; Microsoft tenant.
- **HeyGen API key** — user provides.
- **Voice s2s accelerator** — exists already on the user's laptop, will be reused as a black box in the candidate portal's `/screen` route. Path/contract TBD when the per-feature spec is drafted.
- **Demo timing:** ~60+ minutes live, open format, no WPP-named must-haves.

## 2. Scope

### In scope (build by end of next week)

| # | Item | Where it lives | Spec |
|---|---|---|---|
| 1 | **AC #4 corpus run** | POC1 — close the last yellow on the 13 ACs | Existing runbook ([poc1-accuracy-runbook.md](../../poc1-accuracy-runbook.md)); no new spec |
| 2 | **AG-UI render** | POC2 §4.21 — wire `AgentDrivenComponent` into `WorkflowDetail` | Short spec — `2026-04-30-ag-ui-render-design.md` |
| 3 | **Real HeyGen avatar** | Replace `heygen-mcp` canned mp4 with real API behind same MCP-tool surface | `2026-04-30-heygen-real-design.md` |
| 4 | **Real voice via accelerator** | Replace canned ACS transcript with the user's s2s accelerator running browser-side WebRTC, transcript callback into Phase 6 | `2026-04-30-voice-real-design.md` |
| 5 | **Candidate portal** | New `web/portal/` Vite app — three routes: `/apply`, `/portal?token=xxx`, `/screen?token=xxx` | `2026-04-30-candidate-portal-design.md` |

### Out of scope (deferred to engagement POC, narrated against architecture)

- Full Azure deployment of the app.
- §4.9 — 50→200 CV corpus expansion (only if eval variance demands it).
- §4.12 — APIOps governance gate (engagement POC, narrated).
- §4.15 — Entra Agent ID demonstration for `hiring-agent@wpp` (engagement POC; lab uses `gh` token + DefaultAzureCredential where Entra-ID auth happens to land — `ocr_extract` already does).
- §4.20 — drift-detection live beat (narrated against Fleet Manager skill paragraph).
- §4.22 — APIM jurisdiction-aware routing (engagement POC).

These remain in [SCOPE-DELTA.md](../../SCOPE-DELTA.md) as the engagement-POC commitments.

## 3. Architecture delta

What changes vs `main` as of 2026-04-30:

```
+ web/portal/                                    # NEW separate Vite app
+ web/portal/src/routes/Apply.tsx                # public job-board form + CV upload
+ web/portal/src/routes/Portal.tsx               # status + RSVP + offer accept/decline + onboarding video
+ web/portal/src/routes/Screen.tsx               # full-screen voice call (accelerator)

+ api/server/routes/portal.py                    # NEW — public + magic-link routes
+ api/server/routes/portal_voice.py              # NEW — accelerator transcript callback
+ api/server/services/magic_link.py              # NEW — token issue/verify/consume
+ api/server/services/email_send.py              # NEW — ACS Email send (real)
+ api/server/services/blob_store.py              # NEW — CV upload + video storage
~ api/server/mcp_tools/ocr_extract.py            # unchanged — already real DI
~ api/server/mcp_tools/heygen_render.py          # MOD — swap canned to real HeyGen API + Blob
~ api/server/skills/onboarding-buddy/SKILL.md    # unchanged contract
~ api/server/skills/voice-screener/SKILL.md      # unchanged contract — accelerator just changes the dial transport
~ api/functions/graphs/voice.py                  # MOD — wait for portal callback instead of acs-mcp canned
~ api/functions/graphs/triage.py                 # MOD — emit `cv_crystalliser.component_spec` for AG-UI

~ web/client/routes/WorkflowDetail.tsx           # MOD — render AgentDrivenComponent from triage output
~ web/client/components/apex/                    # admin "candidates / magic-link" panel for demo fallback

+ infra/                                         # NEW — bicep / scripts to stand up Azure resources
+ infra/main.bicep                               # ACS, ACS Email, Storage, Foundry project, judge model
```

The **MCP-contract-as-seam** principle holds: `heygen_render` keeps its Pydantic shape; the orchestration graphs keep their schemas; only the implementations behind the MCP tools and the new portal surface are net-new.

## 4. Candidate portal

### Routes

| Route | Purpose | Auth |
|---|---|---|
| `/apply` | Public form: role dropdown (lists open reqs), CV upload (PDF), name + email | none — public |
| `/portal?token=xxx` | Phase-aware status: progress ribbon, current CTA (RSVP / accept offer), embedded HeyGen video when phase=Onboarding | magic-link token |
| `/screen?token=xxx` | Full-screen voice call (accelerator UI), with phase context | magic-link token |

### Apply flow

```
candidate hits /apply
  POST /api/portal/apply { role_id, name, email, cv_file (multipart PDF) }
  → backend: blob_store.put(cv) → cv_url
  → backend: create candidate record { id, name, email, cv_url, role_id }
  → backend: attach candidate to the role_id's existing HiringOrchestrator workflow
  → backend: fire `candidate.applied` event → Triage (Phase 4) runs cv-crystalliser on cv_url
  → triage emits shortlist_score + component_spec (for AG-UI)
  → if score >= threshold:
      magic_link.issue(candidate_id, scope=screen)
      email_send.magic_link(email, link)
      return 202 { status: "submitted", candidate_id }
  → else:
      return 200 { status: "below_threshold" }
```

For demo simplicity, the role dropdown is hard-coded to a small set of demo reqs (Senior Data Engineer USA, Senior Data Engineer DE, Creative Director). The hiring manager flow that creates reqs stays out-of-scope; reqs are seeded via a fixture.

### Magic-link mechanics

- 32-char URL-safe token, 7-day expiry, single-use semantics for state-changing endpoints (offer accept), repeatable read for status.
- Stored in SQLite under `data/.portal/links.sqlite` (or in workflow state — pick one in per-feature spec).
- `magic_link.consume(token, scope)` validates expiry, scope, and single-use rule.
- **Demo redundancy:** Control Plane gets a *Candidates* panel showing all live magic-link tokens, copy-to-clipboard, so the demoer never needs to dig in an inbox.

### Email send

- Real ACS Email send for production-quality demo footprint.
- Templates: `magic_link_issued`, `interview_scheduled`, `offer_extended` — kept simple HTML.
- Fallback: SMTP-disabled environment renders the email body to a local file under `data/.portal/outbox/` AND surfaces in the admin Candidates panel.

### Portal status page

`/portal?token=xxx` morphs by current workflow phase:

| Phase | Surface |
|---|---|
| 4 Triage | "Application received — we'll be in touch" (token typically not issued yet, but page renders gracefully if it is) |
| 5 Screening | "Shortlisted — book your screening call" → button to `/screen?token=xxx` |
| 6 Voice | "Screening complete — see you for the interview" |
| 7 Interview | "Interview booked for {date}" + RSVP toggle |
| 8 Compliance | "Reviewing eligibility" |
| 9 Offer | Offer letter PDF preview + Accept / Decline buttons |
| 10 Onboarding | HeyGen welcome video player + onboarding checklist |

## 5. Voice integration (accelerator-as-black-box)

The user has an existing speech-to-speech accelerator running on their laptop. We treat it as a black box for the master spec; the per-feature voice spec drills in once the accelerator path is shared.

### Integration shape

```
candidate clicks "Start screening call" on /portal
  → navigates to /screen?token=xxx
  → page mounts the accelerator's WebRTC/voice component
  → component handles audio capture, dial setup (ACS or whatever the accelerator uses), GPT-Realtime
  → on call end: accelerator POSTs transcript + score to /api/portal/voice/{candidate_id}/transcript
  → backend: validates magic link, persists transcript on workflow
  → backend: raises `voice_complete` external event on Durable orchestration
  → Phase 6 voice graph resumes, applies score against rubric, emits verdict
  → portal page redirects to /portal?token=xxx (status updated)
```

The existing `acs-mcp` mock stays as a non-portal fallback (e.g., dev-loop scenarios that don't need the portal).

### Open questions for the per-feature spec

- Where does the accelerator code live; how do we mount it inside the portal Vite app (npm package? git submodule? copied source?)
- Does the accelerator need its own ACS resource we provision, or does it manage its own infra?
- Transcript schema — what fields do we get back; do they map cleanly to `transcript_score` rubric?
- Failure modes — accelerator unreachable, mid-call drop, no audio captured.

## 6. HeyGen integration (real)

`mcp_tools/heygen_render.py` swaps from canned mp4 to real HeyGen API behind the **same MCP tool contract**. The `onboarding-buddy` skill is unchanged.

### Render lifecycle

```
Phase 10 Onboarding entry
  → skill calls heygen_render(script, avatar_id)
  → tool: cache lookup by sha256(script) + avatar_id (Blob-backed)
       hit  → return cached blob URL
       miss →
         POST HeyGen render API { script, avatar_id }
         poll render-job status until done (or callback if HeyGen supports it)
         download mp4
         upload to Azure Blob (container: heygen-renders, name: {sha}.mp4)
         persist cache entry
         return blob SAS URL
  → orchestration stores URL on workflow.onboarding.video_url
  → portal /portal?token=xxx loads the URL when phase=Onboarding
```

### Open questions for the per-feature spec

- HeyGen render time — sync poll vs async webhook?
- Pre-render at workflow start (warm cache) vs on-demand at Phase 10 (cold)? Cold is simpler; warm is faster on demo day.
- Avatar id — one default for demo (`welcome-default`) or per-jurisdiction/role?
- SAS URL expiry — blob lifetime + revocation story.

## 7. POC1 close-out (AC #4 corpus run)

No new spec — runbook exists at [poc1-accuracy-runbook.md](../../poc1-accuracy-runbook.md). What's left:

1. Provision Azure AI Foundry project + judge-model deployment (Azure OpenAI gpt-4.1 or equivalent).
2. Set env vars: `AZURE_FOUNDRY_PROJECT_ENDPOINT`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`.
3. Pre-classify the 300-claim corpus offline (existing rag-classifier path).
4. `POST /api/accuracy/run { sample_size: 300 }` — runs `evaluate()` against the JSONL, results land in `data/.eval/store.sqlite` and the Foundry portal.
5. Inspect per-evaluator scores; iterate prompt + retrieval per the runbook if accuracy <95%.
6. Capture final result in `docs/poc1-accuracy-baseline.json`.

Buffer ~1 day for one prompt iteration.

## 8. AG-UI render (POC2 §4.21)

The `AgentDrivenComponent` primitive is built but not rendered anywhere. Half-day wire-up:

- Triage Phase 4 emits `cv_crystalliser.component_spec` (a list of `AgentComponentSpec` entries) into workflow state — addition to existing cv-crystalliser skill output.
- `WorkflowDetail.tsx` reads `workflow.agent_outputs.cv_crystalliser.component_spec` and renders a `<section>` containing one `<AgentDrivenComponent spec={...} />` per entry.
- Different roles produce different spec kinds:
  - **Senior Data Engineer** → `fact_grid` (employer/title/tenure) + `skill_chips`
  - **Creative Director** → `fact_grid` + `portfolio_gallery` (image URLs from CV — synthetic)
  - **Default** → `fact_grid` only
- Spec kind selection: cv-crystalliser SKILL.md gets a short "Component spec" section instructing the model which spec kind to emit per role.

## 9. Azure resources to provision

| Resource | Purpose | Notes |
|---|---|---|
| Azure Communication Services | Voice transport for the accelerator (if needed beyond what the accelerator already uses) | TBD per voice spec |
| ACS Email | Magic-link emails | Cheap; one Email Communication Service + a verified domain |
| Azure Storage account | CV uploads + HeyGen rendered mp4s + magic-link sqlite (optional) | Single account, multiple containers |
| Azure AI Foundry project + judge-model deployment | AC #4 corpus run + per-agent online evals | One project; Azure OpenAI gpt-4.1 deployment behind it |
| Azure Document Intelligence | OCR (already wired via `ocr_extract`) | Existing — `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` |

Cost: low. One-shot bicep under `infra/main.bicep` provisions all of the above; running cost dominated by Foundry + DI per-call.

## 10. Risks + cuts

### Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Voice accelerator integration takes longer than 2-3 days | HIGH | Examine accelerator early; spec subagent calls out concrete contract; fall back to canned transcript if hard-blocked |
| HeyGen render time too long for demo | MED | Pre-render the demo's expected videos at workflow start; cache aggressively |
| Candidate portal scope creep | MED | Stick to three routes; defer chat surface entirely |
| Foundry corpus run needs >1 prompt iteration | MED | Buffer ~1 day, iterate as runbook prescribes |
| AG-UI render reveals data-shape problems in cv-crystalliser output | LOW | Half-day wire-up; trivially restorable |

### Cut precedence (least painful first, if scope must shed):

1. **AG-UI render** — narrate §4.21 against the existing `AgentDrivenComponent.tsx` primitive file in code review
2. **POC1 corpus iterations beyond first pass** — accept first-pass accuracy if it lands ≥90%; iterate post-demo
3. **HeyGen real** — fall back to canned mp4 (existing mock)
4. **Portal `/screen` route** — drop in-browser voice; voice falls back to canned `acs-mcp` mock
5. **Voice real** (last cut — biggest demo loss) — keep canned transcript mock; narrate the s2s accelerator against the architecture diagram

## 11. Per-feature spec index

After this master spec is approved, the following per-feature specs are drafted (subagents in parallel where flagged):

- **`2026-04-30-candidate-portal-design.md`** — drafted by me. Drills routes, magic-link state machine, apply backend route, status-page phase morphology, ACS Email integration.
- **`2026-04-30-voice-real-design.md`** — drafted by subagent, briefed with the accelerator path/contract once the user shares it. Drills the accelerator's API surface, WebRTC mounting in portal, transcript callback schema.
- **`2026-04-30-heygen-real-design.md`** — drafted by subagent. Drills HeyGen render API, polling vs webhook, Blob upload, cache schema.
- **`2026-04-30-ag-ui-render-design.md`** — drafted by me, short. Spec-kind selection in cv-crystalliser, wire-up in `WorkflowDetail.tsx`.
- **POC1 corpus run** — uses existing [poc1-accuracy-runbook.md](../../poc1-accuracy-runbook.md); no new spec.

## 12. Implementation sequencing (preview)

After the per-feature specs are approved, the implementation plans drive five parallel streams plus an integration tail:

```
Mon-Wed (3 streams running in parallel)
  Stream 1: candidate portal (routes, apply backend, magic link, email)
  Stream 2: voice real (accelerator integration, /screen route, transcript callback)
  Stream 3: heygen real (MCP tool swap, blob upload, cache)
  Stream 4: ag-ui render (cv-crystalliser output + WorkflowDetail wire-up)
  Stream 5: POC1 corpus run (Foundry provisioning, run, iterate)

Thu: integration — full hire walk-through with all five streams converged

Fri: dry run + screenshots + tag v1.0-poc2-frontier
```

Streams 1-3 are large; 4-5 are tactical.

---

## Approval gate

This is the **master spec**. Per-feature specs are derivative and drafted next. Before drafting per-feature specs, the user reviews this doc and approves (or requests changes).
