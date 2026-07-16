# Interchangeable Vertical Packs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace mixed global Agency/Telco registration with one validated active vertical pack per process while preserving Agency as the default and the existing live Telco proof.

**Architecture:** A static loader resolves one immutable `VerticalRuntime` before application state is built. Agency and Telco manifests explicitly compose domains, organisational functions, Durable registrations, governance identities, assets, worlds, projections, memory, recordings, lifecycle hooks, and UI capabilities; compatibility modules expose active-pack views only.

**Tech Stack:** Python 3.11, FastAPI, Azure Functions/Durable Functions, Pydantic/dataclasses, pytest, React 19, TypeScript, Vite, Vitest, Playwright, Bash

---

## File structure

### New shared contracts and loader

- `api/shared/domain_contracts.py` — `Domain`, `Phase`, `HitlGate`,
  `RegionOverlay`, and `WakeHint`.
- `api/shared/function_contracts.py` — organisational `Function` and
  `PersonaTree`.
- `api/shared/agent_contracts.py` — `AgentRegistryEntry`.
- `api/shared/authority_contracts.py` — `AuthorityRow`.
- `api/shared/world_contracts.py` — world, scale, objective, and responder
  registrations.
- `api/shared/projection_contracts.py` — lightweight projection callable type.
- `api/shared/kernel_assets.py` — explicit vertical-neutral identities and
  capabilities.
- `api/shared/vertical_pack.py` — immutable pack/runtime registration types.
- `api/shared/vertical_loader.py` — static pack lookup, selection, validation,
  data-root resolution, and process cache.
- `api/server/runtime_context.py` — FastAPI-facing active runtime accessor.

### New packs

- `verticals/__init__.py`
- `verticals/agency/manifest.py`
- `verticals/agency/domains.py`
- `verticals/agency/functions.py`
- `verticals/agency/agents.py`
- `verticals/agency/authority.py`
- `verticals/agency/durable.py`
- `verticals/agency/worlds.py`
- `verticals/agency/projections.py`
- `verticals/agency/lifecycle.py`
- `verticals/agency/ambient_agents/`
- `verticals/agency/ui.json`
- `verticals/telco/manifest.py`
- `verticals/telco/domains.py`
- `verticals/telco/functions.py`
- `verticals/telco/agents.py`
- `verticals/telco/authority.py`
- `verticals/telco/durable.py`
- `verticals/telco/worlds.py`
- `verticals/telco/projections.py`
- `verticals/telco/entity_projections/` — Telco projection implementations.
- `verticals/telco/lifecycle.py`
- `verticals/telco/ambient_agents/`
- `verticals/telco/ui.json`
- `verticals/telco/skills/` — the two existing proactive-care skills.
- `verticals/telco/mcp_tools/customer_care.py`
- `verticals/telco/personae/` — Telco customer-success roles plus the
  pack-local delivery-lead role.
- `verticals/telco/policies/tools.yaml` — governed care-tool metadata.
- `verticals/{agency,telco}/recordings/`

### Compatibility adapters

- `api/shared/domains.py`
- `api/shared/functions.py`
- `api/shared/agents.py`
- `api/shared/authority.py`
- `api/shared/verticals.py`
- `api/server/world/registry.py`
- `api/server/services/entity_projections/__init__.py`

### Runtime consumers

- `function_app.py`
- `api/server/state.py`
- `api/server/main.py`
- `api/server/services/durable_client.py`
- `api/server/services/simulator_orchestrator.py`
- `api/server/services/blueprint_inventory.py`
- `api/server/services/blueprint_recorder.py`
- `api/server/routes/blueprint.py`
- `api/server/routes/runtime.py`
- `api/server/world/service.py`
- `api/server/services/world_responders.py`
- `api/server/services/entity_reflector.py`
- `api/server/services/persona_responder.py`
- `api/server/services/compose/tape.py`

### Frontend

- `web/shared/runtime.ts`
- `web/client/hooks/useRuntimeManifest.ts`
- `web/client/components/feed/LeftRail.tsx`
- `web/client/routes/World.tsx`
- `web/blueprint/src/lib/types.ts`
- `web/blueprint/src/sections/Composition.tsx`
- `web/blueprint/src/pages/ConstellationPage.tsx`

### Tests and proof

- `tests/api/shared/test_vertical_loader.py`
- `tests/api/shared/test_vertical_pack_validation.py`
- `tests/api/shared/test_vertical_pack_inventory.py`
- `tests/api/functions/test_vertical_function_registration.py`
- `tests/api/server/routes/test_runtime_manifest.py`
- `tests/api/server/services/test_vertical_readiness.py`
- `tests/api/server/services/test_blueprint_pack_isolation.py`
- `tests/api/server/services/test_recording_pack_isolation.py`
- existing vertical, world, projection, memory, governance, and Telco proof tests
- `web/client/hooks/__tests__/useRuntimeManifest.test.tsx`
- `web/client/components/feed/__tests__/LeftRail.vertical.test.tsx`
- `tools/agency_vertical_e2e_proof.sh`
- `tools/agency_vertical_e2e_proof.mjs`

---

### Task 1: Lock the Agency and Telco inventory boundaries

**Files:**
- Create: `tests/api/shared/test_vertical_pack_inventory.py`
- Modify: `tests/api/shared/test_verticals.py`
- Modify: `tests/api/server/services/test_blueprint_inventory_verticals.py`
- Modify: `tests/api/server/test_main_verticals.py`
- Modify: `tests/api/world/actor/test_world_registry.py`

- [ ] **Step 1: Replace the old unset-profile expectation**

Update `tests/api/shared/test_verticals.py` so unset and blank
`ZAVA_VERTICAL` expect Agency rather than `None`:

```python
@pytest.mark.parametrize("value", [None, "", "   "])
def test_active_vertical_defaults_to_agency(
    monkeypatch: pytest.MonkeyPatch,
    value: str | None,
) -> None:
    if value is None:
        monkeypatch.delenv("ZAVA_VERTICAL", raising=False)
    else:
        monkeypatch.setenv("ZAVA_VERTICAL", value)

    verticals = _verticals_module()
    profile = verticals.active_vertical()

    assert profile.name == "agency"
    assert profile.world is None
    assert "network-incident" not in verticals.registered_workflow_types()
    assert "proactive-customer-care" not in verticals.registered_workflow_types()
    assert "order-to-activate" not in verticals.registered_workflow_types()
```

- [ ] **Step 2: Add exact business-registry boundaries**

Create `tests/api/shared/test_vertical_pack_inventory.py`:

```python
from api.shared.vertical_loader import build_runtime

TELCO_WORKFLOWS = {
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
}
TELCO_AGENTS = {
    "proactive-customer-care-entitlement",
    "proactive-customer-care-execution",
}


def test_agency_default_excludes_all_telco_business_assets(tmp_path):
    runtime = build_runtime({}, data_root=tmp_path)

    assert runtime.pack.name == "agency"
    assert TELCO_WORKFLOWS.isdisjoint(runtime.pack.domains)
    assert TELCO_AGENTS.isdisjoint(runtime.pack.agents)
    assert "telco" not in runtime.pack.worlds
    assert all(
        "telco" not in str(path).lower()
        for path in runtime.pack.recordings.curated_dirs
    )


def test_telco_contains_only_the_proven_business_slice(tmp_path):
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )

    assert set(runtime.pack.domains) == TELCO_WORKFLOWS
    assert set(runtime.pack.agents) == TELCO_AGENTS
    assert set(runtime.pack.worlds) == {"telco"}
    assert runtime.world_name == "telco"
    assert runtime.pack.ramp_workflow_types == ()
```

- [ ] **Step 3: Make mismatch expectations explicit**

Add parametrized selection tests:

```python
@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"ZAVA_VERTICAL": "mystery"}, "unknown vertical 'mystery'"),
        (
            {"ZAVA_VERTICAL": "agency", "ZAVA_WORLD": "telco"},
            "world 'telco' is not owned by vertical 'agency'",
        ),
        (
            {"ZAVA_VERTICAL": "telco", "ZAVA_WORLD": "support"},
            "world 'support' is not owned by vertical 'telco'",
        ),
    ],
)
def test_invalid_selection_fails(environment, message, tmp_path):
    with pytest.raises(ValueError, match=message):
        build_runtime(environment, data_root=tmp_path)
```

Change `test_main_verticals.py` so the former
`("telco", "support", "support")` case expects a startup error.

- [ ] **Step 4: Require Blueprint and world isolation**

Update the Blueprint test so:

```python
assert _registry_manifest_types(module) == AGENCY_WORKFLOW_TYPES
assert not any(entry["workflow_type"] == "onboarding" for entry in telco.DOMAINS)
assert {skill.name for skill in telco._load_skills()} == {
    "proactive-customer-care-entitlement",
    "proactive-customer-care-execution",
}
assert {tool.name for tool in telco._load_mcp_tools()} == {"customer_care"}
```

Update `test_world_registry.py` to resolve through an explicit runtime and assert
Agency cannot resolve `telco` and Telco cannot resolve `support`.

- [ ] **Step 5: Run the tests to verify RED**

Run:

```bash
PORTAL_DATA_DIR="$(mktemp -d)" .venv/bin/pytest \
  tests/api/shared/test_verticals.py \
  tests/api/shared/test_vertical_pack_inventory.py \
  tests/api/server/services/test_blueprint_inventory_verticals.py \
  tests/api/server/test_main_verticals.py \
  tests/api/world/actor/test_world_registry.py -q
```

Expected: FAIL because `vertical_loader` does not exist, unset configuration
still returns every domain, mismatched worlds are accepted, and Blueprint still
adds Agency metadata to Telco.

---

### Task 2: Add immutable pack contracts and deterministic selection

**Files:**
- Create: `api/shared/domain_contracts.py`
- Create: `api/shared/function_contracts.py`
- Create: `api/shared/agent_contracts.py`
- Create: `api/shared/authority_contracts.py`
- Create: `api/shared/world_contracts.py`
- Create: `api/shared/projection_contracts.py`
- Create: `api/shared/kernel_assets.py`
- Create: `api/shared/vertical_pack.py`
- Create: `api/shared/vertical_loader.py`
- Create: `tests/api/shared/test_vertical_loader.py`
- Create: `tests/api/shared/test_vertical_pack_validation.py`
- Create: `tests/api/shared/vertical_pack_fakes.py`

- [ ] **Step 1: Write focused loader tests**

Create `tests/api/shared/test_vertical_loader.py`:

```python
def test_selection_table(tmp_path, pack_loader):
    assert build_runtime(
        {}, data_root=tmp_path, pack_loader=pack_loader
    ).pack.name == "agency"
    assert build_runtime(
        {"ZAVA_WORLD": "support"},
        data_root=tmp_path,
        pack_loader=pack_loader,
    ).pack.name == "agency"
    assert build_runtime(
        {"ZAVA_WORLD": "telco"},
        data_root=tmp_path,
        pack_loader=pack_loader,
    ).pack.name == "telco"


def test_data_directory_is_namespaced(tmp_path, pack_loader):
    agency = build_runtime(
        {}, data_root=tmp_path, pack_loader=pack_loader
    )
    telco = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
        pack_loader=pack_loader,
    )

    assert agency.data_dir == tmp_path / "agency"
    assert telco.data_dir == tmp_path / "telco"


def test_world_scale_requires_an_active_owned_world(tmp_path, pack_loader):
    with pytest.raises(ValueError, match="requires an active world"):
        build_runtime(
            {"ZAVA_WORLD_SCALE": "demo"},
            data_root=tmp_path,
            pack_loader=pack_loader,
        )
    with pytest.raises(ValueError, match="unknown scale 'stress'"):
        build_runtime(
            {
                "ZAVA_VERTICAL": "telco",
                "ZAVA_WORLD_SCALE": "stress",
            },
            data_root=tmp_path,
            pack_loader=pack_loader,
        )


def test_active_runtime_is_process_immutable(
    monkeypatch, tmp_path, pack_loader
):
    active_runtime.cache_clear()
    monkeypatch.setattr(vertical_loader, "load_pack", pack_loader)
    monkeypatch.setenv("ZAVA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ZAVA_VERTICAL", "agency")
    first = active_runtime()
    monkeypatch.setenv("ZAVA_VERTICAL", "telco")

    assert active_runtime() is first
    assert active_runtime().pack.name == "agency"
    active_runtime.cache_clear()
```

The `pack_loader` fixture returns two complete in-memory `VerticalPack` test
objects: Agency owns optional support world with `default_world=None`; Telco
owns and defaults to Telco world. Both worlds expose only a `demo` scale. All
other registrations use empty immutable mappings, no-op seed/lifecycle
callbacks, and empty Durable name sets. These fixtures test the loader without
importing production manifests that are created in Task 3.

Implement the fixture in `vertical_pack_fakes.py`:

```python
async def _start(_state):
    return ()


def make_test_pack(name: str, root: Path) -> VerticalPack:
    world_name = "support" if name == "agency" else "telco"
    world = WorldPackRegistration(
        name=world_name,
        scales={
            "demo": WorldScaleProfile(
                name="demo",
                build_scenario=lambda _runtime: None,
                default_minutes_per_second=10.0,
            ),
        },
        default_scale="demo",
        objective_routes=(),
        responders={},
    )
    return VerticalPack(
        root=root / name,
        name=name,
        display_name=name.title(),
        manifest_version="1",
        domains={},
        organisation_functions={},
        agents={},
        authority={},
        policy_sources=(),
        durable_functions=DurableFunctionRegistration(
            register=lambda _app: None,
            orchestrators=frozenset(),
            activities=frozenset(),
        ),
        personae_roots=(),
        skill_roots=(),
        mcp_modules=(),
        external_capabilities=frozenset(),
        worlds={world_name: world},
        default_world=None if name == "agency" else world_name,
        seed=SeedRegistration(bootstrap=lambda _state: None),
        projections={},
        memory_workflow_types=(),
        lifecycle=LifecycleRegistration(start=_start),
        recordings=RecordingSources(curated_dirs=()),
        ui=VerticalUiManifest(
            capabilities=frozenset(),
            lenses=(),
            theme={},
            phase_aliases={},
        ),
        ramp_workflow_types=(),
    )
```

In `test_vertical_loader.py`:

```python
@pytest.fixture
def pack_loader(tmp_path):
    return lambda name: make_test_pack(name, tmp_path)
```

- [ ] **Step 2: Extract registry dataclasses without changing fields**

Move the existing dataclass definitions verbatim:

```python
# api/shared/domain_contracts.py
PhaseKind = Literal["deterministic", "agent", "hitl"]

@dataclass(frozen=True)
class Phase:
    name: str
    kind: PhaseKind

@dataclass(frozen=True)
class HitlGate:
    gate_phase: str
    external_event: str
    persona: str
    wait_probability: float = 0.0
    sick_probability: float = 0.0
    holiday_probability: float = 0.0
    timeout_probability: float = 0.0
    override_probability: float = 0.0
```

Retain every existing `Domain`, `RegionOverlay`, `WakeHint`, `Function`,
`PersonaTree`, `AgentRegistryEntry`, and `AuthorityRow` field. Change
`AgentRegistryEntry.scope_function` from the closed `Literal` to `str` so
vertical-defined functions are type-safe without editing a global union.
Make `Domain` frozen; pack construction wires its `function` field with
`dataclasses.replace` rather than mutating a process-global object.

Move `ObjectiveRoute`, `WorldPackRegistration`, and
`ResponderRegistration` into `world_contracts.py`. Add:

```python
@dataclass(frozen=True, slots=True)
class WorldScaleProfile:
    name: str
    build_scenario: Callable[[Any], Any]
    default_minutes_per_second: float


@dataclass(frozen=True, slots=True)
class WorldPackRegistration:
    name: str
    scales: Mapping[str, WorldScaleProfile]
    default_scale: str
    objective_routes: tuple[ObjectiveRoute, ...]
    responders: Mapping[str, ResponderRegistration]
```

Define `ProjectionFn = Callable[[Workflow], Sequence[Any]]` in
`projection_contracts.py` so `vertical_pack.py` does not import Kuzu/server
modules.

- [ ] **Step 3: Add the pack contracts**

Implement `api/shared/vertical_pack.py` with frozen registrations:

```python
@dataclass(frozen=True, slots=True)
class DurableFunctionRegistration:
    register: Callable[[Any], None]
    orchestrators: frozenset[str]
    activities: frozenset[str]


@dataclass(frozen=True, slots=True)
class RecordingSources:
    curated_dirs: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class VerticalUiManifest:
    capabilities: frozenset[str]
    lenses: tuple[str, ...]
    theme: Mapping[str, str]
    phase_aliases: Mapping[str, Mapping[str, str]]
    aspirational_domains: tuple[str, ...] = ()
    include_meta_skills: bool = False


@dataclass(frozen=True, slots=True)
class SeedRegistration:
    bootstrap: Callable[[Any], None]


@dataclass(frozen=True, slots=True)
class LifecycleRegistration:
    start: Callable[
        [Any],
        Awaitable[Sequence[Callable[[], Any]]],
    ]


@dataclass(frozen=True, slots=True)
class VerticalPack:
    root: Path
    name: str
    display_name: str
    manifest_version: str
    domains: Mapping[str, Domain]
    organisation_functions: Mapping[str, Function]
    agents: Mapping[str, AgentRegistryEntry]
    authority: Mapping[str, AuthorityRow]
    policy_sources: tuple[Path, ...]
    durable_functions: DurableFunctionRegistration
    personae_roots: tuple[Path, ...]
    skill_roots: tuple[Path, ...]
    mcp_modules: tuple[str, ...]
    external_capabilities: frozenset[str]
    worlds: Mapping[str, WorldPackRegistration]
    default_world: str | None
    seed: SeedRegistration
    projections: Mapping[str, ProjectionFn]
    memory_workflow_types: tuple[str, ...]
    lifecycle: LifecycleRegistration
    recordings: RecordingSources
    ui: VerticalUiManifest
    ramp_workflow_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VerticalRuntime:
    pack: VerticalPack
    world_name: str | None
    world_scale_name: str | None
    data_dir: Path
    fingerprint: str
```

Use `MappingProxyType` in `freeze_pack()` so callers cannot mutate registry
mappings.

Pack manifests must remain safe to import in both FastAPI and Functions
processes. Registration callbacks perform provider imports inside the callback:

```python
def register_telco_durable(app: Any) -> None:
    from verticals.telco.durable import register
    register(app)


async def start_telco_lifecycle(state: Any):
    from verticals.telco.lifecycle import start
    return await start(state)
```

Do not import world scenarios, projection modules, lifecycle watchers, or
Durable workflow modules at manifest module import time.

- [ ] **Step 4: Implement selection without importing both packs**

Implement `vertical_loader.py`:

```python
PACK_MODULES = {
    "agency": "verticals.agency.manifest",
    "telco": "verticals.telco.manifest",
}
LEGACY_WORLD_OWNERS = {"support": "agency", "telco": "telco"}


def _normalise(value: str | None) -> str | None:
    cleaned = value.strip().lower() if value is not None else ""
    return cleaned or None


def select_vertical(environment: Mapping[str, str]) -> tuple[str, str | None]:
    explicit_vertical = _normalise(environment.get("ZAVA_VERTICAL"))
    world = _normalise(environment.get("ZAVA_WORLD"))
    name = explicit_vertical or LEGACY_WORLD_OWNERS.get(world or "") or "agency"
    if name not in PACK_MODULES:
        raise ValueError(f"unknown vertical {name!r}")
    return name, world


def build_runtime(
    environment: Mapping[str, str],
    *,
    data_root: Path | None = None,
    pack_loader: Callable[[str], VerticalPack] = load_pack,
) -> VerticalRuntime:
    name, requested_world = select_vertical(environment)
    pack = freeze_pack(pack_loader(name))
    validate_pack(pack)
    world = requested_world or pack.default_world
    if world is not None and world not in pack.worlds:
        raise ValueError(
            f"world {world!r} is not owned by vertical {pack.name!r}"
        )
    requested_scale = _normalise(environment.get("ZAVA_WORLD_SCALE"))
    if requested_scale is not None and world is None:
        raise ValueError("ZAVA_WORLD_SCALE requires an active world")
    scale = (
        requested_scale or pack.worlds[world].default_scale
        if world is not None
        else None
    )
    if world is not None and scale not in pack.worlds[world].scales:
        raise ValueError(
            f"unknown scale {scale!r} for world {world!r}"
        )
    root = data_root or resolve_data_root(environment)
    return VerticalRuntime(
        pack=pack,
        world_name=world,
        world_scale_name=scale,
        data_dir=root / pack.name,
        fingerprint=f"{pack.name}:{pack.manifest_version}",
    )
```

`active_runtime()` resolves `load_pack` at call time so tests can replace the
loader without weakening production caching:

```python
@cache
def active_runtime() -> VerticalRuntime:
    return build_runtime(os.environ, pack_loader=load_pack)
```
Data-root precedence is:

```python
def resolve_data_root(environment: Mapping[str, str]) -> Path:
    raw = (
        _normalise(environment.get("ZAVA_DATA_DIR"))
        or _normalise(environment.get("PORTAL_DATA_DIR"))
        or "data/runtime"
    )
    return Path(raw).expanduser()
```

The loader appends the pack name; callers never append it themselves.

- [ ] **Step 5: Implement atomic validation**

`validate_pack(pack)` must raise `ValueError` with pack and asset IDs for:

```python
for workflow_type, domain in pack.domains.items():
    if workflow_type != domain.workflow_type:
        fail("domain key", workflow_type)
    if not domain.stub and domain.orchestrator_name not in (
        pack.durable_functions.orchestrators
    ):
        fail("missing orchestrator", domain.orchestrator_name)
    for skill in domain.skills:
        if skill not in loaded_skill_names(pack.skill_roots):
            fail("missing skill", skill)

owned_domains = {
    workflow_type
    for function in pack.organisation_functions.values()
    for workflow_type in function.owns_domains
}
if owned_domains != set(pack.domains):
    raise ValueError(
        f"vertical {pack.name!r} function ownership mismatch: "
        f"missing={sorted(set(pack.domains) - owned_domains)}, "
        f"unknown={sorted(owned_domains - set(pack.domains))}"
    )
```

Also validate world default scales/responders, ramp domains, projections,
memory IDs, persona files,
MCP operation references, and curated recording workflow types.
An orchestrator is valid when declared by a live domain, an active world's
responder, or the kernel; this keeps Agency's world-only
`SurgeStaffingOrchestrator` valid without inventing a Blueprint domain.

`kernel_assets.py` declares the supported UI vocabulary:

```python
KNOWN_CAPABILITIES = frozenset({
    "blueprint", "compose", "knowledge", "memory", "world",
})
KNOWN_LENSES = frozenset({
    "agency-operations",
    "telco-network",
    "customer-impact",
    "order",
    "control",
})
```

`load_ui_manifest(path)` rejects unknown keys, capabilities, and lens IDs
before returning `VerticalUiManifest`.

- [ ] **Step 6: Run loader and validator tests**

Run:

```bash
PORTAL_DATA_DIR="$(mktemp -d)" .venv/bin/pytest \
  tests/api/shared/test_vertical_loader.py \
  tests/api/shared/test_vertical_pack_validation.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add \
  api/shared/domain_contracts.py \
  api/shared/function_contracts.py \
  api/shared/agent_contracts.py \
  api/shared/authority_contracts.py \
  api/shared/world_contracts.py \
  api/shared/projection_contracts.py \
  api/shared/kernel_assets.py \
  api/shared/vertical_pack.py \
  api/shared/vertical_loader.py \
  tests/api/shared/test_vertical_loader.py \
  tests/api/shared/test_vertical_pack_validation.py \
  tests/api/shared/vertical_pack_fakes.py
git commit -m "feat(verticals): add pack runtime contract" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Build Agency and Telco business registries

**Files:**
- Create: `verticals/__init__.py`
- Create: `verticals/agency/{__init__,manifest,domains,functions,agents,authority}.py`
- Create: `verticals/telco/{__init__,manifest,domains,functions,agents,authority}.py`
- Create: `verticals/{agency,telco}/worlds.py`
- Create: `verticals/{agency,telco}/projections.py`
- Create: `verticals/{agency,telco}/lifecycle.py`
- Create: `verticals/telco/policies/tools.yaml`
- Create: `verticals/agency/ui.json`
- Create: `verticals/telco/ui.json`
- Move: `api/server/skills/proactive-customer-care-*` to `verticals/telco/skills/`
- Move: `api/server/mcp_tools/customer_care.py` to `verticals/telco/mcp_tools/`
- Move: `api/server/personae/cs_{director,account_director,manager,specialist}` to `verticals/telco/personae/`
- Move: `data/blueprint-recordings/*.jsonl` to the owning pack recording roots
- Create: `verticals/telco/personae/delivery_lead/SKILL.md`
- Create: `verticals/{agency,telco}/recordings/README.md`
- Modify: `api/shared/{domains,functions,agents,authority,verticals}.py`
- Modify: `api/server/services/governance/identity.py`
- Modify: `api/server/services/governance/kernel.py`
- Modify: `api/functions/graphs/executors/agents/agent_proactive_customer_care_entitlement.py`
- Modify: `api/functions/graphs/executors/agents/agent_proactive_customer_care_execution.py`
- Modify: `tests/api/server/services/test_world_bridge_proactive_care_integration.py`
- Modify: `tests/api/shared/test_domains_registry.py`
- Modify: `tests/api/shared/test_functions_registry.py`
- Modify: `tests/api/shared/test_functions_validators.py`
- Modify: `tests/api/shared/test_authority.py`

- [ ] **Step 1: Write active-registry tests**

Add subprocess tests so module caches cannot leak between verticals:

```python
SCRIPT = """
import json
from api.shared.domains import DOMAINS
from api.shared.functions import FUNCTIONS
from api.shared.agents import AGENTS
print(json.dumps({
    "domains": sorted(DOMAINS),
    "functions": sorted(FUNCTIONS),
    "agents": sorted(AGENTS),
}))
"""


def registry_snapshot(vertical: str | None) -> dict:
    env = os.environ.copy()
    env.pop("ZAVA_WORLD", None)
    if vertical is None:
        env.pop("ZAVA_VERTICAL", None)
    else:
        env["ZAVA_VERTICAL"] = vertical
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)
```

Assert default Agency excludes the three Telco domains and two care agents.
Assert Telco contains exactly those domains/agents plus its two organisational
functions.

- [ ] **Step 2: Split domain declarations**

Move the registry types to `domain_contracts.py`. Copy the existing `DOMAINS`
literal into `verticals/agency/domains.py`, rename it `AGENCY_DOMAINS`, and
remove only:

```python
TELCO_WORKFLOW_TYPES = {
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
}
```

Move those three existing `Domain(...)` declarations verbatim into
`verticals/telco/domains.py` as `TELCO_DOMAINS`. Keep phase kinds, HITL gates,
skills, prefixes, orchestrator names, and spawn metadata unchanged.

- [ ] **Step 3: Relocate the existing Telco static assets**

Run:

```bash
mkdir -p verticals/telco/skills verticals/telco/mcp_tools \
  verticals/telco/personae
git mv api/server/skills/proactive-customer-care-entitlement \
  verticals/telco/skills/
git mv api/server/skills/proactive-customer-care-execution \
  verticals/telco/skills/
git mv api/server/mcp_tools/customer_care.py \
  verticals/telco/mcp_tools/customer_care.py
git mv api/server/personae/cs_director verticals/telco/personae/
git mv api/server/personae/cs_account_director verticals/telco/personae/
git mv api/server/personae/cs_manager verticals/telco/personae/
git mv api/server/personae/cs_specialist verticals/telco/personae/
mkdir -p verticals/agency/recordings verticals/telco/recordings
git mv data/blueprint-recordings/network-incident-*.jsonl \
  verticals/telco/recordings/
git mv data/blueprint-recordings/proactive-customer-care-*.jsonl \
  verticals/telco/recordings/
git mv data/blueprint-recordings/order-to-activate-*.jsonl \
  verticals/telco/recordings/
git mv data/blueprint-recordings/*.jsonl verticals/agency/recordings/
```

Create a pack-local `delivery_lead/SKILL.md` with the current
`delivery_lead` frontmatter, external event, authority check, and decision
policy. Agency keeps its existing copy because both isolated packs use the
same role ID.

Add this `README.md` in both recording roots:

```markdown
# Curated Blueprint recordings

These immutable JSONL recordings belong to this vertical pack. Runtime capture
writes beneath the active pack's `ZAVA_DATA_DIR` namespace and must not modify
this directory.
```

Replace the entitlement executor import with:

```python
from verticals.telco.mcp_tools.customer_care import customer_care_policy_lookup_tool
```

Replace the execution-agent import with:

```python
from verticals.telco.mcp_tools.customer_care import (
    customer_care_prepare_credit_tool,
    customer_care_prepare_notification_tool,
)
```

- [ ] **Step 4: Add pack-owned UI metadata**

Move the existing `_PHASE_ALIASES` mapping verbatim into Agency `ui.json`.
Add Agency's Onboarding ring, Procurement/Legal/IT aspirational rings, and
meta-skill flag there. Agency capabilities are `blueprint`, `compose`,
`memory`, and `knowledge`; its lens list is `["agency-operations"]`.

Create Telco `ui.json`:

```json
{
  "capabilities": ["blueprint", "world", "memory", "knowledge"],
  "lenses": ["telco-network", "customer-impact", "order", "control"],
  "theme": {
    "accent": "#14b8a6",
    "label": "Telco"
  },
  "phase_aliases": {},
  "aspirational_domains": [],
  "include_meta_skills": false
}
```

The runtime adds Agency's optional `world` capability only when support world
is selected.

- [ ] **Step 5: Split organisational functions**

Move `Function` and `PersonaTree` to `function_contracts.py`.

Agency retains every current function except `customer-success`; change its
`ops.owns_domains` to:

```python
owns_domains=("crisis-response",)
```

Telco defines:

```python
TELCO_FUNCTIONS = {
    "network-operations": Function(
        name="network-operations",
        display="Network Operations",
        operator_surface="network-operations",
        owns_domains=("network-incident", "order-to-activate"),
        ambient_agents=(),
        kpis=("availability-pct", "mttr", "activation-time"),
        persona_hierarchy=PersonaTree(role="delivery_lead"),
    ),
    "customer-success": Function(
        name="customer-success",
        display="Customer Success",
        operator_surface="customer-success",
        owns_domains=("proactive-customer-care",),
        ambient_agents=(),
        kpis=("nps", "proactive-resolution-pct", "credit-cost"),
        persona_hierarchy=PersonaTree(
            role="cs_director",
            manages=(
                PersonaTree(
                    role="cs_account_director",
                    manages=(
                        PersonaTree(
                            role="cs_manager",
                            manages=(PersonaTree(role="cs_specialist"),),
                        ),
                    ),
                ),
            ),
        ),
    ),
}
```

- [ ] **Step 6: Split agent and authority mappings**

Move the two care agents into `TELCO_AGENTS`. Agency retains all other business
agents. Put `reflector.entity_reflector` in `KERNEL_AGENTS` inside
`kernel_assets.py`; `active_agents(runtime)` returns a read-only merge of
kernel and active-pack identities while `runtime.pack.agents` remains business
content only.

Telco authority contains the current rows for:

```python
TELCO_AUTHORITY_ROLES = {
    "cs_specialist",
    "cs_manager",
    "cs_account_director",
    "cs_director",
    "delivery_lead",
}
```

Agency authority retains all current rows except the four `cs_*` rows.
`delivery_lead` is intentionally present in both isolated packs because both
packs use that role and only one mapping is active in a process.

Create `verticals/telco/policies/tools.yaml` with exactly:

```yaml
tools:
  - id: customer_care_policy_lookup
    reversible: true
    requires_capability: null
    requires_authority: false
    value_field: null
    scope_function: customer-success
    description: Resolve governed Telco care entitlement.
  - id: customer_care_prepare_notification
    reversible: true
    requires_capability: null
    requires_authority: false
    value_field: null
    scope_function: customer-success
    description: Prepare a restoration notification without sending it.
  - id: customer_care_prepare_credit
    reversible: true
    requires_capability: null
    requires_authority: false
    value_field: null
    scope_function: customer-success
    description: Prepare a governed credit for world validation.
```

Agency points `policy_sources` at the existing Agency tool/dream-pass policy
files. Telco points only at its policy file. Change the governance manifest
loader to merge the active pack's declared files and reject duplicate tool IDs.

- [ ] **Step 7: Replace compatibility modules**

Each compatibility module re-exports types and the active mapping:

```python
# api/shared/domains.py
from api.shared.domain_contracts import (
    Domain,
    HitlGate,
    Phase,
    PhaseKind,
    RegionOverlay,
    WakeHint,
)
from api.shared.vertical_loader import active_runtime

DOMAINS = active_runtime().pack.domains


def live_domains() -> tuple[Domain, ...]:
    return tuple(domain for domain in DOMAINS.values() if not domain.stub)
```

Apply the same pattern to `FUNCTIONS`, `AGENTS`, and `AUTHORITY`.
`api/shared/verticals.py` returns an Agency profile when unset and derives all
fields from `active_runtime()`.

Wire function ownership while building each pack:

```python
def wire_domain_functions(domains, functions):
    owner_by_domain = {
        workflow_type: function.name
        for function in functions.values()
        for workflow_type in function.owns_domains
    }
    return {
        workflow_type: replace(
            domain,
            function=owner_by_domain[workflow_type],
        )
        for workflow_type, domain in domains.items()
    }
```

- [ ] **Step 8: Complete each manifest with lazy providers**

World builders and projections must be active-pack-only without making the
manifest import server-heavy modules. Use wrappers:

```python
def lazy_projection(module_name: str) -> ProjectionFn:
    def project(workflow: Workflow):
        module = import_module(module_name)
        return module.project(workflow)
    return project


TELCO_PROJECTIONS = {
    "network-incident": lazy_projection(
        "api.server.services.entity_projections.network_incident"
    ),
    "proactive-customer-care": lazy_projection(
        "api.server.services.entity_projections.proactive_customer_care"
    ),
    "order-to-activate": lazy_projection(
        "api.server.services.entity_projections.order_to_activate"
    ),
}
```

Agency maps every existing projection except those three. World scenario
builders import `SupportScenario` or `NetworkScenario` inside their
`build_scenario` callback. Lifecycle and seed callbacks import their owning
pack modules only when FastAPI invokes them. Durable callbacks import
`verticals.<name>.durable` only when Functions invokes them.

Populate `memory_workflow_types`, recording roots, UI metadata, skill roots,
MCP modules, personae roots, external capabilities, ramp types, and default
world exactly as specified by the design.

Agency's explicitly external skill capabilities are:

```python
AGENCY_EXTERNAL_CAPABILITIES = frozenset({
    "acs_dial",
    "betrvg_check",
    "comp_band_lookup",
    "d365.parseInvoice",
    "eeo_check",
    "finance_bp_card_compose",
    "graph_calendar",
    "graph_invite",
    "graph_mail",
    "greenhouse_post",
    "jd_library_search",
    "linkedin_profile_fetch",
    "linkedin_search",
    "offer_template_fetch",
    "payment.reconcileStatement",
    "propose_skill_amplification",
    "scoring_rubric_load",
    "servicenow_jml",
    "transcript_score",
    "workday.getExpenseClaim",
    "workday.getVendor",
    "workday_position",
})
```

Repeated references in multiple skills still produce one declared capability.
Telco has no external skill capability because all three care operations are
registered by its `customer_care` MCP module.

- [ ] **Step 9: Make governance consume active mappings**

Replace direct all-registry imports in governance with active compatibility
views. Assert unknown inactive agent IDs are denied under enforcement:

```python
assert "proactive-customer-care-entitlement" not in agency.pack.agents
assert "rag-classifier" not in telco.pack.agents
assert "claim.lookup" not in load_tool_manifest(telco).tools
```

- [ ] **Step 10: Run registry suites**

Run:

```bash
PORTAL_DATA_DIR="$(mktemp -d)" .venv/bin/pytest \
  tests/api/shared/test_verticals.py \
  tests/api/shared/test_vertical_pack_inventory.py \
  tests/api/shared/test_domains_registry.py \
  tests/api/shared/test_functions_registry.py \
  tests/api/shared/test_functions_validators.py \
  tests/api/shared/test_authority.py \
  tests/api/server/services/governance \
  tests/api/functions/workflows/test_proactive_customer_care.py \
  tests/api/server/services/test_world_bridge_proactive_care_integration.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add \
  api/shared \
  api/server/services/governance \
  api/server/skills \
  api/server/mcp_tools \
  api/server/personae \
  api/functions/graphs/executors/agents \
  data/blueprint-recordings \
  verticals \
  tests/api/shared \
  tests/api/functions/workflows/test_proactive_customer_care.py \
  tests/api/server/services/governance \
  tests/api/server/services/test_world_bridge_proactive_care_integration.py
git commit -m "feat(verticals): isolate business registries" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Register only active-pack Durable Functions

**Files:**
- Create: `verticals/agency/durable.py`
- Create: `verticals/telco/durable.py`
- Create: `api/functions/kernel_registration.py`
- Modify: `function_app.py`
- Create: `tests/api/functions/test_vertical_function_registration.py`
- Modify: `tests/api/shared/test_domains_registry.py`
- Modify: `tests/api/unit/test_segment_validators_serializable.py`
- Modify: `tests/api/unit/test_hiring_segment_{b,d,e,f}.py`

- [ ] **Step 1: Add subprocess indexing tests**

Create a helper that imports `function_app` with one vertical and inspects
`function_app.app.get_functions()`:

```python
INDEX_SCRIPT = """
import json
import function_app
names = sorted(
    function.get_function_name()
    for function in function_app.app.get_functions()
)
print(json.dumps(names))
"""

TELCO_FUNCTIONS = {
    "NetworkIncidentOrchestrator",
    "ProactiveCustomerCareOrchestrator",
    "OrderToActivateOrchestrator",
    "network_incident_impact_activity_trigger",
    "network_incident_reroute_activity_trigger",
    "customer_care_impact_activity_trigger",
    "customer_care_entitlement_activity_trigger",
    "customer_care_execution_activity_trigger",
    "order_activation_feasibility_activity_trigger",
    "order_activation_prepare_activity_trigger",
}
```

Assert Telco contains those names plus kernel health/starter functions and no
`ExpenseClaimOrchestrator` or `HiringOrchestrator`. Assert Agency contains its
current registrations and none of the Telco set.

- [ ] **Step 2: Convert decorators into pack registrars**

In each pack module, keep trigger functions at module scope and decorate them
inside `register(app)`:

```python
def register(app: df.DFApp) -> None:
    app.orchestration_trigger(context_name="context")(
        NetworkIncidentOrchestrator
    )
    app.activity_trigger(input_name="payload")(
        network_incident_impact_activity_trigger
    )
```

Populate `DurableFunctionRegistration.orchestrators` and `.activities` from
the exact registered names.

- [ ] **Step 3: Reduce `function_app.py` to composition**

Keep telemetry/governance initialization and the one `DFApp`, then register:

```python
runtime = active_runtime()
app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)
register_kernel_functions(app, runtime)
runtime.pack.durable_functions.register(app)
```

Do not import any Agency or Telco workflow module directly from
`function_app.py`.

- [ ] **Step 4: Point unit tests at owning modules**

Replace imports such as:

```python
from function_app import validate_segment_f_output_activity_trigger
```

with:

```python
from verticals.agency.durable import (
    validate_segment_f_output_activity_trigger,
)
```

Update the domain registration test to inspect
`runtime.pack.durable_functions.orchestrators` rather than parsing
`function_app.py` text.

- [ ] **Step 5: Run function registration and workflow tests**

Run:

```bash
ENTITY_PLANE_ENABLED=0 PORTAL_DATA_DIR="$(mktemp -d)" .venv/bin/pytest \
  tests/api/functions/test_vertical_function_registration.py \
  tests/api/unit/test_segment_validators_serializable.py \
  tests/api/unit/test_hiring_segment_b.py \
  tests/api/unit/test_hiring_segment_d.py \
  tests/api/unit/test_hiring_segment_e.py \
  tests/api/unit/test_hiring_segment_f.py \
  tests/api/functions/workflows/test_network_incident.py \
  tests/api/functions/workflows/test_proactive_customer_care.py \
  tests/api/functions/workflows/test_order_to_activate.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add function_app.py api/functions/kernel_registration.py verticals \
  tests/api/functions tests/api/unit tests/api/shared/test_domains_registry.py
git commit -m "refactor(functions): register active vertical" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Build FastAPI state from the active runtime

**Files:**
- Create: `api/server/runtime_context.py`
- Create: `api/server/routes/runtime.py`
- Modify: `api/server/state.py`
- Modify: `api/server/main.py`
- Modify: `api/server/services/simulator_orchestrator.py`
- Modify: `api/server/services/lessons/mem0_store.py`
- Modify: `api/server/services/story_pack.py`
- Modify: `api/server/services/ambient_agents/story_pack_writer.py`
- Modify: `api/server/routes/story_pack.py`
- Modify: `api/server/services/kpi_history.py`
- Modify: `api/server/eval/store.py`
- Modify: `api/server/routes/portal.py`
- Modify: `api/functions/graphs/executors/agents/agent_onboarding.py`
- Modify: `verticals/{agency,telco}/lifecycle.py`
- Create: `tests/api/server/routes/test_runtime_manifest.py`
- Modify: `tests/api/server/test_main_verticals.py`
- Modify: `tests/api/server/services/test_simulator_ramp_verticals.py`

- [ ] **Step 1: Add runtime-manifest route tests**

```python
def test_runtime_manifest_defaults_to_agency(client):
    response = client.get("/api/runtime")

    assert response.status_code == 200
    assert response.json()["vertical"] == {
        "name": "agency",
        "display_name": "Agency",
        "manifest_version": "1",
        "fingerprint": "agency:1",
    }
    assert response.json()["world"] is None
    assert response.json()["world_scale"] is None
    assert "telco-network" not in response.json()["ui"]["lenses"]
```

Add the Telco subprocess/client variant and assert world `telco`.

- [ ] **Step 2: Pass runtime into `AppState`**

Change construction to:

```python
class AppState:
    def __init__(self, runtime: VerticalRuntime | None = None) -> None:
        self.runtime = runtime or active_runtime()
        self.data_dir = self.runtime.data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
```

Replace `_PORTAL_DATA_DIR` uses with `self.data_dir`. Treat
`PORTAL_DATA_DIR` as a root alias in `resolve_data_root`; do not use it
directly in state.

Change `build_default_memory` to accept `data_dir: Path` and default Chroma to
`data_dir / "mem0" / "chroma"` unless `MEM0_CHROMA_DIR` is explicitly set.
Resolve Agency welcome videos from
`active_runtime().data_dir / "welcome-videos"` in both the portal route and
onboarding agent. No runtime writer may retain a literal `data/portal` path.
Resolve story snapshots from `active_runtime().data_dir / "snapshots"` in the
service, writer, and route; remove the three `Path("data/snapshots")`
defaults.
Point KPI history at `self.data_dir / "kpi_history.sqlite"` before the Agency
recorder starts. Make `eval.default_store()` construct
`EvalStore(str(active_runtime().data_dir / "eval" / "store.sqlite"))`.

- [ ] **Step 3: Delegate seeding and lifecycle**

Replace unconditional fixture bootstrap with:

```python
self.runtime.pack.seed.bootstrap(self)
```

In FastAPI lifespan:

```python
pack_stop_actions = list(
    await app_state.runtime.pack.lifecycle.start(app_state)
)
try:
    yield
finally:
    for stop in reversed(pack_stop_actions):
        result = stop()
        if inspect.isawaitable(result):
            await result
```

Lifecycle ownership is:

| Hook | Agency | Telco |
|---|---:|---:|
| Fleet Manager and function FMs | yes | no |
| ambient dispatcher and Agency watchers | yes | no |
| story-pack, KPI-history, dream cadence | yes | no |
| portal orchestration | yes | no |
| compose MCP session manager | yes | no |
| persona responder | yes | yes |
| Blueprint recorder/demo stream | yes | yes |
| replay player and online evaluator | kernel | kernel |
| actor-world service/bridge | selected world startup | selected world startup |

Every module-level `start()` in the current lifespan moves to the owning
lifecycle or remains in the stated kernel section. Teardown actions are
registered immediately after successful start so partial startup unwinds only
what actually started.

- [ ] **Step 4: Make ramp selection pack-owned**

Remove `_WORLD_OWNED_RAMP_TYPES` and profile re-parsing. With no explicit CSV:

```python
requested = runtime.pack.ramp_workflow_types
```

With `SIMULATOR_RAMP_DOMAINS`, reject every workflow type not present in
`runtime.pack.domains`; do not silently schedule an Agency domain under Telco.

- [ ] **Step 5: Make world startup use `runtime.world_name`**

Delete `main.py` environment parsing and string branches:

```python
runtime = app_state.runtime
if runtime.world_name is not None:
    world_service = ActorWorldService.for_runtime(
        runtime,
        seed=int(os.getenv("WORLD_SEED", "42")),
        bus=app_state.bus,
        scale_name=runtime.world_scale_name,
        speed=float(os.getenv("WORLD_MINUTES_PER_SECOND", "10")),
    )
```

- [ ] **Step 6: Run startup, data-root, and ramp tests**

Run:

```bash
PORTAL_DATA_DIR="$(mktemp -d)" .venv/bin/pytest \
  tests/api/server/routes/test_runtime_manifest.py \
  tests/api/server/test_main_verticals.py \
  tests/api/server/services/test_simulator_ramp_verticals.py \
  tests/api/server/test_function_fms_smoke.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add \
  api/server/runtime_context.py \
  api/server/routes/runtime.py \
  api/server/state.py \
  api/server/main.py \
  api/server/services/simulator_orchestrator.py \
  api/server/services/lessons/mem0_store.py \
  api/server/services/story_pack.py \
  api/server/services/ambient_agents/story_pack_writer.py \
  api/server/routes/story_pack.py \
  api/server/services/kpi_history.py \
  api/server/eval/store.py \
  api/server/routes/portal.py \
  api/functions/graphs/executors/agents/agent_onboarding.py \
  api/shared/vertical_loader.py \
  verticals/agency/lifecycle.py \
  verticals/telco/lifecycle.py \
  tests/api/server/routes/test_runtime_manifest.py \
  tests/api/server/test_main_verticals.py \
  tests/api/server/services/test_simulator_ramp_verticals.py \
  tests/api/server/test_function_fms_smoke.py
git commit -m "refactor(server): bootstrap active pack" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Isolate worlds, responders, projections, and memory

**Files:**
- Modify: `verticals/agency/worlds.py`
- Modify: `verticals/telco/worlds.py`
- Modify: `verticals/agency/projections.py`
- Modify: `verticals/telco/projections.py`
- Move: `api/server/world/packs/telco.py` to `verticals/telco/world.py`
- Move: `api/server/services/entity_projections/{network_incident,proactive_customer_care,order_to_activate}.py` to `verticals/telco/entity_projections/`
- Modify: `api/server/world/registry.py`
- Modify: `api/server/world/service.py`
- Modify: `api/server/services/world_responders.py`
- Modify: `api/server/services/entity_projections/__init__.py`
- Modify: `api/server/services/entity_reflector.py`
- Modify: `api/server/services/policy_application.py`
- Modify: `api/server/data_fabric/pack.py`
- Modify: `api/server/services/memory/domain_memory.py`
- Modify: `tests/api/world/actor/test_world_registry.py`
- Modify: `tests/api/server/services/test_world_responders.py`
- Modify: `tests/api/server/services/test_entity_projections_registry.py`
- Modify: `tests/api/server/services/memory/test_domain_memory.py`

- [ ] **Step 1: Write isolation tests first**

```python
def test_agency_projection_registry_has_no_telco(tmp_path):
    runtime = build_runtime({}, data_root=tmp_path)
    assert {
        "network-incident",
        "proactive-customer-care",
        "order-to-activate",
    }.isdisjoint(runtime.pack.projections)


def test_telco_projection_registry_is_exact(tmp_path):
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"}, data_root=tmp_path
    )
    assert set(runtime.pack.projections) == {
        "network-incident",
        "proactive-customer-care",
        "order-to-activate",
    }
```

Add equivalent assertions for world responders and memory workflow types.

- [ ] **Step 2: Move world registrations into pack modules**

Agency `worlds.py` owns only the existing support registration. Telco
`worlds.py` owns only the existing Telco registration and its three objective
routes. Wrap each existing fixed scenario as its compatibility `demo` scale:

```python
WorldPackRegistration(
    name="telco",
    scales={
        "demo": WorldScaleProfile(
            name="demo",
            build_scenario=build_telco_demo,
            default_minutes_per_second=10.0,
        ),
    },
    default_scale="demo",
    objective_routes=TELCO_OBJECTIVE_ROUTES,
    responders=TELCO_RESPONDERS,
)
```

Move the Telco scenario implementation to `verticals/telco/world.py` and update
`api/server/world/projection.py` plus the four Telco actor-world tests to import
that canonical path. Do not leave a second implementation under
`api/server/world/packs/`.

Change resolver signatures:

```python
def resolve_world_pack(
    runtime: VerticalRuntime,
    name: str,
) -> WorldPackRegistration:
    try:
        return runtime.pack.worlds[name]
    except KeyError as exc:
        raise ValueError(
            f"world {name!r} is not owned by vertical {runtime.pack.name!r}"
        ) from exc
```

Put support and Telco responder mappings next to their world registrations;
`world_responders.resolve_responder(runtime, objective_type)` reads the active
mapping only.

- [ ] **Step 3: Replace projection auto-import**

Keep projection helper types in
`api/server/services/entity_projections/__init__.py`, but remove every
bottom-of-file domain import. Each pack imports and maps its projection
functions explicitly:

Move the three Telco projection implementations to
`verticals/telco/entity_projections/` and update their focused tests to import
the new canonical paths.

```python
TELCO_PROJECTIONS = MappingProxyType({
    "network-incident": network_incident.project,
    "proactive-customer-care": proactive_customer_care.project,
    "order-to-activate": order_to_activate.project,
})
```

Inject `runtime.pack.projections` into `EntityReflector`,
`policy_application`, and `data_fabric.pack`.

- [ ] **Step 4: Make memory domain selection explicit**

Replace `configured_memory_domains(... vertical_name=...)` with:

```python
def configured_memory_domains(
    *,
    raw: str | None,
    allowed: Collection[str],
) -> list[str]:
    if raw is None or not raw.strip():
        return sorted(allowed)
    requested = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = sorted(set(requested) - set(allowed))
    if unknown:
        raise ValueError(f"memory domains not in active pack: {unknown}")
    return requested
```

Telco memory IDs are the three Telco workflow types. Agency receives its
existing configured set intersected with Agency domains.

- [ ] **Step 5: Run world/projection/memory tests**

Run:

```bash
PORTAL_DATA_DIR="$(mktemp -d)" .venv/bin/pytest \
  tests/api/world/actor/test_world_registry.py \
  tests/api/server/services/test_world_responders.py \
  tests/api/server/services/test_entity_projections_registry.py \
  tests/api/server/services/entity_projections \
  tests/api/server/services/memory \
  tests/api/server/services/test_world_bridge_network_incident_integration.py \
  tests/api/server/services/test_world_bridge_proactive_care_integration.py \
  tests/api/server/services/test_world_bridge_order_integration.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add \
  api/server/world \
  api/server/services/world_responders.py \
  api/server/services/entity_projections \
  api/server/services/entity_reflector.py \
  api/server/services/policy_application.py \
  api/server/data_fabric/pack.py \
  api/server/services/memory/domain_memory.py \
  verticals/agency/worlds.py \
  verticals/telco/worlds.py \
  verticals/agency/projections.py \
  verticals/telco/projections.py \
  verticals/telco/world.py \
  verticals/telco/entity_projections \
  tests/api/world/actor \
  tests/api/server/services/test_world_responders.py \
  tests/api/server/services/test_entity_projections_registry.py \
  tests/api/server/services/entity_projections \
  tests/api/server/services/memory \
  tests/api/server/services/test_world_bridge_network_incident_integration.py \
  tests/api/server/services/test_world_bridge_proactive_care_integration.py \
  tests/api/server/services/test_world_bridge_order_integration.py
git commit -m "refactor(verticals): isolate runtime assets" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 7: Isolate skills, MCP inventory, personae, and Blueprint composition

**Files:**
- Modify: `verticals/{agency,telco}/manifest.py`
- Modify: `api/server/services/blueprint_inventory.py`
- Create: `tests/api/server/services/test_blueprint_pack_isolation.py`

- [ ] **Step 1: Add exact inventory tests**

```python
def test_telco_blueprint_inventory_is_pack_local(telco_runtime):
    tree = composition_tree(telco_runtime)

    assert {domain["workflow_type"] for domain in tree["domains"]} == {
        "network-incident",
        "proactive-customer-care",
        "order-to-activate",
    }
    assert {skill["name"] for skill in tree["skills"]} == {
        "proactive-customer-care-entitlement",
        "proactive-customer-care-execution",
    }
    assert {mcp["name"] for mcp in tree["mcps"]} == {"customer_care"}
    assert tree["meta_skills"] == []
    assert all(domain["status"] == "live" for domain in tree["domains"])
```

Agency asserts all three Telco collections are absent and retains Onboarding,
Procurement, Legal, IT, and meta-skills.

- [ ] **Step 2: Make Blueprint entirely runtime-driven**

Remove module-level `DOMAINS`, `SKILLS_DIR`, `MCP_TOOLS_DIR`,
`_PHASE_ALIASES`, and hard-coded aspirational entries.

Change loaders:

```python
def _load_skills(runtime: VerticalRuntime) -> list[Skill]:
    return load_skills_from_roots(runtime.pack.skill_roots)


def _load_mcp_tools(runtime: VerticalRuntime) -> list[McpTool]:
    return load_mcp_modules(runtime.pack.mcp_modules)


def composition_tree(
    runtime: VerticalRuntime | None = None,
) -> dict[str, Any]:
    runtime = runtime or active_runtime()
```

Add `vertical` metadata to the response. Agency `ui.json` owns phase aliases,
Onboarding, aspirational rings, and meta-skill visibility. Telco `ui.json`
contains no Agency-only rings.

- [ ] **Step 3: Run Blueprint tests**

Run:

```bash
PORTAL_DATA_DIR="$(mktemp -d)" .venv/bin/pytest \
  tests/api/server/services/test_blueprint_inventory_verticals.py \
  tests/api/server/services/test_blueprint_pack_isolation.py \
  tests/api/server/services/governance/test_permission_handler.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add \
  api/server/services/blueprint_inventory.py \
  verticals/agency/manifest.py \
  verticals/telco/manifest.py \
  tests/api/server/services/test_blueprint_inventory_verticals.py \
  tests/api/server/services/test_blueprint_pack_isolation.py \
  tests/api/server/services/governance/test_permission_handler.py
git commit -m "refactor(blueprint): scope vertical assets" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 8: Scope curated and runtime recordings

**Files:**
- Modify: `api/server/services/blueprint_recorder.py`
- Modify: `api/server/routes/blueprint.py`
- Create: `tests/api/server/services/test_recording_pack_isolation.py`
- Modify: `tests/api/server/services/test_blueprint_recorder.py`

- [ ] **Step 1: Write recording-root and filtering tests**

```python
def test_telco_loader_reads_only_telco_recordings(telco_runtime):
    templates = load_recorded_templates(telco_runtime)
    assert {template["workflow_type"] for template in templates} == {
        "network-incident",
        "proactive-customer-care",
        "order-to-activate",
    }


def test_foreign_override_recording_is_rejected(
    monkeypatch, tmp_path, telco_runtime
):
    monkeypatch.setenv("BLUEPRINT_RECORDINGS_DIR", str(tmp_path))
    write_recording(tmp_path / "hiring.jsonl", workflow_type="hiring")

    with pytest.raises(ValueError, match="not in active vertical 'telco'"):
        load_recorded_templates(telco_runtime)
```

- [ ] **Step 2: Separate curated reads from runtime writes**

Implement:

```python
def runtime_recordings_dir(runtime: VerticalRuntime) -> Path:
    override = os.getenv("BLUEPRINT_RECORDINGS_DIR")
    return (
        Path(override).expanduser()
        if override
        else runtime.data_dir / "blueprint-recordings"
    )


def recording_read_dirs(runtime: VerticalRuntime) -> tuple[Path, ...]:
    return (
        *runtime.pack.recordings.curated_dirs,
        runtime_recordings_dir(runtime),
    )
```

The recorder writes only to `runtime_recordings_dir`. Playback reads both
sources, validates each workflow type against `runtime.pack.domains`, and
deduplicates by filename plus workflow ID.

- [ ] **Step 3: Inject runtime into Blueprint replay**

`BlueprintRecorder` receives `VerticalRuntime` in its constructor.
`load_recorded_templates(runtime)` is called with `app_state.runtime`; there is
no parameterless global directory resolver.

- [ ] **Step 4: Run recording and stream tests**

Run:

```bash
PORTAL_DATA_DIR="$(mktemp -d)" .venv/bin/pytest \
  tests/api/server/services/test_blueprint_recorder.py \
  tests/api/server/services/test_recording_pack_isolation.py \
  tests/api/server/services/test_blueprint_inventory_verticals.py -q
```

Expected: all selected Blueprint recorder/route tests PASS.

- [ ] **Step 5: Commit**

```bash
git add \
  api/server/services/blueprint_recorder.py \
  api/server/routes/blueprint.py \
  tests/api/server/services/test_blueprint_recorder.py \
  tests/api/server/services/test_recording_pack_isolation.py
git commit -m "refactor(recordings): partition vertical replay" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 9: Drive navigation and Blueprint identity from the runtime manifest

**Files:**
- Create: `web/shared/runtime.ts`
- Create: `web/client/hooks/useRuntimeManifest.ts`
- Create: `web/client/hooks/__tests__/useRuntimeManifest.test.tsx`
- Create: `web/client/components/feed/__tests__/LeftRail.vertical.test.tsx`
- Modify: `web/client/components/feed/LeftRail.tsx`
- Move: `web/client/routes/World.tsx` to `web/client/routes/SupportWorld.tsx`
- Create: `web/client/routes/World.tsx`
- Create: `web/client/routes/TelcoWorldRoute.tsx`
- Modify: `web/blueprint/src/lib/types.ts`
- Modify: `web/blueprint/src/sections/Composition.tsx`
- Modify: `web/blueprint/src/pages/ConstellationPage.tsx`

- [ ] **Step 1: Define the shared frontend type**

```typescript
export interface RuntimeManifest {
  vertical: {
    name: string;
    display_name: string;
    manifest_version: string;
    fingerprint: string;
  };
  world: string | null;
  world_scale: string | null;
  capabilities: string[];
  ui: {
    lenses: string[];
    theme: Record<string, string>;
  };
  readiness: {
    functions: "ready" | "unavailable" | "mismatch";
    scheduling_enabled: boolean;
  };
}
```

- [ ] **Step 2: Write hook tests**

Test success, non-200, and abort-on-unmount:

```typescript
it("loads the active vertical once", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
    new Response(JSON.stringify(agencyManifest), { status: 200 }),
  ));
  const { result } = renderHook(() => useRuntimeManifest());
  await waitFor(() => expect(result.current.manifest).toEqual(agencyManifest));
  expect(fetch).toHaveBeenCalledWith("/api/runtime", expect.any(Object));
});
```

Surface fetch errors; do not synthesize a successful Agency manifest.

- [ ] **Step 3: Gate navigation by capabilities**

`LeftRail` renders:

- `world` only for capability `world`
- `memory` only for `memory`
- `knowledge` only for `knowledge`
- `compose` only for `compose`
- Constellation only for `blueprint`

The label next to the saved views identifies the active vertical. Keep
`VITE_BLUEPRINT_URL` solely for host routing; never use it for vertical
selection.

- [ ] **Step 4: Make world rendering manifest-driven**

Move the current `World.tsx` implementation to `SupportWorld.tsx`, rename its
default function `SupportWorld`, and remove the `TelcoWorld` import plus the
`state?.scenario === "telco"` branch.

Create `TelcoWorldRoute.tsx`:

```typescript
import TelcoWorld from "@client/routes/TelcoWorld";
import { useWorldSimulation } from "@client/hooks/useWorldSimulation";

export default function TelcoWorldRoute() {
  const simulation = useWorldSimulation();
  return (
    <TelcoWorld
      state={simulation.state}
      events={simulation.events}
      loading={simulation.loading}
      error={simulation.error}
      onFailSite={simulation.injectSiteFailure}
    />
  );
}
```

Create the new `World.tsx`; it loads the manifest before mounting either child,
so it never polls `/api/world/state` when no world is active:

```typescript
import SupportWorld from "@client/routes/SupportWorld";
import TelcoWorldRoute from "@client/routes/TelcoWorldRoute";
import { useRuntimeManifest } from "@client/hooks/useRuntimeManifest";

export default function World() {
  const { manifest, loading, error } = useRuntimeManifest();
  if (loading) return <div role="status">Loading runtime…</div>;
  if (error || !manifest) {
    return <div role="alert">{error ?? "Runtime unavailable"}</div>;
  }
  if (manifest.world === null) {
    return (
      <div role="status">
        No actor world is active for {manifest.vertical.display_name}.
      </div>
    );
  }
  return manifest.ui.lenses.includes("telco-network")
    ? <TelcoWorldRoute />
    : <SupportWorld />;
}
```

- [ ] **Step 5: Add vertical identity to Blueprint**

Extend `CompositionTree` with the `vertical` object. Render the active display
name in Composition and Constellation headers. Assert a Telco composition has
no Agency-only domain labels.

- [ ] **Step 6: Run focused Vitest and builds**

Run:

```bash
npx vitest run \
  web/client/hooks/__tests__/useRuntimeManifest.test.tsx \
  web/client/components/feed/__tests__/LeftRail.vertical.test.tsx \
  web/client/components/feed/__tests__/LeftRail.test.tsx \
  web/client/routes/__tests__/World.test.tsx \
  web/client/routes/__tests__/TelcoWorld.test.tsx
npm run build:blueprint
```

Expected: Vitest PASS and Blueprint build succeeds.

- [ ] **Step 7: Commit**

```bash
git add web
git commit -m "feat(ui): render active vertical manifest" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 10: Enforce API and Functions vertical agreement

**Files:**
- Modify: `api/functions/kernel_registration.py`
- Modify: `api/server/services/durable_client.py`
- Modify: `api/server/routes/runtime.py`
- Modify: `api/server/main.py`
- Create: `tests/api/server/services/test_vertical_readiness.py`
- Modify: `tests/api/functions/test_vertical_function_registration.py`

- [ ] **Step 1: Add readiness tests**

```python
@pytest.mark.asyncio
async def test_matching_functions_host_enables_scheduling(respx_mock, runtime):
    respx_mock.get(f"{FUNCTIONS_HOST}/api/runtime/vertical").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": runtime.pack.name,
                "fingerprint": runtime.fingerprint,
                "orchestrators": sorted(
                    runtime.pack.durable_functions.orchestrators
                ),
            },
        )
    )

    result = await probe_functions_vertical(runtime)

    assert result.status == "ready"
    assert result.scheduling_enabled is True


@pytest.mark.asyncio
async def test_mismatch_blocks_scheduling(respx_mock, agency_runtime):
    respx_mock.get(f"{FUNCTIONS_HOST}/api/runtime/vertical").mock(
        return_value=httpx.Response(
            200,
            json={"name": "telco", "fingerprint": "telco:1"},
        )
    )

    result = await probe_functions_vertical(agency_runtime)

    assert result.status == "mismatch"
    assert result.scheduling_enabled is False
```

Also test connection failure returns `unavailable` without raising FastAPI
startup.

- [ ] **Step 2: Register the Functions health endpoint**

Kernel registration adds:

```python
def vertical_health(_request: func.HttpRequest) -> func.HttpResponse:
    runtime = active_runtime()
    return func.HttpResponse(
        json.dumps({
            "name": runtime.pack.name,
            "manifest_version": runtime.pack.manifest_version,
            "fingerprint": runtime.fingerprint,
            "orchestrators": sorted(
                runtime.pack.durable_functions.orchestrators
            ),
        }),
        mimetype="application/json",
    )
```

Register it at `GET /api/runtime/vertical`.

- [ ] **Step 3: Probe and cache readiness**

Add a typed `FunctionsReadiness` object in `durable_client.py`. Probe at
FastAPI lifespan startup and before the first schedule after an unavailable
probe. Do not cache failure forever.

Before scheduling:

```python
readiness = await ensure_functions_ready(app_state.runtime)
if not readiness.scheduling_enabled:
    raise RuntimeError(readiness.message)
```

Do not start the world bridge until readiness is `ready`. Replay mode bypasses
the Functions probe but validates tape vertical metadata.

- [ ] **Step 4: Expose readiness in `/api/runtime`**

Return `ready`, `unavailable`, or `mismatch` plus both fingerprints on mismatch.
Never report scheduling enabled when the probe failed.

- [ ] **Step 5: Run readiness and startup tests**

Run:

```bash
PORTAL_DATA_DIR="$(mktemp -d)" .venv/bin/pytest \
  tests/api/server/services/test_vertical_readiness.py \
  tests/api/server/routes/test_runtime_manifest.py \
  tests/api/server/test_main_verticals.py \
  tests/api/functions/test_vertical_function_registration.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/functions api/server tests/api
git commit -m "feat(verticals): enforce host agreement" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 11: Target composition and remove global fallbacks

**Files:**
- Modify: `api/server/services/compose/tape.py`
- Modify: `docs/superpowers/skills/compose-domain/sub-skills/author-function-membership/validator.py`
- Modify: `docs/superpowers/skills/compose-domain/sub-skills/author-decision-mapping/validator.py`
- Modify: `docs/superpowers/skills/compose-domain/sub-skills/author-ambient-trigger/codegen.py`
- Modify: `docs/superpowers/skills/compose-domain/SKILL.md`
- Modify: `docs/superpowers/skills/compose-domain/CHECKLIST.md`
- Modify: related tests under `tests/docs/superpowers/skills/compose_domain/`
- Modify: `README.md`
- Modify: `docs/ADD-A-DOMAIN.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/superpowers/specs/2026-07-10-organisational-world-simulator-design.md`
- Delete obsolete all-vertical registry/scanning code after `rg` verification

- [ ] **Step 1: Add compose-target tests**

Add tests proving:

```python
assert resolve_compose_target(None).name == "agency"
assert resolve_compose_target("telco").name == "telco"
with pytest.raises(ValueError, match="unknown vertical"):
    resolve_compose_target("mystery")
```

The generated output map must use:

```python
{
    "domain": target.root / "domains.py",
    "skills": target.root / "skills",
    "personae": target.root / "personae",
    "mcp_tools": target.root / "mcp_tools",
}
```

- [ ] **Step 2: Pass vertical explicitly through compose**

Add `vertical: str = "agency"` to compose session/request state and tape
metadata. Replay rejects a tape whose vertical differs from the active runtime.
Change compose tape storage to:

```python
def _dir(runtime: VerticalRuntime | None = None) -> Path:
    active = runtime or active_runtime()
    return active.data_dir / "compose-recordings"
```

Pass the selected pack's organisational functions and persona roots into the
function-membership and decision-mapping validators. Remove
`FUNCTIONS_PLACEHOLDER`; a validator that cannot resolve the selected pack
raises a `SchemaError` instead of validating against a stale global list.

Change ambient-trigger code generation from the fixed
`api/server/services/ambient_agents` directory to
`target.root / "ambient_agents"`. Update `SKILL.md` and `CHECKLIST.md` so every
compose invocation names its target vertical, with Agency as the documented
compatibility default.

- [ ] **Step 3: Remove global fallbacks**

Run:

```bash
rg -n "WORLD_PACKS|SKILLS_DIR|MCP_TOOLS_DIR|_PROFILES|api/server/skills" \
  api function_app.py verticals
```

After migration:

- no `WORLD_PACKS` all-vertical dictionary remains
- no Blueprint global skill/MCP root remains
- no `_PROFILES` environment parser remains
- `api/shared/{domains,functions,agents,authority}.py` contain adapters only
- inactive pack modules are absent from the other pack's imports

Keep documentation-only historical references where they describe old paths;
update instructions and active architecture links.

- [ ] **Step 4: Run composition and compatibility tests**

Run:

```bash
PORTAL_DATA_DIR="$(mktemp -d)" .venv/bin/pytest \
  tests/docs/superpowers/skills/compose_domain \
  tests/api/shared \
  tests/api/server/services/test_blueprint_pack_isolation.py \
  tests/api/server/services/test_recording_pack_isolation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api verticals tests docs README.md function_app.py
git commit -m "refactor(verticals): remove global fallbacks" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 12: Prove both verticals and prepare the pull request

**Files:**
- Create: `tools/agency_vertical_e2e_proof.sh`
- Create: `tools/agency_vertical_e2e_proof.mjs`
- Modify: `tools/telco_zava_e2e_proof.sh`
- Modify: `tools/telco_zava_e2e_proof.mjs`
- Modify: `tests/tools/test_telco_zava_e2e_proof.py`
- Create: `tests/tools/test_agency_vertical_e2e_proof.py`

- [ ] **Step 1: Add runtime-isolation assertions to Telco proof**

Before driving workflows, assert:

```javascript
const runtime = await api("/api/runtime");
assert.equal(runtime.vertical.name, "telco");
assert.equal(runtime.world, "telco");
assert.equal(runtime.readiness.functions, "ready");

const composition = await api("/api/blueprint/composition");
assert.deepEqual(
  new Set(composition.domains.map((domain) => domain.workflow_type)),
  new Set([
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
  ]),
);
assert.equal(
  composition.domains.some((domain) => domain.workflow_type === "hiring"),
  false,
);
```

Keep all existing world-evidence, Memory, Knowledge, AG-UI, Constellation,
browser-error, replay-without-Functions, and exact-PID cleanup assertions.

- [ ] **Step 2: Add isolated Agency proof**

Use fresh high ports and a fresh temporary data root. Start Agency with
`ZAVA_VERTICAL=agency`, no `ZAVA_WORLD`, and matching Functions configuration.
Use Azurite `12000-12002`, FastAPI `14101`, Functions `18181`, Control Plane
`16273`, Blueprint `16275`, and `/tmp/zava-agency-proof-$UID`.

The Playwright driver asserts:

- `/api/runtime` reports Agency and no world
- Blueprint contains hiring, expense claim, and the existing Agency catalogue
- no Telco workflow type or Telco lens appears
- the Constellation renders the Agency composition
- no request is made to `/api/world/state` when the world capability is absent
- browser/page/application-network errors are empty

Use exact PID handles and assert every selected port is clear after teardown.

- [ ] **Step 3: Run all focused Python tests**

Run:

```bash
PORTAL_DATA_DIR="$(mktemp -d)" .venv/bin/pytest \
  tests/api/shared \
  tests/api/functions \
  tests/api/server/test_main_verticals.py \
  tests/api/server/routes/test_runtime_manifest.py \
  tests/api/server/services/test_vertical_readiness.py \
  tests/api/server/services/test_blueprint_pack_isolation.py \
  tests/api/server/services/test_recording_pack_isolation.py \
  tests/api/world/actor \
  tests/api/server/services/entity_projections \
  tests/api/server/services/memory \
  tests/tools/test_telco_zava_e2e_proof.py \
  tests/tools/test_agency_vertical_e2e_proof.py -q
```

Expected: all selected tests PASS.

- [ ] **Step 4: Run frontend tests and builds**

Run:

```bash
npx vitest run \
  web/client/hooks/__tests__/useRuntimeManifest.test.tsx \
  web/client/components/feed/__tests__/LeftRail.vertical.test.tsx \
  web/client/components/feed/__tests__/LeftRail.test.tsx \
  web/client/routes/__tests__/World.test.tsx \
  web/client/routes/__tests__/TelcoWorld.test.tsx
npm run build:blueprint
```

Expected: all selected tests PASS and Blueprint production build succeeds.
Run root `npm run build`; compare any failures with the recorded `main`
baseline rather than claiming pre-existing errors are fixed.

- [ ] **Step 5: Run both unmocked proofs**

Run:

```bash
bash tools/agency_vertical_e2e_proof.sh
bash tools/telco_zava_e2e_proof.sh
```

Expected:

- Agency proof exits `0`, renders Agency Constellation, and finds no Telco
  asset.
- Telco live and replay proofs exit `0`; network incident, proactive care,
  normal order, and HITL order complete from world evidence.
- both summaries report `browserErrors: []`.
- all proof ports are clear after each script.

- [ ] **Step 6: Run static checks**

Run:

```bash
.venv/bin/ruff check \
  api/shared/domain_contracts.py \
  api/shared/function_contracts.py \
  api/shared/agent_contracts.py \
  api/shared/authority_contracts.py \
  api/shared/vertical_pack.py \
  api/shared/vertical_loader.py \
  api/server/runtime_context.py \
  api/server/routes/runtime.py \
  verticals
! rg -n \
  'data/portal|data/snapshots|data/\\.eval|data/kpi_history|data/compose-recordings' \
  api/server --glob '*.py'
git diff --check
git status --short
```

Expected: Ruff and diff check succeed; status contains only intentional
vertical-pack changes and proof artifacts remain ignored.

- [ ] **Step 7: Perform final review**

Review the complete diff against
`docs/superpowers/specs/2026-07-16-vertical-pack-architecture-design.md`.
Confirm:

- Agency is the default
- inactive packs are not imported or scanned
- Functions index only active registrations
- worlds, projections, memory, recordings, governance, and UI are isolated
- explicit mismatches block scheduling
- no server or proof process remains running

- [ ] **Step 8: Commit final proof updates**

```bash
git add tools tests docs
git commit -m "test(verticals): prove isolated packs" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

- [ ] **Step 9: Open a pull request**

Push the feature branch only after both proofs pass. Open a pull request with
the architecture spec, this plan, commit sequence, exact verification results,
and the Telco portfolio design listed as follow-on work. Do not push directly
to `main`.
