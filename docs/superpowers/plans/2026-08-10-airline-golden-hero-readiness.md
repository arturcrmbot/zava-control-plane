---
goal: Close Hero 1 correctness gaps and build the machine-proof harness and recording pipeline for integrated-hub-disruption-recovery
version: 1.0
date_created: 2026-08-10
last_updated: 2026-08-10
owner: Zava engineering
status: Planned
tags: [airline, hero-1, correctness, proof-harness, recording]
depends_on: []
---

# Airline Golden Hero Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the golden airline hero's correctness gaps and establish its reusable proof and recording harness.

**Architecture:** Preserve the existing pack-owned world, command, Durable, and projection boundaries. Fix Hero 1 in place, then adapt the generic proof substrate and Telco driver structure without introducing a second runtime path.

**Tech Stack:** Python 3.11, pytest, Azure Durable Functions, FastAPI, Node.js/Playwright, Bash.

---

This plan fixes the three known correctness defects in the golden
`integrated-hub-disruption-recovery` hero and builds the machine-proof
harness plus recording pipeline needed before Hero 2, Hero 3, or the
portfolio proof plan can execute.

Design authority:
[`2026-07-28-airline-vertical-design.md`](../specs/2026-07-28-airline-vertical-design.md).
Proof contract: [`docs/VERTICAL-PROOF.md`](../../VERTICAL-PROOF.md).
Build contract:
[`docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md`](../contracts/VERTICAL-BUILD-CONTRACT.md).

> **For agentic workers:** Execute phases in order. Within a phase, tasks
> may run in parallel only when the Dependencies column permits it. Use
> TDD for every code task. Do not begin the next phase until its
> completion gate passes.

## 1. Requirements & Constraints

- **REQ-001**: The retime option (`SYN-OPTION-RETIME-ONLY`) must have a
  working mutator and evaluator in `verticals/airline/actions/commands.py`.
- **REQ-002**: `GOLDEN_DECISION_ID` must not be hardcoded in the Durable
  orchestrator's `hitl_context`; the decision ID must come from the HITL
  approval payload.
- **REQ-003**: A recorded walk
  (`data/blueprint-recordings/integrated-hub-disruption-recovery-*.jsonl`)
  must exist and be committed.
- **REQ-004**: The airline proof harness (`tools/airline_zava_e2e_proof.sh`
  + `tools/airline_zava_e2e_proof.mjs`) must launch the isolated stack,
  run the golden hero live, capture recordings, validate replay, and tear
  down cleanly — matching the pattern in `tools/telco_zava_e2e_proof.sh`.
- **REQ-005**: `tools/workflow_visibility_proof.py` must pass for
  `ZAVA_VERTICAL=airline` with live/replay parity.
- **REQ-006**: Existing tests must continue to pass after the corrections.

---

## Phase 1 — Retime Mutator and Evaluator

### Task 1.1: Write retime mutator/evaluator unit tests (RED)

**File:** `tests/api/airline/test_retime_command.py`

```python
"""Tests for the retime recovery option mutator and evaluator."""
from __future__ import annotations

import copy
from typing import Any

import pytest

from api.server.world.runtime import SimulationRuntime
from verticals.airline.actions.commands import apply_recovery_command, command_for_option
from verticals.airline.process_profiles import (
    GOLDEN_WORKFLOW_ID,
    GOLDEN_DECISION_ID,
    HITL_PERSONA,
    SCENARIO_ID,
)
from verticals.airline.worlds.scenario import AirlineWorld

_WORKFLOW_ID = GOLDEN_WORKFLOW_ID
_DECISION_ID = GOLDEN_DECISION_ID
_OPTION_ID = "SYN-OPTION-RETIME-ONLY"
_TARGET_SECTOR = "SYN-SECTOR-OUT-001"
_RETIME_MINUTES = 390  # must match verticals/airline/constraints.py


def _world() -> AirlineWorld:
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario(SCENARIO_ID)
    return world


def test_retime_command_accepted() -> None:
    world = _world()
    command = command_for_option(
        world,
        option_id=_OPTION_ID,
        workflow_id=_WORKFLOW_ID,
        decision_id=_DECISION_ID,
        persona=HITL_PERSONA,
    )
    event = apply_recovery_command(world, command)
    assert event.type == "command.accepted"


def test_retime_mutates_sector_departure() -> None:
    world = _world()
    sector_before = copy.deepcopy(world.sectors[_TARGET_SECTOR])
    command = command_for_option(
        world,
        option_id=_OPTION_ID,
        workflow_id=_WORKFLOW_ID,
        decision_id=_DECISION_ID,
        persona=HITL_PERSONA,
    )
    apply_recovery_command(world, command)
    sector_after = world.sectors[_TARGET_SECTOR]
    assert sector_after.delay_minutes == 0
    assert sector_after.scheduled_departure == sector_before.scheduled_departure + _RETIME_MINUTES


def test_retime_evaluation_passes() -> None:
    world = _world()
    command = command_for_option(
        world,
        option_id=_OPTION_ID,
        workflow_id=_WORKFLOW_ID,
        decision_id=_DECISION_ID,
        persona=HITL_PERSONA,
    )
    apply_recovery_command(world, command)
    evaluation = world.recovery_evaluations.get(_WORKFLOW_ID)
    assert evaluation is not None
    assert evaluation.status == "pass"
    assert evaluation.option_id == _OPTION_ID


def test_retime_disruption_resolved() -> None:
    world = _world()
    command = command_for_option(
        world,
        option_id=_OPTION_ID,
        workflow_id=_WORKFLOW_ID,
        decision_id=_DECISION_ID,
        persona=HITL_PERSONA,
    )
    apply_recovery_command(world, command)
    from verticals.airline.process_profiles import STORY_ID
    assert world.disruption_status[STORY_ID] == "resolved"
```

- [ ] Create `tests/api/airline/test_retime_command.py` with the
  content above.

**TDD red command:**

```bash
cd /Users/arturzielinski/dev/github-repos/zava-control-plane
.venv/bin/python -m pytest tests/api/airline/test_retime_command.py -x -q
```

**Expected:** 4 failures — `command.rejected` because there is no
retime mutator.

---

### Task 1.2: Implement `_mutate_retime_plan` and retime evaluator (GREEN)

**File:** `verticals/airline/actions/commands.py`

- [ ] Add `_mutate_retime_plan`:

```python
_RETIME_OPTION_ID = "SYN-OPTION-RETIME-ONLY"
_RETIME_MINUTES = 390  # must match verticals/airline/constraints.py

def _mutate_retime_plan(world: AirlineWorld) -> list[Any]:
    sector = world.sectors[_TARGET_SECTOR_ID]
    crew = world.crew_duties[sector.crew_duty_id]
    slot = world.slots[sector.slot_id]
    sector.scheduled_departure += _RETIME_MINUTES
    sector.delay_minutes = 0
    slot.scheduled_time += _RETIME_MINUTES
    crew.remaining_duty_minutes -= _RETIME_MINUTES
    return [sector, crew, slot]
```

- [ ] Add `_RETIME_OPTION_ID` to the module-level `_KNOWN_OPTION_IDS` set
  (it is already present — verify).

- [ ] Extend `_accept()` to handle retime:

```python
    elif option.option_id == _RETIME_OPTION_ID:
        mutated = _mutate_retime_plan(world)
```

Replace the existing `else` branch that rejects unknown options.

- [ ] Extend `_evaluation_results()` to handle retime:

```python
    elif option.option_id == _RETIME_OPTION_ID:
        crew = world.crew_duties[sector.crew_duty_id]
        checks = (
            ("sector_retimed", sector.delay_minutes == 0),
            ("slot_moved", world.slots[sector.slot_id].scheduled_time > 0),
            ("crew_duty_valid", crew.remaining_duty_minutes >= 0),
            (
                "disruption_resolved",
                world.disruption_status.get(STORY_ID) == "resolved",
            ),
        )
```

**TDD green command:**

```bash
.venv/bin/python -m pytest tests/api/airline/test_retime_command.py -x -q
```

**Expected:** 4 passes.

---

### Task 1.3: Run existing airline tests (REFACTOR)

- [ ] Confirm no regressions:

```bash
.venv/bin/python -m pytest tests/api/airline/ -x -q
```

**Expected:** All tests pass.

---

## Phase 2 — Remove Hardcoded Golden Decision ID

### Task 2.1: Write test for dynamic decision ID (RED)

**File:** `tests/api/airline/test_dynamic_decision_id.py`

```python
"""The orchestrator must not hardcode GOLDEN_DECISION_ID in hitl_context."""
from __future__ import annotations

from verticals.airline.durable import airline_orchestration
from verticals.airline.process_profiles import GOLDEN_DECISION_ID


def test_hitl_context_uses_approval_decision_id() -> None:
    """Orchestrator hitl_context.decision_id must not be GOLDEN_DECISION_ID
    when the approval payload supplies a different decision_id."""
    # This test verifies the code path at the source level:
    # hitl_context must assign decision_id from the approval, not from
    # the module constant.
    import ast, inspect, textwrap
    source = inspect.getsource(airline_orchestration)
    tree = ast.parse(textwrap.dedent(source))
    # Find all Dict nodes that assign "decision_id" key
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "decision_id":
                    # The value must NOT be a Name referencing GOLDEN_DECISION_ID
                    assert not (
                        isinstance(value, ast.Name)
                        and value.id == "GOLDEN_DECISION_ID"
                    ), (
                        "hitl_context still hardcodes GOLDEN_DECISION_ID; "
                        "it must derive decision_id from the approval payload "
                        "or a generated value"
                    )
```

- [ ] Create the test file above.

**TDD red command:**

```bash
.venv/bin/python -m pytest tests/api/airline/test_dynamic_decision_id.py -x -q
```

**Expected:** 1 failure (the source currently references `GOLDEN_DECISION_ID`).

---

### Task 2.2: Replace hardcoded decision ID (GREEN)

**File:** `verticals/airline/durable.py`

- [ ] In `airline_orchestration`, replace the `hitl_context` dict literal's
  `"decision_id": GOLDEN_DECISION_ID` with a dynamically generated
  decision ID:

```python
    decision_id = f"SYN-DECISION-{workflow_id}"
```

Place this line before the `hitl_context` dict. Then use:

```python
        "decision_id": decision_id,
```

- [ ] Remove the `GOLDEN_DECISION_ID` import from the orchestrator's import
  block if it is no longer used.

**TDD green command:**

```bash
.venv/bin/python -m pytest tests/api/airline/test_dynamic_decision_id.py tests/api/airline/ -x -q
```

**Expected:** All pass.

---

## Phase 3 — Proof Harness

### Task 3.1: Create `tools/airline_zava_e2e_proof.sh`

**File:** `tools/airline_zava_e2e_proof.sh`

- [ ] Create the shell script following the same structure as
  `tools/telco_zava_e2e_proof.sh` but with airline-specific values:

```bash
cp tools/telco_zava_e2e_proof.sh tools/airline_zava_e2e_proof.sh
chmod +x tools/airline_zava_e2e_proof.sh
```

- [ ] Apply one reviewed patch that changes the copied script's public
  contract to these exact values while retaining every startup, health,
  teardown, and failure trap from the Telco script:

```text
TELCO_*                         -> AIRLINE_*
ZAVA_VERTICAL=telco            -> ZAVA_VERTICAL=airline
ZAVA_WORLD=telco               -> ZAVA_WORLD=airline
telco_zava_e2e_proof.mjs       -> airline_zava_e2e_proof.mjs
Telco proof                    -> Airline proof
NetworkIncidentOrchestrator    -> AirlineIntegratedHubRecoveryOrchestrator
default API port               -> 14101
default Functions port         -> 18171
default Control Plane port     -> 16273
default Blueprint port         -> 16275
default Azurite ports          -> 12000, 12001, 12002
```

- [ ] Confirm no Telco runtime identifiers remain:

```bash
if rg -n 'ZAVA_VERTICAL=telco|ZAVA_WORLD=telco|telco_zava|NetworkIncidentOrchestrator' \
  tools/airline_zava_e2e_proof.sh; then
  echo "unexpected Telco identifier in airline proof shell" >&2
  exit 1
fi
```

Key differences from telco:
- `ZAVA_VERTICAL=airline`
- `PROOF_WORLD=airline`
- `PROOF_ORCHESTRATOR_GREP=AirlineIntegratedHubRecoveryOrchestrator`
- Port range shifted to avoid collisions with telco proof
- Functions host check: `AirlineIntegratedHubRecoveryOrchestrator`

- [ ] Make executable: `chmod +x tools/airline_zava_e2e_proof.sh`

---

### Task 3.2: Create `tools/airline_zava_e2e_proof.mjs`

**File:** `tools/airline_zava_e2e_proof.mjs`

- [ ] Create the Playwright proof driver modelled on
  `tools/telco_zava_e2e_proof.mjs`, adapted for airline:

The driver must:
1. POST to `/api/world/scenarios/synthetic-hub-cascade` to trigger the
   golden scenario.
2. Poll `GET /api/workflows?type=integrated-hub-disruption-recovery`
   until the workflow reaches `awaiting_hitl`.
3. Read the workflow payload's `hitl_context` and extract
   `external_event`, `instance_id`, `selected_option_id`,
   `evidence_versions`, and `decision_id`.
4. POST the persona auto-close decision to the Durable Functions
   external event endpoint.
5. Poll until the workflow reaches terminal state (`completed` or
   `decision_ready`).
6. Assert cross-surface identity (§2 of VERTICAL-PROOF):
   - `GET /api/workflows/<id>` — status, current_phase
   - `GET /api/world/events?workflow_id=<id>` — ≥1 event
   - `GET /api/memory/search?q=<id>` — ≥1 result
7. Capture recording to `$PROOF_OUT_DIR/recordings/`.
8. In `--replay` mode, start replay-only server and verify the same
   workflow shows consistent detail.

---

### Task 3.3: Validate proof harness runs

- [ ] Run the proof harness locally and verify exit 0:

```bash
bash tools/airline_zava_e2e_proof.sh
```

**Expected:** `AIRLINE ZAVA E2E PROOF PASSED` with evidence directory
populated.

---

## Phase 4 — Recording Pipeline

### Task 4.1: Wire recording source into manifest

**File:** `verticals/airline/manifest.py`

- [ ] Update the `recordings` field:

```python
recordings=RecordingSources(
    curated_dirs=(PACK_ROOT / "recordings",),
),
```

- [ ] Create `verticals/airline/recordings/` directory.

---

### Task 4.2: Capture golden hero recording

- [ ] Using the proof harness output, copy the recorded JSONL file:

```bash
cp tmp/airline-zava-e2e-proof/recordings/integrated-hub-disruption-recovery-*.jsonl \
   data/blueprint-recordings/
```

- [ ] Verify the file exists and is non-empty:

```bash
wc -l data/blueprint-recordings/integrated-hub-disruption-recovery-*.jsonl
```

**Expected:** ≥10 lines.

---

### Task 4.3: Run workflow visibility proof

- [ ] Run the visibility proof tool:

```bash
ZAVA_VERTICAL=airline .venv/bin/python tools/workflow_visibility_proof.py \
  --vertical airline --base-url http://127.0.0.1:14101 \
  --save-dir proof/workflow-details/live
```

**Expected:** Exit 0, all live visibility checks pass.

---

## Phase 5 — Completion Gate

- [ ] All tests pass:

```bash
.venv/bin/python -m pytest tests/api/airline/ -x -q
```

- [ ] Retime option command accepted and evaluated to `pass`.
- [ ] `GOLDEN_DECISION_ID` no longer appears in orchestrator hitl_context
  assignment.
- [ ] Proof harness exits 0.
- [ ] Recording file exists in `data/blueprint-recordings/`.
- [ ] Workflow visibility proof passes for airline.

---

## Scope Decisions

1. **Retime mutator only** — the retime option already passes feasibility
   in `constraints.py`; the gap was solely the missing mutator and
   evaluator in `commands.py`.
2. **Decision ID** — replaced module-constant reference with a
   workflow-derived string `SYN-DECISION-{workflow_id}`, keeping the same
   `SYN-DECISION-` prefix for command validation compatibility.
3. **Proof harness** — port numbers shifted above telco to allow parallel
   proof runs. The shell script reuses `tools/lib/actor_world_proof_stack.sh`.
4. **No UI changes** — this plan addresses backend correctness and harness
   only; UI proof is deferred to plan 4.
