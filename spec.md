# WPP Enterprise Agent Capability Framework - RFP Requirements Specification

## Document Index
- **WPPET-1**: Enterprise Agent Framework Vendor Brief (31 Mar 2026)
- **WPPET-4**: Apex Diagrams (5-layer stack, Control Plane mocks)
- **WPPET-5**: Enterprise Agent Framework Q&A (8 Apr 2026)
- **WPPET-POC1**: Finance Expense Compliance (Procure-to-Pay)
- **WPPET-POC2**: HR Workforce Transformation (Talent Lifecycle)
- **Questionnaire**: 169 questions across 33 sections with MoSCoW ratings

---

## 1. Customer Context

**Client**: WPP (global advertising/communications, 85,000+ employees)
**Programme**: Project Apex / Elevate28
**RFP Owner**: Tom Kelshaw, Enterprise AI CoE Lead
**Classification**: Confidential: Vendor Distribution
**Written Response Deadline**: 23 April 2026
**Live Demo**: Date TBC (half day)

### Strategic Vision
WPP wants to shift from "practitioners using tools" (1-2x productivity) to "experts supervising agent teams" (10-100x productivity). This is NOT about chatbots or copilots - it's about a **software-defined enterprise workforce** operating under human governance via a **purpose-built Control Plane**.

### Five-Layer Enterprise AI Stack (Project Apex)
| Layer | Name | Purpose |
|-------|------|---------|
| L5 | Governance Layer | Design/review/approve agent workflows; controls, measurement, risk, compliance, audit |
| L4 | Control Plane | Review/approve/monitor agent runtime tasks; fleet dashboards, exception queues, autonomy dials, bulk HITL; **1:20-50 human-to-agent ratio** |
| L3 | Framework (ORC/RUN) | Build, test, eval, approve, deploy, runtime, orchestrate, observe |
| L2 | Workforce Design & Ontology | Task-level work mapping, automation priorities, agent ROI measurement, work architecture |
| L1 | AI-Ready Data Layer | Databricks, Snowflake, GCP, Dataverse; MDM, topology, data governance |

**RFP Scope**: Primarily L3 (Framework) and L4 (Control Plane), with deep integration into L5 (Governance) and L1 (Data).

---

## 2. The Control Plane - PRIMARY Requirement

> **A vendor who demonstrates 22 of 23 capabilities brilliantly but fails to propose a Control Plane solution will struggle to pass this POC.**

### Anti-Requirements
- A Copilot Studio bot is NOT a Control Plane
- A Teams approval card is NOT a Control Plane
- An email notification chain is NOT a Control Plane
- MS Teams and email are **surfaces** that deliver alerts FROM the Control Plane
- Vendors demonstrating only single-agent surfaces will score **0** on Control Plane criteria

### Mandatory Control Plane Capabilities

| # | Capability | Description |
|---|-----------|-------------|
| CP-1 | Fleet Dashboard | All active workflows; status, health, SLA, exception state; filterable by agency, market, risk level, jurisdiction, client, workflow type |
| CP-2 | Exception-Only Surfacing | Of N active workflows, operator sees only the 2-3% requiring intervention. Others run autonomously and are invisible unless drilled into |
| CP-3 | Instant Situational Awareness | Click into any workflow, within **5 seconds** understand: what agents did, what stopped progress, what agent recommends, what options are |
| CP-4 | Bulk HITL | Review and approve batches of similar decisions in a single action (e.g., 8 interview schedules, all low-risk) |
| CP-5 | Skill Amplification | Platform proactively surfaces relevant policy, precedents, and recommended approach when operator is uncertain |
| CP-6 | Autonomy Dials | Per-workflow and per-decision-type thresholds, adjustable at runtime without redeployment |
| CP-7 | Role-Based Views | Multiple operators (HR BP, Finance BP, IT Ops) see role-filtered views with RBAC |
| CP-8 | Cross-Workflow Context | Unified view across all workflows, not siloed per-agent |
| CP-9 | Real-Time Observability | End-to-end tracing with OpenTelemetry: inputs, reasoning steps, tool calls, outputs, latency, cost |
| CP-10 | Continuous Evaluation | Automated evals on production traffic: quality, safety, task adherence, tool call accuracy |
| CP-11 | Policy Dry-Run | "If we change threshold X, how many past cases would have been affected?" |
| CP-12 | Human Performance Analytics | Intervention rate, resolution time, override frequency, quality delta |

### Target Operating Model
- **1 HR BP** operating Control Plane across **15-20 concurrent hiring workflows** spanning multiple agencies, markets, and jurisdictions
- **1 Finance Controller** managing **30-50 concurrent invoice workflows**
- Target scale: **500 concurrent workflows across 30 markets**, eventually **40,000+ agent-equivalents**

---

## 3. POC 1: Finance Intelligent Procure-to-Pay

**Duration**: 8-week sprint
**Operator**: Finance Controller via Control Plane
**Concurrency**: 30-50 concurrent invoice workflows

### Agent Team (Minimum)
| Agent | Function |
|-------|----------|
| Orchestrator | Decomposes invoice request, builds task graph, manages workflow state, feeds Control Plane telemetry |
| Intake Agent | Invoice parsing, OCR, data extraction |
| Validation Agent | PO matching, three-way match, duplicate detection |
| Routing Agent | GL coding, cost centre allocation, approval chain |
| Approval Agent | Threshold-based routing with HITL gates |
| Payment Agent | Payment file generation, bank integration |
| Reconciliation Agent | Statement matching, exception identification |

### System Integrations
- Workday (SAML-bridged via Okta)
- Dynamics 365 F&O (native connector)
- Maconomy (custom MCP server or REST adapter)
- Sandbox/mock APIs provided by WPP

### Key Demonstrations Required
- Multi-agent orchestration with parallel + sequential patterns
- Control Plane fleet dashboard with exception-only view
- Bulk approval for batched invoices
- HITL gates for high-value approvals
- Full audit trail and OTEL tracing
- Rollback/compensating transactions
- State persistence across sessions

---

## 4. POC 2: HR Talent Lifecycle (Frontier POC)

**Duration**: 12-week sprint
**Operator**: HR Business Partner (London) via Control Plane
**Concurrency**: 15-20 concurrent hiring workflows
**Scenario**: Hire a Senior Data Engineer at a WPP agency in USA

### Human Participants
| Role | Location | Surface |
|------|----------|---------|
| Hiring Manager | Los Angeles | MS Teams / Copilot 365 |
| HR Business Partner | London | **Control Plane dashboard** (primary) |
| Finance Business Partner | Mumbai | Email with Adaptive Card |
| IT Operations | Chennai | Webhook/API into ServiceNow |
| Candidate | External, varies | Web portal + email/phone |

### Agent Team (Minimum 10+)
| Agent | Function |
|-------|----------|
| Orchestrator | Decompose request, build task graph, manage workflow state, stream OTEL to Control Plane |
| Budget & Approvals | Check headcount budget (Dataverse, Databricks), route approval chain |
| Job Design | Draft role profile, JD, levelling, comp benchmarking from internal sources |
| Sourcing | Search internal talent pool, post on external boards, LinkedIn, ATS (Greenhouse) |
| Triage | Parse CVs, score against criteria, flag concerns, shortlist |
| Screening | Deploy custom questionnaires (email, voice call transcribed), confirm criteria |
| Interview Coordinator | Schedule across timezones, send calendar invites, manage rescheduling |
| Compliance | Check right-to-work, GDPR consent, EU AI Act obligations |
| Offer | Generate offer letter from template, calculate comp against band, route for approval |
| Onboarding | Trigger JML workflow, provision systems, schedule Day 1, assign buddy, create 30/60/90 plan |

### 22 Capability Demonstrations Required

#### 4.1 Multi-Agent Orchestration
- Task graph decomposition visible on Control Plane
- At least 2 patterns: parallel (sourcing + job design) and sequential (offer after interview)
- Dynamic pattern selection based on dependencies
- Tiered model usage with cost breakdown on Control Plane

#### 4.2 Multi-Surface Engagement
- 5 humans across 4 timezones, each on their preferred surface
- All surface inputs converge on Control Plane view
- Single agent session handles inputs from multiple humans and agents concurrently

#### 4.3 Session Durability & State
- State persistence across days/weeks (Monday start, Wednesday approval, next week interview)
- Full platform restart mid-workflow with resume from last checkpoint
- Self-healing: API timeout -> retry with backoff -> fallback to alternative
- Checkpoint inspection from Control Plane at any point

#### 4.4 Rollback & Compensating Actions
- Candidate declines -> offer retracted, headcount released, shortlist reactivated
- Distinguish revocable vs non-revocable actions
- Non-revocable actions require HITL approval before execution

#### 4.5 Voice, Video & Avatar
- Screening call via voice: real-time STT, structured questions, transcription, scoring
- Multi-party video interview with agent as note-taker
- Avatar-delivered personalised onboarding welcome video

#### 4.6 Code Interpreter & Crystallisation
- CV parsing code written and executed in sandbox
- Crystallisation pipeline: code reviewed -> tested -> versioned -> promoted to deterministic library
- Promotion requires Control Plane approval
- Bonus: Computer Use Agent for legacy HR system via Okta

#### 4.7 Memory & Knowledge
- Episodic memory: recall last 3 hires were levelled too low
- Compliance Agent grounded in local employment law
- Post-action review with proposed workflow improvements
- Memory conflict detection and resolution

#### 4.8 Analytics & Data Pipelines
- Budget Agent queries Workday + Databricks, generates cost impact analysis
- Bonus: agent creates data pipeline for weekly hiring funnel metrics

#### 4.9 Evaluation & Testing
- 500 synthetic CVs for bias/accuracy testing
- Multi-prompt eval agent testing across prompt variations
- Bonus: simulation gym at 100x speed

#### 4.10 Builder Experiences
- 3 build modes: pro-code (Python SDK), low-code (visual designer), agentic builder (natural language)
- Pre-built "Talent Acquisition" template, forkable and customisable

#### 4.11 Interoperability & Protocols
- A2A: candidate's external AI agent negotiates interview times
- MCP: Sourcing Agent discovers and uses LinkedIn MCP tool from registry

#### 4.12 Progressive Autonomy & Governance
- Confidence-based: >85% auto-shortlist, 60-85% to HR BP queue, <60% auto-reject
- Thresholds adjustable on Control Plane without redeployment
- Governance-as-code: version-controlled, audit-trailed rules
- Policy dry-run capability

#### 4.13 Tooling Infrastructure & Auth
- Platform-level auth abstraction (agent devs don't manage tokens)
- Automatic token refresh across all grant types
- REST-to-MCP gateway for Greenhouse ATS
- Agent lifecycle: dev -> staging -> production with different model versions/credentials

#### 4.14 Institutional Knowledge Capture
- Capture undocumented hiring process from SOPs, email threads, calendar patterns
- Living process model on Control Plane with drift detection

#### 4.15 Agent Identity & Authority
- Delegated authority with configurable limits, audit trail, time-bound expiry
- Agents in org directory with reporting lines
- Legal audit artefacts accessible from Control Plane

#### 4.16 Org Topology & Escalation
- Intelligent escalation based on timezone, availability, authority
- Cross-entity awareness (role in Media, budget from WPP Corp)

#### 4.17 Economic Reasoning
- Tiered model usage: cheap for keyword filtering, frontier for top 30
- End-of-workflow ROI report on Control Plane

#### 4.18 Process Evolution
- After 10 workflows, detect inefficiencies (e.g., works council causing 3-day delays)
- Improvement proposals surface on Control Plane for approval

#### 4.19 Multi-Modal Work
- Visual reasoning on candidate portfolios
- Anomaly detection on salary benchmarks

#### 4.20 Trust & Verification
- Statistical QC: 10% random sample for human review
- Agent-auditing-agent with different model/criteria
- Transparency marking on outputs
- Model failover to alternative with acceptable quality

#### 4.21 Human Supercharger (Control Plane Detail)
- Everything from Section 2 demonstrated live

#### 4.22 Infrastructure Resilience
- 500 concurrent workflows across 30 markets
- Region failure recovery with acceptable data loss
- Multi-cloud collaboration (Azure + GCP)
- Full observability across all 500 workflows

---

## 5. Assessment Questionnaire - Full Requirements (169 Questions)

### MoSCoW Summary
- **Must Have**: ~85 requirements (non-negotiable)
- **Should Have**: ~60 requirements (expected for serious contender)
- **Could Have**: ~20 requirements (differentiators)
- **Won't Have**: ~4 requirements (acknowledged as out of scope)

### Section-by-Section Requirements

#### 5.1 Platform & Vendor (Refs 1.1-3.3)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 1.1 | Cloud-native architecture with elastic scaling and serverless execution | Must |
| 1.2 | HA/DR with multi-region, RTO/RPO SLAs | Must |
| 2.1 | Market position and 12-24 month roadmap | Should |
| 2.2 | Support model and self-service resources | Should |
| 2.3 | Implementation partner ecosystem | Should |
| 3.1 | Licensing model scaling with agent count, model usage, transactions | Must |
| 3.2 | TCO breakdown: licensing, infra, implementation, training, support | Must |
| 3.3 | Case studies with quantifiable ROI | Must |

#### 5.2 System Integration & Security (Refs 4.1-5.5)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 4.1 | Pre-built connectors for HR systems (Workday) and Finance (Workday, Maconomy, D365 F&O) | Must |
| 4.2 | REST/SOAP APIs, webhooks, SDKs for custom integrations | Must |
| 4.3 | Secure write-back with validation, business rules, error handling | Must |
| 4.4 | Integration middleware/ESB for complex data flows | Should |
| 5.1 | Encryption at rest/in transit, RBAC, ABAC, MFA | Must |
| 5.2 | DLP to control data access/exfiltration by agents | Must |
| 5.3 | SOC 2, ISO 27001, GDPR, HIPAA certifications | Must |
| 5.4 | Data residency and sovereignty controls, regional deployment | Must |
| 5.5 | Version control and rollback with approval gates | Must |

#### 5.3 Core Agentic Capabilities (Refs 6.1-6.5)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 6.1 | Autonomous pattern identification and low-risk decisions | Must |
| 6.2 | Goal decomposition into multi-step tasks across systems | Must |
| 6.3 | Learning from past interactions and human feedback | Must |
| 6.4 | NLU/NLG from emails, chat, free-text fields | Must |
| 6.5 | Tool/API integration with external systems, databases, connectors | Must |

#### 5.4 Data Harmonization (Refs 7.1-7.4)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 7.1 | MDM capabilities for standardised data model across fragmented systems | Should |
| 7.2 | ETL with data quality handling | Should |
| 7.3 | Validation, de-duplication, enrichment, integrity | Should |
| 7.4 | Metadata management for lineage, definitions, relationships | Should |

#### 5.5 Governance & Oversight (Refs 8.1-8.18)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 8.1 | Centralised model registry/catalogue | Must |
| 8.2 | Model metadata: training provenance, data cutoff, licensing, parameters | Should |
| 8.3 | Model versioning to prevent silent updates | Should |
| 8.4 | Model access restriction by user group, sensitivity, environment; prevent shadow AI | Should |
| 8.5 | Centralised agent registry with use-cases and risk levels | Must |
| 8.6 | Agent metadata: capabilities, knowledge sources, tools, risk level | Should |
| 8.7 | Agent versioning for lifecycle management | Should |
| 8.8 | Agent access restriction by user group, sensitivity, environment | Should |
| 8.9 | Continuous monitoring for bias, drift, robustness | Should |
| 8.10 | Agent identity establishment, authentication, lifecycle management | Must |
| 8.11 | Integration with OAuth 2.0, OpenID Connect, Okta, Entra ID | Must |
| 8.12 | Auditability, non-repudiation, secure credential management | Must |
| 8.13 | Tool-use patterns (MCP, REST/OpenAPI), tool registry, tool-level access control | Must |
| 8.14 | Observability: traces, metrics, logs, dashboards | Must |
| 8.15 | Real-time intervention in agent execution loop | Must |
| 8.16 | Policy-as-code to prevent excessive agency | Should |
| 8.17 | Inspectability: audit model versions, prompts, tool definitions per instance | Should |
| 8.18 | Traceability: full chain-of-thought, execution path, reasoning-to-action trace | Must |

#### 5.6 Process Orchestration & HITL (Refs 9.1-10.5)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 9.1 | Low-code/no-code workflow designer: conditional logic, loops, parallel | Must |
| 9.2 | Process monitoring: re-run, terminate capabilities | Must |
| 9.3 | Exception handling: retry, notification, fallback, escalation | Must |
| 10.1 | HITL dashboard: role-based views, customisation, visual monitoring | Must |
| 10.2 | AI-driven prioritisation by criticality, SLA, confidence | Should |
| 10.3 | Contextual information: history, reasoning, agent context for quick decisions | Must |
| 10.4 | Human feedback loop into agent improvement | Should |
| 10.5 | Audit logging: granularity, immutability, customisable reports | Must |

#### 5.7 Multi-Agent Orchestration (Refs 11.1-11.5)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 11.1 | Heterogeneous teams with distinct roles, capabilities, model assignments | Must |
| 11.2 | Dynamic orchestration: sequential, parallel, hierarchical, peer-to-peer, hybrid | Must |
| 11.3 | Agent assembly: spawn sub-agents (persistent vs ephemeral) | Should |
| 11.4 | Agentic-to-deterministic crystallisation with version control | Should |
| 11.5 | Cost optimisation: tiered models, token budgets, caching, batching | Should |

#### 5.8 Multi-Surface Engagement (Refs 12.1-12.6)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 12.1 | MS Teams / Copilot 365 integration (native or bridged) | Must |
| 12.2 | Email: monitor mailboxes, parse, extract intent, compose/send | Must |
| 12.3 | Webhook / REST API endpoints | Must |
| 12.4 | A2A protocol: AgentCards, JSON-RPC, SSE, gRPC | Should |
| 12.5 | Multi-user concurrent: multiple humans + agents, role-based visibility | Should |
| 12.6 | Advanced UI: Adaptive Cards, forms, approval flows, charts, decision trees | Should |

#### 5.9 Session Management & Durability (Refs 13.1-13.5)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 13.1 | State across concurrent and sequential sessions: persistent, serialisable, inspectable | Must |
| 13.2 | Resumability across restarts, failures, handoffs with no context loss | Must |
| 13.3 | Self-healing: failure detection, retry, backoff, fallback, exception routing | Must |
| 13.4 | Rollback and compensating transactions; non-revocable flagging for HITL | Should |
| 13.5 | Periodic/event-driven checkpointing, versioned and auditable snapshots | Should |

#### 5.10 Voice, Video & Avatar (Refs 14.1-14.4)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 14.1 | Real-time STT/TTS for multi-party conversations | Could |
| 14.2 | Agents join voice/video calls as participants | Could |
| 14.3 | Avatar generation (HeyGen, Synthesia), configurable, persistent | Could |
| 14.4 | Agent-generated slide decks delivered via video avatar | Could |

#### 5.11 Code Interpreter & Crystallisation (Refs 15.1-15.4)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 15.1 | Sandboxed code execution: Python, JS, SQL minimum | Must |
| 15.2 | Crystallisation pipeline: review, test, version, promote to function library | Should |
| 15.3 | Computer Use: headless browser/VM with enterprise IDAM | Could |
| 15.4 | Script governance: approval workflow, immutability, version control, audit trail | Should |

#### 5.12 Memory & Knowledge (Refs 16.1-16.6)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 16.1 | Tiered memory: facts, procedural/rules, episodic, semantic, working memory | Must |
| 16.2 | Cross-session persistence with selective sharing and access controls | Must |
| 16.3 | Automated pruning, relevance scoring, time-based decay | Should |
| 16.4 | Grounding in knowledge bases, document stores, databases, APIs | Must |
| 16.5 | Post-action self-review: outcomes vs intent, deviations, procedural memory updates | Should |
| 16.6 | Conflict handling: detection, resolution, provenance tracking | Should |

#### 5.13 Analytics & Fine-Tuning (Refs 17.1-17.3)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 17.1 | Fine-tune on enterprise data, integrate with Databricks/Snowflake | Could |
| 17.2 | Agent-created data pipelines (Prefect, dlt, ADF, BigQuery) | Could |
| 17.3 | In-context analytics: tabular reasoning, visualisations, insights | Should |

#### 5.14 Evaluation & Testing (Refs 18.1-18.4)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 18.1 | Synthetic data generation for testing | Should |
| 18.2 | Multi-prompt evaluator agents | Should |
| 18.3 | Drift detection with automated alerts | Must |
| 18.4 | Sandboxed simulation environments | Should |

#### 5.15 Builder Experiences (Refs 19.1-19.4)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 19.1 | Pro-code SDK (Python minimum, TypeScript desirable) | Must |
| 19.2 | Low-code visual workflow builder | Must |
| 19.3 | Agentic builder from natural language specs | Could |
| 19.4 | Pre-built templates and industry accelerators | Should |

#### 5.16 Interoperability & Protocols (Refs 20.1-20.4)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 20.1 | MCP support: tool communication, discovery, MCP-exposed APIs | Must |
| 20.2 | A2A: AgentCards, task lifecycle, streaming, push notifications | Should |
| 20.3 | Cross-platform federation (Palantir, Salesforce) with security/audit | Should |
| 20.4 | Protocol extensibility for emerging protocols (UCP, AG-UI, AP2) | Could |

#### 5.17 Progressive Autonomy & Governance (Refs 21.1-21.4)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 21.1 | Configurable autonomy tiers based on risk, confidence, history | Must |
| 21.2 | Workflow crystallisation: generative -> deterministic | Should |
| 21.3 | Exception fallback from crystallised to generative | Should |
| 21.4 | Governance-as-code: version-controlled, adaptive, composable, testable | Must |

#### 5.18 Tooling Infrastructure & Auth (Refs 22.1-22.6)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 22.1 | Unified auth abstraction across OAuth 2.0, SAML, PKCE, device flow, service accounts | Must |
| 22.2 | REST-to-MCP gateway: auto-generation, parameter mapping, auth injection | Should |
| 22.3 | Full dev/test/staging/prod lifecycle with approval gates | Must |
| 22.4 | Centralised tool catalogue with metadata | Should |
| 22.5 | Integration with Azure Key Vault / HashiCorp Vault, automated credential rotation | Must |
| 22.6 | Per-tool access control: per-agent, per-environment, rate limiting | Should |

#### 5.19 Institutional Knowledge (Refs 23.1-23.4)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 23.1 | Process mining from email, docs, system interactions, meetings | Could |
| 23.2 | Knowledge extraction from transitioning staff (agent-led interviews, screen analysis) | Could |
| 23.3 | Living process models with drift detection | Could |
| 23.4 | Task mining from desktop activity | Won't |

#### 5.20 Agent Identity & Authority (Refs 24.1-24.4)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 24.1 | Agents as first-class entities in identity systems (not service accounts) | Should |
| 24.2 | Delegated authority: configurable limits, auditable, time-bound, revocable | Should |
| 24.3 | Legal audit artefacts for accountability | Must |
| 24.4 | Agent performance reviews: success rate, error rate, cost, satisfaction | Could |

#### 5.21 Org Topology Awareness (Refs 25.1-25.3)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 25.1 | Real-time organisational graph from calendar, email, collaboration signals | Could |
| 25.2 | Intelligent escalation based on expertise, availability, authority, timezone | Should |
| 25.3 | Cross-entity navigation in matrix organisation | Should |

#### 5.22 Economic Reasoning (Refs 26.1-26.4)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 26.1 | Cost-per-task optimisation: model selection, token budgets, cost-quality tradeoffs | Should |
| 26.2 | Opportunity cost reasoning: prioritise by value | Could |
| 26.3 | SLA-aware scheduling: premium compute for client-facing work | Should |
| 26.4 | ROI self-reporting per agent type | Should |

#### 5.23 Continuous Process Evolution (Refs 27.1-27.4)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 27.1 | Friction/waste detection with improvement proposals | Should |
| 27.2 | A/B testing across agent cohorts | Could |
| 27.3 | Crystallisation pipeline at scale | Could |
| 27.4 | Deprecation and dependency tracking | Should |

#### 5.24 Multi-Modal Work (Refs 28.1-28.4)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 28.1 | Document comprehension: contracts, financials, RFPs, decks with contextual reasoning | Must |
| 28.2 | Spatial/visual reasoning on layouts, diagrams, data visualisations | Should |
| 28.3 | Quantitative reasoning: anomaly detection, assumption validation | Should |
| 28.4 | Temporal/cross-market reasoning: deadlines, dependencies, timezones (100+ markets) | Should |

#### 5.25 Trust & Verification (Refs 29.1-29.6)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 29.1 | Statistical QC: sample-based auditing with configurable confidence | Should |
| 29.2 | Agent-auditing-agent: independent evaluator with separate criteria/models | Should |
| 29.3 | Anomaly detection with behavioural monitoring and alerts | Must |
| 29.4 | Transparency marking: agent-generated vs human-reviewed | Must |
| 29.5 | Multi-model resilience: failover to alternative models | Must |
| 29.6 | Circuit breakers preventing cascading failures | Should |

#### 5.26 Inter-Agent Economy (Refs 30.1-30.3)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 30.1 | Work marketplace: task negotiation, SLA agreement, delivery | Could |
| 30.2 | Reputation scoring between agents | Could |
| 30.3 | Resource contention resolution, deadlock detection | Should |

#### 5.27 Human Supercharger / Control Plane Detail (Refs 31.1-31.6)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 31.1 | Mission control dashboard: 10-50 agents, real-time status, filterable | Must |
| 31.2 | Exception-only surfacing with intelligent filtering | Must |
| 31.3 | Instant situational awareness: full context in seconds | Must |
| 31.4 | Bulk oversight with configurable batch policies | Should |
| 31.5 | Skill amplification: decision-support, coaching, knowledge augmentation | Should |
| 31.6 | Human performance analytics | Could |

#### 5.28 Regional Sovereignty (Refs 32.1-32.5)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 32.1 | Data residency enforcement at runtime (inference, tool calls, memory, logging) | Must |
| 32.2 | Regional governance gates in deployment pipelines | Must |
| 32.3 | Runtime compliance monitoring across sovereignty boundaries | Must |
| 32.4 | Jurisdiction-aware behaviour adaptation (declarative per jurisdiction) | Should |
| 32.5 | EU AI Act conformity: assessment, human oversight, transparency, risk classification | Must |

#### 5.29 Infrastructure Resilience (Refs 33.1-33.6)
| Ref | Requirement | Priority |
|-----|------------|----------|
| 33.1 | HA architecture: active-active/passive, RPO/RTO, failover automation | Must |
| 33.2 | Capacity planning at 10x, 50x, 100x scale with cost modelling | Should |
| 33.3 | Multi-cloud: Azure, AWS, GCP, on-premises | Should |
| 33.4 | Dependency isolation and exit strategy | Must |
| 33.5 | Cross-region replication, DR for in-flight workflows | Must |
| 33.6 | Observability at scale: OpenTelemetry, millions of traces/day | Must |

---

## 6. System Integrations Required

### Identity & Auth
- **Okta**: Primary IdP, SAML-bridged access to business systems
- **Microsoft Entra ID**: Agent identity, cross-tenant access (7 M365 tenants)
- **OAuth 2.0 flows**: AuthCode, Client Credentials, SAML-bridged, PKCE, device flow, OBO

### Business Systems
| System | Auth Method | Integration |
|--------|-----------|-------------|
| Workday | SAML-bridged via Okta | HR data, headcount, budget |
| LinkedIn Recruiter | OAuth 2.0 Authorization Code | Sourcing |
| Greenhouse ATS | API App Credentials | Applicant tracking |
| Microsoft Graph | On-behalf-of | M365 data, calendar, email |
| ServiceNow | API key | IT provisioning |
| Dynamics 365 F&O | Native | Finance |
| Maconomy | REST adapter | Finance |
| SAP BFC | Custom connector | Finance |
| Databricks | - | Analytics, data |
| Snowflake | - | Analytics, data |

### Agent Surfaces
- MS Teams / Copilot 365
- Email (Exchange Online)
- Web portal (React)
- Power Apps
- Webhook / REST API
- ServiceNow (IT Ops)

---

## 7. Non-Functional Requirements

| NFR | Target |
|-----|--------|
| Availability | 99.9% per region (Azure SLA backed) |
| RTO | < 5 minutes cross-region failover |
| RPO | Minimal step/data loss via geo-replicated checkpoints |
| Control Plane latency | < 5 seconds |
| Concurrent workflows (pilot) | 5,000+ |
| Concurrent workflows (prod) | 50,000+ |
| Audit log retention | 7+ years (immutable) |
| Data residency | Platform-level enforcement, 60+ Azure regions |
| Workflow state | Survives full platform restart |

---

## 8. Evaluation Criteria & Scoring

### Weighting (in order of priority)
1. **Control Plane** - Is it a genuine fleet management interface, or a chat wrapper? (highest weight)
2. **Demonstrated beats stated** - Live demo required; slides do not constitute evidence
3. **Honesty about gaps** - "We cannot do this" scores higher than vague roadmap commitments
4. **Architecture coherence** - Does the platform hold together as a system?
5. **Operational readiness at scale** - 500 agent teams, 50,000 humans

### Response Format Required Per Section (4.1-4.22)
| Category | Description |
|----------|-------------|
| Can do today | GA capability with live demonstration |
| Can do with customisation | Bespoke development, estimated effort |
| On roadmap | Planned, expected availability date |
| Cannot do | Not supported, not planned, propose alternative |
| Score | 0-5 per Assessment Criteria scale |

### Additional Deliverables
- Control Plane design: wireframe or live demo (primary evaluated deliverable)
- C4 container diagrams (Context, Container, Component)
- Acceptance criteria per demonstration item

---

## 9. Key Differentiating Themes

### What WPP Values Most
1. **Control Plane is king** - This is the defining requirement. Everything else is secondary.
2. **Fleet management, not chat** - 1:20-50 human-to-agent ratio, not 1:1 conversations
3. **Exception-only paradigm** - Humans see only what needs attention
4. **Governance-as-code** - Version-controlled, audit-trailed, testable policies
5. **Open standards** - A2A, MCP, OpenTelemetry, no vendor lock-in
6. **Honesty** - Gaps acknowledged > roadmap hand-waving
7. **Crystallisation** - Generative -> deterministic over time
8. **Progressive autonomy** - Configurable, adjustable, measurable

### What Will Score Zero
- Presenting a chatbot as a Control Plane
- Teams approval cards as the governance surface
- Single-agent demos without fleet context
- Slides without live demo
- Marketing claims without evidence

---

## 10. Timeline

| Milestone | Date |
|-----------|------|
| Vendor Brief issued | 31 Mar 2026 |
| Vendor Q&A window | 1-15 Apr 2026 |
| Written response deadline | 23 Apr 2026 |
| Vendor shortlist | TBD |
| Live POC demo | TBD (half day) |
| POC 1 build | 8 weeks |
| POC 2 build | 12 weeks (after POC 1) |
| Total programme | ~24 weeks |

---

## 11. Appendix: Regional Sovereignty Exercise (Shortlist Only)

Issued to shortlisted vendors as a differentiator. Scenario reframed to Germany:

- **B.1**: Data residency enforcement - candidate PII cannot reach US-hosted model endpoint
- **B.2**: German employment law - BetrVG works council, co-determination, GDPR
- **B.3**: Jurisdiction switching - identical workflow for UK hire, automatic rule adaptation
- **B.4**: EU AI Act conformity for high-risk automated screening
- **B.5**: Runtime compliance monitoring for sovereignty violations
