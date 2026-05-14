# Cosmic Lens v2 — Design Spec

**Date:** 2026-05-10
**Status:** Approved design. Ready for implementation planning.
**Source of truth for:** the rebuild that follows the v1 cosmic lens and the abandoned org-building (PRs #5 and #6).
**Read this first** in any session that picks up this work. It supersedes `docs/superpowers/specs/2026-05-09-org-building-design.md` entirely.

---

## 0. Why v2 exists (one paragraph)

The Glass Tower (PR #6) failed because **stacking is not flow**. Floors are static furniture; even with elevators and motes, motion only happens at transitions, so 90% of the time the screen is a pretty diorama. The original cosmic lens (v1) had perpetual orbital motion — your eye reads it as alive without anything firing — but it had three real flaws: (1) flow only went outward (suns → planets), never inward; (2) there was nowhere for the entity graph; (3) HITL personas had no spatial home. v2 fixes all three by inverting the direction of flow, making the central body morph between two semantic modes via a toggle, and treating humans as first-class cities.

---

## 1. The picture (60 seconds)

> A central glowing **gently-domed orb / disc** — a tactical "mission control" core — covered in glowing **cities/ports**. Around it orbit **function planets** (one per business function: vendor-kyc, ap-invoice, hiring, perf-review, etc.). Each in-flight workflow is a **small moon orbiting its home planet**, labeled with its ref number (`VKY-0042`). When a workflow needs to do something, it dispatches a **rocket** — a small craft that flies from the moon to the relevant city on the central disc and **parks there for the real duration of the action**. The rocket is labeled with what it's doing and who its pilot is. When the action completes, the rocket flies home and the moon's phase advances. Multi-domain workflows transit the hub: rocket goes home-planet → city → other-planet, spawning a new moon on the destination. Rockets leave **fading trails** behind them, so over time the busy operational corridors emerge as glowing arcs of light. **One toggle** swaps the cities on the central disc between *Capabilities* mode (Tools/Skills/Validators/HITL personas) and *Entities* mode. Same moons, same rockets, two complete operational stories. **Drag with mouse/touchpad rotates the whole scene** so users can choose their angle on the orbital depth without ever losing sight of any city.

That paragraph is the spec in narrative form. The rest is detail.

---

## 2. Anatomy

### 2.1 The central body — "the Hub"

- **Shape:** A **gently-domed central disc** (not a full 3D sphere). It is essentially a coin with a slight crown rising from its visible surface — enough to feel three-dimensional without ever putting cities behind itself.
- **Orientation:** Faces the camera by default. **Drag-to-rotate the whole scene** with mouse/touchpad — when the user rotates, the Hub tilts naturally with the rest of the world but its cities never disappear behind it because they all live on its visible face.
- **No auto-rotation.** The system is calm by default; user-controlled when they want to inspect from a different angle.
- **Two modes**, swappable via the Capabilities/Entities toggle (see §2.9):
  - **Capabilities mode** (default). Cities = MCP tools, skills, validators, HITL personas.
  - **Entities mode.** Cities = entity types. Persistent edges between cities = real Kuzu graph relationships.

This solves three real problems: no backside occlusion, easier 2D force-directed layout, and a "command core" reading that fits an operational view better than a planetarium reading.

### 2.2 Cities (in Capabilities mode)

A city represents a single dockable resource. Five categories, each with its own colour band:

| Category | Examples | Colour family | Notes |
|---|---|---|---|
| **MCP tools** | `stripe.charge`, `docusign.send`, `salesforce.upsert` | Cyan / electric blue | "External capabilities" |
| **Skills** (LLM-backed) | `policy_reasoner`, `summarise_thread`, `extract_invoice` | Violet | "Reasoning" |
| **Python / native tools** | `three_way_match`, `compute_irr`, `score_candidate` | Teal | "Internal compute" |
| **Validators** | `signature_validator`, `compliance_screen`, `schema_check` | Amber | "Gates / checkpoints" — caution colour |
| **HITL personas** | `ap_clerk`, `controller`, `cfo`, `recruiter`, `line_manager`, `legal_counsel`, `ceo`, `candidate` | Warm gold / coral | **First-class citizens.** Distinct from all machines. |

**HITL parity is non-negotiable.** Humans ARE cities. The original cosmic lens had nowhere for them and the building hid them in a sidebar. In v2 they sit on the central disc alongside tools, distinguishable by warm hue. A workflow held up on a real human is visually identical to a workflow held up on a slow API call — because operationally, they are.

### 2.3 Cities (in Entities mode)

When the toggle is flipped, the same Hub now shows **entity types** as cities. Indicative roster (driven by what's actually in the substrate):

`Vendor`, `Invoice`, `Payment`, `Account`, `Candidate`, `Job`, `Offer`, `Contract`, `Performance Review`, `Decision`, `Document`, `Person`, `Money`, `Period`, etc.

**Two crucial differences from Capabilities mode:**
1. Cities are **interconnected by persistent edges** = real Kuzu graph relationships (`Vendor →supplies→ Invoice`, `Candidate →applies_to→ Job`). The structure of the central disc literally *is* the substrate's data model.
2. **Glow/size** = how much that entity type is currently being *touched* (read or written) plus accumulated count over time.

Colour palette is its own thing — TBD in a Phase 2 sub-spec, but suggestion is to colour entities by **ownership domain** (Finance entities one hue, HR entities another, etc.) so the diaspora of an entity-type across domains is visible.

### 2.4 Function planets

- One per top-level function: `vendor-kyc`, `ap-invoice`, `hiring`, `perf-review`, `treasury-fx`, `creative-campaign`, `legal-contracts`, etc.
- Orbit the Hub at function-specific radii (radius could encode something — e.g. external-facing functions further out, internal further in. TBD).
- Each planet has a colour/biome that ties to its function family (Finance = blue/green, HR = warm earth, Creative = magenta, etc.)
- Planet brightness/temperature reflects current load (sum of in-flight workflows on it).

### 2.5 Workflow moons

- One **small moon/orb per in-flight workflow**, orbiting its home function planet.
- **Labeled with the workflow's ref number** (`VKY-0042`, `INV-0871`, `HIRE-0188`).
- Moon visual encodes:
  - **Colour** = current phase (Intake / Triage / Decide / Review / Close — palette TBD)
  - **Size** = workflow priority or value (bigger = bigger deal)
  - **Glow** = recency of last activity (recently active = brighter)
- Multiple moons orbit at the same planet at slightly different radii / phase offsets so they don't collide.
- **When a workflow closes**: closure animation TBD — preferred default is a brief flare and the moon spirals into the planet (i.e., the work becomes part of the planet's accumulated mass).
- **When a workflow exceptions**: red pulse, optional brief halo, moon stays orbiting in a "wounded" state until resolved.

### 2.6 Rockets — the heart of the design

A rocket = **the workflow's currently-active step**, in flight or parked.

**Lifecycle of a rocket:**
1. **Spawn** at the moon when a step begins.
2. **Fly** from moon to its destination city, leaving a trail.
3. **Park** at the city for the **real duration** of the action. Slow LLM call = parked for seconds. Fast tool = parked briefly. HITL waiting on a human = parked for as long as the human takes.
4. **Depart** when the action completes. Returns to its moon.
5. **Moon updates** its phase indicator. New rocket may spawn for the next step.

**Rocket label** (visible on hover, abbreviated when glanced at):

| Mode | Label format | Examples |
|---|---|---|
| **Capabilities** | *Purpose* — what the rocket is here to do | `awaiting HITL decision (ap_clerk)` / `running stripe.charge` / `validating signature` / `thinking…` / `reasoning over policy` |
| **Entities** | *Operation* — what the rocket is doing to data | `reading person details (CAND-0042)` / `updating invoice INV-0871` / `creating vendor record` / `linking decision → workflow` |

**Read vs write encoding in Entities mode** — **directional beam**:
- Parked rocket hovers slightly above its city.
- A glowing beam connects rocket and city.
- **Beam goes UP from city → rocket = read** (data flowing out of the city into the rocket).
- **Beam goes DOWN from rocket → city = write** (data flowing from the rocket into the city).
- The beam direction visually mirrors actual data flow. Readable from far away. Uses motion, not just static encoding.

**Multi-domain handoff**: rocket flies home-planet-moon → hub-city (e.g. `cross_function_router` or directly to a destination function's intake city) → flies out to the destination function planet, **spawning a new moon on that planet** with its own ref number, parent-link briefly visible. The original moon either continues with its own work or sleeps awaiting the handoff to return.

**Multiple parallel rockets per moon**: allowed but rare. If a workflow does parallel tool calls, multiple rockets can be in flight from one moon simultaneously. Each carries its own label.

### 2.7 Trails — emergent corridors

- Every rocket leaves a **fading trail** along its flight path.
- Trail intensity = freshly travelled. Decay window: 30s–5min (tunable).
- Multiple rockets along the same path = denser/brighter compound trail.
- **Net effect over a few minutes**: the operational corridors of the system glow visibly. You can see "AP-invoice → ap_clerk → payment_tool" as a glowing arc because that's the path most rockets just took.
- **In Capabilities mode** trails replace the need for any persistent edges between cities — corridors emerge purely from accumulated motion.
- **In Entities mode** trails layer *on top of* the persistent Kuzu edges, so you see both the static schema and the dynamic access pattern.

### 2.8 City layout — force-directed by call-graph proximity

- Cities self-organise via a force-directed layout where:
  - **Spring** between two cities = strength of their co-occurrence in workflows (cities used together pull together).
  - **Repulsion** between all cities = baseline spacing.
- Result: cities that work together cluster into **operational territories** without being explicitly grouped. `ap_clerk` sits at the natural junction of AP-corridor and KYC-corridor because it touches both. `compute_irr` sits inside the Treasury cluster because that's who calls it.
- Layout runs **in 2D on the disc surface** (simpler and more stable than spherical).
- **Color-by-type is independent of layout**, so you simultaneously read:
  - **Position** = "what does this work with" (operational role)
  - **Colour** = "what kind of resource is this" (capability category)
  - **Glow/size** = "how busy is this right now" (live load)
- Layout converges over time; can be re-run periodically as call-graph evolves. **The map reshapes itself as the org's behaviour shifts.**

### 2.9 The toggle

A **segmented control** placed in the **top-right of the vital-signs bar**, immediately adjacent to the ⚡BURST button:

```
[ Capabilities | Entities ]
```

- One mode at a time. Never both. Reasons:
  - Cognitive load: each mode tells a complete story.
  - Visual budget: each mode needs the full Hub's surface.
  - Honesty: if we showed both we'd be inventing relationships that don't exist (capability-cities have no edges; entity-cities do).
- Always visible. Lives in HUD chrome alongside other view-shaping controls. Treats mode-switching as a first-class control, not a hidden setting.
- **Transition animation**: smooth morph (~600ms). Capability cities dissolve, entity cities materialise in their layout, persistent edges fade in. Camera holds steady. The moons and orbits don't change — only the Hub's content morphs.
- **Labels chosen** because "Capabilities" cleanly covers tools+skills+validators+humans (what the system *uses*) and "Entities" cleanly covers the data plane (what the system *touches*). Neither label elides the other categories.

---

## 3. Behaviour rules

### 3.1 Real-time fidelity (non-negotiable)

The viz is a **real-time x-ray of the system, not theatre.** Therefore:
- Rocket parking duration = **real action duration**, not a stylised animation length.
- A rocket parked for 8 seconds at `ap_clerk` means a real human has been thinking for 8 seconds.
- A rocket parked for 200ms at `stripe.charge` means the API genuinely returned in 200ms.
- A queue of rockets at a city = a real bottleneck.
- This is the property that makes the viz *honest*.

### 3.2 Minimum visible duration

To prevent sub-perceptual blink-throughs, enforce a **minimum 500ms park** for very fast actions. Below that the rocket isn't readable, so we visually round up. Above that, real time wins.

### 3.3 Density caps and level-of-detail

At full demo load (50+ in-flight workflows × multiple rockets each), we'll have 50–200 rockets in motion. Strategies (one or more):
- **Far zoom**: rockets rendered as thin bright lines, cities as dots, trails dominant. You see the *shape* of activity.
- **Close zoom on a planet**: that planet's moons and their rockets are full-resolution; everything else is dim background.
- **Hover a city**: it pulls forward, queued rockets become legible, label expands.
- **Hover a moon**: its rocket is highlighted, current label expands, trail to its current city is bright.
- **Default mid zoom**: balanced — you can read the busiest corridors and the headline cities.

Cap candidates if needed: render at most N rockets per moon (most recent), N cities visible at once (busiest get priority), trail-decay window adjusts to total flux.

### 3.4 Failure / exceptions

- A rocket whose action errors: returns to its moon as a **red bead**, leaves a brief red flash trail.
- The moon enters a "wounded" state (red halo) until the workflow resolves the exception or is retried.
- Optionally, a small dispatch indicator flashes at the relevant function planet.

### 3.5 Color discipline

- 5 bands (Capabilities mode) + N bands (Entities mode). Don't pile on more.
- Reserve white/very-bright for high-attention moments (closures, exceptions, rare events).
- HITL = warm hue, machines = cool hue. This is the most important separation.
- Trails inherit a desaturated version of the rocket's source-category colour, so you can tell *what kind* of work the corridor is for.

---

## 4. HUD elements

These survive intact from the Glass Tower work because they were the parts that actually worked:

- **Vital-signs bar** (top): in-flight count, pending decisions, throughput, exception count, status pill, ⚡BURST button, **and the new `[ Capabilities | Entities ]` mode toggle** (top-right, adjacent to BURST).
- **Live activity rail** (right edge): event feed with filter chips (decisions / thinking / done / exceptions / started / spawned / tools). Auto-pin to top, scroll to pause.
- **Click-to-drill drawer** (slides in from right or bottom): click a planet → function view (workflow list); click a workflow ref on the planet → workflow timeline (existing endpoints already serve this).

**Removed:** the persona strip at the bottom. Reason: HITL personas are now first-class cities on the Hub with their own warm-coloured marker, glow=queue depth, and parked rockets showing pending work. Keeping the strip would say "I don't trust the cities to do their job." Activity rail names personas in the event feed; click-to-drill drawer covers details. **No bottom strip.**

All HUD chrome stays mostly 2D, sitting outside the 3D scene. The 3D handles the *story*; the 2D handles the *facts*.

---

## 5. Backend: what's already there, what's needed

### 5.1 Already in place (from Glass Tower work — **keep these**)

- `GET /api/workflows/index/in-flight` — list of moons
- `GET /api/personas/index/state` — HITL state per persona (will become city state)
- `GET /api/workflows/index/timeline/{id}` — for the drawer
- `GET /api/entities/by-function/{function_key}?kind=K` — for the function drawer
- `POST /api/simulator/inject-burst?n=N` — demo button
- `POST /api/simulator/seed-kpis` — initial state
- SSE stream relaying `persona.thinking`, `persona.decided`, `tool.invoked`, `tool.completed`, `workflow.*` etc. with full field set
- `DEMO_LOUD=1` env var that adds 2–8s sleep on persona decisions so thinking is visible

### 5.2 Likely needed for v2

- **`tool.invoked` / `tool.completed` with timing** must be reliable for every tool call. Rocket parking time depends on these. Audit current emission.
- **Action-label generator** server-side: a small helper that turns an event into a one-line human-readable label ("running stripe.charge", "awaiting HITL decision (ap_clerk)", "reading person details (CAND-0042)", "updating invoice INV-0871"). Could live in `api/server/services/action_labels.py`. Must produce **mode-specific labels** (one for Capabilities, one for Entities).
- **Entity-touch events**: `entity.read` / `entity.upserted` / `entity.linked` need to be relayable through the SSE channel with `entity_kind`, `entity_id`, `verb`, `caller_workflow_id`. (`entity.upserted` exists; `entity.read` may need to be added.)
- **Call-graph affinity endpoint**: `GET /api/cities/affinity` returning pairwise co-occurrence weights between cities, computed from event history. Frontend feeds this to its force-directed layout. Could be cached and refreshed every few minutes.
- **City roster**: `GET /api/cities` returning all known cities with `kind` (mcp/skill/python/validator/persona/entity_type), category, and last-seen activity. Frontend renders one marker per row.
- **Decision flagging**: `decision_id` on rocket-related events so a parked rocket at a HITL city can show the specific decision pending.

### 5.3 What can probably die

- All Glass Tower components (`web/blueprint/src/components/glassTower/*`) — replaced by new cosmic lens components.
- Any tower-specific layout helpers (`tower-registry.ts`).
- The `feature/org-building` branch (PR #5) and the `feature/org-ops-v2` branch (PR #6) once cosmic lens v2 lands. New branch: `feature/cosmic-lens-v2`.

Backend is mostly reusable. The wins from PR #6 (in-flight, persona state, timeline endpoints) are independent of the visual layer and feed v2 directly.

---

## 6. What's explicitly OUT of v1 of v2 (parked for later phases)

Don't try to do these in the first build. They're acknowledged but deliberately deferred so we ship something coherent.

- **CEO-FM (meta-agent) visualisation** — parked. Will need a Phase 2 design (overhead "home star," halo around hub, or summoned craft — TBD then).
- **Historical replay / time-scrubber** — viz is real-time only for v1.
- **Recording / playback of trails over a "shift"** — could be cool but not now.
- **Drill into individual entities** in entity-mode (we show entity *types*; tapping a city could show the top-N hot individuals, but full per-entity orbit is Phase 2).
- **Cross-function entity arcs** beyond the current sub-spawn handling.
- **Detailed exception forensics** beyond the wounded-moon visual.
- **Cosmic-lens "filter chip" controls** beyond what already exists in the activity rail.

These are intentional cuts. Trying to do them in v1 of v2 will repeat the mistake of overscoping.

---

## 7. Open questions resolved

The four foundational decisions made during the brainstorming session that produced this spec:

1. **Hub shape and rotation** → **Gently-domed central disc** (not a full sphere). **Drag-to-rotate the whole scene** with mouse/touchpad. **No auto-rotate.** No backside occlusion ever.
2. **Read/write encoding in Entities mode** → **Directional beam**. Beam goes *up* from city → rocket = read; beam goes *down* from rocket → city = write.
3. **Persona strip (bottom HUD)** → **Removed entirely.** HITL personas are first-class cities on the Hub.
4. **Mode toggle placement and label** → **Segmented control `[ Capabilities | Entities ]` in the top-right of the vital-signs bar**, adjacent to the ⚡BURST button.

### Still open (to resolve during implementation, not blocking)

- **Closure animation** specifics for completed moons — flare-and-fade vs spiral-into-planet vs sail-off-into-space.
- **Initial Hub palette** for entity-mode cities (suggestion: by ownership domain).
- **Density caps** — should we cap rockets visible at extreme load, or just trust LOD and visual saturation to handle it? Test with 200+ rockets first.
- **Function planet radius encoding** — does radius mean anything (priority? user-facing-ness?) or are they evenly distributed?
- **Camera defaults**: starting view, zoom range.
- **Moon collision avoidance** when a planet has 30+ in-flight workflows — radial offset, multi-ring orbits, or LOD-based fade?

These are deliberately implementation-time decisions, not spec-time ones. They depend on visual playtesting that doesn't make sense to simulate in a spec.

---

## 8. Success criteria — how we know v2 worked

Three tests, in order:

1. **The 5-second test**: a stranger looking at the screen for 5 seconds can answer "is the system busy or quiet?" and "is anything stuck?" Without help.
2. **The 60-second test**: with 30 seconds of narration, they can answer "where is work currently piled up?" and "what kind of work is the busiest?" and "is any specific human (or tool) the bottleneck?"
3. **The 5-minute test**: they can identify a specific workflow by ref number, drill into it, and explain its current state and what it's waiting on. Without a single confused question.

The Glass Tower failed test 1. The original cosmic lens passed test 1 but failed test 2 because flow was outward-only and HITLs were invisible. v2 should pass all three.

---

## 9. Risks worth being honest about

- **Force-directed layout may converge to ugly shapes** with sparse data. Need a fallback layout (e.g. category-grouped rings) that activates if affinity data isn't rich enough yet.
- **Real-time fidelity is unforgiving**: if backend events are slow or lossy, the rockets will look wrong. We'll need to monitor SSE freshness.
- **Density at 200+ rockets** — the LOD strategy is hand-wavy in this spec. Will need playtesting before commitment.
- **The toggle is a big mode change**: users who flip it expecting "extra info" will be confused they lose Capability detail. Consider a tiny preview-thumb of the alternate mode to remind them what they'd switch to.
- **Three.js / R3F dedup hazards** as previously hit (`stats-gl` shipping nested `three`). Re-apply the `vite.config.ts` resolve.dedupe rules from PR #6 from day one.
- **Beam direction must be obvious**: if the up/down beam direction in Entities mode is too subtle, users won't perceive read vs write. Test with non-technical viewers; if they can't tell, exaggerate the animation (particles travelling along the beam in the data-flow direction).

---

## 10. Phasing for the build

Not committing to dates — just a rough order so we don't paint ourselves into a corner.

- **Phase A — skeleton**: Hub disc + cities (random layout, single category) + planets + moons orbiting + rockets dispatched and parked. No trails, no toggle, no labels. Just motion.
- **Phase B — semantics**: Real action labels on rockets, real-time parking durations from backend events, colour-by-type, HITL personas as cities.
- **Phase C — emergence**: Force-directed city layout (2D on disc), trails, corridors visible, Capabilities mode complete.
- **Phase D — Entities mode**: Entity cities, persistent edges from Kuzu, mode toggle, directional-beam read/write encoding.
- **Phase E — polish**: Closure animations, exception visuals, density LOD, drawer integration, performance.
- **Phase F (later)**: CEO-FM, time-scrubber, replay, etc.

Each phase should pass the prior phase's success test before moving on.

---

## 11. What stays from prior work

| From | What | Status |
|---|---|---|
| `main` (Phases 1–4) | Substrate: entity graph, compose-domain v4, function FMs, CEO-FM, hitl_gates, observatory event types | **Keep, untouched** |
| PR #5 (`feature/org-building`) | The decorative tower | **Kill on merge of v2** |
| PR #6 (`feature/org-ops-v2`) | Glass Tower frontend | **Kill on merge of v2** |
| PR #6 backend additions | New endpoints, persona thinking events, DEMO_LOUD, simulator burst/seed-kpis | **Keep — feeds v2 directly** |
| PR #6 HUD work | Vital-signs bar, activity rail, drawer | **Keep, port to v2 scene** |
| Original cosmic lens (v1) | Outward-only flow, no entities, no HITL | **Replaced** |

---

## 12. Pre-flight checklist before next code session

Before opening an editor:
- [ ] Re-read this spec.
- [ ] Confirm the substrate's event emissions (§5.2) cover what the rocket parking durations need.
- [ ] Decide whether to merge PR #6 into main first (for backend wins) or carry it forward.
- [ ] Confirm `vite.config.ts` dedup rules carry over.

That's it. Build only after this checklist is clean.

---

*End of spec.*
