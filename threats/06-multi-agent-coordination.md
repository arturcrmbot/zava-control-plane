# Threat 6: Multi-Agent Coordination at Scale
**Severity: High**
**Refs: 11.1-11.5 (Must/Should), 12.5 (Should), POC2 4.1, 4.22**

## The Attack

WPP requires 10+ specialist agents collaborating on a single workflow, with 15-50 such workflows running concurrently. The solution proposes an Orchestrator Agent that dispatches work to specialists via `send_task_to_agent`.

Known SDK issues:
- Sub-agent MCP inheritance broken (CLI #693) — sub-agents can't access parent session's MCP servers
- `send_and_wait()` timeout gives no partial results, unclear session state
- No native multi-agent coordination protocol

Concrete questions the architecture must answer:
- How does the Orchestrator know when a specialist agent finishes? Polling? Event? Callback?
- If 10 specialist agents run concurrently on one workflow, how are they coordinated?
- At 500 concurrent workflows x 10 agents each = 5,000 concurrent agent sessions. Can Foundry Hosted Agents handle this?
- Agent Assembly (11.3, Should): agents spawning sub-agents at runtime. Persistent vs ephemeral lifecycle.
- Multi-user concurrent (12.5, Should): single session handling inputs from multiple humans and agents simultaneously

## The Architecture Question

Is each specialist agent:
a) A sub-agent within the Orchestrator's session (SDK sub-agent composition)
b) An independent Hosted Agent instance triggered by the Orchestrator via API/event
c) A shared pool of agent instances that pick up work from a queue

Each has very different scaling, isolation, and coordination characteristics.

## Research Questions

1. How do Foundry Hosted Agents handle concurrent instances? Is there auto-scaling?
2. What's the inter-agent communication pattern for Hosted Agents? Direct API calls? Event Grid? Service Bus?
3. Has the sub-agent MCP inheritance issue (CLI #693) been resolved?
4. Can Hosted Agents be triggered programmatically (API call with payload) or only via chat/UI?
5. What's the actual concurrency limit for Hosted Agents in a single Foundry project?
6. Is there an agent-to-agent protocol within Foundry, or is this all custom?
