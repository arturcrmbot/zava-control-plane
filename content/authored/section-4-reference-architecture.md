WPP's processes span a spectrum. Some phases are rule-driven and must be deterministic — three-way PO match, jurisdiction routing, payment file generation, JML provisioning. Others require reasoning over unstructured input — CV triage, voice screening, compliance narrative review. A 12-week hiring process is a sequence of deterministic scaffolding gates with agentic reasoning inside specific steps. The architecture expresses this spectrum explicitly across three cooperating execution layers, with a Fleet Manager observing from above, a central governance layer, and a custom Control Plane UI. Deterministic by default, agentic by exception. (Solution §1.)

## Three-layer execution model

A WPP workflow is a Durable Functions orchestration that coordinates Microsoft Agent Framework (MAF) workflow graphs whose agent nodes invoke GHCP SDK sessions. DF provides long-running durability at zero compute; MAF provides the deterministic graph shape of a phase with typed data flow; GHCP SDK is the LLM runtime with hooks, MCP, skills, and OTEL. (Solution §1, §7.)

**Layer 1 — Durable envelope.** Azure Durable Functions (GA): one orchestration instance per workflow. Owns phase boundaries, HITL waits at zero compute for days or weeks, timer escalation, parallel fan-out/fan-in, and checkpoint/replay with geo-replicated state in Azure Storage. Durable Functions is event-sourced and replay-based — the Azure-native equivalent of Temporal, with identical checkpointing semantics. Where WPP's Apex diagrams reference Temporal as the expected state store, Durable Functions provides the same guarantees natively on Azure and composes with MAF via Microsoft's productised Durable Agent Orchestration pattern.

**Layer 2 — Workflow graph.** MAF workflows (v1.0 GA) connect to DF through the MAF durable task extension. Each phase is a graph of typed executors: plain-function executors for deterministic operations, agent executors where LLM reasoning is required, and validator executors between them. The judge/executor pattern is expressed as two nodes and an edge — the judge does not share the executioner's context. Pregel BSP execution. MAF's native pause, resume, and checkpointing are preserved across DF replay.

**Layer 3 — Agent executor contents.** Ephemeral GHCP SDK sessions, invoked only from MAF agent executor nodes. Each session loads SKILL.md skills and MCP tools, reasons, calls tools through pre/post hooks, writes state to Cosmos DB, emits OTEL, and returns a typed result. Primary runtime is Foundry Hosted Agents (preview). Where Hosted Agents preview constraints apply, the same GHCP SDK + MAF composition runs on Azure Container Apps (GA) with Foundry telemetry — functional difference is negligible, and the runtime layer remains replaceable.

| Layer | Substrate | Determinism |
|---|---|---|
| Durable envelope | Azure Durable Functions (GA) | Fully deterministic; event-sourced replay |
| Workflow graph | MAF workflows + durable task extension (GA) | Deterministic by default, agentic by exception |
| Agent executor | GHCP SDK sessions (Hosted Agents or Container Apps) | Probabilistic reasoning sandboxed, wrapped by hooks |

## Skill crystallisation

Proven patterns move left along the spectrum. A phase that starts as an agent executor, is validated downstream, and is stable over N completed workflows is crystallised: promoted from LLM-generated to deterministic code, versioned as a skill in Azure API Center (Design → Preview → Production → Deprecated), and swapped into the MAF graph as a plain-function executor. The agent executor remains as exception fallback. The system gets cheaper, faster, and more predictable as it matures — without re-architecting. Skills are SKILL.md files in Git, registered via GitHub Actions; every step is PR-reviewable and auditable. (Solution §1, §3.)

## Central governance

Governance sits alongside all three tiers.

- **API Center + APIM AI Gateway (GA).** One control point for everything addressable by an agent. API Center: registry, lifecycle, GitHub Actions sync, cross-cloud discovery (Azure, GCP, AWS, on-prem). APIM AI Gateway: model load balancing, failover, token rate limits, per-workflow budgets, semantic caching, jurisdiction-based routing, MCP governance (auth, rate limiting, content safety), A2A governance (preview), REST-to-MCP auto-generation.
- **Foundry Control Plane (GA).** Agent fleet inventory, model registry over the Foundry catalogue, Guardrails (PII, Task Adherence), built-in evaluators for quality, safety, drift. Platform governance; sits alongside the custom operator Control Plane UI that delivers WPP's one-to-fifty fleet management requirement.
- **Agent 365 + Entra (GA May 2026).** Entra Agent ID, agent registry, lifecycle, Conditional Access, Purview DLP, Defender. Entra Agent ID is usable independently today; full Agent 365 integration lands May 2026 and is scoped accordingly in the delivery plan.

## Intelligence Layer

Agents need three kinds of grounding — enterprise documents, business semantics, and work context. Microsoft has a purpose-built product for each. All three are MCP-addressable and sit behind APIM AI Gateway, governed identically to any other tool.

- **Foundry IQ (preview)** — unified agentic retrieval over enterprise corpora. Self-reflective query planner. Federates SharePoint, Fabric, OneLake, Blob, AI Search, web, and MCP behind one permission-aware endpoint. Built on Azure AI Search.
- **Fabric IQ (preview)** — semantic layer over WPP's Fabric and OneLake estate. Business ontology, semantic model, graph engine for multi-hop reasoning. Federates WPP's Databricks and Snowflake data via OneLake shortcuts with Unity Catalog access control preserved.
- **Work IQ MCP (preview)** — Microsoft 365 work graph and memory layer. Consumed by Personal Agents and escalation routing.

The stack separates a GA foundation from a replaceable agent runtime. The foundation — Durable Functions, APIM AI Gateway, API Center, Cosmos DB, Foundry runtime, MAF v1.0, Entra, Log Analytics, Application Insights — is GA and production-proven. The agent runtime is GHCP SDK today. Because skills are SKILL.md files and tools are MCP servers (both open standards), the runtime is replaceable without redesigning the stack. If GHCP SDK stalls or WPP prefers a different runtime, the runtime swaps; skills, tools, workflow graphs, governance, data layer, and Control Plane remain. Preview-layer risk is confined to the agent runtime, not distributed across the stack. (Response-technical-sections §4.1 Appendix.)
