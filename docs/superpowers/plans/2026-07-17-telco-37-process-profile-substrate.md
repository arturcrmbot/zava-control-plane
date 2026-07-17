# Telco 37-Process Profile Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver 37 executable Telco process handles while retaining the nine deep hero workflows and implementing the other 28 through shared profiles, four MCP packs, eight skills, six workflow engines, and a visible simulator-backed world.

**Architecture:** Keep the existing actor world and nine hero workflows intact. Add a data-driven `TelcoProcessProfile` registry for 28 standard workflows, route profiles through six generic Durable engines, expose world data/actions through four MCP capability modules, and use one explicit `TelcoProcessCase` actor plus four mutation families for standard execution. Add one generic process-library UI and prove every profile deterministically; do not create bespoke modules or lenses for standard profiles.

**Tech Stack:** Python 3.11, FastAPI, Azure Durable Functions, SimPy actor world, GitHub Copilot SDK skills/tools, Kuzu entity graph, React 19, TypeScript, Vitest, Pytest, Playwright.

---

## Guardrails

- Work in one isolated worktree.
- Use TDD for every production change.
- Commit after each task.
- Do not modify Agency business assets.
- Do not replace the existing nine hero workflows.
- Do not create one MCP, skill, orchestrator, actor class, or UI component per standard process.
- A standard profile must mutate real state and resolve from evidence; registration-only work is not complete.
- Full browser proof covers one profile per engine, not all 28.
- Contract and deterministic execution tests cover all 28.

## Target file structure

| File | Responsibility |
|---|---|
| `verticals/telco/process_profiles.py` | Profile contracts and the 28 explicit standard profile declarations |
| `verticals/telco/reference_cases.py` | Standard process case actor, fixtures, observations and views |
| `verticals/telco/reference_actions.py` | Profile command validation and four mutation families |
| `verticals/telco/mcp_tools/common.py` | Shared simulator provenance envelope |
| `verticals/telco/mcp_tools/network.py` | Network read/action tool contracts |
| `verticals/telco/mcp_tools/operations.py` | Ticket, work, stock and change tool contracts |
| `verticals/telco/mcp_tools/commercial.py` | Customer, order, revenue and identity tool contracts |
| `verticals/telco/mcp_tools/twin.py` | Forecast, external signal and scenario-comparison contracts |
| `api/functions/workflows/telco_profiled.py` | Six shared Durable orchestration engines |
| `api/functions/activities/telco_profiled.py` | Reusable skill execution and typed command construction |
| `web/client/routes/TelcoProcessLibrary.tsx` | Generic 37-process sales and operator surface |
| `tools/telco_process_profiles_proof.py` | Deterministic contract/execution proof for all standard profiles |

---

### Task 1: Add the explicit process-profile registry

**Files:**
- Create: `verticals/telco/process_profiles.py`
- Create: `tests/api/shared/test_telco_process_profiles.py`
- Reference: `docs/superpowers/specs/2026-07-17-telco-process-profile-substrate-design.md`

- [ ] **Step 1: Write the failing inventory test**

```python
from verticals.telco.process_profiles import (
    ENGINE_CODES,
    STANDARD_PROCESS_PROFILES,
)

EXPECTED_STANDARD_WORKFLOWS = {
    "ran-capacity-planning",
    "network-configuration-validation",
    "rollout-site-planning",
    "network-slice-assurance",
    "energy-optimization",
    "spares-inventory-optimization",
    "site-asset-health-monitoring",
    "backhaul-optimization",
    "core-network-anomaly-management",
    "proactive-service-assurance",
    "network-change-release",
    "spectrum-interference-management",
    "network-security-response",
    "experience-benchmarking",
    "contact-centre-agent-assist",
    "autonomous-self-service",
    "next-best-action",
    "service-provisioning-activation",
    "billing-dispute-resolution",
    "revenue-assurance",
    "collections-dunning",
    "fraud-prevention",
    "customer-onboarding-kyc",
    "complaint-nps-closed-loop",
    "device-lifecycle-upgrade",
    "roaming-experience-steering",
    "number-sim-porting",
    "customer-experience-twin",
}


def test_standard_profile_inventory_is_complete_and_unique():
    assert set(STANDARD_PROCESS_PROFILES) == EXPECTED_STANDARD_WORKFLOWS
    assert len(STANDARD_PROCESS_PROFILES) == 28
    assert len({p.source_id for p in STANDARD_PROCESS_PROFILES.values()}) == 28
    assert len({p.sensor_id for p in STANDARD_PROCESS_PROFILES.values()}) == 28
    assert len({p.command_type for p in STANDARD_PROCESS_PROFILES.values()}) == 28
    assert len({p.success_event for p in STANDARD_PROCESS_PROFILES.values()}) == 28
    assert {p.engine for p in STANDARD_PROCESS_PROFILES.values()} == ENGINE_CODES
```

- [ ] **Step 2: Run the inventory test and verify RED**

Run:

```bash
./.venv/bin/python -m pytest -q tests/api/shared/test_telco_process_profiles.py
```

Expected: collection fails because `verticals.telco.process_profiles` does not exist.

- [ ] **Step 3: Add the immutable profile contracts**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EngineCode = Literal["DDA", "FSP", "CTR", "OFV", "RIG", "ARA"]
MutationFamily = Literal["network", "operations", "commercial", "plan"]

ENGINE_CODES = frozenset({"DDA", "FSP", "CTR", "OFV", "RIG", "ARA"})

TOOLS_BY_PACK = {
    "network": (
        "network_query_state",
        "network_query_impact",
        "network_validate_action",
        "network_prepare_action",
    ),
    "operations": (
        "operations_query_case",
        "operations_search_runbook",
        "operations_match_resources",
        "operations_prepare_case_action",
    ),
    "commercial": (
        "commercial_query_customer",
        "commercial_query_order_revenue",
        "commercial_evaluate_entitlement",
        "commercial_prepare_action",
    ),
    "twin": (
        "twin_forecast",
        "twin_compare_scenarios",
        "twin_query_external_signal",
        "twin_publish_plan",
    ),
}


@dataclass(frozen=True, slots=True)
class StandardPhase:
    name: str
    kind: Literal["deterministic", "agent", "hitl"]
    skill: str | None = None


@dataclass(frozen=True, slots=True)
class TelcoProcessProfile:
    source_id: str
    workflow_type: str
    display_name: str
    function: str
    engine: EngineCode
    phases: tuple[StandardPhase, ...]
    skills: tuple[str, ...]
    mcp_packs: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    sensor_id: str
    objective_type: str
    command_type: str
    success_event: str
    mutation_family: MutationFamily
    hitl_persona: str | None = None
    hitl_event: str | None = None
```

- [ ] **Step 4: Add a compact declaration helper**

```python
def _profile(
    source_id: str,
    workflow_type: str,
    display_name: str,
    *,
    function: str,
    engine: EngineCode,
    skills: tuple[str, ...],
    mcp_packs: tuple[str, ...],
    command_type: str,
    success_event: str,
    mutation_family: MutationFamily,
    hitl_persona: str | None = None,
) -> TelcoProcessProfile:
    phases = ENGINE_PHASES[engine]
    hitl_event = (
        f"{hitl_persona}_decision" if hitl_persona is not None else None
    )
    return TelcoProcessProfile(
        source_id=source_id,
        workflow_type=workflow_type,
        display_name=display_name,
        function=function,
        engine=engine,
        phases=phases,
        skills=skills,
        mcp_packs=mcp_packs,
        allowed_tools=tuple(
            tool
            for pack in mcp_packs
            for tool in TOOLS_BY_PACK[pack]
        ),
        sensor_id=f"sensor:{workflow_type}",
        objective_type=workflow_type.replace("-", "_"),
        command_type=command_type,
        success_event=success_event,
        mutation_family=mutation_family,
        hitl_persona=hitl_persona,
        hitl_event=hitl_event,
    )
```

Define `ENGINE_PHASES` once. Agent phases reference the reusable skill selected
from each profile; do not encode process-specific phases in the engine.

- [ ] **Step 5: Declare the exact 28 profiles**

Create one `_profile(...)` call for every row in Sections 5.1 and 5.2 of the
design spec. Use the exact workflow, engine, skill, MCP, command, success-event
and mutation-family values there. Apply these ownership assumptions:

```python
FUNCTION_BY_SOURCE_PREFIX = {
    "OSS": "network-operations",
    "BSS": "customer-success",
}

FUNCTION_OVERRIDES = {
    "OSS-05": "service-operations",
    "OSS-06": "service-operations",
    "OSS-09": "service-operations",
    "OSS-10": "service-operations",
    "OSS-15": "service-operations",
    "OSS-16": "service-operations",
    "OSS-18": "commercial-risk",
    "BSS-07": "service-operations",
    "BSS-08": "commercial-risk",
    "BSS-09": "commercial-risk",
    "BSS-10": "commercial-risk",
    "BSS-11": "commercial-risk",
    "BSS-12": "commercial-risk",
    "BSS-16": "service-operations",
}
```

Use `network_ops_director`, `service_ops_manager`, `cs_manager`, or
`commercial_risk_director` only when the profile has a material approval
boundary. Profiles without an approval boundary have no HITL phase.

- [ ] **Step 6: Add structural validation**

```python
def validate_process_profiles(
    profiles: dict[str, TelcoProcessProfile],
) -> None:
    for workflow_type, profile in profiles.items():
        if workflow_type != profile.workflow_type:
            raise ValueError(f"profile key mismatch: {workflow_type}")
        if not profile.skills:
            raise ValueError(f"{workflow_type} has no skills")
        if not profile.allowed_tools:
            raise ValueError(f"{workflow_type} has no MCP tools")
        if (profile.hitl_persona is None) != (profile.hitl_event is None):
            raise ValueError(f"{workflow_type} has incomplete HITL metadata")
```

Call validation once after building `STANDARD_PROCESS_PROFILES`.

- [ ] **Step 7: Run the test and verify GREEN**

Run:

```bash
./.venv/bin/python -m pytest -q tests/api/shared/test_telco_process_profiles.py
```

Expected: all profile inventory tests pass.

- [ ] **Step 8: Commit**

```bash
git add verticals/telco/process_profiles.py \
  tests/api/shared/test_telco_process_profiles.py
git commit -m "feat(telco): define standard process profiles"
```

---

### Task 2: Register 37 real domains and four organisation functions

**Files:**
- Modify: `verticals/telco/domains.py`
- Modify: `verticals/telco/functions.py`
- Modify: `verticals/telco/personas.py`
- Modify: `verticals/telco/authority.py`
- Create: `verticals/telco/personae/service_ops_manager/SKILL.md`
- Create: `verticals/telco/personae/commercial_risk_director/SKILL.md`
- Modify: `tests/api/shared/test_telco_expansion_registry.py`

- [ ] **Step 1: Extend the registry test to require 37 non-stub domains**

```python
def test_telco_pack_exposes_37_executable_processes(tmp_path):
    runtime = build_runtime({"ZAVA_VERTICAL": "telco"}, data_root=tmp_path)
    assert len(runtime.pack.domains) == 37
    assert all(not domain.stub for domain in runtime.pack.domains.values())
    assert set(STANDARD_PROCESS_PROFILES) <= set(runtime.pack.domains)
```

Also assert every domain has exactly one function owner.

- [ ] **Step 2: Run the test and verify RED**

Expected: 9 domains found instead of 37.

- [ ] **Step 3: Convert profiles into Domain declarations**

Add:

```python
ENGINE_ORCHESTRATORS = {
    "DDA": "TelcoDetectDiagnoseActOrchestrator",
    "FSP": "TelcoForecastSimulatePlanOrchestrator",
    "CTR": "TelcoCaseTriageResolveOrchestrator",
    "OFV": "TelcoOrderFulfilVerifyOrchestrator",
    "RIG": "TelcoRiskInvestigateGovernOrchestrator",
    "ARA": "TelcoAssistRecommendActOrchestrator",
}


def _domain_from_profile(profile: TelcoProcessProfile) -> Domain:
    gates = ()
    if profile.hitl_persona and profile.hitl_event:
        hitl_phase = next(
            phase.name for phase in profile.phases if phase.kind == "hitl"
        )
        gates = (
            HitlGate(
                hitl_phase,
                profile.hitl_event,
                profile.hitl_persona,
                wait_probability=0.0,
            ),
        )
    return Domain(
        workflow_type=profile.workflow_type,
        display_name=profile.display_name,
        workflow_id_prefix=profile.source_id.replace("-", ""),
        orchestrator_name=ENGINE_ORCHESTRATORS[profile.engine],
        operator_surface=profile.function,
        phases=tuple(Phase(p.name, p.kind) for p in profile.phases),
        hitl_gates=gates,
        skills=profile.skills,
    )
```

Merge generated domains with the existing nine explicit hero domains.

- [ ] **Step 4: Add the two missing organisation functions**

Add `service-operations` and `commercial-risk`. Assign standard profiles from
their `function` field. Keep the existing nine hero owners unchanged.

- [ ] **Step 5: Add two approval personae and authority rows**

Use these authority limits:

```python
"service_ops_manager": AuthorityRow(
    role="service_ops_manager",
    spend_limit_gbp=100_000.0,
    approval_actions=("service_ops_manager_decision",),
    delegate_to="network_ops_director",
),
"commercial_risk_director": AuthorityRow(
    role="commercial_risk_director",
    spend_limit_gbp=1_000_000.0,
    approval_actions=("commercial_risk_director_decision",),
    delegate_to=None,
),
```

Persona SKILL files must use the same frontmatter and `authority_check` pattern
as `verticals/telco/personae/network_ops_director/SKILL.md`.

- [ ] **Step 6: Run pack and Agency regression tests**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/api/shared/test_telco_expansion_registry.py \
  tests/api/shared/test_vertical_pack_inventory.py \
  tests/api/shared/test_authority.py
```

Expected: Telco has 37 domains; Agency remains unchanged.

- [ ] **Step 7: Commit**

```bash
git add verticals/telco/domains.py verticals/telco/functions.py \
  verticals/telco/personas.py verticals/telco/authority.py \
  verticals/telco/personae tests/api/shared
git commit -m "feat(telco): register 37 process domains"
```

---

### Task 3: Add four MCP capability modules

**Files:**
- Create: `verticals/telco/mcp_tools/common.py`
- Create: `verticals/telco/mcp_tools/network.py`
- Create: `verticals/telco/mcp_tools/operations.py`
- Create: `verticals/telco/mcp_tools/commercial.py`
- Create: `verticals/telco/mcp_tools/twin.py`
- Modify: `verticals/telco/manifest.py`
- Create: `tests/api/functions/test_telco_mcp_capabilities.py`

- [ ] **Step 1: Write failing tool-contract tests**

Require these exact tool names:

```python
EXPECTED_TOOLS = {
    "network_query_state",
    "network_query_impact",
    "network_validate_action",
    "network_prepare_action",
    "operations_query_case",
    "operations_search_runbook",
    "operations_match_resources",
    "operations_prepare_case_action",
    "commercial_query_customer",
    "commercial_query_order_revenue",
    "commercial_evaluate_entitlement",
    "commercial_prepare_action",
    "twin_forecast",
    "twin_compare_scenarios",
    "twin_query_external_signal",
    "twin_publish_plan",
}
```

Assert every profile tool is in this set and every tool result includes the
provenance keys `source_mode`, `actor_ids`, `event_ids`, `trace_id`, and
`as_of_sim_time`.

- [ ] **Step 2: Run tests and verify RED**

Expected: modules and tools are missing.

- [ ] **Step 3: Implement the shared provenance helper**

```python
def simulator_result(
    data: dict,
    *,
    actor_ids: list[str],
    event_ids: list[str],
    trace_id: str,
    as_of_sim_time: float,
) -> dict:
    return {
        "data": data,
        "source_mode": "simulated",
        "actor_ids": actor_ids,
        "event_ids": event_ids,
        "trace_id": trace_id,
        "as_of_sim_time": as_of_sim_time,
    }
```

- [ ] **Step 4: Implement four tools per capability module**

Each read tool validates supplied observation data and returns
`simulator_result(...)`. Each prepare tool returns a command proposal only; it
must not mutate world state.

Use `copilot.tools.define_tool`, Pydantic request models, and the existing
`verticals/telco/mcp_tools/customer_care.py` conventions.

- [ ] **Step 5: Register the four modules**

Add these module paths to `mcp_modules`:

```python
"verticals.telco.mcp_tools.network",
"verticals.telco.mcp_tools.operations",
"verticals.telco.mcp_tools.commercial",
"verticals.telco.mcp_tools.twin",
```

Keep `customer_care` temporarily for hero compatibility.

- [ ] **Step 6: Run tool and pack-validation tests**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/api/functions/test_telco_mcp_capabilities.py \
  tests/api/shared/test_vertical_pack_validation.py
```

- [ ] **Step 7: Commit**

```bash
git add verticals/telco/mcp_tools verticals/telco/manifest.py \
  tests/api/functions/test_telco_mcp_capabilities.py
git commit -m "feat(telco): add shared MCP capability packs"
```

---

### Task 4: Add eight reusable reasoning skills

**Files:**
- Create: `verticals/telco/skills/evidence-correlator/SKILL.md`
- Create: `verticals/telco/skills/risk-impact-assessor/SKILL.md`
- Create: `verticals/telco/skills/next-best-action-planner/SKILL.md`
- Create: `verticals/telco/skills/resource-matcher/SKILL.md`
- Create: `verticals/telco/skills/policy-entitlement-evaluator/SKILL.md`
- Create: `verticals/telco/skills/exception-resolution-advisor/SKILL.md`
- Create: `verticals/telco/skills/communication-drafter/SKILL.md`
- Create: `verticals/telco/skills/scenario-comparator/SKILL.md`
- Modify: `verticals/telco/agents.py`
- Create: `tests/api/functions/test_telco_reusable_skills.py`

- [ ] **Step 1: Write failing skill inventory and schema tests**

Assert the eight names exist in the skill root and agent registry. Parse each
SKILL example JSON and require these output keys:

```python
EXPECTED_OUTPUT_KEYS = {
    "evidence-correlator": {
        "evidence_groups", "causal_links", "confidence", "reasoning"
    },
    "risk-impact-assessor": {
        "risk_tier", "impact_score", "affected_actor_ids",
        "uncertainty", "reasoning"
    },
    "next-best-action-planner": {
        "ranked_actions", "selected_action", "reasoning"
    },
    "resource-matcher": {
        "assignments", "unmet_constraints", "reasoning"
    },
    "policy-entitlement-evaluator": {
        "eligible", "entitlement", "requires_approval",
        "policy_refs", "reasoning"
    },
    "exception-resolution-advisor": {
        "root_cause", "resolution_steps", "escalation_required", "reasoning"
    },
    "communication-drafter": {
        "channel", "audience_ids", "message", "reasoning"
    },
    "scenario-comparator": {
        "scenarios", "recommended_scenario", "tradeoffs", "reasoning"
    },
}
```

- [ ] **Step 2: Run tests and verify RED**

- [ ] **Step 3: Author each SKILL contract**

Every SKILL must:

- prohibit invented actor/tool IDs;
- require supplied evidence only;
- define exactly one JSON output shape from the table;
- state that tools prepare actions but do not mutate the world;
- surface uncertainty;
- contain no process-specific vendor names.

- [ ] **Step 4: Register eight agent identities**

Set `scope_function="shared"` and make each agent reversible-only. Allowed
tools are the union needed by profiles that reference the skill; runtime
activity code applies the narrower per-profile allow-list.

- [ ] **Step 5: Run skill and profile compatibility tests**

```bash
./.venv/bin/python -m pytest -q \
  tests/api/functions/test_telco_reusable_skills.py \
  tests/api/shared/test_telco_process_profiles.py
```

- [ ] **Step 6: Commit**

```bash
git add verticals/telco/skills verticals/telco/agents.py \
  tests/api/functions/test_telco_reusable_skills.py
git commit -m "feat(telco): add reusable reasoning skills"
```

---

### Task 5: Implement six shared Durable engines

**Files:**
- Create: `api/functions/workflows/telco_profiled.py`
- Create: `api/functions/activities/telco_profiled.py`
- Modify: `verticals/telco/durable.py`
- Modify: `verticals/telco/manifest.py`
- Create: `tests/api/functions/workflows/test_telco_profiled_orchestration.py`
- Create: `tests/api/functions/workflows/test_telco_profiled_activities.py`
- Modify: `tests/api/functions/test_telco_expansion_registration.py`

- [ ] **Step 1: Write one failing orchestration test per engine**

Parametrise the six engine codes. For each, assert:

- `workflow.started`;
- every declared phase emits start/completion boundaries;
- agent phases call `telco_profile_skill_activity_trigger`;
- HITL runs only when the decision requires approval;
- output contains the profile command type;
- no terminal workflow checkpoint is fabricated before world evaluation.

- [ ] **Step 2: Run tests and verify RED**

- [ ] **Step 3: Implement one generic profile orchestration**

```python
def telco_profile_orchestration(context, engine_code: str):
    payload = context.get_input() or {}
    workflow_type = str(payload["type"])
    profile = STANDARD_PROCESS_PROFILES[workflow_type]
    if profile.engine != engine_code:
        raise ValueError(
            f"{workflow_type} uses {profile.engine}, not {engine_code}"
        )
    # Emit workflow.started, execute declared phases, suspend only when
    # decision.requires_approval, and return the final typed command.
```

Reuse checkpoint/HITL mechanics from
`api/functions/workflows/telco_cascade.py`; do not duplicate six full
orchestrators.

- [ ] **Step 4: Register six thin wrapper functions**

Register exactly:

```text
TelcoDetectDiagnoseActOrchestrator
TelcoForecastSimulatePlanOrchestrator
TelcoCaseTriageResolveOrchestrator
TelcoOrderFulfilVerifyOrchestrator
TelcoRiskInvestigateGovernOrchestrator
TelcoAssistRecommendActOrchestrator
```

- [ ] **Step 5: Implement reusable skill activity**

The activity:

1. reads the profile and phase skill;
2. passes only profile-allowed tools;
3. calls `run_agent_session` in live mode;
4. calls a deterministic selector in proof mode;
5. validates the returned JSON against the skill output contract;
6. threads the result into the next phase.

Model failure must raise or return visible deferral; no success-shaped fallback.

- [ ] **Step 6: Implement profile command construction**

The final activity validates that:

- selected action is in the case's `allowed_actions`;
- actor IDs came from observations/tool results;
- command type equals `profile.command_type`;
- issuer equals the responder owner;
- approval evidence is present when required.

- [ ] **Step 7: Run orchestration, activity and indexing tests**

```bash
./.venv/bin/python -m pytest -q \
  tests/api/functions/workflows/test_telco_profiled_orchestration.py \
  tests/api/functions/workflows/test_telco_profiled_activities.py \
  tests/api/functions/test_telco_expansion_registration.py
```

- [ ] **Step 8: Commit**

```bash
git add api/functions/workflows/telco_profiled.py \
  api/functions/activities/telco_profiled.py \
  verticals/telco/durable.py verticals/telco/manifest.py \
  tests/api/functions
git commit -m "feat(telco): add shared workflow engines"
```

---

### Task 6: Add real standard-process cases, scenarios and commands

**Files:**
- Create: `verticals/telco/reference_cases.py`
- Create: `verticals/telco/reference_actions.py`
- Modify: `verticals/telco/world.py`
- Modify: `verticals/telco/worlds.py`
- Modify: `api/server/world/service.py`
- Modify: `api/server/routes/world.py`
- Create: `tests/api/world/actor/test_telco_reference_cases.py`
- Create: `tests/api/world/actor/test_telco_reference_commands.py`
- Create: `tests/api/routes/test_world_telco_process_profiles.py`

- [ ] **Step 1: Write failing actor/scenario tests for all 28 profiles**

Parametrise every profile and call:

```python
result = scenario.run_reference_process(profile.workflow_type)
```

Assert one `TelcoProcessCase` exists, the expected sensor trips, the case facts
contain actor IDs, and no command outcome is fabricated.

- [ ] **Step 2: Add the process-case actor**

```python
@dataclass(slots=True)
class TelcoProcessCase:
    id: str
    workflow_type: str
    subject_ids: tuple[str, ...]
    status: str
    facts: dict[str, object]
    allowed_actions: tuple[str, ...]
    outcome: dict[str, object] | None = None
```

Store cases on `NetworkScenario.process_cases`.

- [ ] **Step 3: Add explicit fixture builders by mutation family**

Create four builders:

```python
def _case(profile, subject_ids, facts) -> TelcoProcessCase:
    case_id = f"CASE-{profile.source_id}-{len(facts):02d}"
    return TelcoProcessCase(
        id=case_id,
        workflow_type=profile.workflow_type,
        subject_ids=tuple(subject_ids),
        status="open",
        facts={**facts, "source_process": profile.source_id},
        allowed_actions=(profile.command_type,),
    )


def build_network_case(profile, scenario) -> TelcoProcessCase:
    site = max(
        scenario.sites.values(),
        key=lambda item: (item.utilization, item.id),
    )
    assets = [
        asset for asset in scenario.assets.values()
        if asset.site_id == site.id
    ]
    return _case(
        profile,
        [site.id, *(asset.id for asset in assets[:2])],
        {
            "site": scenario._site_view(site),
            "assets": [scenario._asset_view(asset) for asset in assets[:2]],
        },
    )


def build_operations_case(profile, scenario) -> TelcoProcessCase:
    technician = next(iter(scenario.technicians.values()))
    stock = next(iter(scenario.spare_stocks.values()))
    return _case(
        profile,
        [technician.id, stock.id],
        {
            "technician": scenario._technician_view(technician),
            "spare_stock": asdict(stock),
        },
    )


def build_commercial_case(profile, scenario) -> TelcoProcessCase:
    account = next(iter(scenario.accounts.values()))
    subscription = next(
        item for item in scenario.subscriptions.values()
        if item.account_id == account.id
    )
    return _case(
        profile,
        [account.id, subscription.id],
        {
            "account": scenario._account_view(account),
            "subscription": asdict(subscription),
        },
    )


def build_plan_case(profile, scenario) -> TelcoProcessCase:
    site = max(
        scenario.sites.values(),
        key=lambda item: (item.traffic_mbps, item.id),
    )
    return _case(
        profile,
        [site.id],
        {
            "site": scenario._site_view(site),
            "planning_horizon_days": 90,
        },
    )
```

Each builder selects real existing actor IDs and adds process-specific facts
from the design profile. No fixture may contain `"example"`, `"placeholder"`,
or empty facts.

- [ ] **Step 4: Add the generic reference-process trigger**

```python
def run_reference_process(self, workflow_type: str) -> dict:
    profile = STANDARD_PROCESS_PROFILES[workflow_type]
    case = CASE_BUILDERS[profile.mutation_family](profile, self)
    self.process_cases[case.id] = case
    opened = self.runtime.emit(
        "process_case.opened",
        actor_id=case.id,
        trace_id=f"{workflow_type}-{case.id}",
        payload=process_case_view(case),
    )
    sensor = self.runtime.emit(
        "sensor.tripped",
        actor_id=profile.sensor_id,
        target_id=case.id,
        cause_event_id=opened.event_id,
        trace_id=opened.trace_id,
        payload={"case_id": case.id, "measurements": case.facts},
    )
    return {
        "case_id": case.id,
        "root_event_id": opened.event_id,
        "sensor_event_id": sensor.event_id,
    }
```

- [ ] **Step 5: Generate objective routes/responders from profiles**

Each profile route permits only its command type and resolves only from its
success event. Use its shared engine orchestrator.

- [ ] **Step 6: Add case-backed observations**

`build_observation` returns:

- case view;
- real subject actor views;
- profile allowed actions;
- profile MCP packs and allowed tools;
- provenance fields;
- only the command declared by the profile.

- [ ] **Step 7: Write failing command tests for all profiles**

For every profile:

1. open its case;
2. submit a command with the profile command type;
3. assert wrong case/action/actor/approval is rejected atomically;
4. submit valid command;
5. assert case and actor state mutate;
6. assert the profile success event is emitted on the command trace;
7. reapply command and assert idempotency.

- [ ] **Step 8: Implement four mutation families**

`reference_actions.py` validates the complete command before mutation and then:

- `network`: updates a referenced site/asset/service metric or control state;
- `operations`: updates a referenced ticket/work/stock/change case;
- `commercial`: updates account/order/revenue/identity state;
- `plan`: records an approved plan/experiment on the case.

Every mutation sets `case.status = "completed"` and stores a process-specific
`case.outcome`.

- [ ] **Step 9: Add HTTP trigger**

Add:

```text
POST /api/world/processes/{workflow_type}/run
```

Return `ok`, `case_id`, `root_event_id`, `sensor_event_id`, and `workflow_type`.
Reject hero workflow types and unknown profiles.

- [ ] **Step 10: Run all world/profile tests**

```bash
./.venv/bin/python -m pytest -q \
  tests/api/world/actor/test_telco_reference_cases.py \
  tests/api/world/actor/test_telco_reference_commands.py \
  tests/api/routes/test_world_telco_process_profiles.py \
  tests/api/world/actor
```

- [ ] **Step 11: Commit**

```bash
git add verticals/telco/reference_cases.py \
  verticals/telco/reference_actions.py verticals/telco/world.py \
  verticals/telco/worlds.py api/server/world/service.py \
  api/server/routes/world.py tests/api/world tests/api/routes
git commit -m "feat(telco): run standard process cases"
```

---

### Task 7: Add the 37-process library and generic case view

**Files:**
- Modify: `api/shared/kernel_assets.py`
- Modify: `verticals/telco/ui.json`
- Modify: `web/client/hooks/useWorldSimulation.ts`
- Create: `web/client/routes/TelcoProcessLibrary.tsx`
- Modify: `web/client/routes/TelcoWorld.tsx`
- Create: `web/client/routes/__tests__/TelcoProcessLibrary.test.tsx`

- [ ] **Step 1: Write failing UI tests**

Assert:

- 37 process cards render;
- filters work for OSS/BSS, hero/standard and function;
- each standard card shows engine, skills and MCP packs;
- a standard card can trigger its HTTP endpoint;
- selecting a case shows facts, tool provenance, command and outcome;
- hero cards navigate to their existing lens/workflow.

- [ ] **Step 2: Register `process-library` as a known Telco lens**

Add it to `KNOWN_LENSES` and `verticals/telco/ui.json`.

- [ ] **Step 3: Extend world wire types**

Add `TelcoProcessProfileSummary` and `TelcoProcessCase` interfaces. Read profile
summaries from the world snapshot; do not hard-code catalogue rows in React.

- [ ] **Step 4: Implement the process-library component**

Use one compact card component and one generic case drawer. Display:

- source ID;
- process name;
- function;
- hero/standard maturity;
- engine;
- skills;
- MCP packs;
- current status;
- Run button.

Keep cards text-first; no process-specific diagrams.

- [ ] **Step 5: Run UI tests and bundle**

```bash
npm test -- --run \
  web/client/routes/__tests__/TelcoProcessLibrary.test.tsx \
  web/client/routes/__tests__/TelcoWorld.test.tsx
npx vite build
```

- [ ] **Step 6: Commit**

```bash
git add api/shared/kernel_assets.py verticals/telco/ui.json \
  web/client/hooks/useWorldSimulation.ts \
  web/client/routes/TelcoProcessLibrary.tsx \
  web/client/routes/TelcoWorld.tsx \
  web/client/routes/__tests__/TelcoProcessLibrary.test.tsx
git commit -m "feat(telco): add executable process library"
```

---

### Task 8: Add bounded proof, replay and sales documentation

**Files:**
- Create: `tools/telco_process_profiles_proof.py`
- Create: `tests/tools/test_telco_process_profiles_proof.py`
- Modify: `tools/telco_zava_e2e_proof.mjs`
- Modify: `tools/telco_zava_e2e_proof.sh`
- Modify: `docs/superpowers/specs/2026-07-14-telco-oss-process-catalogue.md`
- Modify: `docs/superpowers/specs/2026-07-14-telco-bss-process-catalogue.md`
- Modify: `README.md`

- [ ] **Step 1: Write failing proof-contract tests**

Require:

```json
{
  "workflow_types": 37,
  "hero_workflows": 9,
  "standard_profiles": 28,
  "workflow_engines": 6,
  "skills": 8,
  "mcp_packs": 4
}
```

- [ ] **Step 2: Implement deterministic all-profile proof**

The Python proof runs every standard profile against an isolated world and
checks:

- sensor;
- objective route;
- observation;
- deterministic skill output;
- MCP provenance;
- typed command;
- accepted mutation;
- success evidence;
- resolved objective;
- replayable journal.

Write one compact JSON result row per profile.

- [ ] **Step 3: Extend live browser proof by six samples only**

Select one standard process per engine:

```text
DDA core-network-anomaly-management
FSP ran-capacity-planning
CTR billing-dispute-resolution
OFV service-provisioning-activation
RIG revenue-assurance
ARA contact-centre-agent-assist
```

The browser proof opens the process library, runs these six, and checks the
generic case view. Keep the existing nine-hero proof unchanged.

- [ ] **Step 4: Add standard-profile replay**

Generate recordings for the six samples. Contract tests, not browser replay,
cover the other 22 profiles.

- [ ] **Step 5: Update both catalogues**

For every source row add:

```text
Zava workflow type
Fidelity: hero|standard
Engine
Skills
MCP packs
Typed command
Success evidence
```

- [ ] **Step 6: Add install/run instructions**

Document:

```bash
ZAVA_VERTICAL=telco ZAVA_TELCO_AGENT_MODE=deterministic make up
```

Explain that Agency remains the default and that the process library is
available only under the Telco pack.

- [ ] **Step 7: Run final suites**

```bash
./.venv/bin/python -m pytest -q \
  tests/api/shared \
  tests/api/functions \
  tests/api/world/actor \
  tests/tools/test_telco_process_profiles_proof.py
npm test --silent
npx vite build
bash tools/telco_zava_e2e_proof.sh
```

Expected:

- all 37 domains registered;
- all 28 standard deterministic runs pass;
- nine-hero live/replay proof passes;
- six standard browser samples pass;
- Agency registry and UI remain unchanged;
- proof ports are released.

- [ ] **Step 8: Commit**

```bash
git add tools tests/tools docs/superpowers/specs README.md
git commit -m "docs(telco): prove 37 executable processes"
```

---

## Delivery sequence

| Day | Scope |
|---|---|
| Day 1 | Tasks 1-4: profiles, organisation, MCP packs, reusable skills |
| Day 2 | Task 5 and first half of Task 6: engines, cases, routes |
| Day 3 | Finish Task 6 and Task 7: all commands, process library |
| Day 4 | Task 8: proof, replay, catalogue, rehearsal and buffer |

## Stop conditions

Stop and simplify rather than adding a new abstraction when:

- a standard process requests bespoke UI;
- a fifth MCP capability pack is proposed;
- a ninth reusable skill is proposed;
- a seventh engine is proposed;
- a profile cannot fit one of the four mutation families.

Any exception requires a concrete failing test and evidence that profile
configuration cannot express the behaviour.

## Plan self-review

- Spec coverage: 37 handles, 28 standard profiles, six engines, eight skills,
  four MCP packs, world authority, simulator visibility, UI and proof are each
  covered by a task.
- Placeholder scan: no unresolved implementation markers remain.
- Type consistency: profile field names, engine codes, skill names, MCP module
  names, command fields and proof counts are consistent across tasks.
