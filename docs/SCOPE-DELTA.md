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
| Data | Synthetic fixtures committed to `data/synthetic/` | WPP-supplied datasets (3,430 claims + ground-truth labels for POC1; HR sandbox + 200-CV synthetic gym for POC2) |
| Status | Mid-build · target tag `v0.8-poc1-feature-complete` | Not started · begins at signed contract + kickoff |

The lab build proves the **shape**. The engagement POC proves the shape **at WPP scale, on Azure, with WPP data, in front of WPP evaluators**.

---

## What's identical between the two

The platform layer is the load-bearing reuse. None of this changes when we move from laptop to engagement:

- Three-tier architecture: Fleet Manager (long-lived FastAPI session) / `ExpenseClaimOrchestrator` (Durable Functions) / ephemeral agentic loops per phase
- 7-phase per-claim flow + the validator-as-guardrail edge pattern
- 12 skills with `allowed-tools` frontmatter; agent identity model (`finance-agent@wpp` + `fleet-manager-agent`)
- 14 MCP tools with identical Pydantic schemas — **the MCP contract is the swap-in seam**
- React Control Plane UI + SSC Reviewer Queue
- OTEL emission path, audit ledger shape, bulk HITL pattern, hooks for non-revocable sends

Same code runs on the laptop and on Azure. Backend implementations differ; agent code, skill prompts, and validator logic are unchanged.

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

(Snapshot of where this repo is — see [poc1-status.md](poc1-status.md) for live state. Last refreshed 2026-04-30.)

- ✅ AC #1 fleet view · #2 exception-only · #3 bulk approval · #5 receipt cross-validation (real DI) · #6 progressive enforcement · #7 autonomous learning · #8 SSC Reviewer queue · #9 multi-EMS Control Plane · #10 EMS extensibility narration · #11 region failure simulator · #12 immutable audit + reporting · #13 cost-per-task report
- 🟡 AC #4 Foundry-backed accuracy pipeline shipped 2026-04-30; full 300-claim corpus run still pending (needs Foundry project + judge-model env vars)

The engagement POC must hit all 13 live in front of WPP. The lab build is converging on demoable evidence for the platform claims; the engagement POC then exercises the same code against real systems and real data.

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

Outstanding lab-build polish before `v1.0-poc2-frontier` tag:

- POC1 AC #4 full Foundry corpus run (300 claims, ~25 min compute time)
- One clean end-to-end stack boot to confirm `onboarding_video_url` lands on workflow metadata (the avatar fixes are committed; verification pending stable Functions host startup on this dev machine)
- 30-min demo dry run with someone playing the WPP evaluator
- Demo recording / screenshots

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
