---
goal: Implement Hero 2 (AOG Engineering and Spares Recovery) end to end with distinct domain, world scenario, orchestrator, command, projection, and proof evidence
version: 1.0
date_created: 2026-08-10
last_updated: 2026-08-10
owner: Zava engineering
status: Planned
tags: [airline, hero-2, aog, engineering, durable-functions]
depends_on: [2026-08-10-airline-golden-hero-readiness]
---

# Airline AOG Engineering Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement AOG Engineering and Spares Recovery as a distinct, governed airline hero from sensor through measured world mutation.

**Architecture:** Extend the existing airline actor world with pack-owned engineering entities and a separate command family. Register a dedicated Durable orchestration, agent/tool contracts, persona authority, projection, and diagnostic route while reusing only industry-neutral substrate interfaces.

**Tech Stack:** Python 3.11, pytest, Azure Durable Functions, FastAPI, Pydantic, entity-graph projections.

---

This plan implements the second airline hero workflow —
`aog-engineering-recovery` — from sensor through terminal evaluation.

Design authority:
[`2026-07-28-airline-vertical-design.md`](../specs/2026-07-28-airline-vertical-design.md) §9.
Proof contract: [`docs/VERTICAL-PROOF.md`](../../VERTICAL-PROOF.md).
Build contract:
[`docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md`](../contracts/VERTICAL-BUILD-CONTRACT.md).

> **For agentic workers:** Execute phases in order. Within a phase, tasks
> may run in parallel only when the Dependencies column permits it. Use
> TDD for every code task. Do not begin the next phase until its
> completion gate passes.

## 1. Requirements & Constraints

- **REQ-001**: `aog-engineering-recovery` must be a distinct workflow type
  registered in `verticals/airline/domains.py` with its own phases, HITL
  gate, skills, and orchestrator.
- **REQ-002**: A distinct AOG scenario (`synthetic-aog-defect`) must exist
  in the airline world with its own trigger event and sensor.
- **REQ-003**: The typed command schema must differ from Hero 1's; Hero 1's
  command handler must reject Hero 2's payload and vice versa.
- **REQ-004**: The HITL gate must use the `engineering_duty_manager`
  persona with its own authority row and spend limit (GBP 200,000).
- **REQ-005**: The world mutation must not release the aircraft to service;
  a return-to-service event is external evidence ingestion only.
- **REQ-006**: A deterministic evaluation must verify engineering recovery
  measures.
- **REQ-007**: Cross-surface identity (§2 of VERTICAL-PROOF) must pass
  independently from Hero 1.

---

## Phase 1 — Process Profile and Domain Registration

### Task 1.1: Add AOG process profile

**File:** `verticals/airline/process_profiles.py`

- [ ] Add AOG constants:

```python
AOG_WORKFLOW_TYPE = "aog-engineering-recovery"
AOG_ORCHESTRATOR = "AirlineAogEngineeringRecoveryOrchestrator"
AOG_SENSOR_ID = "sensor:aog_engineering"
AOG_OBJECTIVE_TYPE = "recover_aog_engineering"
AOG_COMMAND_TYPE = "airline.commit_aog_recovery"
AOG_SUCCESS_EVENT = "airline.aog_recovery.applied"
AOG_FAILURE_EVENT = "command.rejected"
AOG_HITL_PERSONA = "engineering_duty_manager"
AOG_HITL_EVENT = "engineering_duty_manager_decision"
AOG_SCENARIO_ID = "synthetic-aog-defect"
AOG_STORY_ID = "SYN-STORY-AOG-001"
```

- [ ] Add `AirlineProcessProfile` entry:

```python
AIRLINE_PROCESS_PROFILES[AOG_WORKFLOW_TYPE] = AirlineProcessProfile(
    workflow_type=AOG_WORKFLOW_TYPE,
    orchestrator=AOG_ORCHESTRATOR,
    sensor_id=AOG_SENSOR_ID,
    objective_type=AOG_OBJECTIVE_TYPE,
    command_type=AOG_COMMAND_TYPE,
    success_event=AOG_SUCCESS_EVENT,
    failure_event=AOG_FAILURE_EVENT,
    hitl_persona=AOG_HITL_PERSONA,
    hitl_event=AOG_HITL_EVENT,
    scenario_id=AOG_SCENARIO_ID,
    story_id=AOG_STORY_ID,
)
```

---

### Task 1.2: Register AOG domain

**File:** `verticals/airline/domains.py`

- [ ] Add import of AOG constants.
- [ ] Add AOG domain entry:

```python
AOG_WORKFLOW_TYPE = "aog-engineering-recovery"

AIRLINE_DOMAINS[AOG_WORKFLOW_TYPE] = Domain(
    workflow_type=AOG_WORKFLOW_TYPE,
    display_name="AOG Engineering & Spares Recovery",
    workflow_id_prefix="AIRAOG",
    orchestrator_name="AirlineAogEngineeringRecoveryOrchestrator",
    operator_surface="engineering-control",
    phases=(
        Phase("Detect AOG Event", "deterministic"),
        Phase("Check Airworthiness Constraints", "deterministic"),
        Phase("Synthesize Engineering Recovery Options", "agent"),
        Phase("Approve Engineering Recovery", "hitl"),
        Phase("Commit Engineering and Operational Actions", "deterministic"),
        Phase("Verify Recovery State", "deterministic"),
    ),
    hitl_gates=(
        HitlGate(
            "Approve Engineering Recovery",
            "engineering_duty_manager_decision",
            "engineering_duty_manager",
        ),
    ),
    skills=("engineering-recovery-planner",),
    stub=False,
)
```

---

### Task 1.3: Add engineering_duty_manager persona and authority

**File:** `verticals/airline/personas.py`

- [ ] Add:

```python
"engineering_duty_manager": Persona(
    role="engineering_duty_manager",
    archetype="approver",
    scope_function="commercial",
    workflow_label="Engineering Duty Manager",
    external_event_default="engineering_duty_manager_decision",
    default_authority_band="synthetic-up-to-GBP-200000",
    uses_authority_mcp=True,
    description=(
        "Approves material engineering recovery and spares decisions for "
        "the synthetic airline operation."
    ),
    display_color="#dc2626",
),
```

**File:** `verticals/airline/authority.py`

- [ ] Add:

```python
"engineering_duty_manager": AuthorityRow(
    role="engineering_duty_manager",
    spend_limit_gbp=200_000.0,
    approval_actions=(
        "engineering_duty_manager_decision",
        "airline.commit_aog_recovery",
    ),
    delegate_to=None,
),
```

**File:** `verticals/airline/functions.py`

- [ ] Add engineering-control function:

```python
"engineering-control": Function(
    name="engineering-control",
    display="Engineering Control",
    operator_surface="engineering-control",
    owns_domains=("aog-engineering-recovery",),
    ambient_agents=(),
    kpis=(),
    persona_hierarchy=PersonaTree(role="engineering_duty_manager"),
),
```

---

## Phase 2 — World Model Extensions

### Task 2.1: Add AOG world model entities

**File:** `verticals/airline/worlds/model.py`

- [ ] Add new dataclasses:

```python
@dataclass
class TechnicalStatus:
    id: str
    aircraft_id: str
    defect_type: str
    status: str  # "grounded", "work_in_progress", "cleared"
    version: int = 1
    last_event_id: str | None = None


@dataclass
class MaintenanceTask:
    id: str
    aircraft_id: str
    task_type: str
    approved_provider: str
    estimated_hours: float
    status: str  # "pending", "in_progress", "completed"
    version: int = 1
    last_event_id: str | None = None


@dataclass
class Spare:
    id: str
    part_number: str
    location_id: str
    status: str  # "available", "reserved", "in_transit"
    traceable: bool = True
    version: int = 1
    last_event_id: str | None = None


@dataclass
class AogRecoveryCommand:
    id: str
    workflow_id: str
    decision_id: str
    option_id: str
    persona: str
    value_gbp: float
    action_types: tuple[str, ...]
    evidence_versions: tuple[tuple[str, int], ...]
    version: int = 1
    last_event_id: str | None = None


@dataclass
class AogRecoveryEvaluation:
    id: str
    workflow_id: str
    command_id: str
    option_id: str
    status: str
    invariant_results: tuple[str, ...]
    sectors_protected: int
    aog_elapsed_hours: float
    spare_availability: str
    work_order_status: str
    passengers_protected: int
    synthetic_recovery_cost_gbp: float
    version: int = 1
    last_event_id: str | None = None
```

---

### Task 2.2: Add AOG reference data

**File:** `verticals/airline/worlds/aog_reference_data.py` (new)

- [ ] Create reference data builder functions:

```python
from verticals.airline.worlds.model import (
    MaintenanceTask,
    Spare,
    TechnicalStatus,
)
from verticals.airline.worlds.reference_data import HUB_ID

AOG_AIRCRAFT_ID = "SYN-TAIL-003"
AOG_SECTOR_ID = "SYN-SECTOR-OUT-003"


def build_technical_statuses() -> list[TechnicalStatus]:
    return [
        TechnicalStatus(
            "SYN-TECHSTATUS-001",
            AOG_AIRCRAFT_ID,
            "engine_vibration_exceedance",
            "grounded",
        ),
    ]


def build_maintenance_tasks() -> list[MaintenanceTask]:
    return [
        MaintenanceTask(
            "SYN-MAINT-001",
            AOG_AIRCRAFT_ID,
            "borescope_inspection",
            "SYN-PROVIDER-001",
            4.0,
            "pending",
        ),
    ]


def build_spares() -> list[Spare]:
    return [
        Spare(
            "SYN-SPARE-001",
            "SYN-PART-ENG-BLADE-01",
            HUB_ID,
            "available",
            traceable=True,
        ),
        Spare(
            "SYN-SPARE-002",
            "SYN-PART-ENG-BLADE-01",
            "SYN-OUT-02",
            "available",
            traceable=True,
        ),
    ]
```

---

### Task 2.3: Extend AirlineWorld for AOG scenario

**File:** `verticals/airline/worlds/scenario.py`

- [ ] Add AOG collections to `__init__`:

```python
self.technical_statuses: dict[str, TechnicalStatus] = {}
self.maintenance_tasks: dict[str, MaintenanceTask] = {}
self.spares: dict[str, Spare] = {}
self.aog_recovery_commands: dict[str, AogRecoveryCommand] = {}
self.aog_recovery_evaluations: dict[str, AogRecoveryEvaluation] = {}
```

- [ ] Add AOG seed calls in `install()`:

```python
from verticals.airline.worlds import aog_reference_data
self._seed_collection(
    self.technical_statuses,
    aog_reference_data.build_technical_statuses(),
    "airline.technical_status.seeded",
)
self._seed_collection(
    self.maintenance_tasks,
    aog_reference_data.build_maintenance_tasks(),
    "airline.maintenance_task.seeded",
)
self._seed_collection(
    self.spares,
    aog_reference_data.build_spares(),
    "airline.spare.seeded",
)
```

- [ ] Add `activate_scenario` support for `"synthetic-aog-defect"`:

The AOG scenario grounds `SYN-TAIL-003`, marks `SYN-TECHSTATUS-001` as
grounded, and emits `airline.aog_event.detected` with trace to the
affected sector `SYN-SECTOR-OUT-003`.

- [ ] Add `reference_process_types` to include `AOG_WORKFLOW_TYPE`.

- [ ] Extend `render_state()` to include new entity types.

---

### Task 2.4: Write AOG scenario unit tests

**File:** `tests/api/airline/test_aog_scenario.py`

- [ ] Test that activating `synthetic-aog-defect` grounds the aircraft,
  emits the source and sensor events, and the observation is buildable.

```bash
.venv/bin/python -m pytest tests/api/airline/test_aog_scenario.py -x -q
```

**Expected:** All pass.

---

## Phase 3 — AOG Commands and Constraints

### Task 3.1: Create AOG constraints module

**File:** `verticals/airline/aog_constraints.py` (new)

- [ ] Define `AogRecoveryAction`, `AogRecoveryOption`, `AogFeasibilityResult`
  dataclasses mirroring `constraints.py` but for engineering actions.
- [ ] Define two AOG recovery options:

1. `SYN-AOG-OPTION-REPAIR-LOCAL` — use locally available spare + approved
   provider, estimated 4h, GBP 85,000.
2. `SYN-AOG-OPTION-SUB-AIRCRAFT` — substitute with reserve tail
   `SYN-TAIL-005` (if available) + retime affected sector, GBP 45,000.

- [ ] Implement `admit_aog_recovery_options(observation)` that validates
  spare traceability, provider approval, aircraft eligibility, and crew
  consequence.

---

### Task 3.2: Create AOG command handler

**File:** `verticals/airline/actions/aog_commands.py` (new)

- [ ] `aog_recovery_command_id(workflow_id, decision_id, option_id) -> str`
  returning `SYN-CMD-AOG-{workflow_id}-{decision_id}-{option_id}`.

- [ ] `command_for_aog_option(world, *, option_id, workflow_id, decision_id, persona) -> SimulationCommand`
  with `type=AOG_COMMAND_TYPE`.

- [ ] `apply_aog_recovery_command(world, command) -> SimulationEvent`:
  - Validates command type is `AOG_COMMAND_TYPE` (rejects Hero 1 payloads).
  - For repair: marks maintenance task in-progress, reserves spare, keeps
    aircraft grounded (AI does not release it).
  - For substitute: swaps aircraft on sector to reserve tail, retimes
    sector.
  - Emits `AOG_SUCCESS_EVENT`, creates `AogRecoveryEvaluation`.

- [ ] Rejection emits `command.rejected`.

---

### Task 3.3: Write AOG command unit tests

**File:** `tests/api/airline/test_aog_commands.py`

- [ ] Tests for both AOG options: repair-local accepted, sub-aircraft
  accepted, cross-command rejection (Hero 1 command type rejected by AOG
  handler).

```bash
.venv/bin/python -m pytest tests/api/airline/test_aog_commands.py -x -q
```

**Expected:** All pass.

---

## Phase 4 — AOG Durable Orchestrator

### Task 4.1: Create AOG MCP tools

**File:** `verticals/airline/mcp_tools/engineering.py` (new)

- [ ] Define `airline_read_aog_evidence` and
  `airline_rank_aog_recovery_options` tools mirroring
  `mcp_tools/operations.py` pattern but with engineering-specific
  parameter models.

---

### Task 4.2: Create AOG skill and agent

**Directory:** `verticals/airline/skills/engineering-recovery-planner/`

- [ ] Create `SKILL.md` with the engineering recovery planner system
  prompt.

**File:** `verticals/airline/agents.py`

- [ ] Add:

```python
"engineering-recovery-planner": AgentRegistryEntry(
    agent_id="engineering-recovery-planner",
    description=(
        "Compares admitted AOG recovery options and explains engineering "
        "trade-offs for the synthetic airline."
    ),
),
```

---

### Task 4.3: Create AOG Durable orchestrator

**File:** `verticals/airline/aog_durable.py` (new)

- [ ] Implement `aog_orchestration(context)` following the same structure
  as `airline_orchestration` but with AOG-specific phases:

  1. `workflow.started` checkpoint
  2. `aog_evidence_activity_trigger` — validate AOG event and technical
     status evidence
  3. `aog_airworthiness_activity_trigger` — deterministic constraint check
  4. `aog_agent_activity_trigger` — agent phase (engineering recovery planner)
  5. `aog_governance_activity_trigger` — authority check for
     `engineering_duty_manager`
  6. HITL gate: `wait_for_external_event("engineering_duty_manager_decision")`
  7. `aog_command_activity_trigger` — commit engineering and operational actions
  8. Terminal checkpoint

- [ ] Register all activity triggers with `@app.activity_trigger`.

- [ ] Register the orchestrator:

```python
@app.orchestration_trigger(context_name="context")
def AirlineAogEngineeringRecoveryOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return aog_orchestration(context)
```

---

### Task 4.4: Create AOG entity projection

**File:** `verticals/airline/entity_projections/engineering.py` (new)

- [ ] Implement `project(workflow)` returning `EntityWrite`, `RelWrite`,
  `DecisionWrite` lists for AOG workflows, mirroring
  `entity_projections/operations.py` but with engineering entity kinds
  (technical-status, maintenance-task, spare).

---

### Task 4.5: Create AOG workflow detail hook

**File:** `verticals/airline/aog_detail.py` (new)

- [ ] Implement `aog_workflow_detail(workflow, app_state)` returning a
  detail dict with AOG-specific fields: story, baseline (grounded aircraft,
  affected sectors), chosen option, governance, mutations, evaluation,
  timeline.

---

## Phase 5 — Wire into Manifest

### Task 5.1: Update manifest.py

**File:** `verticals/airline/manifest.py`

- [ ] Add AOG durable module loading.
- [ ] Add AOG orchestrator to `orchestrators` frozenset.
- [ ] Add AOG activity triggers to `activities` frozenset.
- [ ] Add AOG MCP module to `mcp_modules`.
- [ ] Add AOG projection to projections dict.
- [ ] Add AOG workflow type to `memory_workflow_types`.
- [ ] Update `workflow_detail_hook` to dispatch to AOG detail for
  `aog-engineering-recovery` workflows.

---

### Task 5.2: Update world registration

**File:** `verticals/airline/worlds/registration.py`

- [ ] Add AOG objective route:

```python
ObjectiveRoute(
    sensor_id=AOG_SENSOR_ID,
    objective_type=AOG_OBJECTIVE_TYPE,
    allowed_command_types=frozenset({AOG_COMMAND_TYPE}),
    success_event_types=frozenset({AOG_SUCCESS_EVENT}),
    failure_event_types=frozenset({AOG_FAILURE_EVENT}),
    evaluation_timeout_minutes=90.0,
),
```

- [ ] Add AOG responder:

```python
AOG_OBJECTIVE_TYPE: ResponderRegistration(
    objective_type=AOG_OBJECTIVE_TYPE,
    orchestrator=AOG_ORCHESTRATOR,
    workflow_type=AOG_WORKFLOW_TYPE,
    prefix="aog",
    owner_function="engineering-control",
    timeout_seconds=900.0,
    lifecycle_start_via_bridge=True,
),
```

---

### Task 5.3: Update diagnostics

**File:** `verticals/airline/worlds/diagnostics.py`

- [ ] Extend `build_diagnostic_input` to handle
  `aog-engineering-recovery` workflow type by activating the AOG scenario
  and building its observation.

---

## Phase 6 — AOG Persona Files

### Task 6.1: Create engineering_duty_manager personae

**Directory:** `verticals/airline/personae/engineering_duty_manager/`

- [ ] Create `SKILL.md` with the decision policy for the Engineering
  Duty Manager persona, following the existing
  `duty_operations_manager/SKILL.md` pattern.

---

## Phase 7 — Integration Tests

### Task 7.1: Write AOG end-to-end test

**File:** `tests/api/airline/test_aog_e2e.py`

- [ ] Test the full causal chain: install world → activate AOG scenario →
  build observation → admit options → construct command → apply command →
  verify evaluation and disruption status.

```bash
.venv/bin/python -m pytest tests/api/airline/test_aog_e2e.py -x -q
```

**Expected:** All pass.

---

### Task 7.2: Verify Hero 1 command rejects Hero 2 payload

**File:** `tests/api/airline/test_cross_command_rejection.py`

- [ ] Test that `apply_recovery_command` rejects an `AOG_COMMAND_TYPE`
  command and `apply_aog_recovery_command` rejects a
  `COMMAND_TYPE` command.

```bash
.venv/bin/python -m pytest tests/api/airline/test_cross_command_rejection.py -x -q
```

**Expected:** All pass.

---

### Task 7.3: Full regression

- [ ] Run all airline tests:

```bash
.venv/bin/python -m pytest tests/api/airline/ -x -q
```

**Expected:** All pass, including Hero 1 tests from Plan 1.

---

## Phase 8 — Completion Gate

- [ ] AOG domain registered and visible in pack domains.
- [ ] AOG scenario activates cleanly in the airline world.
- [ ] AOG command accepted and evaluated with `pass` status.
- [ ] Hero 1 and Hero 2 commands reject each other's payloads.
- [ ] `engineering_duty_manager` persona resolves in authority check.
- [ ] Aircraft remains grounded (AI does not release to service).
- [ ] All airline tests pass.

---

## Scope Decisions

1. **Return-to-service**: The design explicitly requires that no AI phase
   releases the aircraft. The `apply_aog_recovery_command` handler for
   the repair option marks work in-progress and reserves the spare but
   keeps `TechnicalStatus.status = "work_in_progress"`. A separate
   `register_return_to_service` event ingestion function (not an AI
   decision) would clear it — this plan does not implement that external
   event path but leaves the data model ready.
2. **Reserve tail sharing**: If Hero 1 has already assigned `SYN-TAIL-005`,
   the AOG substitute option becomes infeasible. This is correct behavior —
   the world prevents overlapping aircraft use.
3. **AOG recordings and proof**: Deferred to Plan 4 (portfolio proof).
   This plan delivers testable working software; recording and proof
   harness integration happens once all three heroes are complete.
4. **SYN-TAIL-003 grounding**: Uses the existing A321 aircraft. The AOG
   scenario does not collide with Hero 1's `synthetic-hub-cascade` which
   affects SYN-TAIL-001/rotation 1.
