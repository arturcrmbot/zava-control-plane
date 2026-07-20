# Fashion Retail Vertical Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and prove a reusable UK/EU Fashion Retail vertical containing
one inventory-rebalancing hero and seven executable supporting workflows.

**Architecture:** Invoke the deployed `compose-org` skill as the controlling
Research -> Design -> Build -> Prove workflow, with the approved design as its
decision input. All business assets live in the automatically discovered
`verticals/fashion/` pack; shared kernel registries remain untouched. A
deterministic actor world, pack-local skills and typed commands feed Durable
workflows, projections, curated recordings, and a permanent
`make prove VERTICAL=fashion` evidence gate.

**Tech Stack:** Python 3.11, Azure Durable Functions, FastAPI, pytest, actor
world contracts, MCP tools, React/Vite, Playwright, Bash, JSONL replay.

---

## File map

### Pack

- `verticals/fashion/manifest.py`: immutable `VerticalPack` composition root.
- `verticals/fashion/domains.py`: eight workflow declarations.
- `verticals/fashion/process_profiles.py`: seven supporting workflow contracts.
- `verticals/fashion/functions.py`: four organisational functions and ownership.
- `verticals/fashion/agents.py`: pack-local reasoning agent registrations.
- `verticals/fashion/personas.py`: approver and operator metadata.
- `verticals/fashion/authority.py`: exact approval events and spend limits.
- `verticals/fashion/durable.py`: hero and shared-engine Durable registrations.
- `verticals/fashion/world.py`: deterministic entities, sensors, commands, and
  KPI evaluation.
- `verticals/fashion/worlds.py`: world scale, objective routes, and responders.
- `verticals/fashion/reference_cases.py`: one deterministic case per workflow.
- `verticals/fashion/reference_actions.py`: case-to-command decisions.
- `verticals/fashion/projections.py`: workflow and entity-graph projections.
- `verticals/fashion/lifecycle.py`: pack bootstrap and teardown hooks.
- `verticals/fashion/ui.json`: Fashion identity, lenses, and capabilities.
- `verticals/fashion/org-brief.yaml`: sourced facts, assumptions, uncertainties,
  and synthetic-world boundaries from Research.
- `verticals/fashion/policies/tools.yaml`: command and approval policy.
- `verticals/fashion/skills/*/SKILL.md`: eight focused reasoning skills.
- `verticals/fashion/personae/*/SKILL.md`: six persona policies.
- `verticals/fashion/mcp_tools/*.py`: typed evidence queries and commands.
- `verticals/fashion/recordings/*.jsonl`: curated workflow recordings.

### Tests and proof

- `tests/api/shared/test_fashion_vertical_pack.py`: pack inventory, functions,
  personas, skills, and discovery isolation.
- `tests/api/shared/test_fashion_process_profiles.py`: workflow declarations,
  stub-free completeness, and profile contract.
- `tests/api/shared/test_fashion_org_brief.py`: org-brief section completeness
  and synthetic-boundary annotation.
- `tests/api/shared/test_fashion_recordings.py`: curated recording registration
  and evidence completeness.
- `tests/api/world/actor/test_fashion_world.py`: deterministic world, golden
  cases, and world-command contracts.
- `tests/api/world/actor/test_fashion_causal_world.py`: causal-signal,
  cohort/lifecycle, and real-entity world behaviours.
- `tests/api/functions/test_fashion_mcp_tools.py`: typed MCP tool validation,
  command schema, and evidence provenance.
- `tests/api/functions/workflows/test_fashion_orchestration.py`: hero and
  supporting workflow execution contracts.
- `tests/api/server/test_fashion_runtime.py`: server runtime payload, pack
  ownership, and process isolation.
- `tests/api/server/services/test_fashion_projections.py`: projection
  registration and entity-graph mapping.
- `tests/api/routes/test_world_fashion_process_run.py`: world process-run route
  behaviour.
- `tests/tools/test_fashion_zava_e2e_proof.py`: proof-contract structure and
  live-stack config assertions.
- `tests/api/shared/test_vertical_loader.py`: automatic Fashion discovery.
- `tests/api/server/test_main_verticals.py`: Fashion world lifecycle.
- `Makefile`: generic `prove` target.
- `tools/fashion_zava_e2e_proof.sh`: isolated stack lifecycle and evidence gate.
- `tools/fashion_zava_e2e_proof.mjs`: Playwright live/replay driver.
- `proof/manifest.json`: generated, gitignored proof result bound to the current
  source commit.

## Task 1: Run the deployed compose-org pipeline

**Files:**
- Read: `docs/superpowers/specs/2026-07-20-fashion-retail-vertical-design.md`
- Create: `verticals/fashion/**`
- Create: `tests/api/**` (Fashion-specific test files)
- Create: `tools/fashion_zava_e2e_proof.sh`
- Create: `tools/fashion_zava_e2e_proof.mjs`
- Modify: `Makefile`

- [ ] **Step 1: Verify the installed plugin and clean input state**

Run:

```bash
copilot plugin list
git status --short
```

Expected: `zava-constellation@zava-constellation (v2.0.0)` is installed and the
working tree is clean.

- [ ] **Step 2: Invoke compose-org in a fresh CLI process**

Run:

```bash
copilot -C "$PWD" \
  --plugin-dir "$HOME/.copilot/installed-plugins/zava-constellation/zava-constellation" \
  --allow-all-tools \
  --no-ask-user \
  --no-remote \
  --no-auto-update \
  --model gpt-5.6-sol \
  --effort high \
  --autopilot \
  -p 'Invoke using-superpowers, then compose-org. Build the approved reusable
Fashion Retail vertical from
docs/superpowers/specs/2026-07-20-fashion-retail-vertical-design.md. The design
answers every business question; do not ask more. Use module-safe pack slug
fashion and ZAVA_VERTICAL=fashion. Execute Research, Design, Build, and Prove.
The current substrate contract wins over generic skill language: all business
assets remain under verticals/fashion, automatic manifest discovery registers
the pack, and no shared/global business registry is edited. Implement exactly
the eight non-stub workflows in the design. Use TDD, commit each phase, and do
not push. Permanent proof is make prove VERTICAL=fashion and must emit
proof/manifest.json.'
```

Expected: the skill identifies its four phases, creates the Fashion pack, runs
targeted tests, and either completes proof or reports a concrete failing gate.
It must not stop for design input.

- [ ] **Step 3: Confirm pack-scoped output**

Run:

```bash
test -f verticals/fashion/manifest.py
test -f verticals/fashion/org-brief.yaml
test -f tools/fashion_zava_e2e_proof.sh
find verticals/fashion -type f -print | sort
git --no-pager log -8 --name-only --format= |
  rg '^(verticals/fashion/|tests/api/.*fashion|tools/fashion_|Makefile)'
```

Expected: all customer-specific runtime code is under `verticals/fashion/`;
only tests, proof tooling, the generic Make target, and proof output live
outside the pack.

## Task 2: Lock pack discovery, inventory, and isolation

**Files:**
- Extend: `tests/api/shared/test_fashion_vertical_pack.py`
- Modify: `tests/api/shared/test_vertical_loader.py`
- Modify: `tests/api/shared/test_vertical_pack_inventory.py`
- Modify: `tests/api/server/test_main_verticals.py`
- Modify: `verticals/fashion/manifest.py`

- [ ] **Step 1: Write the discovery and inventory tests**

Extend `tests/api/shared/test_fashion_vertical_pack.py` with assertions for
`discover_pack_modules`, `build_runtime` completeness, and process isolation.
The file already covers `FASHION_WORKFLOWS`, `FASHION_FUNCTIONS`, stub-free
domain checks, and an isolation subprocess probe. Add or verify these cases:

```python
def test_fashion_pack_is_discovered_and_complete(tmp_path) -> None:
    assert discover_pack_modules()["fashion"] == "verticals.fashion.manifest"
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    )

    assert runtime.pack.name == "fashion"
    assert runtime.world_name == "fashion"
    assert runtime.world_scale_name == "demo"
    assert set(runtime.pack.domains) == FASHION_WORKFLOWS
    assert set(runtime.pack.organisation_functions) == FASHION_FUNCTIONS
    assert all(not domain.stub for domain in runtime.pack.domains.values())


def test_fashion_process_imports_no_other_pack_business_modules() -> None:
    environment = os.environ.copy()
    environment["ZAVA_VERTICAL"] = "fashion"
    script = """
import json
import sys
import api.shared.domains
import api.shared.functions
print(json.dumps(sorted(sys.modules)))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    modules = set(__import__("json").loads(result.stdout))

    assert "verticals.fashion.domains" in modules
    assert "verticals.fashion.functions" in modules
    assert "verticals.agency.domains" not in modules
    assert "verticals.telco.domains" not in modules
```

- [ ] **Step 2: Run tests to verify the generated pack contract**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/shared/test_fashion_vertical_pack.py \
  tests/api/shared/test_vertical_loader.py \
  tests/api/shared/test_vertical_pack_inventory.py -q
```

Expected: PASS. If the generated pack is incomplete, tests fail with the exact
missing registration rather than a fallback pack.

- [ ] **Step 3: Make `manifest.py` expose the complete immutable pack**

The final builder must have this shape:

```python
from __future__ import annotations

from importlib import import_module
from pathlib import Path

from api.shared.vertical_pack import (
    DurableFunctionRegistration,
    LifecycleRegistration,
    RecordingSources,
    SeedRegistration,
    VerticalPack,
)
from verticals._helpers import load_ui_manifest, wire_domain_functions
from verticals.fashion.agents import FASHION_AGENTS
from verticals.fashion.authority import FASHION_AUTHORITY
from verticals.fashion.domains import FASHION_DOMAINS
from verticals.fashion.functions import FASHION_FUNCTIONS
from verticals.fashion.lifecycle import bootstrap, start
from verticals.fashion.personas import FASHION_PERSONAS
from verticals.fashion.projections import FASHION_PROJECTIONS
from verticals.fashion.worlds import FASHION_WORLDS

PACK_ROOT = Path(__file__).resolve().parent


def _load_durable_module():
    return import_module("verticals.fashion.durable")


def build_pack() -> VerticalPack:
    domains = wire_domain_functions(
        dict(FASHION_DOMAINS),
        dict(FASHION_FUNCTIONS),
    )
    return VerticalPack(
        root=PACK_ROOT,
        name="fashion",
        display_name="Fashion Retail",
        manifest_version="1",
        domains=domains,
        organisation_functions=FASHION_FUNCTIONS,
        agents=FASHION_AGENTS,
        authority=FASHION_AUTHORITY,
        personas=FASHION_PERSONAS,
        policy_sources=(PACK_ROOT / "policies" / "tools.yaml",),
        durable_functions=DurableFunctionRegistration(
            load_module=_load_durable_module,
            orchestrators=frozenset(
                domain.orchestrator_name for domain in domains.values()
            ),
            activities=frozenset(
                {
                    "inventory_rebalance_evidence_activity_trigger",
                    "inventory_rebalance_plan_activity_trigger",
                    "inventory_transfer_activity_trigger",
                    "inventory_rebalance_evaluation_activity_trigger",
                    "fashion_profile_skill_activity_trigger",
                    "fashion_profile_command_activity_trigger",
                }
            ),
        ),
        personae_roots=(PACK_ROOT / "personae",),
        skill_roots=(PACK_ROOT / "skills",),
        mcp_modules=(
            "verticals.fashion.mcp_tools.inventory",
            "verticals.fashion.mcp_tools.operations",
        ),
        external_capabilities=frozenset(),
        worlds=FASHION_WORLDS,
        default_world="fashion",
        seed=SeedRegistration(bootstrap=bootstrap),
        projections=FASHION_PROJECTIONS,
        memory_workflow_types=tuple(domains),
        lifecycle=LifecycleRegistration(start=start),
        recordings=RecordingSources(
            curated_dirs=(PACK_ROOT / "recordings",)
        ),
        ui=load_ui_manifest(PACK_ROOT / "ui.json"),
        ramp_workflow_types=(),
    )
```

- [ ] **Step 4: Re-run pack and server lifecycle tests**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/shared/test_fashion_vertical_pack.py \
  tests/api/shared/test_vertical_loader.py \
  tests/api/shared/test_vertical_pack_inventory.py \
  tests/api/server/test_main_verticals.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add verticals/fashion \
  tests/api/shared/test_fashion_vertical_pack.py \
  tests/api/shared/test_vertical_loader.py \
  tests/api/shared/test_vertical_pack_inventory.py \
  tests/api/server/test_main_verticals.py
git commit -m "feat(fashion): register vertical pack"
```

## Task 3: Prove the deterministic actor world

**Files:**
- Extend: `tests/api/world/actor/test_fashion_world.py`
- Extend: `tests/api/world/actor/test_fashion_causal_world.py`
- Modify: `verticals/fashion/world.py`
- Modify: `verticals/fashion/worlds.py`
- Modify: `verticals/fashion/reference_cases.py`
- Modify: `verticals/fashion/reference_actions.py`

- [ ] **Step 1: Write the golden scenario tests**

Extend `tests/api/world/actor/test_fashion_world.py` with golden-scenario and
reference-case coverage. The file already covers `FashionScenario` construction,
command dispatch, and outcome branches. Add or verify these cases:

```python
def test_demo_world_has_designed_scale(runtime) -> None:
    scenario = FashionScenario(
        runtime,
        FashionConfig(seed=42),
    )

    assert len(scenario.stores) == 8
    assert len(scenario.distribution_centres) == 2
    assert len(scenario.brands) == 12
    assert len(scenario.styles) == 24
    assert len(scenario.skus) == 192
    assert len(scenario.customers) == 300


def test_reference_cases_cover_every_workflow() -> None:
    assert set(FASHION_REFERENCE_CASES) == {
        "inventory-rebalancing",
        "demand-spike-response",
        "promotion-readiness",
        "markdown-governance",
        "supplier-delay-recovery",
        "fulfilment-exception-resolution",
        "marketplace-seller-exception",
        "returns-disposition",
    }


def test_golden_rebalance_has_auto_approve_and_no_action_branches(runtime) -> None:
    first = FashionScenario(runtime, FashionConfig(seed=42))
    second = FashionScenario(runtime, FashionConfig(seed=42))

    assert first.snapshot() == second.snapshot()
    cases = FASHION_REFERENCE_CASES["inventory-rebalancing"]
    assert {case.expected_outcome for case in cases} == {
        "auto_execute",
        "approval_required",
        "no_action",
    }
```

- [ ] **Step 2: Run tests and inspect failures**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/world/actor/test_fashion_world.py \
  tests/api/world/actor/test_fashion_causal_world.py -q
```

Expected: initial generated-code failures identify missing counts, cases, or
determinism.

- [ ] **Step 3: Implement the module-safe world contract**

Use immutable command-facing records:

```python
from dataclasses import dataclass
from enum import StrEnum


class InventoryOwnership(StrEnum):
    OWNED = "owned"
    CONCESSION = "concession"
    MARKETPLACE = "marketplace"


@dataclass(frozen=True, slots=True)
class FashionConfig:
    seed: int = 42
    store_count: int = 8
    distribution_centre_count: int = 2
    brand_count: int = 12
    style_count: int = 24
    sku_count: int = 192
    customer_count: int = 300


@dataclass(frozen=True, slots=True)
class InventoryPosition:
    location_id: str
    sku_id: str
    ownership: InventoryOwnership
    on_hand: int
    reserved: int
    safety_stock: int
    version: int

    @property
    def transferable(self) -> int:
        return max(
            0,
            self.on_hand - self.reserved - self.safety_stock,
        )
```

Sensors must emit only from deterministic source state. The world command
handler must never treat concession or marketplace stock as owned inventory.

- [ ] **Step 4: Run world tests**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/world/actor/test_fashion_world.py \
  tests/api/world/actor/test_fashion_causal_world.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add verticals/fashion/world.py verticals/fashion/worlds.py \
  verticals/fashion/reference_cases.py \
  verticals/fashion/reference_actions.py \
  tests/api/world/actor/test_fashion_world.py \
  tests/api/world/actor/test_fashion_causal_world.py
git commit -m "feat(fashion): add causal retail world"
```

## Task 4: Enforce typed command and bounded authority

**Files:**
- Extend: `tests/api/functions/test_fashion_mcp_tools.py`
- Modify: `verticals/fashion/world.py`
- Modify: `verticals/fashion/authority.py`
- Modify: `verticals/fashion/personas.py`
- Modify: `verticals/fashion/policies/tools.yaml`
- Modify: `verticals/fashion/mcp_tools/inventory.py`

- [ ] **Step 1: Write command boundary tests**

Extend `tests/api/functions/test_fashion_mcp_tools.py` with command boundary
assertions. The file already covers tool-name completeness and evidence
provenance. Add or verify transfer command cases:

```python
def test_low_risk_owned_transfer_executes_without_approval(world_state) -> None:
    result = apply_inventory_transfer(world_state, command())
    assert result.event_type == "inventory.transfer.completed"


def test_high_value_transfer_requires_approval(world_state) -> None:
    result = apply_inventory_transfer(
        world_state,
        command(retail_value_gbp=10_000.01),
    )
    assert result.reason == "approval_required"


def test_marketplace_stock_cannot_use_owned_transfer(world_state) -> None:
    result = apply_inventory_transfer(
        world_state,
        command(ownership=InventoryOwnership.MARKETPLACE),
    )
    assert result.reason == "ineligible_ownership"


def test_replayed_command_is_idempotent(world_state) -> None:
    first = apply_inventory_transfer(world_state, command())
    second = apply_inventory_transfer(world_state, command())
    assert second == first
```

- [ ] **Step 2: Run command tests**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/functions/test_fashion_mcp_tools.py -q
```

Expected: FAIL until every threshold and rejection is explicit.

- [ ] **Step 3: Implement the command schema**

Use:

```python
@dataclass(frozen=True, slots=True)
class InventoryTransferCommand:
    command_id: str
    workflow_id: str
    source_location_id: str
    destination_location_id: str
    sku_id: str
    quantity: int
    retail_value_gbp: float
    ownership: InventoryOwnership
    expected_source_version: int
    expected_destination_version: int
    approval_reference: str | None
    reason_code: str
    evidence_digest: str
```

Validation order is idempotency, schema, optimistic versions, ownership,
available stock, safety stock, approval, cost/margin, and fairness. A business
rejection returns a typed `command.rejected` event and makes no state change.

- [ ] **Step 4: Run command and governance tests**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/functions/test_fashion_mcp_tools.py \
  tests/api/server/skills/test_authority_invocation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add verticals/fashion tests/api/functions/test_fashion_mcp_tools.py
git commit -m "feat(fashion): govern inventory commands"
```

## Task 5: Complete all workflow orchestrations

**Files:**
- Extend: `tests/api/functions/workflows/test_fashion_orchestration.py`
- Extend: `tests/api/shared/test_fashion_process_profiles.py`
- Modify: `verticals/fashion/domains.py`
- Modify: `verticals/fashion/process_profiles.py`
- Modify: `verticals/fashion/durable.py`

- [ ] **Step 1: Write workflow shape tests**

Extend `tests/api/functions/workflows/test_fashion_orchestration.py` with hero
phase-contract and completeness assertions. The file already covers orchestration
dispatch for all eight workflow types. Add or verify:

```python
from verticals.fashion.domains import FASHION_DOMAINS


def test_hero_phase_contract() -> None:
    hero = FASHION_DOMAINS["inventory-rebalancing"]
    assert tuple((phase.name, phase.kind) for phase in hero.phases) == (
        ("Detect Imbalance", "deterministic"),
        ("Assess Demand and Constraints", "agent"),
        ("Plan Rebalance", "agent"),
        ("Approve Exception", "hitl"),
        ("Execute Stock Action", "deterministic"),
        ("Verify Outcome", "deterministic"),
    )
    assert hero.skills == (
        "inventory-imbalance-analysis",
        "inventory-rebalance-planner",
    )


def test_every_workflow_has_a_real_orchestrator() -> None:
    assert len(FASHION_DOMAINS) == 8
    assert all(not domain.stub for domain in FASHION_DOMAINS.values())
    assert all(domain.orchestrator_name for domain in FASHION_DOMAINS.values())
```

- [ ] **Step 2: Run workflow tests**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/functions/workflows/test_fashion_orchestration.py \
  tests/api/shared/test_fashion_process_profiles.py -q
```

Expected: FAIL for any missing phase, skill, or orchestration.

- [ ] **Step 3: Keep supporting profiles explicit**

The profile registry must contain:

```python
SUPPORTING_WORKFLOW_TYPES = (
    "demand-spike-response",
    "promotion-readiness",
    "markdown-governance",
    "supplier-delay-recovery",
    "fulfilment-exception-resolution",
    "marketplace-seller-exception",
    "returns-disposition",
)
```

Each profile declares its sensor ID, objective type, command type, success
event, function, phases, skills, and optional HITL persona/event. Reuse at most
three shared engines: forecast-plan-act, case-triage-resolve, and
risk-review-govern.

- [ ] **Step 4: Verify Functions indexing and workflow tests**

Run:

```bash
ZAVA_VERTICAL=fashion uv run --frozen --no-sync pytest \
  tests/api/functions/workflows/test_fashion_orchestration.py \
  tests/api/shared/test_fashion_process_profiles.py \
  tests/api/functions/test_vertical_function_registration.py \
  tests/api/functions/test_vertical_skill_root.py -q
```

Expected: PASS with all eight orchestrator names and their activities indexed.

- [ ] **Step 5: Commit**

```bash
git add verticals/fashion/{domains.py,process_profiles.py,durable.py} \
  tests/api/functions/workflows/test_fashion_orchestration.py \
  tests/api/shared/test_fashion_process_profiles.py
git commit -m "feat(fashion): run retail workflows"
```

## Task 6: Validate skills, personas, tools, projections, and UI

**Files:**
- Extend: `tests/api/shared/test_fashion_vertical_pack.py`
- Extend: `tests/api/server/services/test_fashion_projections.py`
- Extend: `tests/api/server/test_fashion_runtime.py`
- Modify: `verticals/fashion/agents.py`
- Modify: `verticals/fashion/personas.py`
- Modify: `verticals/fashion/authority.py`
- Modify: `verticals/fashion/functions.py`
- Modify: `verticals/fashion/projections.py`
- Modify: `verticals/fashion/ui.json`
- Modify: `verticals/fashion/skills/*/SKILL.md`
- Modify: `verticals/fashion/personae/*/SKILL.md`
- Modify: `verticals/fashion/mcp_tools/*.py`

- [ ] **Step 1: Write asset resolution tests**

Extend `tests/api/shared/test_fashion_vertical_pack.py` with asset-resolution
assertions. The file already covers functions and personas. Add or verify:

```python
from api.shared.vertical_loader import build_runtime


def test_fashion_assets_resolve_from_pack(tmp_path) -> None:
    pack = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    ).pack

    assert set(pack.projections) == set(pack.domains)
    assert set(pack.memory_workflow_types) == set(pack.domains)
    assert pack.ui.theme["label"] == "Fashion Retail"
    assert {"blueprint", "world", "memory", "knowledge"} <= set(
        pack.ui.capabilities
    )
    assert all(
        any((root / skill / "SKILL.md").is_file() for root in pack.skill_roots)
        for domain in pack.domains.values()
        for skill in domain.skills
    )
```

- [ ] **Step 2: Run asset tests**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/shared/test_fashion_vertical_pack.py \
  tests/api/server/services/test_fashion_projections.py \
  tests/api/server/test_fashion_runtime.py \
  tests/api/shared/test_vertical_pack_validation.py -q
```

Expected: 19 passed. `validate_pack` must reject unresolved tools, skills,
personas, policies, projections, and recordings.

- [ ] **Step 3: Check skill/tool least privilege**

Run:

```bash
rg -n '^allowed-tools:' verticals/fashion/skills
ZAVA_VERTICAL=fashion uv run --frozen --no-sync python -c \
  'from api.shared.vertical_loader import active_runtime; print(active_runtime().fingerprint)'
```

Expected: every tool resolves through a declared Fashion MCP module, and the
runtime prints `fashion:1`.

- [ ] **Step 4: Commit**

```bash
git add verticals/fashion \
  tests/api/shared/test_fashion_vertical_pack.py \
  tests/api/server/services/test_fashion_projections.py \
  tests/api/server/test_fashion_runtime.py
git commit -m "feat(fashion): add governed retail assets"
```

## Task 7: Add permanent live and replay proof

**Files:**
- Modify: `Makefile`
- Modify: `tools/fashion_zava_e2e_proof.sh`
- Modify: `tools/fashion_zava_e2e_proof.mjs`
- Create: `verticals/fashion/recordings/*.jsonl`
- Create: `proof/manifest.json`
- Modify: `.gitignore`
- Extend: `tests/tools/test_fashion_zava_e2e_proof.py`

- [ ] **Step 1: Write proof contract tests**

Extend `tests/tools/test_fashion_zava_e2e_proof.py` with proof-contract
assertions. The file already covers `--print-config` output, script/driver path
existence, and manifest schema. Add or verify:

```python
def test_fashion_proof_print_config() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--print-config"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    config = json.loads(result.stdout)
    assert config["vertical"] == "fashion"
    assert config["world"] == "fashion"
    assert config["workflow_count"] == 8


def test_makefile_exposes_pack_scoped_proof() -> None:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert ".PHONY: prove" in text
    assert "VERTICAL is required" in text
    assert "_zava_e2e_proof.sh" in text
```

- [ ] **Step 2: Add the generic Make target and ignore generated proof**

Use:

```make
.PHONY: prove
prove:
	@test -n "$(VERTICAL)" || \
	  (echo "VERTICAL is required, for example: make prove VERTICAL=fashion" >&2; exit 2)
	@script="tools/$$(printf '%s' "$(VERTICAL)" | tr '-' '_')_zava_e2e_proof.sh"; \
	  test -x "$$script" || (echo "missing proof script: $$script" >&2; exit 2); \
	  "$$script"
```

Add `/proof/` to `.gitignore`. Curated JSONL recordings remain tracked under
`verticals/fashion/recordings/`.

- [ ] **Step 3: Run the complete proof**

Run:

```bash
make prove VERTICAL=fashion
```

Expected:

```text
live: PASS
replay: PASS
browser errors: 0
dropped workflow events: 0
workflows: 8/8
all proof ports released
```

The command writes gitignored `proof/manifest.json`, screenshots, recordings,
logs, and before/after snapshots. The manifest's `source_commit` equals
`git rev-parse HEAD`.

Verify:

```bash
jq -e \
  --arg commit "$(git rev-parse HEAD)" \
  '.vertical == "fashion"
   and .source_commit == $commit
   and .live.result == "PASS"
   and .replay.result == "PASS"
   and .browser_errors == []
   and (.workflows | length) == 8' \
  proof/manifest.json
```

Expected: `true`.

- [ ] **Step 4: Verify replay independently**

Run:

```bash
bash tools/fashion_zava_e2e_proof.sh --replay-only
```

Expected: PASS with Functions and the actor world disabled.

- [ ] **Step 5: Commit proof assets**

```bash
git add .gitignore Makefile tools/fashion_zava_e2e_proof.sh \
  tools/fashion_zava_e2e_proof.mjs \
  verticals/fashion/recordings \
  tests/tools/test_fashion_zava_e2e_proof.py
git commit -m "test(fashion): prove live and replay"
```

## Task 8: Run final regression and contract checks

**Files:**
- Modify only files required by failing Fashion-coupled tests.

- [ ] **Step 1: Run the focused Fashion suite**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/shared/test_fashion_vertical_pack.py \
  tests/api/shared/test_fashion_process_profiles.py \
  tests/api/shared/test_fashion_org_brief.py \
  tests/api/shared/test_fashion_recordings.py \
  tests/api/world/actor/test_fashion_world.py \
  tests/api/world/actor/test_fashion_causal_world.py \
  tests/api/functions/test_fashion_mcp_tools.py \
  tests/api/functions/workflows/test_fashion_orchestration.py \
  tests/api/server/test_fashion_runtime.py \
  tests/api/server/services/test_fashion_projections.py \
  tests/api/routes/test_world_fashion_process_run.py \
  tests/tools/test_fashion_zava_e2e_proof.py \
  tests/api/shared/test_vertical_loader.py \
  tests/api/shared/test_vertical_pack_inventory.py \
  tests/api/shared/test_vertical_pack_validation.py \
  tests/api/server/test_main_verticals.py \
  tests/api/functions/test_vertical_function_registration.py \
  tests/api/functions/test_vertical_skill_root.py -q
```

Expected: 161 passed.

- [ ] **Step 2: Build both web applications**

Run:

```bash
npm run build
npm --prefix web/blueprint run build
```

Expected: both builds exit 0.

- [ ] **Step 3: Re-run permanent proof from committed source**

Run:

```bash
make prove VERTICAL=fashion
```

Expected: PASS and `proof/manifest.json.source_commit` matches the current
commit.

- [ ] **Step 4: Check repository hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors and no unexplained generated files.

- [ ] **Step 5: Commit curated recordings and regenerate local proof**

```bash
git add verticals/fashion/recordings
git diff --cached --quiet || git commit -m "test(fashion): curate recordings"
make prove VERTICAL=fashion
jq -e --arg commit "$(git rev-parse HEAD)" \
  '.source_commit == $commit' proof/manifest.json
```

Expected: the generated proof manifest matches final `HEAD`; `proof/` remains
untracked and ignored.
