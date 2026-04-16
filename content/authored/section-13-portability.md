Lock-in is mitigated at every layer of the stack. The architecture separates a GA foundation — Azure Durable Functions, APIM AI Gateway, Azure API Center, Cosmos DB, the Azure AI Foundry runtime, Microsoft Agent Framework v1.0, Entra, Log Analytics, Application Insights — from a replaceable agent runtime layer. The foundation is production-proven; the agent runtime layer is GHCP SDK today. Because skills are SKILL.md files and tools are MCP servers (both open standards), the agent runtime can be replaced without redesigning the stack. If GHCP SDK stalls or WPP prefers a different runtime, the runtime swaps and skills, tools, workflow graphs, governance, the data layer, and the Control Plane all remain. Preview-layer risk is confined to the agent runtime, not distributed across the stack.

| Layer | Portability |
|---|---|
| Agent logic | GHCP SDK is open-source (MIT). Skills are SKILL.md markdown files. WPP retains the ability to self-host, fork, or migrate. |
| Models | GHCP SDK works with any model in the Foundry catalog (1,900+, including OpenAI, Anthropic, Google, Meta, Mistral, and open-source models). Switching a model is an APIM configuration change. |
| Tool layer | MCP is an open standard. All enterprise integrations are MCP servers, portable to any MCP-compliant platform. |
| Interoperability | A2A is an open standard. Agent definitions using A2A are portable across platforms. |
| Telemetry | OpenTelemetry is an open standard. Traces are portable to any OTEL-compatible backend. |
| State | Workflow state is JSON in Cosmos DB, exportable via standard APIs. Durable Functions state in Azure Storage is extractable. |
| Orchestration | Durable Functions is Azure-specific. The pattern (event-driven workflow orchestration with event-sourced replay) is reproducible on Temporal, AWS Step Functions, and similar substrates. |
| Policies | APIM policies are exportable. Governance rules are in version-controlled configuration. |

Exit strategy: export skills (Git), export MCP servers (code), export state (Cosmos DB export), export policies (APIM export). The agentic logic lives in portable artefacts.

The preview-dependency position stated honestly: the GA foundation listed above is the load-bearing layer. The agent runtime is preview today and replaceable. The table below lists known constraints and their mitigations.

| Constraint | Impact | Mitigation |
|---|---|---|
| GHCP SDK in tech preview | API surface may change | Core patterns (skills, MCP, hooks) are proven in production inside GitHub Copilot, which serves millions of developers daily. MIT open-source. Skills and MCP tools port to any MCP-native runtime without redesign. |
| Microsoft Agent Framework v1.0 (released Oct 2025) | Framework is young | Core runtime and workflows are GA. The MAF Durable Task extension for Azure Functions is productised by Microsoft as the Durable Agent Orchestration pattern (Feb 2026). Orchestration patterns are stable. Fallback: GHCP SDK + Durable Functions combination works without MAF. |
| Foundry Hosted Agents: not GA (max 5 replicas in preview) | Scaling ceiling | Azure Container Apps + GHCP SDK + MAF Workflow provides a GA-today alternative with equivalent functionality. Difference vs Foundry Hosted Agents is negligible at the architectural level. |
| Foundry Guardrails tool-call / tool-response interception (preview) | May not be GA by POC | GHCP SDK session hooks provide equivalent enforcement at code level. Guardrails are additive. |
| APIM A2A governance (preview) | A2A features maturing | Not required for core architecture; used in POC2 for external candidate agent demo. HTTP gateway primitives work today. |
| API Center skill registry (preview) | No native Git sync | GitHub Actions workflows synchronise SKILL.md files. Core skill execution is GHCP SDK native. |
| GHCP SDK + Foundry Hosted Agents integration | Hosting adapter needs custom work | Primary integration engineering task for the POC. Container Apps path avoids this adapter entirely. |
| Agent 365 GA: May 2026 | Not GA today; integration with Hosted Agents unclear | Entra Agent ID is usable independently; the Agent 365 umbrella (admin-center lifecycle, cross-service governance flows) GAs in May 2026. |
| Foundry IQ / Fabric IQ / Work IQ in public preview | Intelligence Layer APIs evolving | All three are MCP-addressable with fallbacks to direct Azure AI Search + Fabric SQL + Graph API queries. Upgrade path, not single point of failure. |
| MAI-Transcribe-1 and MAI-Voice-1 (preview, GA Q4 2026) | No SLA | GPT-Realtime (GA) is the primary voice path. MAI models are additive. |
| Copilot Studio on Foundry Hosted Agents | Not supported | Copilot Studio agents are governed via Agent 365 with Entra Agent ID and full Purview/Defender coverage. Copilot Studio artefacts (declarative YAML, Power Platform solutions) are Git-committable via Power Platform ALM and meet §6.5 serialisation parity through the shared governance pathway. |
