## 9.1 One truth for how an agent is defined

WPP §6.5 sets an anti-requirement: "Low-code artefacts must serialise to the same code/config format as pro-code artefacts. No divergent runtimes." Every builder path in this architecture — pro-code, low-code, Threadlight-generated, runtime-spawned — produces declarative, Git-committable artefacts that flow through a single APIOps pipeline, register in Azure API Center, are governed by APIM, and carry Entra Agent IDs. There is one artefact shape, one governance pathway, one runtime. The builder surface changes; the serialised output and its lifecycle do not.

This is also the Phase 0 position on low-code agent construction. Microsoft Copilot Studio is the low-code answer available if WPP requires one; however, for this engagement the recommended path is MAF plus skills pro-code, because skills compose into more skills and the agentic loop expands itself. §9.3 makes the framing explicit.

## 9.2 Builder modes

| Mode | Persona | Solution |
|------|---------|---------|
| Pro-code | Platform engineers, full-stack developers | GHCP SDK Python (primary) plus TypeScript / .NET / Go for skills, MCP servers and hooks. MAF for workflow graphs in Python or .NET. MIT open-source. Recommended for complex autonomous multi-step workflows. |
| Low-code visual builder — Microsoft Copilot Studio | Citizen developers, domain experts | Microsoft's flagship low-code agent builder. Visual drag-and-drop designer with conditional branching, tool bindings (Power Platform connectors plus MCP), HITL touchpoints and knowledge grounding. Exports as declarative YAML / JSON within Power Platform solutions, Git-committable via Power Platform ALM, versioned through environments (Dev → Test → Prod), registered with Entra Agent ID under the Agent 365 umbrella (preview today, GA May 2026), governed by APIM, Purview and Defender. For this engagement, MAF plus skills pro-code is the recommended agent-construction path. |
| Low-code MCP tools — Azure Logic Apps | IT teams adding integrations without writing Python | Visual workflows chaining 1,400+ prebuilt connectors. Each Logic App is exposed as an MCP tool via the APIM REST→MCP gateway. Governed identically to hand-written MCP servers. |
| Low-code config — Custom Control Plane UI | Operators, process owners | Skill library (browse, fork, customise templates backed by Azure API Center), tool catalogue, governance editor, autonomy dials. For operational tuning, not agent construction. All changes written back to Git through APIOps. |
| 60-minute build (§6.4 benchmark) | Junior developers, seasoned UI users | Copilot Studio hits this benchmark natively: template plus 3 MCP tool connectors (pre-wired auth, rate limits, content safety) plus 3 Foundry IQ knowledge sources, then publish. End-to-end build time under 30 minutes. Scripted as an observable task for POC evaluation. |
| Agentic builder (§6.2 design-time) | Domain experts | A MAF agent executor generates SKILL.md files from natural-language specifications. Output is a typed skill definition with declared tools, model assignment and governance rules. Registered in API Center in Design state. A human reviews and approves to promote to Production. Built and demonstrated. |
| Runtime agent assembly (§6.2 runtime) | Supervising agents spawning sub-agents | MAF supports dynamic executor creation at runtime. A supervising agent executor can spawn a sub-workflow or a persistent sub-agent within a domain's Hosted Agent scope. Persistent spawned agents auto-register in Entra Agent ID and API Center (Design state) via a governance-gate callback; the spawning decision is written to the audit ledger. The agent runs in Design state until a human operator promotes it to Production — no runtime escape from governance. |
| Threadlight knowledge extraction | Transitioning staff, SMEs | Microsoft delivery accelerator, built and demonstrated. An interview-capture agent runs alongside an SME, transcribes and structures the conversation, and produces executable SKILL.md files, MAF workflow graphs and MCP tool stubs. Output enters the same API Center governance pathway as hand-written skills. All artefacts are Git-inspectable. Not a black box. |

## 9.3 Copilot Studio as primary low-code (when low-code is required)

Copilot Studio is Microsoft's flagship low-code agent builder and is the low-code answer available in this architecture. It is suitable for citizen developers and domain experts building conversational and workflow agents — assistants, approval flows, knowledge Q&A, form-driven agents — with conditional branching, Power Platform and MCP tool bindings, HITL touchpoints and knowledge grounding. Its artefacts serialise to declarative YAML / JSON within Power Platform solutions, are Git-committable through Power Platform ALM, and register with Entra Agent ID under the Agent 365 umbrella (preview today, GA May 2026), which satisfies §6.5 parity. For this engagement, MAF plus skills pro-code is the recommended path for the core WPP agent fleet: skills compose into more skills, the agentic loop expands itself through the agentic builder (§9.5) and runtime assembly (§9.6), and the deterministic graph primitives of MAF are required for the multi-step workflows described in §6.2. Copilot Studio fulfils WPP's §6.4 low-code MoSCoW requirement; it is not the recommended construction surface for the autonomous multi-phase workflows that dominate WPP's POCs.

## 9.4 60-minute build benchmark (§6.4)

Copilot Studio hits the §6.4 benchmark natively. A citizen developer picks a template, adds 3 MCP tool connectors from the APIM-governed catalogue (pre-wired authentication, rate limits and content safety), adds 3 knowledge sources from Foundry IQ, and publishes. End-to-end build time is under 30 minutes for a junior developer or seasoned UI user. The task is scripted as an observable exercise for POC evaluation, with the deployed agent registered, identity-scoped, observable and reachable from at least one surface — as required by WPP.

## 9.5 Agentic builder (design-time, §6.2)

A MAF agent executor generates SKILL.md files from natural-language specifications supplied by a domain expert. The output is a typed skill definition with declared tools, model assignment and governance rules, registered in Azure API Center in Design state. A human operator reviews the generated skill and approves it for promotion to Production. This is the mechanism by which skills build more skills within the governance pathway. Built and demonstrated.

## 9.6 Runtime agent assembly (§6.2)

MAF supports dynamic executor creation at runtime. A supervising agent executor can spawn a sub-workflow or a persistent sub-agent inside its domain's Hosted Agent scope. For persistent spawned agents, a governance-gate callback auto-registers the new agent in Entra Agent ID and Azure API Center in Design state, and writes the spawning decision to the audit ledger. The spawned agent runs in Design state until a human operator promotes it to Production. This enforces the RFP requirement that "persistent agents must be elevated into the same Data Plane storage schema as human-built agents, along the governance pathway." There is no runtime escape from governance.

## 9.7 Threadlight accelerator

Threadlight is a Microsoft delivery accelerator, built and demonstrated. An interview-capture agent runs alongside a subject-matter expert, transcribes and structures the conversation, and produces executable artefacts: SKILL.md files, MAF workflow graphs and MCP tool stubs with declared schemas. Output enters the same Azure API Center governance pathway as hand-written skills — Design state, human review, promotion to Production. All artefacts are SKILL.md, Python or YAML, fully Git-inspectable. Not a black box.

## 9.8 Code-as-Truth in practice

All agent artefacts are Git-committable and version-controlled:

- Skills: SKILL.md files in Git. Registered in Azure API Center with lifecycle management (Design → Preview → Production → Deprecated). GitHub Actions integration for syncing from repositories.
- APIM policies: version-controlled via APIOps CI/CD. PR review gates. Per-environment policy sets.
- Orchestrations: Durable Functions code in Git. CI/CD deployment with environment-specific configuration.
- Governance rules: autonomy thresholds, compliance rules and jurisdiction skills in version-controlled configuration stores with change tracking (who, when, why).
- Traceability: every routing decision, model selection and tool call is fully traceable in OTEL spans and audit logs. Every action ledger entry links to the OTEL span that produced it, including the reasoning chain and tool call that triggered it.

A team of 5 developers manages 50 agents across dev, staging and production using CI/CD pipelines with PR review gates. Non-technical auditors inspect agent authorisations, actions and rationale via the Foundry Control Plane compliance dashboard and Log Analytics KQL queries. This is the operational expression of §6.5: one artefact shape, one governance pathway, one runtime — regardless of which builder surface produced the agent.
