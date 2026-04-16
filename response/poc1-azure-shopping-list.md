# POC1 — Azure Shopping List

Finance Procure-to-Pay POC. Azure-only consumption. Third-party services (HeyGen, external SaaS) and the Custom Control Plane UI are costed separately.

---

## Shopping list

Most of POC1's stack is **shared platform infrastructure** that POC2 will inherit. Only a handful of lines are POC1-specific (Finance domain). Lines marked **[shared]** stand up once for the platform and serve every domain; lines marked **[POC1]** are net-new for Finance P2P.

| # | Scope | Resource | Tier / config | Purpose |
|---|---|---|---|---|
| 1 | **[POC1]** | **Azure AI Foundry — Agent Service** (Finance) | Hosted Agents (preview), 2 deployments × 2 replicas | Finance Agent + Finance Fleet Manager. No runtime charge — pay only for models/tools. |
| 2 | **[shared]** | **Azure OpenAI — GPT-5.4-mini** | PAYG | Primary model across all agent executors and Fleet Manager batch reasoning. |
| 3 | **[shared]** | **Azure OpenAI — GPT-5.4** (full, non-Pro) | PAYG | Escalation path for complex exceptions + hourly Fleet Manager deep summaries. |
| 4 | **[shared]** | **Azure Functions — Elastic Premium EP1** | 1 vCPU / 3.5 GB, always-on | Hosts Durable Functions orchestrations across both POCs. |
| 5 | **[shared]** | **Azure API Management — Standard v2** | 1 unit | AI Gateway: token rate limits, content safety, semantic cache, model load balancing, MCP governance. One instance for the whole platform. |
| 6 | **[shared]** | **Azure API Center** | Preview (free) | Registry for models, MCP tools, skills. One tenant for the whole platform. |
| 7 | **[shared]** | **Azure Cosmos DB — Serverless (NoSQL)** | Serverless account, separate containers per domain | Workflow state + append-only action ledger. Account shared; containers domain-scoped. |
| 8 | **[shared]** | **Azure Blob Storage — Hot LRS** | Standard GPv2 | DF Task Hub + audit archive. Containers domain-scoped. |
| 9 | **[shared]** | **Azure Key Vault** | Standard | Per-domain credential containers in one shared vault. |
| 10 | **[shared]** | **Azure AI Search — Basic** | 1 SU (POC1 baseline; POC2 upgrades to Standard S1) | Substrate for Foundry IQ. POC1 indexes vendor master, purchasing policy, tax rules. |
| 11 | **[POC1]** | **Azure Document Intelligence** | PAYG, prebuilt invoice model | Deterministic OCR; LLM only on low-confidence fields. Specific to invoice intake. |
| 12 | **[POC1]** | **Azure Container Apps — Consumption** | 0.25 vCPU / 0.5 GiB × 3 apps | Hosts Finance-domain MCP servers (Workday, D365 F&O, Maconomy). |
| 13 | **[shared]** | **Azure Monitor — Log Analytics + App Insights** | PAYG Analytics tier | One workspace for the whole platform. OTEL from DF, MAF, GHCP SDK sessions, APIM, MCPs. |
| 14 | **[shared]** | **Azure Event Grid** | Standard topic | Telemetry fan-out to Fleet Manager(s). |
| 15 | **[shared]** | **Azure Content Safety / Foundry Guardrails** | PAYG per text record | Four-point interception on all agent I/O. |
| 16 | **[shared]** | **Microsoft Entra Agent ID** | Existing Entra P2 tenancy | Agent identity registry; one identity per Hosted Agent deployment. No incremental cost. |

---

## Assumptions

| Assumption | Value | Rationale |
|---|---|---|
| Fixed infrastructure operating mode | 24 × 7 | APIM, Durable Functions host, AI Search, Container Apps cannot be paused meaningfully in a development environment. |
| Fleet Manager operating mode | 24 × 7 from day 1 | Reasons over telemetry in ~3-minute batches with an hourly deep pass on GPT-5.4. |
| Invoices processed end-to-end | 10,000 | Dev iterations + test + demo + slack. |
| Pages per invoice (OCR) | 2 | One invoice + one PO attachment on average. |
| Agent executor hit rate | ~30% of invoices | P2P is deterministic-by-default; LLM only fires on exception paths (low-confidence OCR, GL coding, reconciliation exceptions). |
| Test iteration multiplier | 3× | Same invoice reprocessed across dev iterations, debugging, demo rehearsals. |
| Agent executor token profile | 8k input / 1k output per invocation | Invoice content + skill prompt + MCP tool responses. |
| Fleet Manager batch rate | ~500 passes/day (every ~3 minutes) + hourly deep pass | Aggregated reasoning over telemetry, not per-event. |
| Fleet Manager context profile | 5k in / 500 out per batch; 8k in / 2k out for hourly deep | Telemetry summaries, not raw event dumps. |
| Content Safety inspection | 4 passes × ~20k agent invocations | Matches Foundry Guardrails' four intervention points. |

---

## Out of scope (deliberately excluded)

| Excluded | Reason |
|---|---|
| Voice / ACS / GPT-Realtime / avatars | POC2 scope. |
| Custom Control Plane UI + SignalR + React hosting | Costed separately. |
| Microsoft Fabric capacity + Fabric IQ | Not load-bearing for POC1; cost-centre / agency hierarchy can be sourced directly from D365 F&O or Dataverse. Re-appears in POC2 where episodic memory and cross-entity ontology are genuinely needed. |
| Agent 365 / Purview DLP / Defender for Cloud AI licences | Absorbed by existing WPP M365 E5 + Defender tenancy. |
| Private Endpoints / VNet / NAT gateway | Not baselined; adds ~$135 per 8 weeks if compliance posture mandates. |
| Secondary region / DR | POC runs in a single region. |
| Third-party SaaS (Workday, D365 sandbox, Maconomy licences) | WPP-provided per POC spec. |
| Production capacity (500 concurrent × 30 markets) | Different order of magnitude — separate exercise. |

---

## Model family

Frontier-only. No legacy 4-series models.

- **GPT-5.4-mini** — default for agent executors and Fleet Manager batch reasoning.
- **GPT-5.4** (full, non-Pro) — escalation path for complex exceptions and hourly Fleet Manager deep summaries.
- **GPT-5.4 Pro** — not used in POC1; reserved for scenarios requiring maximum reasoning depth.

