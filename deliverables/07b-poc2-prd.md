# POC 2 PRD — People: Advanced Talent Lifecycle Agent Team

**Owner:** Microsoft (delivery); WPP AI CoE (acceptance)
**Status:** Draft for WPP review
**Date:** 2026-04-16
**Timeline:** 12-week sprint following POC 1

## 1. Problem statement

WPP frames POC 2 as the frontier POC:

> *"This is not a HR chatbot. We are asking you to demonstrate an agentic operating model for HR, where agents perform the bulk of operational work and humans supervise, intervene, and decide at critical moments via a Control Plane, not a chat interface."*

> *"A vendor who demonstrates 22 of 23 capabilities brilliantly but fails to propose a Control Plane solution will struggle to pass this POC."*

Today a hire at a US WPP agency involves 8–12 people across HR, Finance, IT, Legal and the hiring manager's team; 45–60 days; largely manual. The target is to compress cycle time to "days, not months" with one HR Business Partner supervising 15–20 concurrent hiring workflows spanning agencies, markets and jurisdictions through the Control Plane.

## 2. Goals

- Primary: demonstrate a single HR Business Partner operating the Control Plane across 15–20 concurrent hiring workflows spanning agencies, markets and jurisdictions.
- Secondary: exercise the full 22-capability surface from WPP's POC 2 brief (§4.1–§4.22) in live demo.
- Secondary: compress end-to-end hiring cycle time against the 45–60 day baseline for the Senior Data Engineer scenario.
- Secondary: demonstrate skill-based specialisation inside a domain Hosted Agent as the primary topology, with the "9+ separate specialist agents" topology available for comparison. Trade-off analysis is carried in response §6 and §18; both topologies are supported by MAF.

## 3. Non-goals

- Full Apex five-layer build-out. Layer 1 (Data) and Layer 2 (Workforce Design) are upstream workstreams.
- Production-grade integration to all 15+ external management systems or to the full WPP organisation. POC is scenario-scale.
- The Regional Sovereignty Exercise (Appendix B of WPP's POC 2 brief). It is flagged as tie-breaker, shortlist-only, and is not required in the initial response. Readiness is demonstrable if the engagement proceeds to shortlist.

## 4. Scenario

US WPP agency hiring a Senior Data Engineer. Five human participants across four timezones:

| Role | Location | Primary surface |
|---|---|---|
| Hiring Manager | Los Angeles | M365 Copilot in Teams |
| HR Business Partner | London | Custom Control Plane UI |
| Finance Business Partner | Mumbai | Email with Adaptive Card approvals |
| IT Operations | Chennai | ServiceNow |
| Candidate | External | Web portal, voice, email |

All surface inputs converge on a single workflow view in the Control Plane.

## 5. User journeys

The workflow consists of approximately ten phases, each implemented as a MAF workflow graph inside a Durable Functions orchestration spanning the multi-week hiring cycle.

1. **Headcount gap** — Hiring Manager's personal assistant surfaces the gap, manager approves, orchestration begins.
2. **Budget approval** — Budget and Approvals skill checks Workday headcount and Databricks forecast, routes HITL approval to the Finance BP via email Adaptive Card.
3. **Job design** — Job Design skill drafts the JD; `validate_jd_completeness` asserts structure; Foundry IQ provides comp benchmarking.
4. **Sourcing** — Sourcing skill runs deterministic Greenhouse and LinkedIn MCP queries.
5. **CV triage** — `agent_cv_scorer` reasons over each CV; `validate_bias_markers` runs deterministic bias checks and flags to Fleet Manager; shortlist produced.
6. **Voice screening** — GPT-Realtime over Azure Communication Services conducts structured screening with live STT, structured questioning and scoring; validator checks completeness and policy alignment.
7. **Interview coordination** — Work IQ resolves timezone, availability and rescheduling across Los Angeles, London, Mumbai and candidate preference.
8. **Compliance** — Compliance skill is jurisdiction-aware: right-to-work, GDPR consent, EU AI Act high-risk classification; Task Adherence guardrail detects drift from jurisdiction policy.
9. **Offer letter** — templated deterministic generation with `agent_personaliser` for narrative sections; non-revocable send gated by a GHCP SDK hook requiring dual-control HITL.
10. **JML onboarding** — ServiceNow MCP creates provisioning tickets; 30/60/90 plan scheduled.
11. **Avatar welcome video** — agent drafts the script; HeyGen MCP generates a personalised, branded welcome video; HR BP approves on the Control Plane before release.

## 6. Functional requirements — WPP §4.1 to §4.22

| Ref | Requirement | Our approach | Status |
|---|---|---|---|
| 4.1 | Multi-Agent Orchestration | Durable Functions envelope across the 12-week process; MAF workflow graphs per phase with typed edges and validator nodes; ephemeral GHCP SDK sessions inside agent executors. | Can do today |
| 4.2 | Multi-Surface Engagement | Teams/Copilot 365 (Hiring Manager); email Adaptive Cards (Finance BP); web portal, email, voice (Candidate); ServiceNow webhooks (IT Ops); Control Plane (HR BP). Single workflow session ingests all surfaces concurrently. | Can do today |
| 4.3 | Session Durability and State | Workflow state survives platform restart; concurrent workflows resume from last checkpoint; state persists across days and weeks. Cosmos DB state store and Durable Functions history table. | Can do today |
| 4.4 | Roll-Back and Compensating Actions | Revocable vs non-revocable action taxonomy. Offer retraction releases Workday headcount hold, notifies hiring manager, re-activates shortlist. Non-revocable actions (background check, GDPR consent, outbound emails and calls) surface on Control Plane for HITL approval before execution. | Can do today |
| 4.5 | Voice, Video and Avatar | GPT-Realtime plus ACS for voice screening; Teams for multi-party interview with agent note-taker; HeyGen MCP for avatar welcome video. All artefacts HITL-gated. | Can do today (GPT-Realtime and ACS GA; MAI-Transcribe-1 preview, GA Q4 2026) |
| 4.6 | Code Interpreter and Crystallisation | CV parsing agent scorer is observed across runs; after a success threshold the pipeline proposes promotion to a deterministic classifier registered in API Center. Promotion requires Control Plane approval; agent implementation retained as fallback. Computer Use / RPA Playwright scripts reviewable on Control Plane before execution. | Can do today |
| 4.7 | Memory and Knowledge | Workflow state store plus Fabric IQ recall of past hires at the agency (for example, "last three Data Engineer hires levelled too low"). Post-action review surfaces proposed workflow improvements. Memory conflict resolution between Screening skill and human reference-check validator is detected, resolved and audited. | Can do today (Fabric IQ preview; direct Fabric SQL fallback) |
| 4.8 | Analytics and Data Pipelines | Budget and Approvals combines Workday headcount with Databricks forecast for cost-impact analysis on the Control Plane. Bonus: agent-authored code-interpreter pipeline pulling weekly hiring funnel metrics into the Control Plane dashboard, deployable to GitHub and to Prefect/dlt. | Can do today |
| 4.9 | Evaluation and Testing | 500 synthetic CVs with controlled attributes through Foundry Evaluators for bias, accuracy and edge-case testing. Multi-prompt eval agent tests Job Design and Screener. Simulation gym replays the full workflow at elevated speed. | Can do today |
| 4.10 | Builder Experiences | Pro-code Python SDK graph; low-code visual designer; agentic builder NL-to-orchestration. Scenario ships as a forkable *Talent Acquisition* template. | Can do today |
| 4.11 | Interoperability and Protocols | A2A AgentCards and JSON-RPC task lifecycle for the external candidate agent, governed through APIM. MCP used throughout internally and externally; Sourcing skill discovers LinkedIn MCP tool from the registry. | Preview (APIM A2A governance preview; HTTP gateway primitives GA today) |
| 4.12 | Progressive Autonomy and Governance | Screening thresholds: >85% auto-shortlist; 60–85% to HR BP Control Plane queue; <60% auto-reject with notification. Runtime adjustability is supported; production recommendation is tightened governance (PR-gated APIOps, dual-control on writes, change-request workflow). Governance-as-code rule: *no automated rejection in Germany or France without works council notification* — platform-enforced, version-controlled, audit-trailed. Policy dry-run on Control Plane. | Can do today |
| 4.13 | Tooling Infrastructure and Auth | Workday (SAML-Okta), LinkedIn Recruiter (OAuth 2.0 Authorization Code), Greenhouse (API App Credentials via REST-to-MCP), Microsoft Graph (OBO), ServiceNow (API key). Platform-level auth abstraction, auto token refresh, per-environment credentials across dev/staging/prod. | Can do today |
| 4.14 | Institutional Knowledge Capture | Threadlight interviews an HR SME, captures jurisdiction-specific compliance patterns, emits executable skills for the MAF graph. Captured practice rendered as a living process model on the Control Plane. Drift detection flags behavioural divergence. Bonus: task mining from desktop activity via Process/BA agent. | Can do today (Threadlight accelerator built and demonstrated) |
| 4.15 | Agent Identity and Authority | Budget and Approvals holds delegated authority up to £10k from the Finance BP, time-bound, revocable from the Control Plane, audit-logged. Hiring Agent appears in the organisational directory with stated reporting line. Entra Agent ID provides workload identity today; Agent 365 primitives adopted on GA. | Preview for Agent 365 (GA May 2026); Entra Agent ID usable independently today |
| 4.16 | Org Topology and Escalation | Platform selects the right human by timezone, availability and authority across Berlin, London and Mumbai. Cross-entity approval chain rendered on the Control Plane (role in Media, budget from WPP Corp). | Can do today |
| 4.17 | Economic Reasoning | Tiered model usage: cheap model keyword-filters 200 CVs; frontier model scores the top 30. Per-workflow cost on the Control Plane; per-hire ROI report at completion. | Can do today |
| 4.18 | Process Evolution | After ten completed workflows the Fleet Manager identifies *works council notification consistently causes three-day delays* and proposes submitting earlier. Proposals surface on the Control Plane for HR BP approval; not auto-implemented. | Can do today |
| 4.19 | Multi-Modal Work | Screening performs visual reasoning over candidate portfolio PDFs; Budget flags salary anomalies against benchmark history ("30% above benchmark midpoint; last quarter's hires at 95% of midpoint"). | Can do today |
| 4.20 | Trust and Verification | 10% statistical QC sample of successfully screened CVs for HR BP spot-check. Independent agent-auditing-agent re-scores the Triage sample with a different model and produces a discrepancy report. Candidate-facing artefacts labelled *Prepared by AI Agent; reviewed and approved by [HR BP name]*. Model failover to alternative of acceptable quality, Control Plane visible. | Can do today |
| 4.21 | Human Supercharger: Control Plane Detail Screens | Bulk-approval forms, interview scorecards, escalation cards render dynamically per workflow type from MAF agent executors emitting AG-UI event streams over SSE. Skill amplification: when the operator is uncertain (German works council example), the Fleet Manager proactively surfaces policy, precedents and recommended approach, grounded through Foundry IQ over WPP corpora. | Can do today |
| 4.22 | Infrastructure Resilience | Target scale 500 concurrent workflows across 30 markets. Region-down recovery with in-flight workflows, Control Plane shows the event and resumes from last checkpoint. Observability filtered by market, agency, and agent type. Multi-cloud: Azure agents collaborating with GCP partner agents. | Can do today |

## 7. Agent team

WPP's brief names ten agents as the minimum suggested team. Our implementation preserves each as a skill inside one domain Hosted Agent, `hiring-agent@wpp`. Each skill declares its own role, tool allow-list, model assignment and governance rules.

| Agent / skill | Responsibility | Executor type | Crystallisation candidate |
|---|---|---|---|
| Orchestrator | Decomposes request, builds task graph, manages workflow state, feeds Control Plane telemetry | Deterministic (MAF graph + Durable Functions) | No |
| Budget and Approvals | Checks headcount budget (Dataverse, Databricks), routes approvals | Deterministic with HITL gate | No |
| Job Design | Drafts role profile, JD, levelling, comp benchmarking from Foundry IQ | Hybrid: `agent_jd_drafter` + `validate_jd_completeness` | Partial (structure templating) |
| Sourcing | Internal talent pool, Greenhouse, LinkedIn, referrals via MCP | Deterministic | No |
| Triage | Parses CVs, scores against criteria, flags concerns, shortlists. Procedural memory for role-specific rules. | Agentic with validator: `agent_cv_scorer` + `validate_bias_markers` | Yes — target crystallisation to deterministic classifier with agent fallback |
| Screening | Custom questionnaires via email and voice | Agentic: GPT-Realtime over ACS, structured scoring validator | Partial (scoring rubric) |
| Interview Coordinator | Timezone scheduling, calendar invites, rescheduling | Deterministic (Work IQ) | No |
| Compliance | Right-to-work, GDPR consent, EU AI Act, jurisdiction-aware | Hybrid: `agent_compliance_narrative` + deterministic rule executors (GDPR checklist, EU AI Act classifier) | Yes (rule executors); agent retained for narrative |
| Offer | Generates offer letter from template, calculates comp, routes approval | Hybrid: deterministic template + `agent_personaliser`; non-revocable send gated by GHCP SDK hook | Partial (template sections) |
| Onboarding | Triggers JML, provisions systems, schedules Day 1, assigns buddy, 30/60/90 plan | Deterministic (ServiceNow MCP) | No |

This is the "skills-based specialisation inside a domain Hosted Agent" pattern, not "9+ separate agent processes". See response §6 and §18 for the trade-off analysis. Both topologies are supported by MAF and a hybrid is available: skills inside a domain, A2A across domains.

## 8. Integration requirements

All MCP traffic is brokered by APIM AI Gateway with private egress, FQDN allow-list and per-jurisdiction routing enforced at the gateway. REST-only systems are exposed through the APIM REST-to-MCP gateway.

| System | Auth | Integration |
|---|---|---|
| Greenhouse ATS | API App Credentials | REST-to-MCP gateway |
| LinkedIn Recruiter | OAuth 2.0 Authorization Code | Native MCP |
| Workday (hiring) | SAML bridged via Okta | Native MCP |
| Microsoft Graph | OBO (On-Behalf-Of) | Native MCP |
| ServiceNow | API key | Native MCP |
| Azure Communication Services | Managed identity | Direct SDK under MAF executor |
| HeyGen | API key | REST-to-MCP gateway |

Platform-level auth abstraction handles token refresh automatically. Per-environment credentials and model versions are enforced across dev, staging and production via APIOps.

## 9. Control Plane requirements

- **Fleet dashboard** — all active workflows with status, health, SLA, exception; filterable by agency, market, risk and jurisdiction.
- **Exception-only surfacing** — of 15 active workflows, the HR BP sees only the 2–3 requiring intervention.
- **Instant situational awareness** — under 5 seconds to full context on a workflow.
- **Bulk HITL** — 8 low-risk interview schedules approved in a single action.
- **Skill amplification** — when the HR BP is uncertain (for example on German works council requirements), the Fleet Manager proactively surfaces relevant policy, precedents and recommended approach via Foundry IQ over WPP corpora, without being asked.
- **Autonomy dials** — per-workflow and per-decision-type, runtime-adjustable. Production recommendation is tightened governance (PR-gated APIOps promotion, dual-control on writes, or runtime adjustment disabled in production tenants with a change-request workflow). The mechanism is in the platform; the governance posture is a per-tenant deployment decision.
- **AG-UI dynamic components** — bulk-approval forms, interview scorecards, escalation cards, policy dry-run views, all rendered per workflow type from MAF agent executors emitting AG-UI event streams over SSE. No UI hardcoded per workflow.
- **Runtime agent assembly** — Threadlight interviews an SME mid-POC, captures a jurisdiction-specific compliance pattern, emits a SKILL.md, auto-registers it in Entra Agent ID and API Center in Design state. The HR BP reviews and promotes to Production; the new capability is live in the next workflow without a redeploy.

WPP anti-requirement:

> *"Copilot Studio bot, Teams approval card, email chain is not a Control Plane. Vendors demonstrating only single-agent surfaces will score 0 on Control Plane criteria."*

Our Control Plane is a first-class fleet management surface. Copilot Studio is available for citizen-developer scenarios and for the 60-minute-build benchmark, not as a substitute for the Control Plane.

## 10. Non-functional requirements

| NFR | Target | Source / Mitigation |
|---|---|---|
| Availability | 99.9% per region | Azure regional SLAs; multi-region failover for critical control-plane components |
| RTO | Under 5 minutes | Durable Functions checkpointed state; Cosmos DB multi-region replication |
| RPO | Near-zero | Cosmos DB synchronous replication in-region; geo-redundant backup |
| Control Plane latency | Under 5 seconds to full situational awareness | OTEL-backed telemetry pipeline; pre-aggregated fleet queries |
| Concurrent workflows (POC scale) | 15–20 | Single HR BP operating range; scale target 500 workflows at production |
| Audit log retention | 7 years minimum (POC); 7–12 years production target | Log Analytics with long-term archive to storage |
| Data residency | Platform-enforced per jurisdiction | APIM routing, Foundry Guardrails, APIOps CI gate reject non-compliant backends |
| Session durability | State persists across multi-day and multi-week phases with no context loss | Durable Functions history + Cosmos DB state store; full platform restart resumes from last checkpoint |

## 11. Acceptance criteria

Each criterion references the WPP §4.x it satisfies. Evaluation method given: live demo, report or architecture walkthrough.

1. **AC-4.1** — Durable Functions orchestration across two concurrent workflows in different phases, MAF graph executing per phase. Live demo.
2. **AC-4.2** — All five human surfaces exchange input on one workflow session without context loss. Live demo.
3. **AC-4.3** — Full platform restart mid-workflow; resume from last checkpoint with no context loss. Live demo.
4. **AC-4.4** — Offer retracted after candidate declines; Workday hold released; shortlist re-activated. Non-revocable action queued for HITL before execution. Live demo.
5. **AC-4.5** — Voice screen conducted end-to-end with structured scoring; avatar welcome video generated and HITL-approved. Live demo.
6. **AC-4.6** — Agent CV scorer observed; crystallisation proposal surfaces; HR BP promotes to deterministic classifier; fallback path verified. Live demo plus architecture walkthrough.
7. **AC-4.7** — Episodic memory recall of past hires levelled too low triggers procedural rule on Control Plane; memory conflict between Screening and human reference-check detected and audited. Live demo.
8. **AC-4.8** — Budget cost-impact analysis rendered on Control Plane; agent-authored funnel pipeline deployed to GitHub. Live demo plus report.
9. **AC-4.9** — 500 synthetic CVs processed through Foundry Evaluators; bias, accuracy and edge-case results rendered. Report.
10. **AC-4.10** — Same scenario built in pro-code, low-code and NL-driven builder. 60-minute-build benchmark executed under 30 minutes by junior developer. Live demo.
11. **AC-4.11** — External candidate agent negotiates interview time via A2A AgentCards and JSON-RPC; Sourcing skill uses LinkedIn MCP tool from registry. Live demo.
12. **AC-4.12** — Threshold change on Control Plane takes effect with audit entry; governance-as-code rule blocks automated rejection in Germany without works council notification; policy dry-run answers historical-impact question. Live demo.
13. **AC-4.13** — All seven integrations demonstrate auth abstraction and token refresh; Greenhouse via REST-to-MCP; dev/staging/prod credential separation. Architecture walkthrough plus live demo.
14. **AC-4.14** — Threadlight captures jurisdiction pattern from SME interview mid-POC; SKILL.md produced and registered; drift detection flags simulated deviation. Live demo.
15. **AC-4.15** — Budget delegated authority cap of £10k demonstrated, time-bound, revocable from Control Plane; Hiring Agent visible in org directory. Live demo plus architecture walkthrough.
16. **AC-4.16** — Escalation routes to the right human across Berlin, London and Mumbai by timezone and authority; cross-entity approval chain rendered. Live demo.
17. **AC-4.17** — Tiered model cost report rendered per workflow; per-hire ROI report at completion. Live demo plus report.
18. **AC-4.18** — Fleet Manager proposes works council timing change after 10 workflows; HR BP approves on Control Plane. Live demo.
19. **AC-4.19** — Portfolio PDF visual reasoning demonstrated; salary anomaly flagged with benchmark history. Live demo.
20. **AC-4.20** — 10% statistical QC sample; agent-auditing-agent discrepancy report produced; labelling on candidate-facing artefacts; model failover event visible on Control Plane. Live demo plus report.
21. **AC-4.21** — Dynamic AG-UI components render per workflow type; skill amplification surfaces German works council guidance without being asked. Live demo.
22. **AC-4.22** — Region-down recovery with in-flight workflows; 500-workflow scale evidence from load test; observability filtered by market, agency and agent type. Live demo plus report.

## 12. Evaluation criteria

WPP's stated priorities are qualitative, not percentage-weighted.

- **Control Plane** — genuine fleet management versus chat wrapper. Most heavily weighted.
- **Demonstrated beats stated** — live demo required.
- **Honesty about gaps** — known constraints listed explicitly.
- **Architecture coherence** — GA foundation, replaceable runtime, consistent identity and governance.
- **Operational readiness at scale** — evidence for 500 agent teams under load from 50,000 humans.

## 13. What WPP provides

From WPP's POC 2 brief:

- Synthetic data and APIs for Workday, Greenhouse ATS, and candidate records.
- Vendor-hosted environment support.
- Half-day live demo window with evaluator panel.

## 14. What Microsoft provides

- Vendor-hosted Azure environment.
- GHCP SDK plus MAF Workflow plus Durable Functions plus APIM AI Gateway runtime stack.
- Foundry Hosted Agents (preview), with Azure Container Apps as the GA fallback running the same GHCP SDK image.
- Custom Control Plane UI and Fleet Manager agents.
- Voice subsystem: GPT-Realtime plus ACS Call Automation.
- Avatar: HeyGen MCP integration.
- Threadlight knowledge-extraction accelerator, built and demonstrated.
- Engineering team: 1 Solutions Architect plus 2–3 engineers, with Microsoft Services co-investment.

## 15. Timeline

Twelve-week sprint following POC 1 completion.

| Week | Milestone | Deliverable |
|---|---|---|
| 1–2 | Environment and scaffolding | Azure environment provisioned; Hiring Agent scaffolding; MCP server skeletons for Greenhouse, LinkedIn, Workday, ServiceNow, ACS, HeyGen |
| 3–4 | Budget, Job Design, Sourcing | Three phases end-to-end on synthetic data; Foundry IQ grounding for comp benchmarking; Fabric IQ headcount lookups |
| 5–6 | Triage and Screening | `agent_cv_scorer` with `validate_bias_markers`; Voice Screening (GPT-Realtime + ACS) with structured scoring validator |
| 7–8 | Coordination, Compliance, Offer | Interview coordination via Work IQ; jurisdiction-aware Compliance (US + one additional jurisdiction); Offer with non-revocable send and dual-control HITL |
| 9 | Onboarding and Avatar | ServiceNow MCP provisioning tickets; HeyGen MCP avatar welcome video with HITL approval |
| 10 | Control Plane polish | AG-UI dynamic components; skill amplification; autonomy dials; bulk HITL |
| 11 | Multi-human / multi-surface and runtime assembly | All five surfaces concurrent on one session; Threadlight mid-POC knowledge-capture demo with human promotion |
| 12 | Scale and dry-run | Scale testing, fault injection, region-down recovery, dry-run demo walkthrough |
| Half-day | Live demo | WPP evaluator panel |

## 16. Dependencies

- Synthetic candidate data from WPP: 500 CVs for §4.9 evaluation plus scenario-specific test data for the Senior Data Engineer workflow.
- Sandbox or mock credentials for Workday, Greenhouse, LinkedIn, ServiceNow and Azure Communication Services.
- Foundry IQ knowledge base content for compliance (GDPR, EU AI Act, plus BetrVG if shortlist-bound).
- Entra tenant for agent identities. Either the WPP tenant or the vendor tenant is acceptable.

## 17. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Foundry Hosted Agents preview scaling ceiling | Medium | Medium | Azure Container Apps GA fallback running the same GHCP SDK image; multiple Hosted Agent deployments to raise ceiling |
| Agent 365 not GA in time for POC (targeted May 2026) | Medium | Low | Entra Agent ID usable independently today; Agent 365 primitives adopted on GA |
| GPT-Realtime latency on voice screening | Low | Medium | Fallback to ACS plus MAI-Transcribe-1 path; MAI-Transcribe-1 preview today, GA Q4 2026; validator absorbs any regression |
| APIM A2A governance preview | Medium | Low | A2A required only for the §4.11 external candidate agent demo; HTTP gateway primitives GA today degrade gracefully |
| Foundry IQ, Fabric IQ, Work IQ preview | Medium | Low | All three are MCP-addressable; fallback to direct Azure AI Search, Fabric SQL and Microsoft Graph API queries |
| Threadlight delivery dependency | Low | Medium | Accelerator is built and demonstrated; confirmed by Microsoft delivery team |
| Jurisdiction-aware compliance complexity (§4.12, Appendix B) | Medium | Medium | Jurisdiction-specific skills plus APIM routing plus APIOps CI gate; extendable pattern, not per-agent hardcoding |
| "9+ separate agents" mental-model mismatch | Low | Low | Response §6 and §18 carry the skills-vs-separate-agents trade-off analysis; hybrid topology supported by MAF |
| Autonomy-dial governance tension with stated brief | Medium | Low | Mechanism in the platform; production recommendation is tightened governance (PR-gated APIOps, dual-control, change-request workflow); framed explicitly in response §5.5 |

## 18. Success criteria

POC 2 passes sign-off when all of the following are met:

- 22/22 WPP §4.x capabilities demonstrated in the half-day live demo.
- 15 or more concurrent workflows managed on the HR BP's Control Plane.
- Multi-jurisdiction compliance switching demonstrated (US plus one additional jurisdiction, likely UK; DE reserved for the shortlist Regional Sovereignty Exercise).
- No data loss through a region-down recovery test.
- Runtime agent assembly live: Threadlight captures a new skill mid-POC; human promotes it; new capability live in the next workflow without a redeploy.
- 60-minute-build benchmark: junior developer builds a 3-MCP, 3-knowledge-source agent via Copilot Studio in under 30 minutes, scripted.

## 19. Open questions

Items requiring WPP input before kick-off:

- Exact agency and market selection for the multi-jurisdiction test (US plus which second jurisdiction).
- Synthetic data delivery date and format.
- Sandbox credentials timeline across Workday, Greenhouse, LinkedIn, ServiceNow and ACS.
- Demo audience composition and date.
- Shortlist path: is POC 2 expected to include the Appendix B Regional Sovereignty Exercise, or is it truly shortlist-only?
