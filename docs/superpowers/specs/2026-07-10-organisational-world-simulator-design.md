# Organisational World Simulator — Design Spec

**Date:** 2026-07-10
**Status:** Approved design (spine). Industry-independent core agreed. The first proving substrate is a deliberately **minimal, purpose-built telco slice** (~4 processes, §11.1) — *not* a retrofit of the existing 30+ agency domains (too much surface to model while the engine is new), and *not* the full telco vertical. Later verticals and the hard implementation choices in §12 are deferred to detail review + planning.
**Source of truth for:** a new **world-model layer** that turns the Zava substrate from a *workflow-spawner* into a *closed-loop living organisation*. A generic, tick-driven **stock-and-flow engine** advances a simulated world; **sensors** spawn work when the world hits a condition; **actuators** feed workflow outcomes back into the world. Any industry is supplied as a declarative, pluggable **world pack** — the engine itself contains zero industry knowledge.

**Read this first** in any session that picks up this work. It builds on, and does not replace:

- [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) — the four planes + the closed-loop insight layer. The world engine is a **new layer underneath** that drives the existing planes.
- [`docs/ADD-A-DOMAIN.md`](../../ADD-A-DOMAIN.md) + [`docs/superpowers/skills/compose-domain/SKILL.md`](../skills/compose-domain/SKILL.md) — how the *response half* of a world pack (domains, personae, projections) is already authored.
- [`docs/superpowers/specs/2026-07-07-visual-domain-composer-design.md`](2026-07-07-visual-domain-composer-design.md) — the live authoring surface a future pass could extend to author the *world half*.
- [`api/server/services/simulator_orchestrator.py`](../../../api/server/services/simulator_orchestrator.py) + [`api/server/data_fabric/`](../../../api/server/data_fabric/) — today's ramp-loop simulator, which this subsumes.

---

## 0. Why this exists (one paragraph)

Today Zava's "world" is **static** — a seeded snapshot of an organisation (`data_fabric/`) — and a **timer** (`simulator_orchestrator.ramp_loop`) spawns workflow instances onto it. Work exists because the clock said so; nothing evolves on its own; a workflow's payload is coherent but its *existence* is not caused by anything. That means the substrate's cleverest asset — an org of agents deciding things — is reacting to a scheduler, not to a world. The Organisational World Simulator inverts this: it introduces a **living world that ticks forward by itself** and **work that emerges as a consequence of the world's condition**, then closes the loop by writing decision outcomes back into the world. The result is a genuine *organisational simulator*: cross-function cascades and resource contention **emerge** rather than being scripted, anomaly-style domains detect conditions **nobody drew for them**, and every run is different. Crucially it is built as a **generic engine + declarative industry packs**, so it is industry-independent and adapts to any vertical. The first proving ground is a deliberately **minimal telco slice** (~4 processes, §11.1) chosen to exercise every primitive at the smallest honest scale; the *full* telco world and any agency retrofit are later, separate work.

---

## 1. The picture — the closed loop

The entire design is one loop. Everything else is detail.

```
        ┌─────────────────────────────────────────────┐
        │                                             │
        ▼                                             │
   ┌─────────┐   sense     ┌──────────┐   decide   ┌────────────┐
   │  WORLD  │ ──────────▶ │ SENSORS  │ ─────────▶ │ RESPONDERS │
   │  STATE  │  (signals)  │(triggers)│  (events)  │ workflows, │
   │(ticking)│             └──────────┘            │ personae,  │
   └─────────┘                                     │ FM agents  │
        ▲                                          └────────────┘
        │                  act (feedback)                 │
        └─────────────────────────────────────────────────┘
```

- **World state** advances every tick in demo-warped time (reusing `time_compression`).
- **Sensors** watch signals/conditions and emit ordinary bus events.
- **Responders** are Zava's *existing* machinery — Durable workflows, personae, Fleet Managers — now triggered by the world instead of a timer.
- **Actuators** subscribe to responders' completion events and mutate world state, closing the loop.

---

## 2. Scope & non-goals

**In scope (this spec — the industry-independent core):**

- A generic **World Model engine** (`world/engine/`): tick loop, stock integrator, signal evaluator, resource allocator, perturbation scheduler, sensor + actuator runtime, and the sandboxed-expression evaluator they share.
- The **narrow-waist contract** (`world/contract.py`): the seven primitive types every pack conforms to (§3).
- **World packs** (`world/packs/<industry>/`): the declarative content shape + a boot-time loader, selected one-at-a-time by a `ZAVA_WORLD` flag (§5).
- **Coupling to Zava** through the two existing seams only — the EventBus and the entity graph (§6).
- A **cosmic-lens signals stream** so the living world is renderable (§6).
- **Determinism/replay** parity with Zava's tape philosophy (§8).

**Non-goals (deferred / out of scope here):**

- **The full telco vertical.** This spec defines a deliberately **minimal telco slice** (~4 processes, §11.1) as the first proving substrate. The *full* telco world — its complete function set, domain catalogue, and signal taxonomy — is a follow-on spec + plan. Either way the engine must never bake in telco nouns; the slice lives entirely in a pack under `world/packs/telco/`.
- **Simulating the existing 30+ agency domains.** Explicitly out of scope as a first move: modelling a large interacting world *and* debugging a new engine at once, on top of the live flagship, is the wrong risk profile. A small agency retrofit is a *later, optional* commercial pack (§7, §12).
- **Rewriting the substrate.** The engine is *additive*. Durable workflows, personae, projections, governance (AGT), the cosmic lens, and the Visual Domain Composer are reused unchanged except for the additive signals stream.
- **Retiring the current ramp loop immediately.** The ramp loop coexists behind the flag until at least one world pack proves the model (§7).
- **Public deploy changes.** The engine is in-process and localhost-first; it introduces no new external ingress and does not alter the `.poc-safety` posture (§9).
- **A visual world-pack authoring tool.** Packs are hand-authored (declarative files) in v1; wiring the Visual Domain Composer to author the world half is a later pass (§11).

---

## 3. Core concepts — the narrow waist (seven primitives)

The make-or-break decision: the engine defines a **small, fixed vocabulary of primitive types**; an industry supplies an **unlimited number of instances**. This is the same shape Zava already uses — a fixed `Domain`/`Phase`/`HitlGate` vocabulary carrying 38 domain instances. The primitives:

| Primitive | What it is | Universal because… |
|---|---|---|
| **Stock** | a level that fills/drains (backlog, cash, capacity, morale, inventory) | every org is made of accumulating quantities |
| **Flow / Dynamic** | a rule that moves stocks each tick | it is arithmetic over stocks |
| **Signal** | a derived, observable readout (SLA %, CSAT, utilisation) computed from stocks/entities | every org is measured by derived metrics |
| **Resource** | a finite pool multiple functions contend for (people, budget, capacity) | every org allocates scarce means |
| **Perturbation** | an exogenous kick (demand surge, failure, viral moment, regulation) | every org faces an environment it does not control |
| **Sensor** | `when <condition over signals/state> then emit <bus event>` (with cooldown) | conditions producing work is universal |
| **Actuator** | `when <responder outcome event> then apply <effect> to world state` | decisions feeding back is universal |

**Why this set is genuinely universal:** it is precisely how operations-research / system-dynamics modelling represents *any* organisation — hospital, bank, telco, agency. Stocks + flows + finite resources + exogenous shocks + condition-driven responses + feedback is the general grammar of an operating organisation, not a telco-specific one.

`world/contract.py` declares these as typed, frozen dataclasses. The math/logic-bearing fields (a Flow's rate, a Signal's formula, a Sensor's condition, an Actuator's effect) are **sandboxed expression strings**, evaluated as described in §4.4.

---

## 4. The engine (generic mechanism) — `world/engine/`

Zero industry vocabulary. Testable in isolation against a 10-line toy pack.

### 4.1 Tick loop

An async loop advancing the world by a fixed time-step Δt, cadenced against `time_compression.business_now` / `DEMO_TIME_WARP_FACTOR` so the world runs in the same warped time as the rest of the demo. Each tick, in order:

1. Apply any perturbations firing this tick (§4.5).
2. Evaluate flows/dynamics → integrate stocks (`stock += (inflow − outflow) · Δt`), clamped to declared bounds.
3. Recompute signals from stocks/entities.
4. Evaluate sensors; emit bus events for any whose condition is newly met and off-cooldown (§4.6).
5. Publish a `world.tick` snapshot (signals + notable stock deltas) to the bus / SSE for the cosmic lens.

Actuators are *not* on the tick path — they are bus subscribers (§4.7) so feedback is event-driven, not polled.

### 4.2 Stock integrator

Holds the mutable stock vector. Applies flows with explicit-Euler integration (adequate for demo fidelity; the integrator is swappable if a stiff pack ever needs it). Enforces `min`/`max` clamps and non-negativity where declared.

### 4.3 Signal evaluator

Computes each `Signal` formula from the current stock vector + injected read-only helpers (entity-graph counts, resource utilisation). Pure; no side effects.

### 4.4 Sandboxed expression evaluator (shared)

The rate/formula/condition/effect fields are evaluated in a **locked-down namespace** — the *exact* mechanism Zava already uses for persona `decision_policy` blocks (`compile()` + a curated builtins whitelist; see [`persona_responder.py`](../../../api/server/services/persona_responder.py) `_DECISION_BUILTINS`). Injected reads: `stocks`, `signals`, `resources`, `graph` (read-only), plus safe math. No `import`, no file/network, no reflection. A bad expression raises at load/compile time and disables *that instance* only, never the engine. Reusing this runtime keeps one sandbox story across personae and world packs.

### 4.5 Perturbation scheduler

Turns `Perturbation` declarations into timed effects. Supports three schedules (mirroring the existing ambient-trigger taxonomy): `poisson(rate)` (random arrivals), `cron`-like (wall-clock), and `manual` (operator-injected via a REST endpoint / demo trigger). A perturbation applies a bounded, time-boxed effect to one or more stocks/flows (e.g. `+40% arrival_rate for 20m`). Seeded RNG (§8) makes random perturbations reproducible.

### 4.6 Sensor runtime

Each tick, evaluates every `Sensor.condition`. On a rising edge (false→true) and past its `cooldown`, emits the sensor's declared bus event with a small payload (which signals/stocks tripped it). This is the sole bridge from world → work; it deliberately emits **ordinary events the existing ambient dispatcher / domain registry already understand**, so no new spawn path is introduced (§6).

### 4.7 Actuator runtime

Subscribes to the bus for the responder-completion events named in each `Actuator.on`. When one fires, evaluates the actuator's `effect` in the sandbox with the event outcome injected, and applies the resulting delta to world state (e.g. `resources.agents.capacity += outcome.hired`). This is the feedback path; without it the world is a one-way feed.

### 4.8 Lifecycle

One engine per process, started from `main.py`'s lifespan **only when a pack is active** (`ZAVA_WORLD` set). Disabled by default so nothing changes for the current substrate until a pack is chosen. Honours the same `ENTITY_PLANE_ENABLED=0` guard inside the Functions worker so the engine runs only in the FastAPI process (single-writer discipline).

---

## 5. World packs (declarative content) — `world/packs/<industry>/`

An industry is **authored, not coded.** A pack is a folder discovered at boot (mirroring how personae are walked from `personae/*/SKILL.md`, cadences from YAML, projections auto-imported). A pack declares:

- **The world half (new):** its `Stock`s, `Flow`s, `Signal`s, `Resource`s, `Perturbation`s, `Sensor`s, `Actuator`s.
- **The response half (existing Zava registries):** the pack's `Domain`s (`domains.py`), function membership (`functions.py`), `personae/*/SKILL.md`, and entity projections — authored today via `compose-domain` / the Visual Domain Composer.
- **Seed:** initial entity-graph contents for the vertical (the pack's `data_fabric` equivalent), so a cold start has a coherent structural world.

Illustrative, **industry-neutral** fragment (a support queue) to make "declarative" concrete:

```yaml
stocks:      [ Stock(support_backlog, initial=0, min=0) ]
resources:   [ Resource(agents, capacity=20) ]
signals:     [ Signal(sla_breach_pct, "(support_backlog - agents*HANDLE)/max(support_backlog,1)") ]
dynamics:
  - Flow(into=support_backlog, rate="ticket_arrival_rate")           # inflow
  - Drain(support_backlog,     rate="allocated(agents) * HANDLE")    # outflow
perturbations:
  - Perturbation(demand_surge, effect="+40% ticket_arrival_rate", dur=20m, schedule="poisson(rare)")
sensors:
  - Sensor(when="sla_breach_pct > 0.15", emit="ops.surge_staffing.requested", cooldown=30m)
actuators:
  - Actuator(on="surge-staffing.completed", effect="agents.capacity += outcome.hired")
```

**One pack active at a time**, selected by `ZAVA_WORLD=<industry>` (default unset → engine off, current substrate unchanged). This mirrors the existing flag posture (`ZAVA_MODE=replay`, the Apex→Zava rebrand). Packs live side by side; the flagship agency demo is never disturbed by a telco pack existing on disk.

---

## 6. Coupling to Zava — only two existing seams

The engine never reaches into the substrate's internals. It couples through the two things Zava already has, so "works with the rest of Zava" is true by construction:

```
   WORLD ENGINE (generic)                    REST OF ZAVA (unchanged)
   ┌───────────────────┐   emit signals /    ┌──────────────┐
   │ tick · stocks ·   │   sensor events     │  EventBus    │──▶ ambient dispatcher
   │ signals · sensors │ ──────────────────▶ │ (nervous sys)│──▶ Durable workflows
   │ · resources       │ ◀────────────────── │              │──▶ personae / FMs
   └───────────────────┘   workflow.*        └──────────────┘
        │  ▲               completed events         │
        │  └──────── actuators subscribe ───────────┘
        ▼
   ┌───────────────────┐
   │  Entity graph     │  ← world's structural memory (existing Kuzu)
   └───────────────────┘  → cosmic lens renders the living world
```

1. **Sensors emit existing events.** `emit="ops.surge_staffing.requested"` is an event the existing ambient dispatcher + domain registry already turn into a workflow. **No new spawn mechanism.**
2. **Actuators consume existing events.** `on="surge-staffing.completed"` is an existing workflow/decision-completion event. Feedback is just another bus subscriber.
3. **Structural memory is the entity graph.** Entities/decisions still project into Kuzu via existing projections; the pack only adds node kinds it needs.
4. **The cosmic lens gains a signals stream.** The lens already renders the graph + workflow activity; we add a `world.tick` SSE channel so the *fast* state (signals, stock levels) is renderable. This is the only UI-facing addition in v1.

From Zava's point of view the world is simply a new **publisher + subscriber** on the bus and a **reader/writer** of the graph. Additive, isolable, removable.

**Two tiers of work (design intent).** Durable workflows are heavyweight; a lively world could flood the Functions host. Sensors therefore distinguish *reactions* (cheap, in-process ambient-agent handling for high-frequency low-stakes conditions) from *processes* (consequential, multi-phase → a real Durable workflow). The exact routing rule is an open question (§12) but the two-tier intent is part of the design.

---

## 7. Relationship to today's simulator

The current `simulator_orchestrator.ramp_loop` spawns each live domain on a time-warped Poisson timer, with a few `cadenced_rituals`. Under the world model that becomes a special case: **"advance the world; work emerges."** Migration posture:

- **Coexistence behind the flag.** With `ZAVA_WORLD` unset, the ramp loop runs exactly as today. With a pack active, the engine drives emergence and the ramp loop is disabled for that pack's domains.
- **The first substrate is a new, small pack — not the agency world.** The minimal telco slice (§11.1) is authored fresh under `world/packs/telco/`; the existing agency substrate stays on the ramp loop, untouched. The `data_fabric` seeders generalise into per-pack seed modules, so a *small* agency slice can optionally be retrofitted as a commercial pack **later** (not required to prove the engine, and never the full 30+ domains up front).
- **No behavioural regression** for the existing 38 agency domains while the flag is unset — protected by the registry-consistency tests plus new engine-off tests.

---

## 8. Determinism & replay

Zava prizes deterministic seeding + replay tapes (`ZAVA_MODE=replay`, the compose tapes). The world model must not break that:

- **Seeded RNG.** One seed per run drives all stochastic perturbations and any dynamics noise; given `(seed, pack, Δt, wall-clock start)` the world evolves identically.
- **Reproducible ticks.** Integration is pure over the stock vector; feedback is deterministic given deterministic responders (personae already are).
- **Tape-friendly.** The `world.tick` stream is recordable/replayable through the same mechanism as the existing SSE tapes, so a demo world can be replayed bit-identically — the honest way to de-risk a multi-minute live demo.

---

## 9. Safety

- **No new external surface.** The engine is in-process (FastAPI). Its only inbound operator control (manual perturbation injection) rides the existing demo-trigger route, subject to the existing read/route auth posture. `.poc-safety` is unchanged; nothing here binds a public interface.
- **Sandbox for pack expressions.** Pack-authored expressions run in the persona-grade sandbox (§4.4) — no `import`, file, network, or reflection — so a world pack cannot escalate beyond arithmetic over injected state.
- **Single active pack + single writer.** One pack at a time; the engine runs only in the FastAPI process (mirrors `ENTITY_PLANE_ENABLED=0` in the worker), preserving Kuzu's single-writer discipline.

---

## 10. Testing strategy

**Engine (pytest, `tests/api/world/`):**

- **Integrator** — stocks fill/drain correctly; clamps hold; a known 2-stock model matches a hand-computed trajectory.
- **Signal evaluator** — formulas compute from a fixed stock vector; a bad formula disables only its signal.
- **Perturbation scheduler** — seeded `poisson`/`cron`/`manual` schedules are reproducible; effects are bounded and time-boxed.
- **Sensor runtime** — rising-edge + cooldown semantics; emits the exact declared event; no re-fire while latched.
- **Actuator runtime** — a mocked completion event applies the correct delta; malformed effect is isolated.
- **Determinism** — same seed ⇒ identical tick trajectory (the replay guarantee).
- **Engine-off default** — with `ZAVA_WORLD` unset, no engine starts and the current ramp-loop behaviour is byte-for-byte unchanged.

**Coupling (pytest):**

- A **toy pack** end-to-end: perturbation → stock change → signal crosses threshold → sensor emits → (stub) workflow-completion event → actuator restores the stock. Asserts the full loop over the real bus with no industry nouns.

**Prove-the-waist (design-validation gate):** the contract must carry **two structurally different packs with no engine edits** — the neutral **toy pack** (generic support-org, slow stocks; lives permanently in the engine's unit tests) and the **minimal telco slice** (§11.1; fast signals + resource contention). If both fit cleanly, the narrow waist is validated against genuinely different shapes; if either forces an engine change, revise the contract before growing any vertical. (A real agency pack later would be a third, commercial confirmation.)

---

## 11. Milestones (the plan will sequence these)

1. **Contract + engine core** — `world/contract.py` (the seven primitives) + integrator + signal evaluator + shared sandbox, unit-tested against a neutral **toy pack** (support-queue). No bus, no UI. The toy pack stays as the engine's permanent industry-neutral guard.
2. **Perturbations + sensors + actuators** — the scheduler and the two runtimes; the full loop proven over the real EventBus with a stub responder.
3. **Pack loader + `ZAVA_WORLD` flag + lifespan wiring** — discover a pack folder, start/stop the engine, engine-off default verified.
4. **Minimal telco slice — the first working substrate** *(the "make sure it works" gate)*. A deliberately small, purpose-built pack (§11.1): ~4 processes across 2 functions, exercising every primitive incl. fast signals, resource contention, and feedback. Passing it validates the narrow waist against a genuinely different shape from the toy pack. Its response half (domains/personae/projections) is authored via compose-domain / the Visual Domain Composer.
5. **Cosmic-lens signals stream** — `world.tick` SSE channel + minimal lens rendering of the slice's live signals/stocks (the mast-fault→recovery cascade made visible).
6. **Grow / later (separate specs/plans)** — expand the slice toward a full telco world; wire the Visual Domain Composer to author the *world half*; optionally retrofit a small agency slice as a commercial pack for the flagship upgrade. None of these is required to prove the engine.

Beyond the milestones: a two-tier work router tuned from real load; richer integrators only if a pack demands them.

### 11.1 The minimal telco slice (M4 target)

The smallest telco organism that still exercises every primitive — the concrete target for the first working substrate:

```
Functions (2):   Network Operations  ·  Customer Care
Stocks:          network_health · call_queue_depth · open_incidents
Resource:        field_tech_pool          ← finite; simultaneous incidents contend for it
Signals:         dropped_call_rate · avg_hold_time · sla_breach
Perturbations:   mast_fault (manual + rare poisson) · demand_surge
Sensors:         dropped_call_rate > X → incident.requested
                 call_queue_depth   > Y → care_surge.requested
Processes (~4):  network-incident · field-dispatch · care-surge-staffing · churn-save
Actuators:       incident resolved → restore network_health
                 dispatch done     → release a field tech
                 surge-staffing    → raise care capacity
```

One clean cascade — *mast fault → dropped calls ↑ → call-queue spike → incident ignites → field-dispatch (techs contended) → recovery, with churn-risk as a side-effect* — touches stocks, flows, a shared resource, perturbations, sensors, actuators, and feedback. Four processes, not thirty; fully in our control; zero flagship risk; and it grows straight into the full telco vertical. Exact stock equations, thresholds, and process phases are pinned during planning.

---

## 12. Open questions / deferred decisions

- **Time-series storage for fast state.** Kuzu is a graph, not a metrics store. Options: in-memory ring buffers (simplest, demo-sufficient) vs. a lightweight sqlite history for scrubbing/replay. Lean ring-buffer + optional sqlite; decide in planning.
- **Two-tier work routing rule.** What makes a tripped sensor a cheap in-process *reaction* vs. a Durable *process*? Likely a per-sensor `tier` field; needs a concrete rule and load testing.
- **How much of the world is agent-driven vs. authored physics.** Recommendation stands: authored, legible dynamics for the *environment*; agentic intelligence in the *responders*. Revisit only if a pack needs endogenous agents driving the world itself.
- **Retrofit the agency world as a pack?** *Resolved:* not first. The first substrate is a new minimal telco slice (§11.1), not an agency retrofit — the 30+ existing processes are too much surface to model while the engine is new. A *small* agency slice is a later, optional commercial pack for the flagship upgrade.
- **Contract expressivity edges.** Do delays/pipelines (a change that takes N ticks to bite) and simple queues need first-class primitives, or do stocks-of-stocks express them? Settle during "prove the waist" (M4).
- **Full telco specifics** — the complete function set, domain catalogue, and signal taxonomy of a full telco world remain deferred to the telco follow-on spec. The *minimal* slice's shape is pinned in §11.1; only its exact equations, thresholds, and process phases await planning.
