# Threat 4: Low-Code / No-Code Builder Experience
**Severity: Medium-High**
**Refs: 19.1-19.2 (Must), 9.1 (Must), 19.3 (Could), 19.4 (Should)**

## The Attack

WPP requires THREE builder personas (all addressing Must Have requirements):
1. Pro-code SDK — Python minimum, TypeScript desirable (19.1, Must)
2. Low-code visual workflow builder suitable for citizen developers (19.2, Must)
3. Low-code/no-code workflow designer with conditional logic, loops, parallel (9.1, Must)

GHCP SDK is prompt-first. Writing a markdown agent definition is simpler than coding MAF workflow graphs, but it is NOT a visual designer. There is no drag-and-drop, no visual workflow builder, no canvas for citizen developers.

The solution.md dismisses Copilot Studio as "not serious" — but WPP explicitly requires a visual builder for citizen developers, and it's a Must Have.

## The Tension

- Copilot Studio IS a visual builder, and it IS integrated with Foundry
- But Copilot Studio cannot do what GHCP SDK does (true autonomous multi-step reasoning)
- WPP's anti-requirement says "Copilot Studio bot is not a Control Plane" — but they're not asking Copilot Studio to BE the Control Plane, they're asking for it as a builder tool
- Could Copilot Studio be the low-code surface that produces agent definitions consumed by GHCP SDK?

## Research Questions

1. Can Copilot Studio export agent definitions that GHCP SDK consumes? Or are they fundamentally different runtimes?
2. Is there a visual builder for GHCP SDK agent definitions (prompt + skills + MCP config)?
3. Could we build a lightweight web-based agent configurator as part of the Control Plane UI?
4. Does WPP actually need citizen developers building autonomous agents, or is low-code for simpler workflows acceptable?
5. Is "prompt + YAML config" actually low-code enough to satisfy the requirement if we provide good templates and a library?
