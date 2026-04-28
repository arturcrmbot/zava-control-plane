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
| **OCR / receipt extraction** | Stub. `doc_intelligence_extract.py` is a pass-through over fields already attached to synthetic claims. | Azure Document Intelligence over real receipt PDFs; `agent_field_extractor` for low-confidence cases. |
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
| **Accuracy gate** | Smoke 5/6 on a 20-claim sample today; target ≥95% on the 300-claim local run. | **≥95% on the WPP 3,430-line dataset — 40% of the POC1 score.** |
| **Region failover** | `simulate-region-failure` simulator command (kills the Functions host, restarts) — local proof of replay. | Real Azure region pair with Cosmos DB geo-replication; live failover demonstrated against 500 in-flight workflows. |
| **HITL surfaces** | Web UI + a `/api/simulator/justification` endpoint that fakes the employee reply. | Real Adaptive Card sent via Outlook through the recipient's M365 Personal Agent. |
| **60-minute Copilot Studio build** | Not in this repo. | Separate scripted demo: junior dev builds a new agent with 3 MCPs + 3 knowledge sources in under 30 minutes. |

### Lab build status against the 13 acceptance criteria

(Snapshot of where this repo is — see [poc1-status.md](poc1-status.md) for live state.)

- ✅ AC #1 fleet view · #2 exception-only · #3 bulk approval · #5 receipt cross-validation · #6 progressive enforcement · #9 multi-EMS Control Plane
- 🟡 AC #4 accuracy pipeline live, full corpus run pending · #7 justification round-trip wired, autonomy-proposal Fleet Manager extension to-build · #8 SSC Reviewer queue route just landed · #10 EMS extensibility narration script to-build
- ❌ AC #11 region failure simulator · #12 audit query + summariser skill · #13 cost-per-task report (the MCP tools `audit_query` / `query_reviewer_decisions` / `query_economics` just landed in `main`; the skill + UI surfaces remain)

The engagement POC must hit all 13 live in front of WPP. The lab build is converging on demoable evidence for the platform claims; the engagement POC then exercises the same code against real systems and real data.

---

## POC2 — much wider gap

POC2 in the lab is **not started**. The plan in [poc2-status.md](poc2-status.md)
calls out that ~75% of POC1 source artefacts are domain-agnostic platform
and reuse. The 25% that's POC2-specific (10 hiring skills, 7 mocks,
synthetic 200-CV corpus, voice + avatar tracks, Threadlight, A2A,
multi-jurisdiction compliance) is greenfield.

So for POC2:

- **Lab build** (when it starts): same single-laptop pattern, mocked Greenhouse / LinkedIn / Workday-HR / Graph / ServiceNow / ACS / HeyGen, synthetic CVs, simulated multi-surface convergence.
- **Engagement POC**: real ATS sandbox, real LinkedIn Recruiter API, real Microsoft Graph (Teams / Outlook / Calendar), real ServiceNow tenant, real ACS phone number, real HeyGen API key, real BetrVG corpus, real Foundry Guardrails for jurisdiction routing.

The same swap-in story applies — MCP contracts identical, backend implementations different.

---

## Why this distinction matters for the bid

The bid response sections (§10.1, §11, §B.4, §B.5) describe **the engagement POC**, not the lab build. Foundry IQ, Fabric IQ, Document Intelligence, Entra Agent ID, real EMS connections — those are commitments for the engagement, grounded by a lab build that has already proven the architecture at the laptop scale.

When recording / demoing for WPP evaluation:

- **If we record from the lab build**, frame it as *"the architecture proven on a laptop; same code runs on Azure; here's the swap-in seam"*. Honest, derisks the technical claim, but is not the engagement POC.
- **If we record from the engagement POC**, that lands after kickoff with WPP's data and sandbox credentials. Higher fidelity but on the engagement timeline.

Both are valid; pick consciously.

The lab build's job in the meantime is to make sure no architectural surprise lands on the engagement timeline. By the time we hit kickoff, swapping `policy_search` from a local index to Foundry IQ should be a config change, not a redesign.
