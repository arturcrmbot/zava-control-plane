# Section 6 — Multi-Agent Orchestration and Durability

WPP's POC 2 brief describes a "9+ specialist agents" hiring team; the Apex reference diagrams name Temporal as the expected workflow state store. This section addresses multi-agent coordination and long-running durability on the Azure-native stack WPP has standardised on.

## 6.1 Two coordination substrates, layered

**Within a phase — MAF workflow graph.** Microsoft Agent Framework workflows (v1.0 GA) execute each phase as a graph of typed executors under Pregel BSP semantics. Typed edges; first-class fan-out and fan-in; conditional routing into recovery branches; validator executors between agent output and any non-revocable action; native pause/resume. The stable MAF orchestration patterns — sequential, concurrent, handoff, group chat, Magentic-One — cover the multi-agent topologies WPP requires.

**Across phases — Azure Durable Functions.** A single DF orchestration owns the long-running envelope: phase boundaries, HITL waits at zero compute for days or weeks, timer-driven escalation, checkpoint/replay, geo-replicated state in Azure Storage. Each phase's MAF workflow is invoked as a durable activity via the MAF Durable Task extension; MAF's own pause/resume and checkpointing are preserved across DF replay.

## 6.1a Durable Functions as the Azure-native equivalent of Temporal

WPP's Apex diagrams (`WPPET-4-Apex-diagrams.pdf`) reference Temporal as the expected workflow state store: "e.g. Temporal · Durable · Checkpointed". Durable Functions provides the same execution model: event-sourced history, deterministic replay-based recovery, checkpointed state in geo-replicated Azure Storage, zero-compute waits for external events, timer-driven escalation, and compensating-action patterns for sagas.

The differences are cloud-native integration and licensing. DF is first-class in Azure Functions, co-deployed with APIM, Event Grid, and SignalR without additional workflow infrastructure. It is GA and bundled with the Azure Functions consumption plan — no separate Temporal Cloud subscription and no self-hosted Temporal cluster to operate. For WPP's Temporal mental model, DF is a drop-in conceptual equivalent on the Azure surface already in place.

## 6.2 The Durable Agent Orchestration pattern

Microsoft productised the DF + MAF + SignalR composition in February 2026 as the Durable Agent Orchestration pattern, documented in the Microsoft Learn tutorial "Orchestrate durable agents". It is the architectural backbone of this response: DF as the long-running envelope, MAF workflows as the phase-internal graph, SignalR as the real-time channel to humans and the Control Plane. The integration points — MAF Durable Task extension, checkpoint interleaving, external-event plumbing — are maintained by Microsoft.

## 6.3 Agent executors and GHCP SDK sessions

GHCP SDK sessions on Foundry Hosted Agents are invoked only from MAF agent executor nodes. They are ephemeral: each session loads the required skills and MCP tools, reasons, calls tools through hooks, emits OpenTelemetry spans, and returns a typed result to its MAF executor. Identity comes from the Hosted Agent container — on-behalf-of the triggering human for human-initiated phases, app-only for autonomous phases. Hosted Agents are preview with a five-replica cap; Azure Container Apps is the GA fallback with the same governance posture.

## 6.4 Skills, not separate agents — the architectural choice

POC 2 names Budget, Job Design, Sourcing, Triage, Screening, Interview Coordinator, Compliance, Offer, Onboarding, and Voice Screening. The brief's mental model is one independent agent process per role with inter-agent protocol between them.

We implement the same capabilities with a different topology: one domain-scoped Hosted Agent per domain (Hiring, Finance, Compliance) running ephemeral GHCP SDK sessions from MAF agent executors, each loading a different **skill** per phase. Each skill declares its own role, tool allow-list, model assignment, and governance rules. Specialisation is preserved; the coordination substrate is a MAF workflow graph with typed edges and validator nodes, not an A2A protocol between separate processes.

| Dimension | 9 separate specialist agents | Skills-based (our approach) |
|---|---|---|
| Specialisation | 1 agent per role, distinct identity per role | 1 skill per role, distinct role definition + tool allow-list + model per skill |
| Coordination substrate | A2A protocol between agents (JSON-RPC / SSE) on every handoff | MAF workflow graph edges — in-process, typed, deterministic |
| Identity surface | 9 Entra Agent IDs per domain, 9 Conditional Access policies, 9 audit identities | 1 domain Entra Agent ID; policy + audit segmentation at the skill layer via APIM |
| Context sharing | Each agent re-grounds or serialises context across the A2A boundary | Shared workflow state in the MAF graph; no re-grounding |
| Latency | N × retrieval + N × inference + N × network hops | 1 × shared retrieval + N × inference; zero inter-agent network hops within the graph |
| Cost | N × working-memory tokens; every A2A handoff re-establishes context | Amortised working memory; context flows down MAF edges |
| Failure modes | Network partition between agents; protocol version drift; handoff races | In-process graph execution; Pregel BSP guarantees deterministic fan-in |
| Debuggability | N separate OTEL traces per workflow; stitching via correlation IDs | Single MAF workflow trace per phase; natural parent-child span hierarchy |
| Governance surface | Per-agent governance — 9 APIM policy sets to keep aligned | Per-skill governance with one shared domain identity; fewer drift points |
| Operationalisation at fleet scale | 9 × N workflows of agent instances to monitor, scale, restart | N workflows × one domain pool of Hosted Agents; skills load in ~ms |
| Matches "specialist team" mental model | Yes | Yes — skills are the specialists; the graph is the team |

**What WPP gets either way:** heterogeneous expertise per phase (skills with distinct models and tools); role-based authority and tool access (skill-declared allow-lists enforced at APIM); auditability per role (skill-tagged OTEL spans and audit ledger entries); independent evolution per role (skill-versioned artefacts in API Center).

**What WPP avoids:** 9× identity, governance, and operational overhead per domain; inter-agent protocol failure modes; latency and cost of re-grounding across every handoff; debugging a correlation-ID graph instead of a single workflow trace.

*If WPP evaluators prefer the separate-agent topology after review, both are supported by MAF; a hybrid is supported (skills inside a domain, A2A across domains).*

## 6.5 A2A where it belongs

Agent-to-agent protocols are the right choice when an agent is genuinely off-platform. Partner candidate agents, supplier pricing agents, and jurisdictional compliance authorities owned by another organisation interact through APIM A2A governance (AgentCards, JSON-RPC task lifecycle, SSE streaming). Agent-process separation applies at the organisational boundary; skill-based specialisation applies at the domain boundary.

## 6.6 HITL pattern in detail

For long waits across phase boundaries, the MAF agent executor detects that human input is required, composes the message or Adaptive Card, and routes it via the human's preferred surface through their Personal Agent. The executor signals the DF orchestration to suspend; DF issues `wait_for_external_event` and holds at zero compute until the human responds. The response reaches DF as a `raise_event` call, unblocking the orchestration into the next phase. Bulk approval raises events on multiple DF instances simultaneously from a single operator action in the Control Plane. For shorter-lived HITL within a phase, MAF's native pause/resume handles the wait without descending into the DF layer.

## 6.7 Supported topologies

Both substrates adapt based on runtime data, not static DAGs. Supported end-to-end: sequential (interview coordination after CV screening); parallel fan-out / fan-in (sourcing and job design concurrently, results joined downstream); conditional (a compliance flag from a validator executor triggers an additional review branch without modifying the base workflow); timer escalation (DF timers escalate unresolved HITL waits to a second approver or the Fleet Manager queue); bulk HITL (one operator decision raises events on many DF instances in parallel).
