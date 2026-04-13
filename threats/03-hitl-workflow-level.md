# Threat 3: Human-in-the-Loop at Workflow Level
**Severity: High**
**Refs: 10.1-10.5 (Must), 8.15 (Must), 21.1 (Must), 31.4 (Should), POC2 4.12**

## The Attack

GHCP SDK's HITL model is a PermissionHandler — a function that approves or denies tool calls within a session. The Pulse Agent auto-approves everything and uses draft-first patterns for outbound actions.

WPP's HITL model is fundamentally different:
- Role-based exception routing: screening exception goes to HR BP, budget exception goes to Finance BP (10.1, Must)
- AI-driven prioritisation by criticality, SLA, confidence (10.2, Should)
- Contextual information surfaced for quick decisions (10.3, Must)
- Bulk approval: approve 8 similar decisions in one action (31.4, Should)
- Real-time intervention: intercept and modify agent execution mid-loop (8.15, Must)
- Configurable autonomy tiers adjustable at runtime (21.1, Must)

The gap: GHCP SDK sessions don't "pause and wait for human input from a dashboard." A session runs, hits a decision point, and either proceeds or fails. There's no native "park this workflow, put an item in the HR BP's exception queue, wait for approval, then resume with the decision."

## What We'd Need to Build

- Exception queue service: agents write decisions needing human input to a queue
- Control Plane UI reads queues, presents to role-appropriate human
- Approval webhook: human decides, webhook triggers new session that reads decision + state and continues
- Autonomy threshold engine: reads runtime config, decides whether to auto-proceed or queue for human
- Bulk approval API: apply one decision across multiple queued items

## Research Questions

1. Can Foundry Hosted Agents be paused/resumed externally, or is it always session-start to session-end?
2. Is there an existing approval/queue service in Azure that fits this pattern (Logic Apps, Power Automate, Service Bus)?
3. How do other Foundry customers implement HITL for hosted agents?
4. Could the PermissionHandler be made async — park the session, wait for external signal?
5. Is this just an event-driven queue pattern (agent writes to queue, human reads, approval triggers next session)?
