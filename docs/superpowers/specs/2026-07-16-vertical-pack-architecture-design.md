# Interchangeable Vertical Pack Architecture — Design Specification

**Date:** 2026-07-16  
**Status:** Approved direction; written-spec review pending  
**Scope:** Vertical packaging and Agency/Telco isolation only  
**Follow-on:** A separate Telco portfolio and synthetic-world specification

## 0. Decision

Zava will load exactly one self-contained vertical pack per process. Agency is
the compatibility default. Telco is selected explicitly, except for a
documented legacy inference from `ZAVA_WORLD=telco`.

The platform kernel remains shared. A vertical pack owns the business content
that gives that kernel meaning:

- domains and workflow registrations
- Durable orchestrators and activities
- agents, personae, skills, and MCP capabilities
- world registrations, sensors, commands, and scale profiles
- projections and operational-memory registrations
- Blueprint composition metadata and replay recordings
- Control Plane lens configuration and vertical identity
- immutable seed/demo assets and mutable runtime-data namespace

The loader uses a static in-repository registry. It does not scan installed
packages, Python entry points, or arbitrary directories. Only the selected
pack is imported.

## 1. Problem

Agency content still exists, but the runtime currently composes globally:

- `api/shared/domains.py` exposes every domain through one `DOMAINS` mapping.
- `api/shared/agents.py` exposes every machine agent through one `AGENTS`
  mapping.
- `function_app.py` imports and decorates Agency and Telco functions together.
- `api/server/world/registry.py` registers support and Telco worlds together.
- Blueprint filters domains but scans every skill and MCP module on disk.
- Blueprint playback reads every JSONL recording from one directory.
- startup modules wire Agency-specific watchers regardless of active vertical.

Consequently, an Agency deployment can show Telco domains, events, recordings,
agents, or tools. More filtering on top of the same global registries would
hide symptoms while preserving the source of the contamination.

## 2. Goals

1. Preserve the established Agency article/demo as the default experience.
2. Make Agency and Telco mutually isolated at boot, runtime, storage, replay,
   Functions indexing, and UI composition.
3. Give future verticals one explicit, testable package contract.
4. Keep governance, workflow/event contracts, StateStore, Durable ingestion,
   graph/memory primitives, AG-UI, Blueprint protocols, and reusable renderers
   in the shared kernel.
5. Keep existing import surfaces working during migration without retaining
   global all-vertical registries.
6. Fail early and descriptively for unknown, incomplete, duplicate, or
   cross-wired packs.
7. Avoid speculative plugin infrastructure and avoid a bulk repository
   reorganisation unrelated to vertical isolation.

## 3. Non-goals

This specification does not:

- implement the full Telco process catalogue
- select or implement the first 12–15 expanded Telco workflows
- enlarge the Telco actor world
- permit multiple active verticals in one API or Functions process
- support runtime hot-swapping; changing vertical requires process restart
- define a third-party plugin marketplace or Python package entry points
- allow arbitrary user-authored Python packs
- create a separate frontend build for every vertical
- move every existing shared module into a new physical `kernel/` directory

The Telco portfolio, maturity tiers, and demo/standard/stress simulation are a
dependent follow-on design.

## 4. Architectural invariants

The implementation must preserve these invariants:

1. **One active pack:** every process resolves one immutable
   `VerticalRuntime` before constructing application state.
2. **Agency default:** with both selection variables unset or blank, Agency is
   active and existing default world behaviour is unchanged.
3. **No inactive imports:** normal startup does not import the inactive pack's
   workflow, agent, world, projection, or UI-registration modules.
4. **No global scans:** runtime inventory never scans a directory containing
   assets from more than the active pack.
5. **Explicit kernel assets:** a shared asset is included only through the
   kernel registry, not because it happened to be found on disk.
6. **Pack-local IDs:** duplicate domain, agent, skill, MCP operation, world,
   projection, or function IDs are boot errors.
7. **Cross-process agreement:** FastAPI and Azure Functions expose and compare
   the same vertical fingerprint before live workflow scheduling.
8. **Pack-scoped persistence:** mutable runtime data and newly captured
   recordings are written beneath the active pack's data namespace.
9. **No silent fallback:** an explicit invalid vertical/world combination
   fails startup. It never falls back to Agency or an aggregate world.
10. **Truthful UI:** Control Plane and Blueprint render the active runtime
    manifest; build-time environment variables are not a second source of
    vertical truth.

## 5. Chosen package shape

Vertical content lives in a visible top-level Python package:

```text
verticals/
  __init__.py
  agency/
    __init__.py
    manifest.py
    domains.py
    agents.py
    functions.py
    worlds.py
    projections.py
    memory.py
    personae/
    skills/
    mcp_tools/
    recordings/
    seeds/
    ui.json
  telco/
    __init__.py
    manifest.py
    domains.py
    agents.py
    functions.py
    worlds.py
    projections.py
    memory.py
    personae/
    skills/
    mcp_tools/
    recordings/
    seeds/
    ui.json
```

Only files needed by a pack are required. An empty capability is represented
explicitly in its manifest, not by probing for a directory.

Shared contracts and mechanisms remain in the existing `api/shared` and
`api/server` packages. The implementation extracts only the registry types and
loader needed to break circular imports:

```text
api/shared/vertical_pack.py       # frozen contract types
api/shared/vertical_loader.py     # selection, validation, process cache
api/shared/domain_contracts.py    # Domain, Phase, HitlGate, ...
api/shared/agent_contracts.py     # AgentRegistryEntry, ...
api/server/runtime_context.py     # resolved VerticalRuntime for FastAPI
```

This is a surgical extraction, not a wholesale rename of the kernel.

## 6. Pack and runtime contracts

`VerticalPack` is immutable after construction:

```python
@dataclass(frozen=True, slots=True)
class VerticalPack:
    name: str
    display_name: str
    manifest_version: str
    domains: Mapping[str, Domain]
    organisation_functions: Mapping[str, OrganisationFunction]
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
    projections: tuple[ProjectionRegistration, ...]
    memory: tuple[MemoryRegistration, ...]
    recordings: RecordingSources
    ui: VerticalUiManifest
    ramp_workflow_types: tuple[str, ...]
```

The mappings exposed by a built pack are read-only. A pack builder may use
ordinary dictionaries internally, but the loader freezes them before
publication.

`VerticalRuntime` adds environment-specific decisions:

```python
@dataclass(frozen=True, slots=True)
class VerticalRuntime:
    pack: VerticalPack
    world_name: str | None
    data_dir: Path
    fingerprint: str
```

The fingerprint is derived from the pack name and manifest version. It is for
configuration agreement, not source-code integrity.

### 6.1 Static registry

The loader owns one auditable mapping:

```python
PACK_MODULES = {
    "agency": "verticals.agency.manifest",
    "telco": "verticals.telco.manifest",
}
```

It imports the selected module and calls `build_pack()`. It does not import
both modules to discover their names. Adding a vertical therefore requires a
reviewable registry change.

### 6.2 Function registration

`DurableFunctionRegistration` declares:

- a callable that decorates an existing `df.DFApp`
- the orchestrator names it registers
- the activity names it registers
- any shared kernel function capabilities it requires

`function_app.py` becomes a small composition root:

1. initialise telemetry and governance
2. create `df.DFApp`
3. register kernel-level functions
4. resolve the active vertical
5. call only that pack's function registrar

Azure Functions indexes decorators at module import, so changing vertical
requires a Functions host restart. Inactive workflow modules are not imported.

### 6.3 Shared kernel assets

Kernel assets are narrowly defined infrastructure capabilities, such as
checkpoint delivery, audit, governance, and standard event ingestion. They are
registered by explicit ID.

Business domains, aspirational rings, phase aliases, business agents, world
commands, and recordings are never kernel assets. A skill may reference:

- an MCP operation registered by its pack
- an explicitly registered kernel operation
- an explicitly declared external capability

Unresolved tool names are validation errors rather than silently disappearing
from Blueprint composition.

## 7. Selection semantics

Selection is resolved once per process from normalized environment values.
Blank values count as unset.

| `ZAVA_VERTICAL` | `ZAVA_WORLD` | Result |
|---|---|---|
| unset | unset | Agency; no actor world; existing default ramp behaviour |
| `agency` | unset | Agency; no actor world |
| `telco` | unset | Telco; Telco default world |
| unset | `support` | Agency inferred; support world |
| unset | `telco` | Telco inferred for legacy compatibility; Telco world |
| `agency` | `support` | Agency; support world |
| `telco` | `telco` | Telco; Telco world |
| unknown value | any | startup failure |
| explicit pack/world mismatch | any | startup failure |

World inference exists only for the two existing legacy world names. New
worlds do not gain implicit vertical selection; callers must set
`ZAVA_VERTICAL`.

Agency declares the support world but has no default actor world, preserving
today's unset behaviour. Telco declares and defaults to the Telco world,
preserving the existing `ZAVA_VERTICAL=telco` behaviour.

`active_vertical()` and `registered_workflow_types()` become compatibility
views over `VerticalRuntime`, not independent environment parsers.

## 8. Boot and data flow

```text
environment
    |
    v
vertical_loader.resolve_runtime()
    |-- select one module
    |-- build immutable pack
    |-- validate references and IDs
    |-- resolve pack-owned world
    |-- resolve pack data directory
    `-- cache VerticalRuntime
           |
           +--> FastAPI AppState
           |      domains / agents / worlds / projections / memory
           |
           +--> Functions composition root
           |      kernel registrations + active pack registrations
           |
           +--> Blueprint inventory / recorder / replay
           |      active roots and active workflow types only
           |
           `--> Control Plane runtime manifest
                  identity / capabilities / lenses / theme
```

All consumers receive the same runtime object or obtain the same process cache.
No consumer reparses the environment.

## 9. Registry migration

### 9.1 Domains and functions

The `Domain`, `Phase`, `HitlGate`, `RegionOverlay`, and `WakeHint` types move to
`domain_contracts.py`. Agency and Telco each build their own domain mapping.
The organisational `Function` and `PersonaTree` types move to
`function_contracts.py`; each pack declares the business functions that own its
domains.

`api/shared/domains.py` remains temporarily as a compatibility adapter:

- it re-exports the contract types
- its `DOMAINS` view contains only the active pack's domains
- `live_domains()` reads the active pack
- it contains no business-domain declarations

Function back-references are wired while building the selected pack. There is
no boot-time mutation across one global domain dictionary.

`api/shared/functions.py` follows the same compatibility pattern as
`api/shared/domains.py`: it re-exports contract types and exposes only the
active pack's organisational function mapping. It does not register Azure
Functions; that is the separate `durable_functions` field and Functions
composition root described in section 6.2.

### 9.2 Agents, personae, and governance

`AgentRegistryEntry` moves to `agent_contracts.py`. `AuthorityRow` moves to
`authority_contracts.py`. Each pack owns its business-agent mapping, delegated
authority rows, policy sources, and persona roots. Governance enforcement
remains shared and is initialised with:

```text
kernel identities/safety policy + active pack identities/authority/policy
```

The inactive pack contributes nothing to the authority graph, capability
allow-list, persona responder, or audit identity catalogue.

Pack policy overlays may extend shared policy definitions but may not replace
or weaken kernel safety rules. Duplicate policy/tool IDs fail validation.

### 9.3 Skills and MCP modules

Blueprint and runtime skill loading receive explicit `skill_roots`. MCP
registrations receive explicit module names. Neither scans the old global
folders after migration.

During migration, existing files are moved to their owning pack rather than
copied. A compatibility import module may re-export an MCP implementation when
needed, but there is one canonical source file.

The domain composer must target a vertical. Its backward-compatible default is
Agency. Generated domains, skills, personae, MCP modules, and recordings are
written beneath the selected pack.

### 9.4 Worlds and objectives

`ObjectiveRoute` and `WorldPackRegistration` remain shared contract types.
`WORLD_PACKS` is removed as a global all-vertical dictionary.

Agency's manifest declares `support`; Telco's declares `telco`.
`ActorWorldService.for_world` resolves through the active runtime and cannot
open a world belonging to another pack.

Each `WorldPackRegistration` owns its named scale-profile registrations. This
architecture defines that selection seam; the follow-on Telco specification
defines the actual demo/standard/stress counts and distributions. An unknown
scale profile fails instead of reverting to a fixed scenario configuration.

### 9.5 Projections and memory

Projection auto-import is replaced by explicit pack registrations. Shared
projection machinery remains generic. Pack registrations declare the entity
kinds and workflow types they consume.

Operational-memory stores are created only for active domains. Agency-specific
watchers and recorders start from Agency's lifecycle registration; Telco does
not boot them accidentally.

## 10. Blueprint, recordings, and UI

### 10.1 Blueprint inventory

`composition_tree(runtime)` builds from:

- active pack domains
- active pack skill roots
- active pack MCP modules
- explicit kernel assets
- active pack phase aliases and aspirational metadata

The current global `SKILLS_DIR`, `MCP_TOOLS_DIR`, module-level `DOMAINS`, and
hard-coded Agency rings are removed. Legacy Onboarding and aspirational Agency
rings move into the Agency UI/composition manifest.

The response includes:

```json
{
  "vertical": {
    "name": "agency",
    "display_name": "Agency",
    "manifest_version": "1",
    "fingerprint": "agency:1"
  }
}
```

### 10.2 Recordings

Committed, curated recordings live under:

```text
verticals/<name>/recordings/
```

New recorder output lives under:

```text
<ZAVA_DATA_DIR>/<name>/blueprint-recordings/
```

`ZAVA_DATA_DIR` defaults to a repository-local runtime-data root.
`PORTAL_DATA_DIR` remains a deprecated alias for that root for one migration
cycle. In both cases the resolver appends the active pack name. Tests and proof
scripts continue to supply fresh temporary roots; they do not need to construct
pack-specific subdirectories themselves.

Playback reads only the active pack's curated and runtime recording roots.
`BLUEPRINT_RECORDINGS_DIR`, when explicitly set for tests or proof capture,
replaces the runtime recording root but does not bypass active workflow-type
validation.

Every recording must resolve to an active workflow type. Foreign or unknown
recordings are reported and excluded; committed curated recordings with such
errors fail validation.

Existing mixed recordings are classified by workflow type and moved to the
correct pack. Unknown files are quarantined for explicit review rather than
randomly assigned.

### 10.3 Control Plane and Blueprint

FastAPI exposes a read-only runtime manifest endpoint containing:

- active vertical identity and fingerprint
- enabled capabilities and routes
- active world identity, if any
- UI theme tokens
- configured lens IDs and renderer IDs

Control Plane and Blueprint read this endpoint. They do not infer the vertical
from hostnames, ports, URL paths, or build-time variables.

Reusable React renderers stay in the shared frontend. `ui.json` maps active
pack entities and capabilities onto those renderer IDs. A new renderer is
shared platform code; a pack chooses and configures it declaratively.

Unavailable routes or lenses are absent from navigation instead of rendering
empty Agency/Telco shells.

## 11. FastAPI and Functions agreement

FastAPI and Functions are separate processes and could be started with
different environment values. That must be observable before scheduling work.

Both processes expose:

- vertical name
- manifest version
- fingerprint
- registered orchestrator names

The shared Functions health registration provides this information. FastAPI's
Durable client verifies the fingerprint during startup/readiness and before
the first live schedule after a Functions reconnect.

A mismatch:

- marks workflow scheduling unavailable
- exposes an unhealthy readiness result with both fingerprints
- does not start the actor-world bridge
- does not silently schedule an orchestrator with the same name from another
  pack

An unreachable Functions host is also degraded readiness, not a FastAPI boot
failure. Ramp scheduling and the actor-world bridge remain disarmed until a
matching host is available. Read-only API and UI surfaces may still start.

Replay mode does not require a Functions host, but the replay's vertical
metadata must match the active pack.

## 12. Validation and failure behaviour

Pack validation runs before FastAPI state construction and before Functions
registration.

Hard failures include:

- unknown pack or world
- world not owned by the selected pack
- duplicate IDs across pack and kernel registrations
- live domain without its declared orchestrator
- function registration not declared by the active pack or kernel
- domain skill not present in active roots
- skill tool not resolved by active MCPs, kernel tools, or declared external
  capabilities
- projection or memory registration for an unknown workflow type
- default world not declared by the pack
- ramp workflow type not present and live in the pack
- curated recording for an unknown or foreign workflow type
- invalid UI renderer/lens ID

Errors identify the pack, asset kind, offending ID, and expected owner.
Validation never catches a broad exception and proceeds with a partial pack.

Mutable runtime startup failures retain existing component-level handling only
where degraded operation is already intentional. Pack composition itself is
atomic: valid or not started.

Functions unavailability and API/Functions fingerprint mismatch are runtime
readiness failures. They block all live scheduling and actor-world bridge
startup but do not disguise themselves as successful readiness or terminate
otherwise valid read-only/replay surfaces.

## 13. Agency migration and compatibility

Agency migrates first because it is the public compatibility contract.

Before moving assets, tests capture the exact Agency baseline by ID, not only
counts:

- domains and phase definitions
- skills and MCP operations
- machine agents and personae
- aspirational Blueprint metadata
- orchestrator/activity registrations
- replay recording workflow types
- default simulator-ramp workflow types

The baseline excludes the three Telco workflow types and Telco-only identities.

With no environment variables:

- Agency composition is returned
- no Telco domain, agent, world, recording, or UI lens is visible
- no actor world starts automatically
- the existing Agency ramp behaviour remains
- the recorded Agency Constellation remains coherent

Compatibility modules remain for one migration cycle, but return active-pack
content only. New code must accept `VerticalRuntime` or an explicit registry
rather than importing compatibility globals.

## 14. Telco migration boundary

After Agency is isolated and proven, existing Telco content moves into the
Telco pack:

- network incident
- proactive customer care
- order to activate
- Telco workflow activities and orchestrators
- Telco machine identities and policy overlays
- Telco world and objective routes
- Telco projections and operational memories
- Telco recordings and UI lenses

This migration preserves the currently proven canonical IDs, world-evidence
completion, HITL behaviour, graph projection, AG-UI stream, and Blueprint
normalisation. It does not add new Telco processes.

The follow-on Telco portfolio specification builds on this pack without
changing the loader or kernel contracts.

## 15. Testing and proof

### 15.1 Contract tests

- environment normalization and selection table
- static registry imports only the selected module
- immutable registry views
- unknown and mismatched selection errors
- duplicate and dangling-reference validation
- deterministic fingerprint generation
- process cache cannot switch vertical after resolution

### 15.2 Agency tests

- unset environment produces the captured Agency baseline
- Agency Functions indexing contains no Telco orchestrator/activity
- Agency Blueprint composition contains no Telco asset
- Agency recordings never select a Telco workflow
- Agency startup does not boot the Telco world or Telco projections
- existing Agency focused and article/replay proofs remain green

### 15.3 Telco tests

- `ZAVA_VERTICAL=telco` selects Telco and defaults its world
- Telco Functions indexing contains no Agency business orchestrator/activity
- Telco Blueprint composition contains no Agency domain, skill, recording, or
  aspirational ring
- existing network, care, order, Memory, Knowledge, AG-UI, and Constellation
  tests remain green
- the existing isolated unmocked Telco proof remains green

### 15.4 Cross-process and browser proof

- API/Functions matching fingerprints reach ready state
- mismatched fingerprints block scheduling with a descriptive readiness error
- Agency and Telco each receive a fresh isolated full-stack run
- Control Plane navigation and Blueprint composition match the runtime manifest
- browser, page, console, and application-network error counts are zero
- all spawned process handles and isolated ports are released

## 16. Delivery sequence

Implementation is split into reviewable phases:

1. Capture Agency/Telco baseline inventories and write failing isolation tests.
2. Add contract types, static loader, runtime cache, and validators.
3. Build and migrate the Agency pack; make it the default.
4. Make FastAPI, Functions, Blueprint, and frontend consume the active runtime.
5. Build and migrate the Telco pack.
6. Partition recordings, mutable data paths, projections, memory, and worlds.
7. Remove global scanning and all-vertical registries.
8. Run Agency and Telco unit, integration, build, and unmocked browser proofs.

Each phase is committed separately on a feature branch. Nothing is pushed
directly to `main`; review happens through a pull request.

## 17. Alternatives rejected

### 17.1 Dynamic Python plugins

Entry points or installable packages would support out-of-repository verticals,
but introduce version negotiation, package trust, dependency conflicts, and
opaque discovery before there is a real need. A static registry provides the
same in-repository interchangeability with a smaller failure surface.

### 17.2 Filtering the current global folders

Adding more workflow-type filters is initially cheaper, but inactive assets
would still be imported, registered, scanned, and available to accidental
consumers. It cannot guarantee Functions, governance, recordings, projections,
or startup watchers are isolated.

### 17.3 Separate repositories or complete applications

Independent applications provide strong isolation but duplicate the kernel and
make improvements drift. The requirement is interchangeable business packs on
one substrate, not a fleet of forks.

## 18. Acceptance criteria

The architecture migration is complete when:

1. Unset configuration boots Agency and reproduces the captured Agency
   composition without any Telco asset.
2. `ZAVA_VERTICAL=telco` boots only Telco business content and preserves the
   existing live Telco proof.
3. Functions indexes only kernel plus active-pack functions.
4. Blueprint scans and replays only kernel plus active-pack assets.
5. worlds, agents, personae, projections, memory, policies, and UI lenses are
   sourced from the active pack.
6. committed and mutable recordings are pack-scoped.
7. invalid pack composition or API/Functions mismatch fails descriptively.
8. Agency and Telco unmocked browser proofs pass independently with zero
   browser/page/network application errors.
9. no compatibility-global consumer can observe inactive-pack content.
10. the Telco portfolio can add catalogue/simulated/live processes entirely
    inside `verticals/telco/` without changing the kernel loader.
