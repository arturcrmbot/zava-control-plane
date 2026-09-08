---
goal: Implement Hero 3 (Pre-emptive Schedule Resilience) end to end with distinct domain, world scenario, orchestrator, command, projection, and proof evidence
version: 1.0
date_created: 2026-08-10
last_updated: 2026-08-10
owner: Zava engineering
status: Planned
tags: [airline, hero-3, schedule-resilience, preemptive, durable-functions]
depends_on: [2026-08-10-airline-golden-hero-readiness, 2026-08-10-airline-aog-engineering-recovery]
---

# Airline Schedule Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Pre-emptive Schedule Resilience as a distinct governed airline hero with an explicit no-action decision.

**Architecture:** Extend the airline world with forecast constraints and schedule-risk state, then add an isolated command family, Durable orchestration, agent/tool contracts, authority, projection, and diagnostic route. Keep forecast uncertainty visible and deterministic feasibility authoritative.

**Tech Stack:** Python 3.11, pytest, Azure Durable Functions, FastAPI, Pydantic, entity-graph projections.

---

This plan implements the third airline hero workflow —
`preemptive-schedule-resilience` — from forecast sensor through terminal
network-stability evaluation.

Design authority:
[`2026-07-28-airline-vertical-design.md`](../specs/2026-07-28-airline-vertical-design.md) §10.
Proof contract: [`docs/VERTICAL-PROOF.md`](../../VERTICAL-PROOF.md).
Build contract:
[`docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md`](../contracts/VERTICAL-BUILD-CONTRACT.md).

> **For agentic workers:** Execute phases in order. Within a phase, tasks
> may run in parallel only when the Dependencies column permits it. Use
> TDD for every code task. Do not begin the next phase until its
> completion gate passes.

## 1. Requirements & Constraints

- **REQ-001**: `preemptive-schedule-resilience` must be a distinct
  workflow type registered in `verticals/airline/domains.py`.
- **REQ-002**: A distinct scenario (`synthetic-schedule-restriction`)
  must exist with a forecast-type trigger rather than a live disruption.
- **REQ-003**: The typed command schema must differ from Hero 1 and Hero 2;
  each hero's command handler must reject the other two heroes' payloads.
- **REQ-004**: The HITL gate must use `network_operations_director` with
  spend limit GBP 300,000.
- **REQ-005**: A no-action option must be present as an explicit
  `"monitor_risk"` action, not an omission.
- **REQ-006**: The evaluation must compare post-action deliverability with
  the no-action counterfactual.
- **REQ-007**: Cross-surface identity (§2 of VERTICAL-PROOF) must pass
  independently from Hero 1 and Hero 2.

---

## Phase 1 — Process Profile and Domain Registration

### Task 1.1: Add schedule resilience process profile

**File:** `verticals/airline/process_profiles.py`

- [ ] Add constants:

```python
SCHED_WORKFLOW_TYPE = "preemptive-schedule-resilience"
SCHED_ORCHESTRATOR = "AirlineScheduleResilienceOrchestrator"
SCHED_SENSOR_ID = "sensor:schedule_resilience"
SCHED_OBJECTIVE_TYPE = "preemptive_schedule_resilience"
SCHED_COMMAND_TYPE = "airline.commit_schedule_adjustment"
SCHED_SUCCESS_EVENT = "airline.schedule_adjustment.applied"
SCHED_FAILURE_EVENT = "command.rejected"
SCHED_HITL_PERSONA = "network_operations_director"
SCHED_HITL_EVENT = "network_operations_director_decision"
SCHED_SCENARIO_ID = "synthetic-schedule-restriction"
SCHED_STORY_ID = "SYN-STORY-SCHED-001"
```

- [ ] Add `AirlineProcessProfile` entry:

```python
AIRLINE_PROCESS_PROFILES[SCHED_WORKFLOW_TYPE] = AirlineProcessProfile(
    workflow_type=SCHED_WORKFLOW_TYPE,
    orchestrator=SCHED_ORCHESTRATOR,
    sensor_id=SCHED_SENSOR_ID,
    objective_type=SCHED_OBJECTIVE_TYPE,
    command_type=SCHED_COMMAND_TYPE,
    success_event=SCHED_SUCCESS_EVENT,
    failure_event=SCHED_FAILURE_EVENT,
    hitl_persona=SCHED_HITL_PERSONA,
    hitl_event=SCHED_HITL_EVENT,
    scenario_id=SCHED_SCENARIO_ID,
    story_id=SCHED_STORY_ID,
)
```

---

### Task 1.2: Register schedule resilience domain

**File:** `verticals/airline/domains.py`

- [ ] Add:

```python
SCHED_WORKFLOW_TYPE = "preemptive-schedule-resilience"

AIRLINE_DOMAINS[SCHED_WORKFLOW_TYPE] = Domain(
    workflow_type=SCHED_WORKFLOW_TYPE,
    display_name="Pre-emptive Schedule Resilience",
    workflow_id_prefix="AIRSCHED",
    orchestrator_name="AirlineScheduleResilienceOrchestrator",
    operator_surface="network-planning",
    phases=(
        Phase("Detect Schedule Risk Signal", "deterministic"),
        Phase("Assess Network Ripple Effects", "agent"),
        Phase("Synthesize Resilience Options", "agent"),
        Phase("Approve Schedule Adjustment", "hitl"),
        Phase("Commit Schedule Adjustment", "deterministic"),
        Phase("Verify Network Stability", "deterministic"),
    ),
    hitl_gates=(
        HitlGate(
            "Approve Schedule Adjustment",
            "network_operations_director_decision",
            "network_operations_director",
        ),
    ),
    skills=("schedule-risk-assessor", "resilience-option-ranker"),
    stub=False,
)
```

---

### Task 1.3: Add network_operations_director persona and authority

**File:** `verticals/airline/personas.py`

- [ ] Add:

```python
"network_operations_director": Persona(
    role="network_operations_director",
    archetype="approver",
    scope_function="commercial",
    workflow_label="Network Operations Director",
    external_event_default="network_operations_director_decision",
    default_authority_band="synthetic-up-to-GBP-300000",
    uses_authority_mcp=True,
    description=(
        "Owns consequential schedule-resilience decisions for the "
        "synthetic airline network."
    ),
    display_color="#7c3aed",
),
```

**File:** `verticals/airline/authority.py`

- [ ] Add:

```python
"network_operations_director": AuthorityRow(
    role="network_operations_director",
    spend_limit_gbp=300_000.0,
    approval_actions=(
        "network_operations_director_decision",
        "airline.commit_schedule_adjustment",
    ),
    delegate_to=None,
),
```

**File:** `verticals/airline/functions.py`

- [ ] Add:

```python
"network-planning": Function(
    name="network-planning",
    display="Network Planning",
    operator_surface="network-planning",
    owns_domains=("preemptive-schedule-resilience",),
    ambient_agents=(),
    kpis=(),
    persona_hierarchy=PersonaTree(role="network_operations_director"),
),
```

---

## Phase 2 — World Model Extensions

### Task 2.1: Add schedule resilience reference data

**File:** `verticals/airline/worlds/schedule_reference_data.py` (new)

- [ ] Define forecast restriction entities:

```python
from dataclasses import dataclass

@dataclass
class ForecastRestriction:
    id: str
    restriction_type: str  # "airport_capacity", "airspace", "weather", "crew"
    affected_station_id: str
    affected_window_start: float
    affected_window_end: float
    confidence: float  # 0.0-1.0
    capacity_reduction_pct: int
    status: str  # "forecast", "confirmed", "expired"
    version: int = 1
    last_event_id: str | None = None


def build_forecast_restrictions() -> list[ForecastRestriction]:
    return [
        ForecastRestriction(
            "SYN-RESTRICTION-001",
            "airport_capacity",
            "SYN-HUB-01",
            120.0,   # affects afternoon window
            240.0,
            0.75,
            40,      # 40% capacity reduction
            "forecast",
        ),
    ]
```

---

### Task 2.2: Extend AirlineWorld for schedule scenario

**File:** `verticals/airline/worlds/scenario.py`

- [ ] Add `forecast_restrictions` collection to `__init__`.
- [ ] Seed forecast restrictions in `install()`.
- [ ] Add `activate_scenario` support for `"synthetic-schedule-restriction"`:

The scenario confirms the forecast restriction, identifies sectors in the
affected window (SYN-SECTOR-OUT-003 and SYN-SECTOR-OUT-004, departing at
170 and 180 minutes), and emits `airline.schedule_risk.detected`.

- [ ] Add `reference_process_types` to include `SCHED_WORKFLOW_TYPE`.

---

### Task 2.3: Write schedule scenario unit tests

**File:** `tests/api/airline/test_schedule_scenario.py`

- [ ] Test that activating `synthetic-schedule-restriction` confirms the
  restriction, emits source and sensor events, and the observation is
  buildable with affected sectors and the no-action counterfactual.

```bash
.venv/bin/python -m pytest tests/api/airline/test_schedule_scenario.py -x -q
```

**Expected:** All pass.

---

## Phase 3 — Schedule Commands and Constraints

### Task 3.1: Create schedule constraints module

**File:** `verticals/airline/schedule_constraints.py` (new)

- [ ] Define `ScheduleAction`, `ScheduleOption`, `ScheduleFeasibilityResult`.
- [ ] Three options:

1. `SYN-SCHED-OPTION-BUFFER` — add 30-minute buffer to affected sectors,
   GBP 35,000. Actions: `add_buffer` on each affected sector.
2. `SYN-SCHED-OPTION-CANCEL-ONE` — cancel the lowest-priority sector
   `SYN-SECTOR-OUT-004`, GBP 120,000. Action: `cancel_sector`.
3. `SYN-SCHED-OPTION-MONITOR` — retain schedule unchanged with explicit
   `monitor_risk` action, GBP 0. This is the no-action option.

- [ ] `admit_schedule_options(observation)` validates slot feasibility,
  crew margin, and aircraft availability.

---

### Task 3.2: Create schedule command handler

**File:** `verticals/airline/actions/schedule_commands.py` (new)

- [ ] `schedule_command_id(workflow_id, decision_id, option_id) -> str`
  returning `SYN-CMD-SCHED-{workflow_id}-{decision_id}-{option_id}`.

- [ ] `command_for_schedule_option(world, *, option_id, workflow_id, decision_id, persona) -> SimulationCommand`
  with `type=SCHED_COMMAND_TYPE`.

- [ ] `apply_schedule_command(world, command) -> SimulationEvent`:
  - Validates command type is `SCHED_COMMAND_TYPE` (rejects Hero 1/2).
  - Buffer: retimes affected sectors, adjusts slots.
  - Cancel: cancels `SYN-SECTOR-OUT-004`.
  - Monitor: records explicit risk-accepted decision with no mutation.
  - Emits `SCHED_SUCCESS_EVENT`, creates `ScheduleEvaluation`.

- [ ] Add `ScheduleEvaluation` dataclass to `worlds/model.py`:

```python
@dataclass
class ScheduleEvaluation:
    id: str
    workflow_id: str
    command_id: str
    option_id: str
    status: str
    invariant_results: tuple[str, ...]
    predicted_delay_reduction_pct: int
    predicted_cancellations_avoided: int
    schedule_capacity_retained_pct: int
    passengers_notified: int
    forecast_uncertainty: float
    synthetic_intervention_cost_gbp: float
    version: int = 1
    last_event_id: str | None = None
```

---

### Task 3.3: Write schedule command unit tests

**File:** `tests/api/airline/test_schedule_commands.py`

- [ ] Tests for all three options: buffer accepted, cancel accepted,
  monitor accepted (no mutation but explicit evaluation).
- [ ] Cross-command rejection: Hero 1 and Hero 2 payloads rejected.

```bash
.venv/bin/python -m pytest tests/api/airline/test_schedule_commands.py -x -q
```

**Expected:** All pass.

---

## Phase 4 — Schedule Durable Orchestrator

### Task 4.1: Create schedule MCP tools

**File:** `verticals/airline/mcp_tools/planning.py` (new)

- [ ] `airline_read_schedule_risk_evidence` — reads forecast restriction
  and affected sector evidence.
- [ ] `airline_rank_resilience_options` — returns admitted options with
  ranking context.

---

### Task 4.2: Create schedule skills and agents

**Directory:** `verticals/airline/skills/schedule-risk-assessor/`

- [ ] Create `SKILL.md`.

**Directory:** `verticals/airline/skills/resilience-option-ranker/`

- [ ] Create `SKILL.md`.

**File:** `verticals/airline/agents.py`

- [ ] Add:

```python
"schedule-risk-assessor": AgentRegistryEntry(
    agent_id="schedule-risk-assessor",
    description=(
        "Explains forecast restriction effects across the synthetic "
        "airline network."
    ),
),
"resilience-option-ranker": AgentRegistryEntry(
    agent_id="resilience-option-ranker",
    description=(
        "Ranks deterministically feasible pre-emptive schedule "
        "intervention options."
    ),
),
```

---

### Task 4.3: Create schedule Durable orchestrator

**File:** `verticals/airline/schedule_durable.py` (new)

- [ ] Implement `schedule_orchestration(context)` with six phases:

  1. `workflow.started` checkpoint
  2. `schedule_evidence_activity_trigger` — validate forecast restriction
     evidence
  3. `schedule_agent_activity_trigger` — assess ripple effects (agent)
  4. `schedule_agent_activity_trigger` — synthesize resilience options (agent)
  5. `schedule_governance_activity_trigger` — authority check for
     `network_operations_director`
  6. HITL gate:
     `wait_for_external_event("network_operations_director_decision")`
  7. `schedule_command_activity_trigger` — commit schedule adjustment
  8. Terminal checkpoint

- [ ] Register activities and orchestrator:

```python
@app.orchestration_trigger(context_name="context")
def AirlineScheduleResilienceOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return schedule_orchestration(context)
```

---

### Task 4.4: Create schedule entity projection

**File:** `verticals/airline/entity_projections/planning.py` (new)

- [ ] `project(workflow)` for `preemptive-schedule-resilience` workflows.

---

### Task 4.5: Create schedule workflow detail hook

**File:** `verticals/airline/schedule_detail.py` (new)

- [ ] `schedule_workflow_detail(workflow, app_state)` returning
  schedule-specific detail dict.

---

## Phase 5 — Wire into Manifest

### Task 5.1: Update manifest.py

**File:** `verticals/airline/manifest.py`

- [ ] Add schedule durable module loading.
- [ ] Add schedule orchestrator/activities.
- [ ] Add schedule MCP module.
- [ ] Add schedule projection.
- [ ] Add schedule workflow type to `memory_workflow_types`.
- [ ] Update `workflow_detail_hook` to dispatch to schedule detail.

---

### Task 5.2: Update world registration

**File:** `verticals/airline/worlds/registration.py`

- [ ] Add schedule objective route with `SCHED_SENSOR_ID`,
  `SCHED_OBJECTIVE_TYPE`, `SCHED_COMMAND_TYPE`, `SCHED_SUCCESS_EVENT`,
  `SCHED_FAILURE_EVENT`.

- [ ] Add schedule responder with `SCHED_ORCHESTRATOR`,
  `SCHED_WORKFLOW_TYPE`, prefix `"sched"`, owner function
  `"network-planning"`.

---

### Task 5.3: Update diagnostics

**File:** `verticals/airline/worlds/diagnostics.py`

- [ ] Extend `build_diagnostic_input` to handle
  `preemptive-schedule-resilience`.

---

## Phase 6 — Schedule Persona Files

### Task 6.1: Create network_operations_director personae

**Directory:** `verticals/airline/personae/network_operations_director/`

- [ ] Create `SKILL.md` with decision policy.

---

## Phase 7 — Integration Tests

### Task 7.1: Write schedule end-to-end test

**File:** `tests/api/airline/test_schedule_e2e.py`

- [ ] Full chain: install → activate schedule scenario → build observation →
  admit options (including no-action) → construct command → apply → verify
  evaluation.
- [ ] Specifically test the monitor/no-action option produces a valid
  evaluation with no world mutation.

```bash
.venv/bin/python -m pytest tests/api/airline/test_schedule_e2e.py -x -q
```

**Expected:** All pass.

---

### Task 7.2: Cross-command rejection for all three heroes

**File:** `tests/api/airline/test_three_hero_isolation.py`

- [ ] For each of the 3 command types, verify the other 2 handlers reject
  them.

```bash
.venv/bin/python -m pytest tests/api/airline/test_three_hero_isolation.py -x -q
```

**Expected:** All pass.

---

### Task 7.3: Full regression

```bash
.venv/bin/python -m pytest tests/api/airline/ -x -q
```

**Expected:** All airline tests pass.

---

## Phase 8 — Completion Gate

- [ ] Schedule domain registered with 6 distinct phases.
- [ ] Schedule scenario activates with forecast restriction trigger.
- [ ] All three options (buffer, cancel, monitor) accepted and evaluated.
- [ ] No-action/monitor option produces explicit evaluation with
  `monitor_risk` action recorded.
- [ ] All three hero command types reject each other.
- [ ] `network_operations_director` persona resolves in authority check.
- [ ] All airline tests pass.

---

## Scope Decisions

1. **Forecast vs live**: The schedule hero uses a forecast-type trigger
   (`airline.schedule_risk.detected`) rather than a live disruption. The
   scenario sets `confidence: 0.75` on the restriction to demonstrate
   that the evaluation must surface forecast uncertainty.
2. **No-action option**: Implemented as an explicit `monitor_risk` action
   with GBP 0 value, not an omission. The evaluation records the
   no-action counterfactual and makes the risk-accepted decision visible.
3. **Affected sectors**: The restriction targets the hub afternoon window
   (120–240 min), catching SYN-SECTOR-OUT-003 (170) and SYN-SECTOR-OUT-004
   (180). This avoids colliding with Hero 1's morning cascade (60–150 min)
   or Hero 2's AOG scenario on SYN-TAIL-003.
4. **Recordings and proof**: Deferred to Plan 4. This plan delivers
   testable working software.
