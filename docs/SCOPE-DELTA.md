# Scope Delta — local lab build vs engagement POC

Two different artefacts share the name "POC1" / "POC2" in our world. They
are not the same thing and conflating them creates a credibility risk if
WPP can't tell which one we mean.

| | Local lab build (this repo) | Engagement POC (the bid response) |
|---|---|---|
| Purpose | Derisk the architecture, prove the Control Plane experience, build a recordable shape-of-the-thing demo | Customer-facing 8-week (POC1) / 12-week (POC2) engagement starting at WPP kickoff |
| Where it runs | Single laptop, localhost only | Vendor-hosted Azure environment per WPP's RFP §9 |
| Audience | GBB internal + reviewers + technical evaluators | WPP evaluators + AI CoE + Finance / HR sponsors |
| Owner | This repo | A future engagement repo seeded from this code |
| Data | Synthetic fixtures committed to `data/synthetic/` (POC1 + POC2 + per-fleet-domain corpora) | WPP-supplied datasets (3,430 claims + ground-truth labels for POC1; HR sandbox + 200-CV synthetic gym for POC2) |
| Scope reach | **Eight live domains** on a single substrate — POC1 expense + POC2 hiring + six fleet-* domains graduated by `compose-domain` (v1 then v3) and brought to first-class FM parity | The bid commits to POC1 and POC2; the six fleet-* domains demonstrate the substrate's *composition* claim that adding domain N+1 is a config change, not an integration project |
| Status | Substrate-complete · 8 domains run unattended via the autonomous demo loop | Not started · begins at signed contract + kickoff |

The lab build proves the **shape**. The engagement POC proves the shape **at WPP scale, on Azure, with WPP data, in front of WPP evaluators**.

The lab build also carries a third claim the bid response does not need
to make verbatim: that the substrate is **composable**, not just
reusable — i.e. that the same Durable + MAF + GHCP + Fleet-Manager spine
hosts radically different business processes (expense compliance, talent
lifecycle, vendor KYC, IT access, performance review, contract renewal,
employee onboarding, travel pre-approval) without per-domain plumbing.
This is the conversation we want to have once the bid claims are
accepted.

---

## What's identical between the two

The platform layer is the load-bearing reuse. None of this changes when we move from laptop to engagement:

- Three-tier architecture: Fleet Manager (long-lived FastAPI session) / `<Domain>Orchestrator` (Durable Functions) / ephemeral agentic loops per phase
- Per-domain phase flow + the validator-as-guardrail edge pattern
- Skills with `allowed-tools` frontmatter; per-domain agent identity model (`finance-agent@wpp` for POC1, `hiring-agent@wpp` for POC2, `fleet-manager-agent` for the supervisor session)
- MCP tools with identical Pydantic schemas — **the MCP contract is the swap-in seam**
- React Control Plane UI + SSC Reviewer Queue + Candidate Portal
- OTEL emission path, audit ledger shape, bulk HITL pattern, hooks for non-revocable sends
- **The domain registry pattern** ([`api/shared/domains.py`](../api/shared/domains.py)) — every per-domain integration fact lives in one dataclass, every generic substrate layer (FM skill text, simulator spawners, resolve route, blueprint inventory, triage wake set) reads from it. Adding the ninth domain — engagement-POC or otherwise — is a registry entry plus a YAML brief through `compose-domain`, not a refactor.

Same code runs on the laptop and on Azure. Backend implementations differ; agent code, skill prompts, validator logic, registry shape, and the composition meta-skill are unchanged.

---

## POC1 — where the engagement POC differs from the lab build

| Capability | Lab build (this repo) | Engagement POC (proper) |
|---|---|---|
| **OCR / receipt extraction** | Real Azure Document Intelligence as of 2026-04-30 — `ocr_extract` MCP tool wraps the DI prebuilt-receipt / prebuilt-layout / prebuilt-invoice / prebuilt-idDocument / prebuilt-document models, sha256+model cache, Entra-ID auth (tenant policy disables key auth on Cognitive Services). `receipt-validator` and `cv-crystalliser` skills both call it as their first step. | Same `ocr_extract` MCP contract; engagement POC adds `agent_field_extractor` fallback for low-confidence cases. |
| **Policy retrieval** | In-process embedding index using `sentence-transformers` (`all-MiniLM-L6-v2`) over `data/synthetic/policy.md`. | Foundry IQ over the WPP-supplied T&E policy corpus. **Same `policy_search` MCP contract.** |
| **Employee history / breach data** | Reads `data/synthetic/employees.json` from disk. | Fabric IQ over WPP HR data. **Same `employee_history` MCP contract.** |
| **Precedents** | 53 hand-authored fixtures in `data/synthetic/precedents.json`; token-overlap retrieval. | WPP SSC reviewer decisions accumulating in Foundry IQ over the engagement window; same `precedents_search` contract. |
| **EMS connections** | Node + Express mocks (`workday-mcp` :4101, `concur-mcp` :4102, `maconomy-mcp` :4103) with synthetic claim data. | Workday SAML-Okta, SAP Concur OAuth 2.0, Deltek Maconomy REST — all via APIM AI Gateway with credentials in Key Vault. |
| **Workflow state** | In-process `StateStore` (lost on restart). | Cosmos DB, geo-replicated, with point-in-time restore. |
| **Durable runtime** | Azurite locally (10000-10002). | Azure Storage with geo-redundant durable hub. |
| **Authentication** | Single `gh auth token`; implicit operator identity. | Entra Agent ID for `finance-agent@wpp`; OBO for human-triggered actions; Conditional Access; phishing-resistant MFA on operators. |
| **Network posture** | Localhost only — no isolation. | Front Door → APIM (Private Endpoint) → backends on Private Endpoints; Azure Firewall egress allow-list; APIM the only public edge. |
| **Agent hosting** | GHCP SDK session against the public GitHub Copilot endpoint. | Foundry Hosted Agents (preview) or ACA fallback (GA), with Foundry Tracing. |
| **Audit retention** | In-process action ledger; cleared with `make reset`. | Log Analytics → Azure Storage immutable export, 7–12 year retention. |
| **Cost attribution** | OTEL spans local-only; cost numbers synthetic. | App Insights with real model-token cost per claim, per phase, per layer. |
| **Synthetic dataset** | 300 claims, 30 employees, 53 precedents, 1 policy doc, all committed to git. | WPP-supplied 3,430 claims with ground-truth R/A/G labels + real T&E policy + delegated authority matrix + real org chart. |
| **Accuracy gate** | Foundry-backed pipeline as of 2026-04-30: `evaluate()` batch over a pre-classified JSONL + online subscriber that scores every `agent.completed` event + 3 deterministic custom evaluators (`PolicyClauseCited`, `ToolCallValidity`, `GoldLabelMatch`) + per-agent LLM-judge set; sqlite store; UI reads `/api/evals/summary`. `/api/accuracy/run` returns 503 if Foundry isn't configured. Full 300-claim corpus run still pending. | Same Foundry `evaluate()` SDK; **≥95% on the WPP 3,430-line dataset — 40% of the POC1 score.** |
| **Region failover** | `simulate-region-failure` simulator command (kills the Functions host, restarts) — local proof of replay. | Real Azure region pair with Cosmos DB geo-replication; live failover demonstrated against 500 in-flight workflows. |
| **HITL surfaces** | Web UI + a `/api/simulator/justification` endpoint that fakes the employee reply. | Real Adaptive Card sent via Outlook through the recipient's M365 Personal Agent. |
| **60-minute Copilot Studio build** | Not in this repo. | Separate scripted demo: junior dev builds a new agent with 3 MCPs + 3 knowledge sources in under 30 minutes. |

### Lab build status against the 13 acceptance criteria

(Snapshot of where this repo is — see [poc1-status.md](poc1-status.md) for live state. Last refreshed 2026-05-04.)

- ✅ All 13 ACs demoable on the laptop. AC #1 fleet view · #2 exception-only · #3 bulk approval · #4 accuracy pipeline (Foundry-backed; rag-classifier prompt tuned 2026-05-01: 60% → 70% on 10-claim smoke, zero green→red false flags) · #5 receipt cross-validation (real DI) · #6 progressive enforcement · #7 autonomous learning · #8 SSC Reviewer queue · #9 multi-EMS Control Plane · #10 EMS extensibility narration · #11 region failure simulator · #12 immutable audit + reporting · #13 cost-per-task report

**AC #4 — explicitly punted to engagement-POC scope.** Running the full 300-claim synthetic-corpus accuracy gate is not a useful number — the real metric is ≥95% on WPP's 3,430-line dataset (40% of POC1 score per the brief). The pipeline + prompt are demonstrably working; we'll run the corpus gate when WPP supplies their data after engagement kickoff.

The engagement POC must hit all 13 live in front of WPP. The lab build is converging on demoable evidence for the platform claims; the engagement POC then exercises the same code against real systems and real data.

---

## Substrate-level work that landed since the bid was written

The bid response (§10.1, §11, §B.4, §B.5) describes the engagement POC1
+ POC2 deliverables. The lab build has gone further than the bid
commits to, in ways that **strengthen** the bid claims rather than
extend them:

- **Domain registry centralised.** Every per-domain fact (workflow_type,
  prefix, orchestrator name, HITL gate → persona / external_event
  mapping, operator surface, optional wake hints) lives in
  [`api/shared/domains.py`](../api/shared/domains.py). Adding a domain
  becomes a registry entry. Read by FM skill text, simulator spawners,
  resolve route, blueprint inventory, triage.
- **`Workflow.payload` generalised.** The per-domain field sprawl on
  `Workflow` (`claim`, `invoice`, `metadata`) is replaced with a single
  opaque `payload: dict`. POC1/POC2 reads keep working via back-compat
  properties; all eight domains upsert into `StateStore` and surface in
  `query_fleet`.
- **Generalised resolve route.** Operator clicks on the exception queue
  resolve the right Durable external event for any domain via a
  `pending_gates` cache populated on every `suspended` event, with the
  registry as cold-cache fallback. Zero per-domain branches.
- **Fleet Manager domain-aware.** The FM session's skill text is
  composed at boot from the static SKILL.md plus a templated
  *"Domains under supervision"* block built from the registry; per-domain
  wake hints (`vendor.kyc.high_risk`, `access.scope.privileged`,
  `travel.policy.exception`, etc.) extend the wake set without editing
  shared event types.
- **Per-domain seed corpora.** Six fleet-* domains carry
  `data/synthetic/<workflow_type>/*.json` (≥40 records each, scenario-
  tagged: `clean` / `policy-exception` / `privileged-broad` etc.). The
  autonomous ramp loop rotates through scenarios per domain.
- **Persona `escalate` verdict.** Persona `decision_policy` blocks now
  return one of three verdicts — `approve`, `reject`, `escalate`. The
  third leaves the Durable gate open and emits a
  `workflow.hitl.escalated` event tagged with the originating role,
  which the FM picks up via triage and composes into an enriched
  exception. Demonstrated in `vendor_kyc_finance_bp` (high-risk
  jurisdictions), `it_access_it_admin` (broad-scope role templates),
  `contract_finance_bp` (price jump >25%).
- **Six fleet-* domains in `main`.** `travel-preapproval`, `vendor-kyc`,
  `employee-onboarding`, `it-access-request`, `contract-renewal`,
  `perf-review` — graduated from YAML briefs by `compose-domain` v1
  then v3, and brought to substrate parity per
  [`plan/feature-fleet-domain-substrate-1.md`](../plan/feature-fleet-domain-substrate-1.md)
  (all six phases shipped). They run end-to-end on the autonomous loop,
  appear in `query_fleet`, are resolvable from the operator UI, and
  produce FM-escalated exception traffic.

Why this matters for the bid: every one of these is **a load-bearing
reuse** that survives the move to Azure. The bid doesn't have to claim
them, but they make the platform claim more credible if WPP technical
evaluators look closely at the code.

## Foundry credibility lift (2026-05-05)

A second batch of work landed the day before the Friday demo, narrowing
the lab-vs-engagement gap on three axes the bid lists explicitly. Full
plan: [`plan/feature-foundry-credibility-friday-1.md`](../plan/feature-foundry-credibility-friday-1.md).

| Axis | Before 2026-05-05 | After 2026-05-05 |
|---|---|---|
| **Foundry Tracing tab** | OTEL spans emitted with all the right `gen_ai.*` semantic conventions, but `APPLICATIONINSIGHTS_CONNECTION_STRING=` was empty in `.env`. Nothing left the laptop. | App Insights conn string wired into both processes (FastAPI + Functions). The Foundry portal's *Tracing* tab at https://ai.azure.com surfaces every `gen_ai.generate_content` span with `gen_ai.agent.name`, `gen_ai.request.model`, `wpp.skill`, `gen_ai.usage.input_tokens` / `output_tokens`, plus tool-call children. Same shape Microsoft Agent Framework / Semantic Kernel / OpenAI Agents SDK / GHCP SDK all share. The demo can switch tabs from the local UI to the Foundry portal and walk a live workflow. |
| **Cost-per-task (AC #13)** | Two hardcoded constants in `economics.py` (`MODEL_CALL_RATE = $0.02`, `COMPUTE_RATE_PER_SECOND = $0.0001`). Numbers were synthetic. | Cost derived from real `gen_ai.usage.*` span attributes × published Azure per-million-token rates ([`model_pricing.py`](../api/server/services/model_pricing.py); `gpt-4.1` $2/$8 per M, `gpt-4.1-mini` $0.40/$1.60, source URL + date in module docstring). The `costPerTaskUsd` on the Workflow detail tile is now Microsoft's number, derived from Microsoft's telemetry, against Microsoft's published pricing. |
| **Immutable audit (AC #12)** | `audit_logger.py` was `self._entries: list[dict] = []` — zero persistence. "Immutable audit + 7-12 year retention" was a narrated bid claim. | `audit_logger.log()` dual-writes to in-memory list + an Azure Storage append blob (one per `workflow_id`, container `audit-ledger` on `apexdemo62525`, version-level immutability enabled via `--enable-vlw`). Auth via `AzureCliCredential` against the existing tenant. The blob URL surfaces on the workflow detail response as `auditBlobUrl`. The bid claim is now literal on the lab side. |
| **POC2 evaluator coverage** | Only `rag-classifier` and `arbitration` (POC1) had per-agent evaluator sets. All seven hiring agents fell through to a generic `coherence/fluency/tool_call_validity/violence/hate_unfairness` default. | Three deterministic evaluators added to [`custom_evaluators.py`](../api/server/eval/custom_evaluators.py): `CVFieldExtractionAccuracy` (joins `cvs/*.json` ground truth), `ShortlistDecisionMatch`, `JurisdictionRoutingCorrectness`. Wired in `_PER_AGENT` for all 7 hiring agents (`cv-crystalliser`, `auto-shortlister`, `jurisdiction-router`, `betrvg-checker`, `voice-screener`, `interview-recommender`, `offer-personaliser`). LLM-judges (`groundedness`, `relevance`, `coherence`) added per-agent based on the agent's expected output shape. Evaluations UI splits into Finance / Hiring sections. |

**What this does NOT do** — still engagement-POC scope:
- Migrate GHCP SDK agents to Foundry-hosted `PromptAgentDefinition` agents.
- Register agents through APIM AI Gateway as Foundry custom agents.
- Light up the Foundry Control Plane *Operate* / per-agent *Monitor* tab + `EvaluationRule` continuous-eval rules (those bind to a `agent_name` registered with Foundry).
- Real Foundry IQ / Fabric IQ swap-ins for `policy_search` / `employee_history`.
- Real EMS connections, real Cosmos DB, real Entra Agent ID, real APIM private endpoints.

But the seam is now narrower than the bid suggested: in engagement scope the agents register via AI Gateway, which lights up the Operate tab — *same App Insights resource, same span shape, just a different agent registration mechanism*. The lab build is one preview-feature flip away from full Foundry surface coverage.

---

## POC2 — closing fast

POC2 in the lab landed on `main` 2026-04-30 — the spine merge brought the 10-phase `HiringOrchestrator`, ten hiring skills, seven MCP mocks (4201–4207), a 50-CV synthetic corpus across 5 roles × 2 jurisdictions, and Tracks B (multi-surface) / D (jurisdiction) / E (frontier: A2A inbound + episodic recall + AG-UI primitive) / F (POC1 reuse). See [poc2-status.md](poc2-status.md) §1 for the per-capability matrix — 17/22 ✅, 5/22 🟡, 0/22 ❌.

**As of 2026-04-30 evening (demo-ready additions):**

- ✅ Candidate portal `web/portal/` Vite app (styled hero / phase ribbon / per-phase CTAs): `/apply`, `/portal?token`, `/screen?token`, `/recruiter`
- ✅ Real Azure GPT-Realtime voice (native WebRTC in portal — no iframe)
- ✅ Real Azure AI Speech batch avatar synthesis (custom-subdomain endpoint, Entra-ID auth, per-role character/style)
- ✅ Real ACS Email send (Azure-managed domain, DKIM/DMARC/SPF verified)
- ✅ AG-UI scorecard rendering on `WorkflowDetail`
- ✅ Recruiter view moved out of admin Control Plane into the portal app (filterable magic-link table)

**Outstanding lab-build polish before `v1.0-poc2-frontier` tag (priority order):**

1. **One clean end-to-end stack boot through to onboarding-video render.** Avatar fixes are committed (V1/V2 in rag-classifier prompt; custom-subdomain endpoint; per-role character/style; mp4-download auth). Just needs a stable Functions-host startup to confirm `onboarding_video_url` lands on workflow metadata. **Operational, not feature work.** Use `scripts/run-func.bat` for the env-pinned boot.
2. **30-min demo dry run** with someone playing the WPP evaluator — walk all 22 capability beats per [poc2-DEMO.md](poc2-DEMO.md). Bug fixes captured as we go.
3. **Demo recording + screenshots** — final artefact for evaluator review (or live demo prep).

**Punted to engagement POC** (these were always engagement-POC scope per master spec; not lab-build blockers):

- AC #4 corpus-wide accuracy gate (≥95%) — runs on real WPP 3,430-claim dataset, not synthetic
- §4.9 200-CV expansion — only if eval variance demands; 50-CV gym is enough for the demo
- §4.12 APIOps governance gate — narrated against the architecture
- §4.15 Entra Agent ID for `hiring-agent@wpp` — narrated; lab uses `gh` CLI token (Entra-ID auth IS demonstrated by `ocr_extract` and `avatar_render` though)
- §4.20 drift-detection live beat — Fleet Manager skill paragraph + reuse `query_traces`; demo'd narratively
- §4.22 APIM jurisdiction-aware routing — narrated

Engagement-POC differences vs the lab build are the same shape as POC1:

- **Lab build (today):** mocked Greenhouse / LinkedIn / Workday-HR / Graph / ServiceNow / ACS / HeyGen — canned transcripts, mp4 stubs, synthetic CVs, signed-payload verification stubbed at the A2A boundary.
- **Engagement POC:** real ATS sandbox, real LinkedIn Recruiter API, real Microsoft Graph (Teams / Outlook / Calendar), real ServiceNow tenant, real ACS phone number, real HeyGen API key, real BetrVG corpus, real Foundry Guardrails for jurisdiction routing, APIM mTLS + signed JWT at the A2A boundary.

The same swap-in story applies — MCP contracts identical, backend implementations different.

---

## Why this distinction matters for the bid

The bid response sections (§10.1, §11, §B.4, §B.5) describe **the engagement POC**, not the lab build. Foundry IQ, Fabric IQ, Document Intelligence, Entra Agent ID, real EMS connections — those are commitments for the engagement, grounded by a lab build that has already proven the architecture at the laptop scale.

When recording / demoing for WPP evaluation:

- **If we record from the lab build**, frame it as *"the architecture proven on a laptop; same code runs on Azure; here's the swap-in seam"*. Honest, derisks the technical claim, but is not the engagement POC.
- **If we record from the engagement POC**, that lands after kickoff with WPP's data and sandbox credentials. Higher fidelity but on the engagement timeline.

Both are valid; pick consciously.

The lab build's job in the meantime is to make sure no architectural surprise lands on the engagement timeline. By the time we hit kickoff, swapping `policy_search` from a local index to Foundry IQ should be a config change, not a redesign.
