# Zava and Constellation Story Design

**Date:** 2026-08-10
**Status:** Approved
**Scope:** Canonical product narrative, published article, and public Constellation demo
**Audience:** Enterprise leaders, architects, sellers, and delivery teams evaluating agentic transformation

## 1. Decision

Zava is a working reference implementation of an agentic organisation at
scale.

It shows how agents, people, workflows, policies, memory, and enterprise
systems can operate through one shared control plane. Customers use it as an
executable blueprint and source of inspiration, then connect their existing
systems, skills, MCPs, data, and people.

The canonical short statement is:

> **See what an agentic organisation actually looks like - and use the
> blueprint to build yours.**

The canonical explanatory statement is:

> **Zava shows how specialised agents and people can work across an
> organisation through shared workflows, skills, enterprise tools, governance,
> memory, and observability. It runs as a complete synthetic organisation so
> the pattern can be demonstrated anywhere; customers then replace the
> synthetic edges with their existing estate.**

## 2. The Customer Problem

Most demonstrations show one assistant or agent completing one task. They do
not answer the harder enterprise questions:

- What happens when agentic capabilities operate across many functions?
- How do agents share skills and enterprise integrations instead of rebuilding
  them for every use case?
- How are long-running work, retries, approval boundaries, and human authority
  coordinated?
- How can leaders see what the agentic workforce is doing?
- How does an organisation connect this pattern to systems and capabilities it
  already owns?

Zava makes that future concrete with running code rather than slides.

## 3. Product Hierarchy

| Element | Canonical role |
|---|---|
| **Zava** | The working reference implementation: substrate, workflows, agents, governance, memory, integrations, and control plane. |
| **Constellation** | The visual command surface showing the agentic workforce operating across the organisation. |
| **Vertical pack** | A concrete industry expression of the reference pattern, with relevant processes, actors, systems, authority, and terminology. |
| **compose-org** | The design-time factory that adapts the reference implementation to an organisation or industry. |
| **Simulation** | Synthetic organisational activity that keeps the demonstrator alive without requiring customer data or systems. |
| **Customer estate** | The real systems, skills, MCPs, data, people, policies, and processes connected to the pattern during adoption. |

Simulation is subordinate to the story. It exists to generate credible work,
context, consequences, and activity for the demonstrator. Zava is not
positioned as a simulation product, a digital-twin validation phase, or an
isolated rehearsal environment customers must operate before integration.

## 4. Narrative Sequence

The article, demo, seller talk track, and README must tell the story in the same
order:

1. **Isolated agents do not make an agentic organisation.** Pilots repeatedly
   rebuild orchestration, integrations, policy, identity, evaluation, and
   observability.
2. **An agentic workforce needs shared organisational infrastructure.**
   Specialised agents should compose skills and enterprise tools while durable
   workflows, policy, identity, audit, and human authority remain consistent.
3. **Zava shows the complete pattern running.** Multiple functions, workflows,
   agents, personae, and systems operate through one control plane.
4. **Constellation makes the workforce visible.** A viewer can see work begin,
   agents use skills and tools, policy intervene, people approve, and work
   resolve.
5. **The customer does not start again.** Existing systems, agent investments,
   skills, MCPs, and policies connect to the shared pattern incrementally.

The printing-press analogy remains useful because it explains reuse and
compounding. It supports this narrative; it is not the product definition.

## 5. Capability Model

Zava demonstrates seven capabilities as one coherent system:

1. **Organisation-wide coordination** - many business functions and workflows
   operate concurrently rather than as disconnected assistants.
2. **Specialised agentic work** - agents select and execute bounded skills
   inside deterministic workflow and approval boundaries.
3. **Reusable enterprise connectivity** - MCP adapters and shared tools are
   available to every authorised agent instead of being rebuilt per use case.
4. **Durable execution** - long-running workflows preserve state across
   retries, failures, and human decisions.
5. **Governed authority** - identity, capability policy, delegated authority,
   validation, audit, and human escalation constrain every action.
6. **Organisational context** - personae, memory, and the knowledge graph give
   work continuity across domains.
7. **Unified visibility** - Constellation and the operator surfaces expose work,
   decisions, tools, policies, and outcomes across the organisation.

Vertical packs prove that the pattern can express materially different
industries without turning Zava into a collection of unrelated demos.

## 6. What Is Real and What Is Synthetic

The story must distinguish implementation truth from demonstration data.

### Real

- executable application code;
- Durable workflows and checkpoints;
- agent sessions, skills, and MCP boundaries;
- governance, authority, validation, and audit paths;
- memory and knowledge projections where enabled;
- runtime events and recorded replay telemetry;
- browser and API surfaces;
- vertical build and proof contracts.

### Synthetic or stubbed

- the demonstrated organisation and operating records;
- simulated people and personae unless a real participant is connected;
- actor-world activity used to create credible work;
- external business systems represented by mock MCPs;
- generated shocks, demand, entities, and scenarios.

The synthetic layer is replaceable scaffolding. It must never be described as a
mandatory customer adoption stage.

## 7. Customer Adoption Story

Customers should connect their estate sooner rather than later:

1. Use Zava to understand the target operating pattern and select a valuable
   cross-functional journey.
2. Keep the customer's existing agent, workflow, integration, and policy
   investments where they fit.
3. Replace the relevant synthetic MCPs and records with existing systems and
   data.
4. Connect real skills, policies, and people at the same boundaries used by the
   demonstrator.
5. Expand across functions while reusing the shared control-plane capabilities.

The handoff is not "run the simulation first, then begin integration." It is
"use the running reference to agree the pattern, then make its edges real."

## 8. Published Article Design

The article remains an external positioning piece rather than a build manual.

### Opening

Lead with:

> **See what an agentic organisation actually looks like - and use the
> blueprint to build yours.**

The current "Why your agentic strategy isn't moving the needle" argument can
remain as the problem statement. The opening must quickly contrast isolated
agent pilots with an organisation-wide agentic workforce.

### Structure

1. Isolated initiatives repeatedly rebuild the same foundations.
2. The printing press explains why shared infrastructure compounds.
3. Zava is introduced as a working reference organisation, not merely a
   substrate diagram.
4. The shared harness, skills, MCPs, governance, memory, and workflows are
   explained as the infrastructure of an agentic workforce.
5. Constellation shows that workforce operating across functions.
6. Vertical packs show that the pattern generalises.
7. The close explains how customers connect their existing estate.

### Required corrections

- Do not present simulation as the product or adoption strategy.
- Do not imply that customers should replace existing investments wholesale.
- Do not let workflow, skill, MCP, or domain counts substitute for the business
  argument.
- State clearly which demonstrated data and systems are synthetic.
- Make every material claim traceable to code or visible evidence.
- Preserve the printing register only where it makes the central argument
  clearer.

## 9. Constellation Demo Design

Constellation is the visual proof of an agentic workforce at scale, not a
standalone cosmic visualisation.

### Default journey

1. **Orient:** one sentence explains that the viewer is watching a working
   agentic organisation.
2. **Show scale:** the default view exposes concurrent activity across business
   functions and domains.
3. **Follow one decision:** a guided cross-functional journey zooms from
   organisation-wide activity into one workflow and back out again.
4. **Expose the shared substrate:** the viewer sees skills, tools, validation,
   policy, personae, and Durable execution participating in that journey.
5. **Make governance visible:** authority decisions, escalations, denials, and
   approvals are named rather than represented only as colour or motion.
6. **Connect to reality:** a concise handoff identifies the synthetic edges and
   shows where customer systems, skills, MCPs, policies, and people connect.

The existing Aurora budget-pressure cascade remains a useful cross-functional
guided example because it links operational data, CFO observation, governed
policy, in-flight work, and CEO synthesis. It is a zoom-in proof point, not the
definition of Zava. Telco, airline, and other packs remain additional evidence
that the same substrate supports different organisations.

### Visual rules

- Every animated event must correspond to runtime or recorded telemetry.
- Business meaning must be readable without the presenter decoding colours.
- The organisation-wide view comes before technical drill-down.
- "Live" and "replay" modes must be labelled truthfully.
- A viewer must be able to distinguish shared substrate capabilities from
  pack-specific behaviour.
- Simulation controls remain presenter tools, not the primary public call to
  action.

## 10. Claim-to-Evidence Contract

| Claim | Required evidence |
|---|---|
| Agentic workforce at scale | Concurrent activity across multiple functions and domains in Constellation and workflow APIs. |
| Shared capabilities compound | Composition data and events showing different workflows reusing skills, MCPs, governance, and workflow infrastructure. |
| Agents remain governed | Named authority result, policy decision, validator result, or audit entry attached to the guided journey. |
| Long-running work is durable | Workflow state and checkpoint progression through agent and human boundaries. |
| It connects to the existing estate | Explicit MCP, skill, policy, persona, and data boundaries plus a synthetic-to-real replacement map. |
| It is running code, not slides | Live or clearly labelled recorded telemetry traceable to workflow and audit identifiers. |
| The pattern generalises | Proven vertical packs using the same substrate contracts with materially different industry behaviour. |

Claims without evidence are removed, narrowed, or labelled as forward-looking.

## 11. Shared Language

Use these terms consistently:

- **agentic organisation** or **agentic workforce at scale** for the outcome;
- **working reference implementation** or **executable blueprint** for Zava;
- **shared control plane** or **shared substrate** for the reusable foundation;
- **Constellation** for the visual command surface;
- **vertical pack** for an industry expression;
- **synthetic organisational activity** for demonstration scaffolding;
- **connect your existing estate** for adoption.

Avoid making these the headline:

- digital twin;
- simulation platform;
- validation environment;
- workflow catalogue;
- agent framework;
- autonomous enterprise.

## 12. Truth Boundaries

- Zava remains a proof of concept and reference implementation, not a packaged
  production platform.
- Public replay is recorded telemetry and must not be described as live.
- Synthetic data and mock systems must remain explicit.
- Zava demonstrates a scalable operating pattern; it does not claim that every
  business decision should be autonomous.
- Human authority and existing enterprise investments are part of the target
  model, not transitional inconveniences.
- The story must not outrun the proof status of a vertical or capability.

## 13. Persistence and Change Control

This document is the canonical narrative contract until an explicit replacement
is approved.

Implementation must:

1. link this contract from the repository documentation index and README;
2. keep this file as the only long-form narrative authority; shorter summaries
   must link back here and may not introduce new claims;
3. make the article, cloud demo, seller talk track, and deployment documentation
   use the shared language in section 11;
4. maintain the claim-to-evidence table as capabilities change;
5. record any deliberate narrative change in a new approved design rather than
   allowing copy to drift independently.

## 14. Implementation Decomposition

The work splits into four ordered tracks:

1. **Story contract and documentation alignment** - establish the living story,
   terminology, and evidence map.
2. **Article realignment** - revise the published essay without changing claims
   ahead of implementation truth.
3. **Constellation narrative journey** - add orientation, scale, guided evidence,
   and the synthetic-to-real handoff.
4. **Cloud proof and deployment** - publish a truthful replay, verify every
   article claim against the deployed surface, and retain a reproducible proof.

Each track gets its own executable implementation plan. Story and terminology
land first so the other tracks cannot invent incompatible positioning.

## 15. Acceptance Criteria

The design succeeds when:

- a new viewer can explain Zava in one sentence after 30 seconds;
- the explanation centres agentic work across an organisation, not simulation;
- the article and cloud demo tell the same story in the same order;
- the Constellation demo shows both organisation-wide scale and one inspectable
  cross-functional journey;
- viewers can identify what is real, what is synthetic, and what they connect;
- every material claim has visible or inspectable evidence;
- no surface positions Zava as a mandatory simulation-first adoption path.
