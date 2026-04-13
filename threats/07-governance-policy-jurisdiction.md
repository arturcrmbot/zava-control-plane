# Threat 7: Governance-as-Code & Jurisdiction-Aware Policy
**Severity: High**
**Refs: 21.4 (Must), 32.1-32.5 (Must), 8.16 (Should), POC2 4.12, Appendix B**

## The Attack

WPP requires declarative, version-controlled, testable governance policies that:
- Enforce rules across the full agent lifecycle (21.4, Must)
- Are adaptive to runtime context (jurisdiction changes behaviour)
- Are composable (inheritance between policy sets)
- Are audit-trailed with author, timestamp, rationale
- Support dry-run against historical traces (POC2 4.12)
- Enforce data residency at runtime — model inference, tool calls, memory, logging (32.1, Must)
- Adapt agent behaviour by jurisdiction automatically (32.4, Should)
- Monitor compliance continuously with near-real-time violation detection (32.3, Must)

GHCP SDK has session hooks (`on_pre_tool_use`, `on_post_tool_use`) which are Python functions. These are code-level guardrails, not declarative policy-as-code. They're not version-controlled separately, not testable independently, not composable, and don't support dry-run.

The Pulse Agent's hooks validate paths and log audit trails — useful but primitive compared to what WPP is asking.

## The Specific Challenge: Jurisdiction Switching

POC2 Appendix B: Run identical workflow for USA hire vs Germany hire. In Germany:
- Works council notification required (BetrVG)
- Candidate PII cannot reach US-hosted model endpoint
- GDPR consent management for employee data
- EU AI Act conformity for automated screening

In USA: none of these apply. The switch must be automatic based on jurisdiction, not reconfigured per agent.

With GHCP SDK: where does this logic live? In every agent's prompt? In hooks? In MCP tool config? In Foundry platform policy?

## Research Questions

1. Does Foundry provide policy-as-code enforcement that applies to Hosted Agents?
2. Can Azure Policy / Foundry compliance policies intercept GHCP SDK model calls and enforce region constraints?
3. Is there a way to make GHCP SDK hooks declarative (loaded from config/YAML rather than hardcoded)?
4. How would jurisdiction-aware behaviour work — prompt injection based on jurisdiction context, or platform-level routing?
5. Does Foundry support policy dry-run ("what if we changed this threshold")?
6. What does Entra Agent ID + Conditional Access provide for policy enforcement on agent actions?
7. Can Microsoft Purview DLP policies apply to GHCP SDK sessions (tool inputs/outputs)?
