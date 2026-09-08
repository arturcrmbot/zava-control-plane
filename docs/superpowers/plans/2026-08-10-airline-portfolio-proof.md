---
goal: Capture recordings for all three airline heroes, pass all nine VERTICAL-PROOF gates, and prepare seller-review (leaving human review PENDING)
version: 1.0
date_created: 2026-08-10
last_updated: 2026-08-10
owner: Zava engineering
status: Planned
tags: [airline, proof, recordings, vertical-proof, seller-review]
depends_on: [2026-08-10-airline-golden-hero-readiness, 2026-08-10-airline-aog-engineering-recovery, 2026-08-10-airline-schedule-resilience]
---

# Airline Portfolio Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce repeatable evidence for every airline hero and pass every machine gate in the vertical proof contract.

**Architecture:** Drive all three workflows through one isolated live stack, persist distinct recordings and detail snapshots, replay those same workflows, and compare the user-visible evidence. Keep proof artifacts attributable to the airline pack and reserve demo-ready approval for the human seller review.

**Tech Stack:** Bash proof stack, Node.js/Playwright, Python workflow visibility checker, Azure Durable Functions, FastAPI.

---

This plan captures recordings for all three airline heroes, runs the
nine VERTICAL-PROOF completion criteria, and prepares the seller-review
gate — leaving human seller review explicitly PENDING.

Design authority:
[`2026-07-28-airline-vertical-design.md`](../specs/2026-07-28-airline-vertical-design.md) §17.
Proof contract: [`docs/VERTICAL-PROOF.md`](../../VERTICAL-PROOF.md).
Build contract:
[`docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md`](../contracts/VERTICAL-BUILD-CONTRACT.md).

> **For agentic workers:** Execute phases in order. Within a phase, tasks
> may run in parallel only when the Dependencies column permits it. Use
> TDD for every code task. Do not begin the next phase until its
> completion gate passes.

## 1. Requirements & Constraints

- **REQ-001**: A committed recording
  (`data/blueprint-recordings/<wt>-*.jsonl`) must exist for each of the
  three heroes: `integrated-hub-disruption-recovery`,
  `aog-engineering-recovery`, `preemptive-schedule-resilience`.
- **REQ-002**: All nine VERTICAL-PROOF §6 completion criteria must pass.
- **REQ-003**: `tools/workflow_visibility_proof.py` must pass for all
  three heroes with live/replay parity.
- **REQ-004**: The proof harness must run all three heroes in one
  integrated session.
- **REQ-005**: Seller review must be marked PENDING — machine proof
  cannot set it to PASS.
- **REQ-006**: No phantom workflows may appear when Functions host is
  disabled.
- **REQ-007**: Direct diagnostic must work when actor world is disabled.
- **REQ-008**: Zero browser console errors.
- **REQ-009**: HITL auto-close within 15 seconds with `PERSONA_AUTO_CLOSE=*`.

---

## Phase 1 — Extended Proof Harness

### Task 1.1: Update proof shell script for three heroes

**File:** `tools/airline_zava_e2e_proof.sh`

- [ ] Add Functions host orchestrator checks for all three:

```bash
for orchestrator in \
  AirlineIntegratedHubRecoveryOrchestrator \
  AirlineAogEngineeringRecoveryOrchestrator \
  AirlineScheduleResilienceOrchestrator; do
  grep -q "$orchestrator" "$FUNC_LOG" || {
    err "Functions host did not index $orchestrator"
    exit 4
  }
done
```

---

### Task 1.2: Update proof driver for all three heroes

**File:** `tools/airline_zava_e2e_proof.mjs`

- [ ] Add scenario triggers for all three heroes:

```javascript
const SCENARIOS = [
  {
    scenario_id: "synthetic-hub-cascade",
    workflow_type: "integrated-hub-disruption-recovery",
    hitl_event: "duty_operations_manager_decision",
    hitl_persona: "duty_operations_manager",
  },
  {
    scenario_id: "synthetic-aog-defect",
    workflow_type: "aog-engineering-recovery",
    hitl_event: "engineering_duty_manager_decision",
    hitl_persona: "engineering_duty_manager",
  },
  {
    scenario_id: "synthetic-schedule-restriction",
    workflow_type: "preemptive-schedule-resilience",
    hitl_event: "network_operations_director_decision",
    hitl_persona: "network_operations_director",
  },
];
```

- [ ] For each scenario:
  1. POST to `/api/world/scenarios/{scenario_id}` to trigger.
  2. Poll `GET /api/workflows?type={workflow_type}` until `awaiting_hitl`.
  3. Extract `hitl_context` from workflow payload.
  4. POST persona auto-close decision.
  5. Poll until terminal state.
  6. Assert cross-surface identity (§2).
  7. Capture recording.

---

## Phase 2 — Recording Capture and Commit

### Task 2.1: Capture all three recordings

- [ ] Run the proof harness to generate recordings:

```bash
bash tools/airline_zava_e2e_proof.sh
```

**Expected:** Three recording files in
`tmp/airline-zava-e2e-proof/recordings/`:
- `integrated-hub-disruption-recovery-*.jsonl`
- `aog-engineering-recovery-*.jsonl`
- `preemptive-schedule-resilience-*.jsonl`

---

### Task 2.2: Copy recordings to data directory

- [ ] Copy recordings:

```bash
cp tmp/airline-zava-e2e-proof/recordings/*.jsonl \
   data/blueprint-recordings/
```

- [ ] Verify all three exist:

```bash
ls -la data/blueprint-recordings/integrated-hub-disruption-recovery-*.jsonl
ls -la data/blueprint-recordings/aog-engineering-recovery-*.jsonl
ls -la data/blueprint-recordings/preemptive-schedule-resilience-*.jsonl
```

**Expected:** Three non-empty files.

---

## Phase 3 — VERTICAL-PROOF Gate 1: Proof Chain

### Task 3.1: Verify proof chain for each hero

For each of the three workflow types, confirm the causal chain:

```
actor world → sensor fires → objective registered → Durable orchestration
→ HITL gate raised → typed command issued → world mutation written
→ evaluation passes
```

- [ ] Hero 1 (`integrated-hub-disruption-recovery`):

```bash
# Scenario trigger
curl -sf http://127.0.0.1:14101/api/world/scenarios/synthetic-hub-cascade | jq .

# Wait for workflow
curl -sf 'http://127.0.0.1:14101/api/workflows?type=integrated-hub-disruption-recovery' | jq '.[0].status'
# Expected: "completed" or "decision_ready"

# Verify world events
curl -sf 'http://127.0.0.1:14101/api/world/events?workflow_id=AIRHUB-0001' | jq length
# Expected: ≥1
```

- [ ] Hero 2 (`aog-engineering-recovery`): same pattern with
  `synthetic-aog-defect` scenario and workflow type
  `aog-engineering-recovery`.

- [ ] Hero 3 (`preemptive-schedule-resilience`): same pattern with
  `synthetic-schedule-restriction` scenario and workflow type
  `preemptive-schedule-resilience`.

---

## Phase 4 — VERTICAL-PROOF Gate 2: Identity Consistency

### Task 4.1: Cross-surface verification for each hero

For each hero, verify all eight surfaces agree:

| Surface | Command |
|---------|---------|
| World | `GET /api/world/events?workflow_id=<id>` — ≥1 event |
| Workflow API | `GET /api/workflows/<id>` — `status`, `current_phase` |
| Drawer | Open workflow card; confirm phase ribbon matches API |
| Memory | `GET /api/memory/search?q=<id>` — ≥1 result |
| Knowledge | Cypher `MATCH (w {id: "<id>"}) RETURN w.status` |
| AG-UI | Confirm `workflow.completed` event carries correct `workflow_id` |
| Graph | `MATCH (w)-[:HAS_PHASE]->()` returns expected count |
| Constellation | Workflow appears with correct phase sequence |

- [ ] Hero 1: 8 surface checks pass.
- [ ] Hero 2: 8 surface checks pass.
- [ ] Hero 3: 8 surface checks pass.

---

## Phase 5 — VERTICAL-PROOF Gate 3: Replay Probes

### Task 5.1: Functions-disabled probe

- [ ] Stop the Azure Functions host.
- [ ] Trigger each scenario.
- [ ] Verify: no phantom `workflow.started` event appears in the feed.
- [ ] Verify: no `500` error propagates to the browser.
- [ ] Restart Functions host and confirm normal operation resumes.

```bash
# Kill Functions host
kill $FUNC_PID

# Trigger scenario (expect no workflow)
curl -sf http://127.0.0.1:14101/api/world/scenarios/synthetic-hub-cascade || true
sleep 2
curl -sf 'http://127.0.0.1:14101/api/workflows?type=integrated-hub-disruption-recovery' | jq length
# Expected: 0 (no new workflow)
```

---

### Task 5.2: Actor-world-disabled probe

- [ ] Stop the actor world process.
- [ ] POST to the pack-owned diagnostic route.
- [ ] Verify: Durable orchestration completes without the actor world.
- [ ] Verify: no dead letter entries.
- [ ] Verify: the diagnostic preserves its real source sensor input.
- [ ] Verify: no claimed world mutation while the world is disabled.
- [ ] Restart actor world and confirm full chain works.

---

## Phase 6 — VERTICAL-PROOF Gate 4: Browser Error Gate

### Task 6.1: Browser console error check

- [ ] Open browser DevTools before starting proof run.
- [ ] After all three heroes complete:
  - Zero console errors.
  - Zero dropped workflow events (contiguous AG-UI stream).
  - Click-to-first-visible latency < 1 second for each scenario.

---

### Task 6.2: HITL completion latency

- [ ] With `PERSONA_AUTO_CLOSE=*`, verify each HITL gate shows:
  - Persona decision
  - `durable.resumed`
  - Terminal workflow state
  — all within 15 seconds.

---

### Task 6.3: Clean teardown

- [ ] After stopping the stack:

```bash
lsof -ti :14101 | head -1  # FastAPI
lsof -ti :18171 | head -1  # Functions
lsof -ti :16273 | head -1  # Control Plane
```

**Expected:** All empty — no orphan processes.

---

### Task 6.4: Backend restart recovery

- [ ] Keep browser mounted, restart the actor-world backend.
- [ ] Verify the client replays from `after=0` when `latest_seq` is lower.
- [ ] No manual page refresh required.

---

## Phase 7 — VERTICAL-PROOF Gate 5: Distinct Hero Evidence

### Task 7.1: Verify hero evidence isolation

For each pair of heroes, confirm distinct:

| Dimension | Hero 1 | Hero 2 | Hero 3 |
|-----------|--------|--------|--------|
| Trigger | `synthetic-hub-cascade` | `synthetic-aog-defect` | `synthetic-schedule-restriction` |
| Workflow type | `integrated-hub-disruption-recovery` | `aog-engineering-recovery` | `preemptive-schedule-resilience` |
| Command type | `airline.commit_recovery_plan` | `airline.commit_aog_recovery` | `airline.commit_schedule_adjustment` |
| HITL persona | `duty_operations_manager` | `engineering_duty_manager` | `network_operations_director` |
| Success event | `airline.recovery.applied` | `airline.aog_recovery.applied` | `airline.schedule_adjustment.applied` |
| Recording file | `integrated-hub-*` | `aog-engineering-*` | `preemptive-schedule-*` |

- [ ] All six dimensions are distinct across all three heroes.

---

## Phase 8 — VERTICAL-PROOF Gate 5a: Execution Visibility

### Task 8.1: Run workflow visibility proof — live

- [ ] With the stack running and all three heroes terminal:

```bash
ZAVA_VERTICAL=airline .venv/bin/python tools/workflow_visibility_proof.py \
  --vertical airline --base-url http://127.0.0.1:14101 \
  --save-dir proof/workflow-details/live
```

**Expected:** Exit 0. All three workflow types pass visibility checks.

---

### Task 8.2: Run workflow visibility proof — replay

- [ ] Switch to replay mode and run:

```bash
ZAVA_VERTICAL=airline .venv/bin/python tools/workflow_visibility_proof.py \
  --vertical airline --base-url http://127.0.0.1:14101 \
  --compare-dir proof/workflow-details/live \
  --save-dir proof/workflow-details/replay
```

**Expected:** Exit 0. Live/replay parity confirmed.

---

## Phase 9 — VERTICAL-PROOF Gates 6, 7, 8

### Task 9.1: HITL authority matrix (Gate 6)

- [ ] For each hero, verify:
  - The real governance authority matrix allows the emitted
    action/category/value.
  - The suspended workflow persists `payload.hitl_context` for recovery
    sweeps.

```bash
# Hero 1: duty_operations_manager, airline.commit_recovery_plan, ≤150k
# Hero 2: engineering_duty_manager, airline.commit_aog_recovery, ≤200k
# Hero 3: network_operations_director, airline.commit_schedule_adjustment, ≤300k
```

---

### Task 9.2: Graduate.sh validation (Gate 7)

- [ ] Preserve the compose-domain sandbox used to add each new airline
  workflow and run its generated graduation script from a clean checkout:

```bash
ZAVA_VERTICAL=airline bash tools/scratch/compose-domain/<run-id>/graduate.sh
```

**Expected:** The generated script prints `step 6/6`, validates all three
workflow types in `active_runtime().pack.domains`, and exits 0. The proof
harness is additional evidence and cannot substitute for this gate.

---

### Task 9.3: Recording existence (Gate 8)

- [ ] Verify committed recordings:

```bash
ls data/blueprint-recordings/integrated-hub-disruption-recovery-*.jsonl
ls data/blueprint-recordings/aog-engineering-recovery-*.jsonl
ls data/blueprint-recordings/preemptive-schedule-resilience-*.jsonl
```

**Expected:** Three non-empty committed files.

---

## Phase 10 — VERTICAL-PROOF Gate 9: Execution Visibility (Full)

This is covered by Phase 8 Tasks 8.1 and 8.2 above.

---

## Phase 11 — Seller Review Preparation

### Task 11.1: Document seller walk for all three heroes

**File:** `verticals/airline/SELLER-REVIEW.md` (new)

- [x] Create a seller-review checklist document:

```markdown
# Airline Vertical — Seller Review

**Status:** PENDING (requires human review)

## Machine proof status

All nine VERTICAL-PROOF completion criteria pass. Evidence directory:
`proof/workflow-details/`.

## Seller walk: Hero 1 — Integrated Hub Disruption Recovery

1. [ ] Orient: open synthetic airline world; identify hub bank
2. [ ] Establish health: morning bank feasible, KPIs stable
3. [ ] Trigger: activate `synthetic-hub-cascade`
4. [ ] Observe causality: delay + stand constraint cascade
5. [ ] Inspect intelligence: workflow detail shows deterministic vs agent
6. [ ] Govern: Duty Operations Manager approval visible
7. [ ] Execute: typed command mutation visible
8. [ ] Measure: D0/D15, cancellations avoided, crew margin, cost
9. [ ] Trace: same workflow ID across 8 surfaces
10. [ ] Reset: healthy bank restored

## Seller walk: Hero 2 — AOG Engineering & Spares Recovery

1. [ ] Trigger: activate `synthetic-aog-defect`
2. [ ] Observe: aircraft grounded, maintenance/spares constraints visible
3. [ ] Govern: Engineering Duty Manager approval
4. [ ] Execute: work order + spares coordination
5. [ ] Verify: aircraft NOT released by AI
6. [ ] Trace: cross-surface identity

## Seller walk: Hero 3 — Pre-emptive Schedule Resilience

1. [ ] Trigger: activate `synthetic-schedule-restriction`
2. [ ] Observe: forecast restriction, affected sectors
3. [ ] Govern: Network Operations Director approval
4. [ ] No-action option: explicit monitor_risk visible
5. [ ] Execute: schedule adjustment applied
6. [ ] Verify: deliverability vs counterfactual
7. [ ] Trace: cross-surface identity

## Seller review criteria (human only)

- [ ] Reset works cleanly between heroes
- [ ] Pacing is seller-appropriate
- [ ] Visual quality meets bar
- [ ] Story coherence across all three heroes
- [ ] No confusing or misleading UI elements

## Readiness

| Gate | Status |
|------|--------|
| Build ready | PASS (all machine gates) |
| Demo ready | PENDING (awaits human seller review) |
| Deployed | NOT STARTED |
```

---

### Task 11.2: Mark proof manifest

- [ ] If `proof/manifest.json` exists, add airline entries. If not, this
  step is informational only (per VERTICAL-PROOF §6a: "This contract
  version does not change proof/manifest.json").

---

## Phase 12 — Final Regression and Completion Gate

### Task 12.1: Full test suite

```bash
.venv/bin/python -m pytest tests/api/airline/ -x -q
```

**Expected:** All pass.

---

### Task 12.2: Full proof harness

```bash
bash tools/airline_zava_e2e_proof.sh
```

**Expected:** `AIRLINE ZAVA E2E PROOF PASSED`.

---

## Completion Checklist — Nine VERTICAL-PROOF Gates

| # | Gate | Status |
|---|------|--------|
| 1 | §1 Proof chain passes for all 3 heroes | PASS |
| 2 | §2 Identity consistency (8 surfaces) for all 3 heroes | PASS |
| 3 | §3a Functions-disabled probe passes | PASS |
| 4 | §3b Actor-world-disabled probe passes | PASS |
| 5 | §4 Browser error gate (zero errors, clean teardown) | PASS |
| 6 | §5 Distinct hero evidence (trigger, command, world case) | PASS |
| 7 | §6.6 HITL authority matrix verified for all 3 personas | PASS |
| 8 | §6.7 graduate.sh / proof harness exit 0 | PASS |
| 9 | §6.8 Recordings committed for all 3 heroes | PASS |

**Readiness:**
- **Build ready:** All nine gates pass → **PASS**
- **Demo ready:** Seller review → **PENDING** (human completes)
- **Deployed:** Separate deployment flow → **NOT STARTED**

---

## Scope Decisions

1. **Seller review PENDING**: The VERTICAL-PROOF contract and build
   contract both explicitly state that machine proof cannot set seller
   review to PASS. The `SELLER-REVIEW.md` document provides the human
   reviewer a structured checklist.
2. **All three heroes in one proof session**: The proof harness triggers
   all three scenarios sequentially in one isolated stack. The heroes
   use non-colliding scenarios (hub cascade, AOG defect, schedule
   restriction) and can all run against the same seeded world.
3. **No proof/manifest.json changes**: Per VERTICAL-PROOF §6a, the
   current contract version does not change the manifest schema.
4. **Replay parity**: The visibility proof's `--compare-dir` mode
   confirms live/replay parity per §5a.
5. **Port allocation**: Airline proof ports (14101, 18171, etc.) are
   shifted above telco proof ports (13101, 17171) to allow parallel runs.
