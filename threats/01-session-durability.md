# Threat 1: Session Durability & Workflow Continuity
**Severity: Critical**
**Refs: 13.1-13.5 (all Must Have), POC2 4.3, 4.4**

## The Attack

GHCP SDK sessions are ephemeral. A hiring workflow spans days/weeks with multiple humans acting asynchronously (Monday request, Wednesday budget approval, next week interviews). There is no "resume session" in the SDK — each session starts fresh.

WPP explicitly requires:
- State persistence across concurrent and sequential sessions — persistent, serialisable, inspectable (13.1, Must)
- Resumability across infrastructure restarts, agent failures, handoffs — no context loss (13.2, Must)
- Self-healing: failure detection, retry, backoff, fallback, exception routing (13.3, Must)
- Rollback and compensating transactions; non-revocable actions flagged for HITL (13.4, Should)
- Periodic/event-driven checkpointing, versioned and auditable snapshots (13.5, Should)

## What We'd Need to Build

- External state store (Dataverse/Cosmos) as the continuity layer
- Event-driven session spawning: webhook/event fires -> new GHCP SDK session reads state -> continues workflow
- State serialisation format capturing: workflow progress, agent memory, pending decisions, action history
- Checkpoint versioning for "inspect any point in time" from Control Plane
- Action ledger distinguishing revocable vs non-revocable, supporting compensating actions (rollback)
- Resume logic: session reads last checkpoint, reconstructs context, continues from where it left off

## Research Questions

1. What does Foundry Hosted Agents provide for state persistence? Is there a durable state store built in?
2. Can GHCP SDK sessions be triggered by external events (webhooks, queue messages)?
3. Are there existing patterns in Azure (Durable Functions, Temporal, Dapr) that could wrap GHCP SDK sessions?
4. How does the Pulse agent handle state between sessions today? Can that pattern scale?
5. Is this actually a real problem or standard event-driven architecture that we just need to wire up?
