## 10.2 POC 2 — People: Advanced Talent Lifecycle Agent Team

POC 2 is the flagship frontier POC. It addresses the 15% *Advanced capabilities* weight and stress-tests the full 22-capability catalogue across a multi-jurisdiction hiring workflow. WPP's framing sets the scoring posture:

> *"This is not a HR chatbot. We are asking you to demonstrate an agentic operating model for HR, where agents perform the bulk of operational work and humans supervise, intervene, and decide at critical moments via a Control Plane, not a chat interface."*

> *"A vendor who demonstrates 22 of 23 capabilities brilliantly but fails to propose a Control Plane solution will struggle to pass this POC."*

The operating model is one HR Business Partner supervising 15–20 concurrent hiring workflows through the Control Plane, spanning multiple agencies, markets, and jurisdictions. Cycle time is compressed from 45–60 days to days, not months. The reference scenario is a Senior Data Engineer hire at a US WPP agency with five humans across four timezones: Hiring Manager (Los Angeles, Teams); HR BP (London, Control Plane); Finance BP (Mumbai, email); IT Ops (Chennai, ServiceNow); Candidate (external, web and voice). All surface inputs converge on a single workflow view. The shape corresponds to Apex Diagram 3/4 — a shared Fleet Dashboard with role-filtered views over N parallel workflow instances, jurisdiction-scoped, with per-instance autonomy and per-agency authentication scope.

## Duration, operator, concurrency, cast

Twelve-week sprint following POC 1. One HR BP (London) operates the Control Plane. 15–20 concurrent hiring workflows. Five humans as above.

## Architecture

One domain-scoped Hosted Agent: `hiring-agent@wpp`. Skills: Budget and Approvals, Job Design, Sourcing, Triage, Screening, Interview Coordinator, Compliance (jurisdiction-aware), Offer, Onboarding, Voice Screening. Each skill declares its own role, tool allow-list, model assignment, and governance rules. The specialist team in the brief is preserved as skills; the coordination substrate is a typed MAF workflow graph, with A2A used at the organisational boundary where a candidate's external AI assistant participates. Rationale in §18. Entra Agent ID provides workload identity today; Agent 365 primitives are adopted on GA in May 2026. Nothing in the POC is blocked on that milestone.

## MCP integrations

Greenhouse ATS, LinkedIn Recruiter, Workday (hiring), Microsoft Graph (calendar and email), ServiceNow (IT provisioning), Azure Communication Services (voice), HeyGen (avatar). All MCP traffic is brokered by APIM AI Gateway. REST-only systems (Greenhouse, HeyGen) are exposed through the APIM REST-to-MCP gateway. Private egress, FQDN allow-list, and per-jurisdiction routing are enforced at the gateway.

## Execution shape

Each hire is a Durable Functions orchestration spanning weeks. The ten phases — budget and approvals, job design, sourcing, CV triage, voice screening, interview coordination, compliance, offer, JML onboarding, avatar welcome — are each a MAF workflow graph. Deterministic executors dominate: sourcing queries, interview scheduling, JML provisioning tickets, offer letter templating, HeyGen video generation. Agent executors are bounded: JD drafting, CV scoring, voice screening, compliance narrative, offer personalisation. Validator executors sit between any agent output and any downstream non-revocable action.

## What the POC demonstrates

Every POC 1 capability is present. The following items additionally demonstrate the 22 WPP Advanced Capability criteria (§4.1–§4.22).

- **Layered orchestration (§4.1, §4.3)** — Durable Functions envelope across 12 weeks; MAF workflow graphs per phase; ephemeral GHCP SDK sessions inside agent executors. State survives platform restart; all concurrent workflows resume from last checkpoint with no context loss.
- **Deterministic-by-default graphs** — phase graphs are annotated with code-vs-LLM boundaries. What is deterministic is visibly deterministic; what is probabilistic is bounded and gated by a validator.
- **Multi-surface convergence (§4.2)** — Hiring Manager on Teams/Copilot 365 for focused prompts; Finance BP on email Adaptive Cards for one-click approval; Candidate on web, email, phone; IT Ops on ServiceNow webhooks; HR BP on the Control Plane. A single workflow session ingests all surfaces concurrently.
- **Revocable vs non-revocable actions (§4.4)** — offer retraction releases the Workday headcount hold, notifies the hiring manager, re-activates the shortlist. Non-revocable actions — background check, GDPR consent, outbound candidate emails and calls — surface on the Control Plane for HITL approval before execution.
- **Voice screening with structured scoring (§4.5)** — GPT-Realtime over Azure Communication Services performs the agent-led screen with live STT, structured questioning, and scoring. A validator executor checks completeness and policy alignment before any downstream action.
- **Avatar onboarding video (§4.5)** — HeyGen API MCP generates a personalised, branded welcome video, queued on the Control Plane for HR BP approval before release.
- **CV parsing with crystallisation pipeline (§4.6)** — an agent CV scorer is observed over repeated runs; after a success threshold the pipeline proposes promotion to a deterministic classifier in API Center. Promotion requires Control Plane approval; the agent implementation is preserved as a fallback.
- **Episodic memory (§4.7)** — the workflow state store plus Fabric IQ recall that the last three Data Engineer hires at this agency were levelled too low and re-levelled within six months. The recall feeds a procedural rule visible on the Control Plane. Memory conflicts — Screening skill and human reference-check validator updating the same record — are detected, resolved, and audited.
- **Analytics and data federation (§4.8)** — Budget and Approvals combines Workday headcount with Databricks forecast for cost-impact analysis on the Control Plane. Fabric IQ queries levelling-history data in Databricks Unity Catalog through OneLake shortcuts; the recall above runs against WPP's existing data estate with no migration.
- **Synthetic CV evaluation (§4.9)** — 500 synthetic CVs with controlled attributes run through Foundry Evaluators for bias, accuracy, and edge-case testing. A simulation gym replays the workflow at elevated speed to surface failure modes.
- **Three build modes (§4.10)** — pro-code Python SDK graph; low-code visual designer; agentic builder NL-to-orchestration. The scenario ships as a forkable *Talent Acquisition* template.
- **A2A and MCP interop (§4.11)** — the candidate's external AI assistant negotiates interview times with the Interview Coordinator skill via A2A AgentCards and JSON-RPC, governed through APIM. The Sourcing skill discovers an approved LinkedIn MCP tool from the MCP registry.
- **Jurisdiction-aware compliance (§4.12, Appendix B)** — USA vs Germany enforcement switches by APIM routing, jurisdiction-specific skill loading, Foundry Guardrails, and MAF validators for GDPR consent and EU AI Act classification. A governance-as-code rule — *no automated rejection in Germany or France without works council notification* — is platform-enforced, version-controlled, audit-trailed. A Control Plane policy dry-run answers *if we lower auto-shortlist from 85% to 75%, how many of last quarter's candidates would have been affected?*
- **Autonomy dials (§4.12)** — Screening auto-shortlist thresholds are runtime-adjustable through the Control Plane and demonstrated live. Our production recommendation is tightened governance: PR-gated APIOps promotion, dual-control on writes, or runtime adjustment disabled in production tenants with a change-request workflow. The mechanism is in the platform; the governance posture is a per-tenant deployment decision. §5.5 sets out the options.
- **Auth matrix and REST-to-MCP (§4.13)** — Workday (SAML-Okta), LinkedIn Recruiter (OAuth 2.0 Authorization Code), Greenhouse (API App Credentials via REST-to-MCP), Microsoft Graph (OBO), ServiceNow (API key). Platform-level auth abstraction, auto token refresh, per-environment models and credentials across dev/staging/prod.
- **Institutional knowledge capture (§4.14)** — Threadlight interviews an HR SME mid-POC, captures a jurisdiction-specific compliance pattern, and produces executable skills in the MAF graph. Drift detection flags behavioural divergence from the living process model.
- **Agent identity and delegated authority (§4.15)** — Budget and Approvals holds delegated authority up to £10k from the Finance BP, time-bound, revocable from the Control Plane, audit-logged. The Hiring Agent appears in the organisational directory with a stated reporting line.
- **Org topology and escalation (§4.16)** — the platform selects the right human by timezone, availability, and authority across Berlin, London, and Mumbai. Cross-entity approval chains — role in Media, budget from WPP Corp — render on the Control Plane.
- **Economic reasoning (§4.17)** — tiered model usage: cheap model keyword-filters 200 CVs, frontier model scores the top 30. Per-workflow cost on the Control Plane, per-hire ROI report at completion.
- **Process evolution (§4.18)** — after ten completed workflows the Fleet Manager identifies that *works council notification consistently causes three-day delays* and proposes submitting earlier. Proposals surface on the Control Plane for HR BP approval; they are not auto-implemented.
- **Multi-modal work (§4.19)** — Screening performs visual reasoning over candidate portfolio PDFs; Budget flags salary anomalies against benchmark history.
- **Trust and verification (§4.20)** — 10% of successfully screened CVs sampled for HR BP spot-check; an independent agent-auditing-agent re-scores the Triage sample with a different model and produces a discrepancy report. Candidate-facing artefacts are labelled *Prepared by AI Agent; reviewed and approved by [HR BP name]*. Model failover to an alternative of acceptable quality is demonstrated with Control Plane visibility.
- **AG-UI dynamic components and skill amplification (§4.21)** — bulk-approval forms, interview scorecards, and escalation cards render dynamically per workflow type from MAF agent executors emitting AG-UI event streams over SSE. No UI is hardcoded per workflow. When the operator is uncertain — for example on German works council requirements — the Fleet Manager proactively surfaces relevant policy, precedents, and recommended approach, grounded through Foundry IQ over WPP corpora.
- **Runtime agent assembly** — in a single demonstrated flow, Threadlight captures a jurisdiction-specific compliance pattern from an SME interview, generates a SKILL.md, and auto-registers it in Entra Agent ID and API Center in Design state. The operator reviews and promotes to Production; the new capability is live in the next workflow without a redeploy.
- **Infrastructure resilience and residency (§4.22)** — a German workflow routes only to EU model endpoints and an EU Log Analytics workspace. The APIOps CI pipeline rejects a deliberate PR that registers a US backend to the DE skill — the gate is demonstrated live. Region-down recovery with in-flight workflows is demonstrated; the Control Plane shows the event and resumes from the last checkpoint. Observability is filtered by market, agency, and agent type.

## On the Regional Sovereignty Exercise (Appendix B)

Appendix B is a tie-breaker issued to shortlisted vendors and is not required in the initial response. Readiness is stated briefly; §7.8 holds the compliance detail.

- **Data residency enforced at runtime** — Foundry Guardrails, APIM routing, and the APIOps CI gate enforce residency for inference, tool calls, state, and logs. Platform-level, not developer configuration.
- **German employment law** — the Compliance skill carries a BetrVG sub-skill; Foundry IQ is grounded over a DE legal corpus. Rules declaratively configured per jurisdiction.
- **Jurisdiction switching** — state- and skill-driven; the Control Plane displays jurisdiction context per workflow and switches UK vs DE rules without manual reconfiguration.
- **EU AI Act conformity** — automated candidate screening is classified high-risk in the agent registry. Mandatory human oversight on the Control Plane, technical documentation generation, and Foundry Evaluators provide the conformity evidence base.
- **Runtime compliance monitoring** — the Fleet Manager and Microsoft Defender for AI raise near-real-time alerts on sovereignty-boundary crossings, endpoint-region changes, or routing through non-compliant intermediaries.

Cross-reference §7.8 for the compliance detail.
