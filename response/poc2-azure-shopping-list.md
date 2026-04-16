# POC2 — Azure Shopping List

HR Talent Lifecycle POC. 12-week "frontier" sprint. Azure-only consumption. Third-party services (HeyGen avatar, Greenhouse / LinkedIn / Workday SaaS licences) and the Custom Control Plane UI are costed separately.

**POC2 is incremental on POC1.** It assumes the shared platform from [poc1-azure-shopping-list.md](poc1-azure-shopping-list.md) is already standing (APIM, API Center, Functions EP1, Cosmos DB, Blob Storage, Key Vault, Log Analytics, Event Grid, Content Safety, Entra Agent ID, base model deployments, single region with APIM jurisdiction routing). This list shows only what POC2 **adds** or **upgrades**.

---

## Net-new resources (POC2-specific)

| # | Resource | Tier / config | Purpose |
|---|---|---|---|
| N1 | **Azure AI Foundry — Agent Service** (Hiring) | Hosted Agents (preview), 3 deployments × 2-3 replicas | Hiring Agent + Hiring Fleet Manager + External A2A Candidate Agent bridge. Distinct from POC1's Finance deployments. No runtime charge. |
| N2 | **Azure OpenAI — GPT-Realtime** | PAYG | Speech-to-speech front end for voice screening. New model deployment in shared Azure OpenAI account. |
| N3 | **Azure Communication Services** | PAYG voice calling + PSTN, ≥1 acquired number | Telephony substrate for candidate voice screening calls. New service. |
| N4 | **Microsoft Fabric — F2 capacity** | PAYG | Substrate for Fabric IQ: headcount ontology, agency hierarchy, comp bands, cross-entity matrix navigation (role in Media Agency, budget from WPP Corp), levelling history. Load-bearing for episodic memory + budget reasoning. POC1 descoped this; POC2 introduces it. |
| N5 | **Azure Container Apps — Consumption** | 0.25 vCPU / 0.5 GiB × 6 apps | Hiring-domain MCP servers: Greenhouse ATS, LinkedIn Recruiter, Workday (hiring), MS Graph, ServiceNow, ACS control plane. |
| N6 | **Azure AI Foundry — Evaluators** | PAYG | 500-CV synthetic evaluation run (task adherence, tool call accuracy, bias markers, groundedness). Continuous evaluation on production traces. |
| N7 | **Azure Document Intelligence** | PAYG, prebuilt / layout model | Light use — right-to-work document parsing, offer letter extraction. Reuses POC1's resource if already provisioned; if not, net-new. |

---

## Upgrades to shared infrastructure

| # | Resource | POC1 baseline | POC2 upgrade | Reason |
|---|---|---|---|---|
| U1 | **Azure AI Search** | Basic, 1 SU | Standard S1, 1 replica / 1 partition | Jurisdiction corpora (USA employment law, German BetrVG, GDPR, EU AI Act, WPP people handbooks, comp benchmarking) exceed Basic tier capacity and need permission filtering. |
| U2 | **Azure API Management** | Standard v2, base usage | Standard v2 + A2A governance policies enabled (preview) | Required for external candidate agent demo. No tier change; configuration only. |
| U3 | **Azure Cosmos DB** | Serverless, ~50M RU baseline | Higher RU + new containers for episodic memory (past-hire levelling, outcomes) | Episodic memory load-bearing for Fleet Manager precedent retrieval. |
| U4 | **Azure Monitor — Log Analytics** | ~100 GB / 8 weeks ingest | ~250+ GB / 12 weeks ingest | More agent roles (10+), longer runs, voice transcripts, A2A traces. |
| U5 | **Azure Event Grid** | ~500k ops / 8 weeks | Higher volume — more agents, more phase transitions, multi-jurisdiction | No tier change; consumption-driven. |

---

## Shared platform infrastructure consumed (already standing from POC1)

POC2 reuses these without standing them up again:

- Azure Functions Elastic Premium EP1 (Durable Functions host)
- Azure API Management — Standard v2
- Azure API Center
- Azure Cosmos DB serverless account
- Azure Blob Storage
- Azure Key Vault
- Azure OpenAI — GPT-5.4-mini (more tokens)
- Azure OpenAI — GPT-5.4 full (more tokens)
- Azure Content Safety / Foundry Guardrails
- Microsoft Entra Agent ID
- **Work IQ MCP** — existing M365 tenancy (preview); used by Personal Agents, Interview Coordinator (timezone / calendar), org-topology escalation routing

---

## Assumptions

| Assumption | Value | Rationale |
|---|---|---|
| Build operating mode | Dev-style utilisation curve — not 24×7 production | Weeks 1-4 mostly local dev; weeks 5-8 integration; weeks 9-12 demo prep + multi-jurisdiction rehearsals. |
| Fleet Manager operating mode | Activated from week 4 onwards, 24×7 during weeks 4-12 | Realistic once workflows start existing in volume. |
| End-to-end hiring workflows executed | ~50 (test + demo + rehearsal) | Conservative; 15-20 concurrent at demo peak × multiple rehearsals. |
| Synthetic CV evaluation | 500 CVs × 3-5 eval runs | POC2 spec requires 500-CV eval via Foundry Evaluators. |
| Voice screening calls | ~50 calls × 15 minutes | Screening agent demo runs, multi-jurisdiction variants. |
| Jurisdictions exercised | USA + Germany, single Azure region with APIM routing | POC2 frontier requirement — jurisdiction switching via APIM routing to region-appropriate model endpoints + jurisdiction-specific skills + Foundry IQ corpora. No second region stood up; routing is policy-as-code in APIM. |
| Agent roles loaded as skills | 10+ skills on the Hiring Agent Hosted Agent | Per solution §4.4 — skills specialise within one domain-scoped agent, not separate agents. |
| Agent executor token profile | 8k-15k input / 1k-2k output per invocation | Larger than POC1 — CVs are longer than invoices; compliance narratives are token-heavy. |
| Fleet Manager profile | Batch reasoning every ~3 min + hourly deep pass on GPT-5.4 | Higher event rate than POC1 due to 10+ agent roles per workflow. |
| Episodic memory reads | Fabric IQ + Work IQ on every major phase transition | Load-bearing for "recall past hires levelled too low" demo. |
| A2A external candidate agent | 1 integration, APIM-governed (preview) | Single demo flow to show external-agent interop. |

---

## Out of scope (deliberately excluded)

| Excluded | Reason |
|---|---|
| HeyGen avatar generation | Third-party; external parties excluded. |
| Candidate web portal | Not needed — candidate experience is voice (ACS) + email. |
| Custom Control Plane UI + SignalR + React hosting | Platform shopping list. Needed Day 1 of POC1 but counted separately. |
| Agent 365 / Purview DLP / Defender for Cloud AI | Out of scope for the Azure consumption line. |
| M365 Copilot + M365 Agents SDK surface licences | Existing WPP M365 tenancy. |
| Third-party SaaS (Greenhouse, LinkedIn Recruiter, Workday sandbox licences) | WPP-provided per POC spec. |
| Private Endpoints / VNet / NAT gateway | Add if compliance posture mandates network isolation. |
| Secondary region / DR | Single-region deployment; jurisdiction handled by APIM model-endpoint routing. |
| Production run-rate (500 concurrent × 30 markets) | Different order of magnitude — separate exercise. |
| MAI-Voice-1 (preview TTS) | Primary voice uses GPT-Realtime (GA); MAI-Voice-1 additive only. |

---

## Model family

Frontier-only. No legacy 4-series models.

- **GPT-5.4-mini** — default for agent executors (job design, CV triage, interview coordination, onboarding) and Fleet Manager batch reasoning.
- **GPT-5.4** (full, non-Pro) — compliance narrative (jurisdiction-aware right-to-work, GDPR, EU AI Act), offer personalisation, Fleet Manager hourly deep pass, complex exception handling.
- **GPT-Realtime** — speech-to-speech for voice screening.
- **GPT-5.4 Pro** — not used in POC2; reserved for scenarios requiring maximum reasoning depth.

