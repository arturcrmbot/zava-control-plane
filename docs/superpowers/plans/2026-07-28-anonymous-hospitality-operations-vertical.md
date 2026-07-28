# Anonymous Hospitality Operations Vertical Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and prove an anonymous `hospitality` vertical with one bespoke
hotel-operations recovery hero and seven executable supporting workflows.

**Architecture:** A pack-owned deterministic hotel actor world drives sensors,
Durable workflows, canonical agent sessions, governed HITL, typed commands,
idempotent mutations, projections, and measured evaluations. The hero has
bespoke planning and mutation logic; supporting workflows share a small
profile-driven orchestration engine while retaining distinct evidence and
commands.

**Tech Stack:** Python 3.11+, FastAPI, Azure Durable Functions, Pydantic,
pack-local MCP tools, pytest, TypeScript/React shared world renderer,
Playwright, JSON/YAML runtime assets.

**Repository rule:** Commit only reviewed Hospitality milestones on
`feature/hospitality-demo`; never stage, stash, reset, or modify unrelated dirty
paths. All business behavior stays under `verticals/hospitality/`; proof
launchers and Hospitality tests are the only expected external additions.

---

## File map

### Pack composition and contracts

- Create `verticals/hospitality/__init__.py`: package marker.
- Create `verticals/hospitality/org-brief.yaml`: anonymous facts, assumptions,
  and uncertainties only.
- Create `verticals/hospitality/generation-manifest.json`: ownership ledger.
- Create `verticals/hospitality/manifest.py`: sole `VerticalPack` composition
  root.
- Create `verticals/hospitality/domains.py`: eight `Domain` definitions.
- Create `verticals/hospitality/functions.py`: six organisation functions.
- Create `verticals/hospitality/agents.py`: machine-agent registry.
- Create `verticals/hospitality/personas.py`: persona registry.
- Create `verticals/hospitality/authority.py`: bounded authority matrix.
- Create `verticals/hospitality/ui.json`: pack UI metadata.

### Process and world behavior

- Create `verticals/hospitality/process_profiles.py`: supporting-engine profile
  contracts.
- Create `verticals/hospitality/reference_cases.py`: eight deterministic cases.
- Create `verticals/hospitality/reference_actions.py`: expected typed actions.
- Create `verticals/hospitality/actors.py`: immutable entity records.
- Create `verticals/hospitality/dynamics.py`: deterministic time-based changes.
- Create `verticals/hospitality/sensors.py`: threshold crossings and
  deduplication.
- Create `verticals/hospitality/recovery.py`: hero option generation and ranking.
- Create `verticals/hospitality/world.py`: world state, commands, events, reset,
  and evaluation.
- Create `verticals/hospitality/worlds.py`: world registration and objective
  routing.
- Create `verticals/hospitality/lifecycle.py`: pack bootstrap/start lifecycle.

### Execution, tools, and projections

- Create `verticals/hospitality/durable.py`: hero and profiled orchestrators and
  activities.
- Create `verticals/hospitality/mcp_tools/__init__.py`: MCP package marker.
- Create `verticals/hospitality/mcp_tools/common.py`: typed tool result helpers.
- Create `verticals/hospitality/mcp_tools/operations.py`: bounded reads and
  command preparation.
- Create `verticals/hospitality/projections.py`: workflow projections.
- Create `verticals/hospitality/entity_projections/__init__.py`: export marker.
- Create `verticals/hospitality/entity_projections/operations.py`: Knowledge
  entity/relationship projection.

### Runtime authored assets

- Create `verticals/hospitality/policies/tools.yaml`: tool access policy.
- Create nine `verticals/hospitality/skills/*/SKILL.md` files: one per reasoning
  capability.
- Create twelve `verticals/hospitality/personae/*/SKILL.md` files: one per
  authority role.
- Create `verticals/hospitality/ui/world-scene.json`: bounded hotel network.
- Create eight `verticals/hospitality/recordings/*.jsonl` files after qualifying
  runs.

### Proof and tests

- Create `tools/hospitality_zava_e2e_proof.sh`: permanent proof wrapper.
- Create `tools/hospitality_zava_e2e_proof.py`: static/runtime proof controller.
- Create `tools/hospitality_zava_browser_proof.mjs`: browser assertions and
  evidence capture.
- Create `tests/api/hospitality/`: focused pack, world, command, orchestration,
  projection, and anonymity tests.
- Create `tests/tools/test_hospitality_zava_e2e_proof.py`: proof harness tests.
- Modify only if required by an existing generic convention:
  `tests/api/server/test_main_verticals.py` and
  `tests/api/shared/test_vertical_loader.py`. Preserve all current user changes.

---

### Task 1: Lock anonymous pack inventory

**Files:**
- Create: `tests/api/hospitality/test_pack_inventory.py`
- Create: `tests/api/hospitality/test_customer_boundary.py`
- Create: `verticals/hospitality/org-brief.yaml`
- Create: `verticals/hospitality/generation-manifest.json`

- [ ] **Step 1: Write the failing inventory test**

```python
import json
from pathlib import Path

import yaml

PACK_ROOT = Path(__file__).resolve().parents[3] / "verticals" / "hospitality"
EXPECTED_WORKFLOWS = {
    "hotel-operations-recovery",
    "room-readiness-coordination",
    "asset-maintenance-response",
    "guest-service-recovery",
    "occupancy-pressure-response",
    "workforce-demand-balancing",
    "food-and-beverage-readiness",
    "energy-anomaly-response",
}


def test_hospitality_pack_inventory() -> None:
    brief = yaml.safe_load((PACK_ROOT / "org-brief.yaml").read_text())
    assert set(brief["workflows"]) == EXPECTED_WORKFLOWS
    ledger = json.loads((PACK_ROOT / "generation-manifest.json").read_text())
    assert ledger["vertical"] == "hospitality"
    assert all(record["ownership"].startswith("bespoke") for record in ledger["records"])
```

- [ ] **Step 2: Write the failing anonymity test**

```python
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[3] / "verticals" / "hospitality"
FORBIDDEN = (
    "whitbread",
    "premier inn",
    "costa",
    "beefeater",
    "brewers fayre",
)


def test_hospitality_assets_are_customer_anonymous() -> None:
    for path in PACK_ROOT.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".json", ".yaml", ".yml", ".md"}:
            text = path.read_text(encoding="utf-8").lower()
            assert not any(term in text for term in FORBIDDEN), path
```

- [ ] **Step 3: Run tests and confirm discovery fails**

Run:

```bash
uv run pytest tests/api/hospitality/test_pack_inventory.py \
  tests/api/hospitality/test_customer_boundary.py -q
```

Expected: failure because the Hospitality brief and ownership ledger do not
exist.

- [ ] **Step 4: Add the anonymous brief and ownership ledger**

The brief records the six functions, eight workflows, synthetic thresholds,
fictional geography, and explicit uncertainties. The generation manifest uses
schema `1`, marks hand-authored business code as `bespoke`, and lists the three
external proof launchers as `bespoke-external`; it must never point to another
vertical.

- [ ] **Step 5: Re-run the anonymity test**

Run:

```bash
uv run pytest tests/api/hospitality/test_customer_boundary.py -q
```

Expected: pass.

### Task 2: Build the static pack graph

**Files:**
- Create: `verticals/hospitality/__init__.py`
- Create: `verticals/hospitality/domains.py`
- Create: `verticals/hospitality/functions.py`
- Create: `verticals/hospitality/authority.py`
- Create: `verticals/hospitality/personas.py`
- Create: `verticals/hospitality/agents.py`
- Create: `verticals/hospitality/ui.json`
- Create: `tests/api/hospitality/test_static_contracts.py`

- [ ] **Step 1: Write failing static-contract tests**

```python
from verticals.hospitality.agents import HOSPITALITY_AGENTS
from verticals.hospitality.domains import HOSPITALITY_DOMAINS
from verticals.hospitality.functions import HOSPITALITY_FUNCTIONS


def test_every_domain_has_one_owner_and_agent() -> None:
    owners = {
        workflow_type: function.name
        for function in HOSPITALITY_FUNCTIONS.values()
        for workflow_type in function.owns_domains
    }
    assert set(owners) == set(HOSPITALITY_DOMAINS)
    assert len(HOSPITALITY_AGENTS) == len(HOSPITALITY_DOMAINS)
    assert all(agent.allowed_tools for agent in HOSPITALITY_AGENTS.values())
```

- [ ] **Step 2: Run tests and confirm missing static modules**

Run:

```bash
uv run pytest tests/api/hospitality/test_static_contracts.py -q
```

Expected: import or validation failure.

- [ ] **Step 3: Define the eight domains**

Use existing `Domain`, `Phase`, and `HitlGate` contracts. The hero phases are:

```python
(
    Phase("Detect Operational Risk", "deterministic"),
    Phase("Assess Guest and Operational Impact", "agent"),
    Phase("Plan Network Recovery", "agent"),
    Phase("Evaluate Policy and Authority", "deterministic"),
    Phase("Approve Recovery Exception", "hitl"),
    Phase("Execute Recovery Plan", "deterministic"),
    Phase("Verify Recovery Outcome", "deterministic"),
)
```

Each supporting domain has distinct display, prefix, orchestrator, function,
skill, HITL persona, and command semantics.

- [ ] **Step 4: Define functions, personas, authority, and agents**

Authority rows use exact action names such as `execute_hotel_recovery`,
`dispatch_maintenance_work_order`, and `apply_workforce_shift_plan`. Agent tool
allowlists reference only Hospitality MCP tool IDs.

- [ ] **Step 5: Run static tests**

Run:

```bash
uv run pytest tests/api/hospitality/test_pack_inventory.py \
  tests/api/hospitality/test_static_contracts.py -q
```

Expected: pass. Do not create a partially wired manifest or runtime stubs;
composition happens only after the world, tools, skills, Durable module, and
scene are real.

### Task 3: Implement deterministic hotel world

**Files:**
- Create: `verticals/hospitality/actors.py`
- Create: `verticals/hospitality/dynamics.py`
- Create: `verticals/hospitality/reference_cases.py`
- Create: `verticals/hospitality/sensors.py`
- Create: `verticals/hospitality/recovery.py`
- Create: `verticals/hospitality/world.py`
- Create: `tests/api/hospitality/test_world_seed.py`
- Create: `tests/api/hospitality/test_hotel_recovery_sensor.py`
- Create: `tests/api/hospitality/test_recovery_planner.py`

- [ ] **Step 1: Write deterministic seed tests**

```python
from verticals.hospitality.world import HospitalityWorld


def test_demo_seed_is_repeatable() -> None:
    first = HospitalityWorld.demo(seed=20260728).snapshot()
    second = HospitalityWorld.demo(seed=20260728).snapshot()
    assert first == second
    assert len(first["hotels"]) == 6
    assert len(first["rooms"]) == 240
    assert len(first["bookings"]) == 180
```

- [ ] **Step 2: Write the hero sensor test**

```python
def test_outage_crosses_operations_risk_once(hero_world) -> None:
    hero_world.trigger_scenario("riverside-hot-water-outage")
    first = hero_world.poll_sensor_events()
    second = hero_world.poll_sensor_events()
    assert [event.type for event in first] == ["hotel.operations-risk.detected"]
    assert second == ()
```

- [ ] **Step 3: Write planner constraint tests**

Cover accessible/family compatibility, room readiness, restoration time,
workforce skill, sister-property travel, recovery cost, and no-action outcomes.
Assert the golden plan restores eight rooms and proposes ten compatible moves
without changing protected requirements.

- [ ] **Step 4: Implement focused entity records**

Use frozen, slotted dataclasses with explicit version fields for mutable world
entities. Keep IDs deterministic and serialize through one `snapshot()` method.

- [ ] **Step 5: Implement world reset, virtual time, and sensor dedupe**

`reset(seed)` reconstructs all state. Sensor dedupe keys are
`(source_event_id, workflow_type)`, not mutable timestamps.

- [ ] **Step 6: Implement recovery option ranking**

Use deterministic constrained scoring. Agent phases may explain and select
among valid options later; they do not generate invalid capacity.

- [ ] **Step 7: Run world tests**

Run:

```bash
uv run pytest tests/api/hospitality/test_world_seed.py \
  tests/api/hospitality/test_hotel_recovery_sensor.py \
  tests/api/hospitality/test_recovery_planner.py -q
```

Expected: pass.

### Task 4: Add typed commands and mutations

**Files:**
- Create: `verticals/hospitality/reference_actions.py`
- Extend: `verticals/hospitality/world.py`
- Create: `tests/api/hospitality/test_commands.py`

- [ ] **Step 1: Write failing command tests**

```python
def test_hotel_recovery_command_is_idempotent(hero_world, approved_command) -> None:
    first = hero_world.apply_command(approved_command)
    second = hero_world.apply_command(approved_command)
    assert first.accepted is True
    assert second.idempotent_replay is True
    assert hero_world.snapshot() == first.snapshot


def test_recovery_rejects_stale_room_version(hero_world, approved_command) -> None:
    approved_command["expected_versions"]["ROOM-RIV-101"] -= 1
    result = hero_world.apply_command(approved_command)
    assert result.accepted is False
    assert result.reason == "stale_entity_version"
```

- [ ] **Step 2: Add one payload validator per command**

Use typed dataclasses or Pydantic models. All payloads include:
`command_id`, `workflow_id`, `expected_versions`, `evidence_digest`,
`reason_code`, `estimated_value_gbp`, and `approval_ref` when required.

- [ ] **Step 3: Implement atomic mutation handlers**

Validate the full command before mutation. Emit explicit rejection events for
unknown command, stale version, duplicate ID, incompatible room, insufficient
capacity, protected-requirement breach, missing authority, and invalid bounds.

- [ ] **Step 4: Run command tests**

Run:

```bash
uv run pytest tests/api/hospitality/test_commands.py -q
```

Expected: pass.

### Task 5: Add MCP tools and runtime skills

**Files:**
- Create: `verticals/hospitality/mcp_tools/__init__.py`
- Create: `verticals/hospitality/mcp_tools/common.py`
- Create: `verticals/hospitality/mcp_tools/operations.py`
- Create: `verticals/hospitality/policies/tools.yaml`
- Create: `verticals/hospitality/skills/*/SKILL.md`
- Create: `tests/api/hospitality/test_mcp_tools.py`
- Create: `tests/api/hospitality/test_runtime_skills.py`

- [ ] **Step 1: Write failing tool-registration tests**

```python
from verticals.hospitality.mcp_tools import operations


def test_hospitality_agents_reference_registered_tools(active_hospitality_pack):
    registered = set(operations.TOOL_BY_NAME)
    referenced = {
        tool
        for agent in active_hospitality_pack.agents.values()
        for tool in agent.allowed_tools
    }
    assert referenced <= registered
```

- [ ] **Step 2: Implement bounded read tools**

Expose typed reads for hotel status, arrival demand, compatible inventory,
assets/work orders, teams/shifts, service capacity, energy, and policy.
Responses include source versions and evidence timestamps.

- [ ] **Step 3: Implement command-preparation tools**

Preparation tools return validated command candidates only. They never mutate
world state or manufacture authority.

- [ ] **Step 4: Author nine focused runtime skills**

Every skill declares only registered Hospitality tools and a typed output shape.
The two hero skills separate impact analysis from recovery planning.

- [ ] **Step 5: Run tool and skill tests**

Run:

```bash
uv run pytest tests/api/hospitality/test_mcp_tools.py \
  tests/api/hospitality/test_runtime_skills.py -q
```

Expected: pass.

### Task 6: Implement Durable, agent, and HITL execution

**Files:**
- Create: `verticals/hospitality/process_profiles.py`
- Create: `verticals/hospitality/durable.py`
- Create: `verticals/hospitality/personae/*/SKILL.md`
- Create: `tests/api/hospitality/test_durable_workflows.py`
- Create: `tests/api/hospitality/test_hitl_recovery.py`

- [ ] **Step 1: Write one orchestration test per workflow**

Drive the generator with a fake Durable context and assert:

- declared phase order;
- canonical activity names;
- one typed terminal command;
- distinct command type per workflow;
- hero suspension and resume at the declared external event.

- [ ] **Step 2: Write agent-evidence and HITL tests**

Assert every declared `agent` phase invokes `run_agent_session` with workflow,
orchestration, phase, skill, and tool provenance. Assert suspended records
persist persona, phase, expected event, evidence digest, and proposed command.

- [ ] **Step 3: Implement the profile engine**

Profiles contain immutable behavior metadata:

```python
@dataclass(frozen=True, slots=True)
class HospitalityProcessProfile:
    workflow_type: str
    skill_id: str
    hitl_persona: str
    approval_action: str
    command_type: str
    detector: str
    evaluator: str
```

- [ ] **Step 4: Implement the bespoke hero orchestration**

Call canonical `run_agent_session` for both hero agent phases. Policy evaluation
is deterministic. HITL uses the governance kernel and a reconstructable
external-event contract.

- [ ] **Step 5: Implement seven profiled orchestrators**

Use the shared engine only for common checkpoint/agent/HITL/execute/verify
mechanics. Resolve profile-specific validators, tools, command constructors, and
evaluators by explicit mapping; reject unknown profiles.

- [ ] **Step 6: Run orchestration tests**

Run:

```bash
uv run pytest tests/api/hospitality/test_durable_workflows.py \
  tests/api/hospitality/test_hitl_recovery.py -q
```

Expected: pass.

### Task 7: Wire world registration, lifecycle, and projections

**Files:**
- Create: `verticals/hospitality/worlds.py`
- Create: `verticals/hospitality/lifecycle.py`
- Create: `verticals/hospitality/projections.py`
- Create: `verticals/hospitality/entity_projections/__init__.py`
- Create: `verticals/hospitality/entity_projections/operations.py`
- Create: `verticals/hospitality/manifest.py`
- Create: `tests/api/hospitality/test_world_registration.py`
- Create: `tests/api/hospitality/test_projections.py`

- [ ] **Step 1: Write failing registration tests**

Assert the `hospitality` world exposes `demo` scale, all eight objective routes,
all command responders, deterministic reset, and one evaluation per workflow.

- [ ] **Step 2: Write projection identity tests**

Assert graph writes preserve workflow ID, command ID, hotel/room/booking IDs,
decision persona, and terminal outcome.

- [ ] **Step 3: Register world and lifecycle**

The lifecycle owns only Hospitality runtime state. No global route or registry
edits are allowed.

- [ ] **Step 4: Compose and validate the complete pack**

`manifest.py` imports only `api.shared.*`, `verticals._helpers`, and
`verticals.hospitality.*`. It sets:

```python
name="hospitality"
display_name="Hospitality"
default_world="hospitality"
mcp_modules=("verticals.hospitality.mcp_tools.operations",)
external_capabilities=frozenset()
```

Call `api.shared.vertical_loader.validate_pack(build_pack())` in the focused
test; do not defer missing assets or create success-shaped placeholders.

- [ ] **Step 5: Add workflow and entity projections**

Project bounded hotel, room-block, asset, team, booking-move, decision, command,
and evaluation nodes/relationships.

- [ ] **Step 6: Run registration tests**

Run:

```bash
ZAVA_VERTICAL=hospitality uv run pytest \
  tests/api/hospitality/test_world_registration.py \
  tests/api/hospitality/test_projections.py -q
```

Expected: pass.

### Task 8: Build the bounded Hospitality scene

**Files:**
- Create: `verticals/hospitality/ui/world-scene.json`
- Update: `verticals/hospitality/ui.json`
- Create: `tests/api/hospitality/test_world_scene.py`

- [ ] **Step 1: Write failing scene tests**

Assert six unique property locations, bounded room-block layers, event mappings
for fault/work-order/readiness/booking-move/shift/evaluation, and no direct
rendering of all 180 bookings or 240 rooms.

- [ ] **Step 2: Implement scene metadata**

Use fictional labels:

- Riverside Central
- Airport North
- City Gate
- Harbour View
- Messe Central
- Rhine Park

The scene must not use a customer colour palette or copied property names.

- [ ] **Step 3: Validate with shared scene loader**

Run:

```bash
ZAVA_VERTICAL=hospitality uv run pytest \
  tests/api/hospitality/test_world_scene.py \
  tests/api/routes/test_world_scene_routes.py -q
```

Expected: pass without changing shared renderer code.

### Task 9: Add pack and server integration coverage

**Files:**
- Create: `tests/api/hospitality/test_runtime_integration.py`
- Modify only if necessary: `tests/api/server/test_main_verticals.py`
- Modify only if necessary: `tests/api/shared/test_vertical_loader.py`

- [ ] **Step 1: Write runtime selection tests**

Assert `ZAVA_VERTICAL=hospitality` returns the correct pack, world, functions,
domains, personas, capabilities, and world-scene URL.

- [ ] **Step 2: Write inactive-pack isolation tests**

Load `agency`, `telco`, `fashion`, and `travel` independently and assert no
Hospitality workflows, personas, skills, tools, worlds, or projections leak.

- [ ] **Step 3: Run targeted shared integration**

Run:

```bash
uv run pytest tests/api/hospitality \
  tests/api/shared/test_vertical_loader.py \
  tests/api/server/test_main_verticals.py -q
```

Expected: pass. Do not revert or rewrite pre-existing user changes in shared
tests.

### Task 10: Add permanent proof and recordings

**Files:**
- Create: `tools/hospitality_zava_e2e_proof.sh`
- Create: `tools/hospitality_zava_e2e_proof.py`
- Create: `tools/hospitality_zava_browser_proof.mjs`
- Create: `tests/tools/test_hospitality_zava_e2e_proof.py`
- Create after qualifying runs: `verticals/hospitality/recordings/*.jsonl`
- Update: `verticals/hospitality/generation-manifest.json`

- [ ] **Step 1: Write proof-runner contract tests**

Assert the runner:

- requires `ZAVA_VERTICAL=hospitality`;
- records source commit and runtime fingerprint;
- inventories all eight workflows;
- requires live and replay source modes;
- checks HITL, identity, browser errors, dropped events, and cleanup;
- preserves seller review as `PENDING`;
- tears down on success, failure, and interruption.

- [ ] **Step 2: Implement proof wrapper and controller**

The shell wrapper uses `set -euo pipefail` and an EXIT trap. The Python
controller writes `proof/manifest.json` only after validating evidence; failures
write a non-ready result with the exact gate and resume command.

- [ ] **Step 3: Implement browser proof**

Use the existing Playwright setup. Trigger the named scenario through the UI,
verify first visible state within one second, inspect the approval, complete it,
open the workflow drawer and evidence surfaces, and assert zero console errors.

- [ ] **Step 4: Run proof harness tests**

Run:

```bash
uv run pytest tests/tools/test_hospitality_zava_e2e_proof.py -q
```

Expected: pass.

- [ ] **Step 5: Run one complete live proof**

Run:

```bash
make prove VERTICAL=hospitality
```

Expected: all eight workflows complete with distinct evidence, replay probes
pass, recordings are produced, and teardown clears proof-owned ports.

- [ ] **Step 6: Run the second qualifying proof**

Run the same command without source changes:

```bash
make prove VERTICAL=hospitality
```

Expected: `proof/manifest.json` records two consecutive passing runs from the
same source and runtime fingerprint, with `build_ready: true` and
`seller_review: PENDING`.

### Task 11: Final regression and ownership audit

**Files:**
- Update: `verticals/hospitality/generation-manifest.json`
- Update only generated evidence outputs required by the proof contract.

- [ ] **Step 1: Validate the active pack**

```bash
ZAVA_VERTICAL=hospitality uv run python -c \
  'from api.shared.vertical_loader import active_runtime, validate_pack; r=active_runtime(); validate_pack(r.pack); print(r.fingerprint)'
```

Expected: pack validates and prints one runtime fingerprint.

- [ ] **Step 2: Run all Hospitality tests**

```bash
uv run pytest tests/api/hospitality \
  tests/tools/test_hospitality_zava_e2e_proof.py -q
```

Expected: pass.

- [ ] **Step 3: Run directly coupled shared tests**

```bash
uv run pytest tests/api/shared/test_vertical_loader.py \
  tests/api/shared/test_vertical_pack_validation.py \
  tests/api/server/test_main_verticals.py \
  tests/api/routes/test_world_scene_routes.py -q
```

Expected: pass.

- [ ] **Step 4: Audit anonymity and ownership**

```bash
rg -ni 'whitbread|premier inn|costa|beefeater|brewers fayre' \
  verticals/hospitality tests/api/hospitality \
  tools/hospitality_zava_* && exit 1 || true
git --no-pager diff --check
```

Expected: no identifying terms and no whitespace errors.

- [ ] **Step 5: Confirm no unrelated files were changed by this build**

Compare final changed paths with the initial dirty-tree snapshot. Hospitality
work may add only the paths in this plan and precise generic test integrations;
all pre-existing electronics and shared-file edits remain untouched.
