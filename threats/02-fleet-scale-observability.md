# Threat 2: Fleet-Scale Orchestration & Observability
**Severity: Critical**
**Refs: 31.1-31.6 (Must), 8.14 (Must), 8.18 (Must), 33.6 (Must), POC2 4.22**

## The Attack

GHCP SDK is designed for single-agent sessions. WPP requires a fleet management model: 1 human overseeing 15-50 concurrent agent workflows, with real-time observability across the entire fleet.

The Foundry Control Plane provides APIs for observability, evaluation, and compliance — but does GHCP SDK running as a Hosted Agent actually emit telemetry to those APIs? The Pulse Agent writes JSONL files locally. That's fine for a single daemon, but WPP needs:

- Real-time fleet dashboard across 500+ concurrent workflows (31.1, Must)
- Exception-only surfacing — intelligent filtering of the 2% needing attention (31.2, Must)
- Instant situational awareness — full context in <5 seconds (31.3, Must)
- End-to-end OTEL tracing: inputs, reasoning steps, tool calls, outputs, latency, cost (8.14, Must)
- Full chain-of-thought and execution path traceability (8.18, Must)
- Unified observability at millions of traces/day (33.6, Must)

## What We'd Need to Build

- OTEL instrumentation in GHCP SDK sessions (or confirm Foundry Hosted Agents provides this)
- Telemetry aggregation layer feeding the custom Control Plane UI
- Real-time event streaming (WebSocket/SSE) from agent sessions to fleet dashboard
- Cost attribution per agent, per workflow, per model call
- Session-level trace reconstruction for situational awareness drill-down

## Research Questions

1. Do Foundry Hosted Agents automatically emit OTEL traces for GHCP SDK sessions?
2. What telemetry does the GHCP SDK natively produce? Can we hook into it?
3. Does the Foundry Control Plane API support real-time streaming or is it polling-based?
4. How do Foundry's built-in evaluators work with Hosted Agents — do they apply to GHCP SDK sessions?
5. What's the actual architecture for getting agent reasoning traces into a fleet dashboard?
