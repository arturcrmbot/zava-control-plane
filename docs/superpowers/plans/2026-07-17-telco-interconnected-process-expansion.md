# Telco Interconnected Process Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add six world-backed Telco workflows that form one causal storm-to-retention story and increase the active Telco pack from three to nine live workflow types.

**Architecture:** Extend the authoritative Telco actor world with network assets, weather, field resources, work orders, tickets, experience episodes, and retention offers. Each process uses its own sensor trace, canonical objective/Workflow, Durable responder, typed command, evidence-backed evaluation, graph/memory projection, and real operator lens; cross-process causality uses `cause_event_id`, `parent_trace_id`, and `contributing_trace_ids`.

**Tech Stack:** Python 3.11, SimPy, Azure Durable Functions, Microsoft Agent Framework/GitHub Copilot runtime, FastAPI, KuzuDB, React 19, TypeScript, Vitest, pytest, Playwright.

**Design:** [`docs/superpowers/specs/2026-07-17-telco-interconnected-process-expansion-design.md`](../specs/2026-07-17-telco-interconnected-process-expansion-design.md)

---

## File structure

**Create:**

- `verticals/telco/operations.py` — asset, weather, work-order, technician, spare, ticket, experience, and retention actors.
- `api/functions/workflows/{outage_risk_management,predictive_site_maintenance,field_repair_dispatch,capacity_optimization,service_ticket_resolution,retention_orchestration}.py` — Durable orchestrators.
- Matching `*_activities.py` files — deterministic/agent decision boundaries returning typed commands.
- `verticals/telco/entity_projections/*.py` — one projection per new workflow.
- `verticals/telco/skills/*/SKILL.md` — advisory agent skills.
- `verticals/telco/personae/network_ops_director/SKILL.md` — operations escalation.
- `tests/api/world/actor/test_telco_operations.py` — actor generation, dynamics, and commands.
- Focused workflow, bridge, projection, memory, UI, and proof tests named in each task.
- `tools/telco_interconnected_e2e_proof.{sh,mjs}` — isolated four-scenario live/replay proof.

**Modify:**

- `verticals/telco/world.py` — world installation, dynamics, sensors, commands, observations, and snapshot.
- `verticals/telco/worlds.py` — objective routes/responders.
- `verticals/telco/domains.py`, `functions.py`, `authority.py`, `personas.py`, `manifest.py`, `durable.py`, `projections.py`, `ui.json`.
- `api/server/routes/world.py` — scenario injection routes.
- `api/server/services/entity_graph.py` — six typed generic relationships.
- `web/client/hooks/useWorldSimulation.ts` — new wire types/injections.
- `web/client/routes/TelcoWorld.tsx` — Network, Field Operations, Customer Impact, Orders, Control lenses.
- `web/shared/runtime.ts` — `field-operations` renderer/lens identity.

---

### Task 1: Add operational actors, deterministic dynamics, and perturbations

**Files:**

- Create: `verticals/telco/operations.py`
- Modify: `verticals/telco/world.py`
- Modify: `api/server/world/service.py`
- Modify: `api/server/routes/world.py`
- Test: `tests/api/world/actor/test_telco_operations.py`
- Test: `tests/api/routes/test_world_telco_operations.py`

- [ ] **Step 1: Write failing actor-generation tests**

```python
def test_demo_world_creates_operational_resources():
    world = ActorWorldService.telco(
        seed=42,
        bus=EventBus(),
        minutes_per_second=1000,
    )
    scenario = world.scenario

    assert len(scenario.assets) == 48
    assert len(scenario.technicians) == 20
    assert {stock.part_kind for stock in scenario.spare_stocks.values()} == {
        "radio-unit", "power", "cooling", "backhaul",
    }
    assert scenario.assets["AST-SITE-01-radio-unit"].site_id == "SITE-01"
```

Add deterministic checks for the seeded unavailable technician and regional
radio spare shortage.

- [ ] **Step 2: Run actor-generation tests and confirm failure**

Run:

```bash
pytest tests/api/world/actor/test_telco_operations.py -q
```

Expected: failure because `assets`, `technicians`, and `spare_stocks` do not
exist.

- [ ] **Step 3: Create operational actor dataclasses**

```python
@dataclass(slots=True)
class NetworkAsset:
    id: str
    site_id: str
    kind: str
    health: float
    temperature_c: float
    load: float
    failure_probability: float = 0.0
    status: str = "healthy"


@dataclass(slots=True)
class WorkOrder:
    id: str
    site_id: str
    asset_id: str
    kind: str
    priority: int
    required_skill: str
    required_spare: str
    due_at: float
    status: str = "open"
    technician_id: str | None = None


@dataclass(slots=True)
class Technician:
    id: str
    region: str
    skills: tuple[str, ...]
    status: str = "available"
    assigned_work_order_id: str | None = None
```

Also define:

```python
@dataclass(slots=True)
class WeatherEvent:
    id: str
    region: str
    severity: float
    power_risk: float
    cooling_risk: float
    starts_at: float
    ends_at: float


@dataclass(slots=True)
class SpareStock:
    id: str
    region: str
    part_kind: str
    quantity: int
    reorder_point: int


@dataclass(slots=True)
class CareTicket:
    id: str
    account_id: str
    subscription_id: str
    incident_trace_id: str
    category: str
    severity: str
    status: str = "open"
    root_cause: str | None = None


@dataclass(slots=True)
class ExperienceEpisode:
    id: str
    account_id: str
    source_trace_id: str
    kind: str
    impact_score: float
    occurred_at: float


@dataclass(slots=True)
class RetentionOffer:
    id: str
    account_id: str
    reason: str
    value_gbp: float
    offer_kind: str
    status: str = "proposed"
```

- [ ] **Step 4: Install deterministic operational state**

In `NetworkScenario.__init__`, add dictionaries for every new actor kind and
sequence counters. In `install()`, call `_create_operational_state()` after
sites/accounts and before sessions.

```python
for site in self.sites.values():
    for kind in ("radio-unit", "power", "cooling", "backhaul"):
        asset_id = f"AST-{site.id}-{kind}"
        self.assets[asset_id] = NetworkAsset(
            id=asset_id,
            site_id=site.id,
            kind=kind,
            health=round(self.runtime.rng.uniform(0.72, 0.99), 4),
            temperature_c=round(self.runtime.rng.uniform(28, 48), 2),
            load=site.utilization,
        )
```

Create five technicians per region. Make `TECH-WEST-05` unavailable and set
west-region radio spare quantity to zero.

- [ ] **Step 5: Add deterministic dynamics and risk projections**

Add `_operations_loop()` scheduled once per simulation minute:

```python
weather_factor = self._weather_risk(asset.site_id)
load_factor = max(0.0, self.sites[asset.site_id].utilization - 0.7)
asset.health = max(
    0.0,
    asset.health - 0.0004 - weather_factor * 0.004 - load_factor * 0.002,
)
asset.temperature_c = round(
    28.0 + asset.load * 35.0 + weather_factor * 12.0,
    2,
)
asset.failure_probability = round(
    min(1.0, (1.0 - asset.health) * 0.75 + weather_factor * 0.35),
    4,
)
```

Emit `asset.metrics` only when health/risk crosses a declared band; do not
journal every loop iteration.

- [ ] **Step 6: Add storm and resource perturbation routes**

Add request models/endpoints:

```python
class WeatherRiskRequest(BaseModel):
    region: str
    severity: float = Field(ge=0.1, le=1.0)
    duration_minutes: float = Field(gt=0, le=240)


@router.post("/inject/weather-risk")
async def inject_weather_risk(body: WeatherRiskRequest) -> dict:
    service = _require_telco_world()
    event_id = service.inject_weather_risk(
        region=body.region,
        severity=body.severity,
        duration_minutes=body.duration_minutes,
    )
    return {"ok": True, "event_id": event_id}
```

Also add `POST /api/world/inject/spare-shortage` and
`POST /api/world/inject/technician-unavailable`.

Add matching `ActorWorldService` proxies:

```python
def inject_weather_risk(
    self,
    region: str,
    *,
    severity: float,
    duration_minutes: float,
) -> str:
    return self._require_scenario_method("inject_weather_risk")(
        region,
        severity=severity,
        duration_minutes=duration_minutes,
    )


def inject_spare_shortage(self, region: str, part_kind: str) -> str:
    return self._require_scenario_method("inject_spare_shortage")(
        region,
        part_kind,
    )


def inject_technician_unavailable(self, technician_id: str) -> str:
    return self._require_scenario_method("inject_technician_unavailable")(
        technician_id,
    )
```

Reuse or add `_require_scenario_method(name)` to raise a clear `ValueError`
when the active world does not support the injection.

- [ ] **Step 7: Run actor/route tests**

Run:

```bash
pytest \
  tests/api/world/actor/test_telco_operations.py \
  tests/api/routes/test_world_telco_operations.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add verticals/telco/operations.py verticals/telco/world.py \
  api/server/world/service.py api/server/routes/world.py \
  tests/api/world/actor/test_telco_operations.py \
  tests/api/routes/test_world_telco_operations.py
git commit -m "feat(telco): add operational world actors"
```

---

### Task 2: Register six domains, objective routes, responders, authority, and Durable skeletons

**Files:**

- Modify: `verticals/telco/domains.py`
- Modify: `verticals/telco/functions.py`
- Modify: `verticals/telco/authority.py`
- Modify: `verticals/telco/personas.py`
- Modify: `verticals/telco/manifest.py`
- Modify: `verticals/telco/worlds.py`
- Modify: `verticals/telco/durable.py`
- Create: `verticals/telco/personae/network_ops_director/SKILL.md`
- Create: six orchestrator/activity modules under `api/functions/workflows/`
- Test: `tests/api/shared/test_telco_expansion_registry.py`
- Test: `tests/api/functions/test_telco_expansion_registration.py`

- [ ] **Step 1: Write failing pack inventory tests**

```python
EXPECTED = {
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
    "outage-risk-management",
    "predictive-site-maintenance",
    "field-repair-dispatch",
    "capacity-optimization",
    "service-ticket-resolution",
    "retention-orchestration",
}


def test_telco_pack_declares_nine_live_workflows(tmp_path):
    runtime = build_runtime({"ZAVA_VERTICAL": "telco"}, data_root=tmp_path)
    assert set(runtime.pack.domains) == EXPECTED
    assert all(not domain.stub for domain in runtime.pack.domains.values())
    declared_orchestrators = runtime.pack.durable_functions.orchestrators
    for domain in runtime.pack.domains.values():
        assert domain.orchestrator_name in declared_orchestrators
    responder_workflows = {
        responder.workflow_type
        for world in runtime.pack.worlds.values()
        for responder in world.responders.values()
    }
    assert EXPECTED <= responder_workflows
```

Assert ownership: six network/field domains under `network-operations`, three
customer domains under `customer-success`.

- [ ] **Step 2: Run inventory tests and confirm failure**

Run:

```bash
pytest tests/api/shared/test_telco_expansion_registry.py -q
```

Expected: only three workflow types exist.

- [ ] **Step 3: Add Domain declarations**

Use this exact ownership:

```python
NETWORK_DOMAINS = (
    "network-incident",
    "order-to-activate",
    "outage-risk-management",
    "predictive-site-maintenance",
    "field-repair-dispatch",
    "capacity-optimization",
)
CUSTOMER_DOMAINS = (
    "proactive-customer-care",
    "service-ticket-resolution",
    "retention-orchestration",
)
```

Use these exact ordered phase/kind tuples:

```python
NEW_PHASES = {
    "outage-risk-management": (
        ("External Signal Correlation", "deterministic"),
        ("Exposure Assessment", "agent"),
        ("Pre-stage Plan", "agent"),
        ("High-cost Approval", "hitl"),
        ("Pre-stage Execution", "deterministic"),
        ("Risk Verification", "deterministic"),
    ),
    "predictive-site-maintenance": (
        ("Telemetry Correlation", "deterministic"),
        ("Failure Diagnosis", "agent"),
        ("Repair-or-Replace Decision", "agent"),
        ("Replacement Approval", "hitl"),
        ("Work Order Creation", "deterministic"),
        ("Maintenance Verification", "deterministic"),
    ),
    "field-repair-dispatch": (
        ("Work Intake", "deterministic"),
        ("Resource Matching", "agent"),
        ("Dispatch Plan", "deterministic"),
        ("Exception Approval", "hitl"),
        ("Repair Execution", "deterministic"),
        ("Repair Verification", "deterministic"),
    ),
    "capacity-optimization": (
        ("Congestion Correlation", "deterministic"),
        ("Optimisation Plan", "agent"),
        ("Guardrail Evaluation", "deterministic"),
        ("Capital Approval", "hitl"),
        ("Optimisation Execution", "deterministic"),
        ("Stability Verification", "deterministic"),
    ),
    "service-ticket-resolution": (
        ("Ticket Intake", "deterministic"),
        ("Root-cause Correlation", "agent"),
        ("Resolution Plan", "agent"),
        ("Vulnerable Customer Review", "hitl"),
        ("Resolution Execution", "deterministic"),
        ("Customer Verification", "deterministic"),
    ),
    "retention-orchestration": (
        ("Experience Aggregation", "deterministic"),
        ("Churn Driver Analysis", "agent"),
        ("Offer Selection", "agent"),
        ("High-value Offer Approval", "hitl"),
        ("Offer Execution", "deterministic"),
        ("Outcome Tracking", "deterministic"),
    ),
}
```

Add orchestrator name, operator surface, declared agent skills, exact external
event/persona HITL gate, and `spawn_fn=None` because all six are
world-event-driven.

Wrap every declared phase:

```python
phases=tuple(Phase(name, kind) for name, kind in NEW_PHASES[workflow_type])
```

- [ ] **Step 4: Add function ownership and authority chain**

```python
"network-operations": Function(
    ...,
    owns_domains=NETWORK_DOMAINS,
    persona_hierarchy=PersonaTree(
        role="network_ops_director",
        manages=(PersonaTree(role="delivery_lead"),),
    ),
)
```

Add:

```python
"network_ops_director": AuthorityRow(
    role="network_ops_director",
    spend_limit_gbp=1_000_000.0,
    approval_actions=("network_ops_director_decision",),
    delegate_to=None,
)
```

Change `delivery_lead.delegate_to` to `network_ops_director`. Add matching
Persona metadata and a SKILL frontmatter contract:

```yaml
external_event: network_ops_director_decision
```

- [ ] **Step 5: Add objective routes/responders**

Append to `TELCO_WORLD.objective_routes`:

```python
ObjectiveRoute(
    sensor_id="sensor:outage_risk",
    objective_type="outage_prevention",
    allowed_command_types=frozenset({"prestage_field_resources"}),
    success_event_types=frozenset({"resources.prestaged"}),
    failure_event_types=frozenset({"command.rejected"}),
    evaluation_timeout_minutes=60.0,
)
```

Add all six route contracts:

| Sensor | Objective | Command | Success event | Timeout |
|---|---|---|---|---:|
| `sensor:outage_risk` | `outage_prevention` | `prestage_field_resources` | `resources.prestaged` | 60 |
| `sensor:asset_failure_risk` | `site_maintenance` | `create_maintenance_work_order` | `work_order.created` | 60 |
| `sensor:work_order_ready` | `field_repair` | `dispatch_field_repair` | `asset.repaired`, `asset.replaced` | 180 |
| `sensor:site_congestion` | `capacity_recovery` | `apply_capacity_action` | `site.capacity.stable` | 60 |
| `sensor:ticket_pressure` | `ticket_resolution` | `resolve_ticket_batch` | `ticket_batch.resolved` | 60 |
| `sensor:churn_risk` | `customer_retention` | `apply_retention_offer` | `retention_offer.issued` | 60 |

Every route uses `command.rejected` as failure evidence. Add these exact
responders:

| Objective | Orchestrator | Workflow type | Prefix | Owner function | Timeout | Observation key |
|---|---|---|---|---|---:|---|
| `outage_prevention` | `OutageRiskManagementOrchestrator` | `outage-risk-management` | `outage` | `outage_risk` | 300 | `outage_risk` |
| `site_maintenance` | `PredictiveSiteMaintenanceOrchestrator` | `predictive-site-maintenance` | `maint` | `site_maintenance` | 300 | `asset_failure_risk` |
| `field_repair` | `FieldRepairDispatchOrchestrator` | `field-repair-dispatch` | `repair` | `field_repair` | 600 | `work_order` |
| `capacity_recovery` | `CapacityOptimizationOrchestrator` | `capacity-optimization` | `capacity` | `capacity_optimization` | 300 | `site_congestion` |
| `ticket_resolution` | `ServiceTicketResolutionOrchestrator` | `service-ticket-resolution` | `ticket` | `ticket_resolution` | 300 | `ticket_pressure` |
| `customer_retention` | `RetentionOrchestrationOrchestrator` | `retention-orchestration` | `retain` | `customer_retention` | 300 | `churn_risk` |

- [ ] **Step 6: Add Durable skeletons and registrations**

Each orchestrator must:

1. emit `workflow.started`;
2. checkpoint every real phase;
3. call deterministic/agent activities;
4. suspend only when authority requires;
5. return `status="decision_ready"` plus one typed command;
6. never emit terminal workflow completion before world evaluation.

Register six orchestrators and their activity triggers in
`verticals/telco/durable.py`; add names to
`DurableFunctionRegistration.orchestrators/activities`.

- [ ] **Step 7: Verify pack and Functions indexing**

Run:

```bash
pytest \
  tests/api/shared/test_telco_expansion_registry.py \
  tests/api/functions/test_telco_expansion_registration.py \
  tests/api/shared/test_vertical_pack_validation.py -q
```

Expected: all pass; Agency process imports none of the new Telco modules.

- [ ] **Step 8: Commit**

```bash
git add verticals/telco api/functions/workflows \
  tests/api/shared/test_telco_expansion_registry.py \
  tests/api/functions/test_telco_expansion_registration.py
git commit -m "feat(telco): register process cascade"
```

---

### Task 3: Implement outage-risk and predictive-maintenance workflows

**Files:**

- Create: `verticals/telco/skills/outage-risk-planning/SKILL.md`
- Create: `verticals/telco/skills/site-failure-diagnosis/SKILL.md`
- Modify: outage/maintenance workflow and activity modules
- Modify: `verticals/telco/world.py`
- Test: `tests/api/world/actor/test_telco_risk_maintenance.py`
- Test: `tests/api/server/services/test_world_bridge_outage_maintenance.py`

- [ ] **Step 1: Write failing sensor-chain test**

```python
def test_storm_opens_outage_then_maintenance_objectives():
    world = service()
    world.inject_weather_risk("west", severity=0.9, duration_minutes=60)
    world.runtime.run_until(15)

    sensors = [
        e.actor_id for e in world.runtime.journal if e.type == "sensor.tripped"
    ]
    assert "sensor:outage_risk" in sensors
    assert "sensor:asset_failure_risk" in sensors
```

Assert different `trace_id` values and `parent_trace_id` causality.

- [ ] **Step 2: Implement rising-edge risk sensors**

Trip `sensor:outage_risk` when regional weather/power exposure exceeds 0.7.
Trip `sensor:asset_failure_risk` per asset when failure probability exceeds
0.65. Store latches by region/asset and reset only below 0.45.

- [ ] **Step 3: Implement `prestage_field_resources`**

Validation:

```python
if not isinstance(payload.get("technician_ids"), list):
    return "technician_ids must be a list"
if any(self.technicians[tid].status != "available" for tid in ids):
    return "technician is not available"
if any(self.spare_stocks[sid].quantity < qty for sid, qty in reservations):
    return "insufficient spare stock"
```

Apply reservations atomically; emit `resources.prestaged`.

- [ ] **Step 4: Implement `create_maintenance_work_order`**

Require real asset, no active duplicate work order, valid kind, spare/skill,
priority 1–5, and authority evidence for replacement. Create `WorkOrder`, emit
`work_order.created`, then emit `sensor:work_order_ready` on a new trace whose
payload includes `parent_trace_id`.

- [ ] **Step 5: Implement advisory activities**

The outage agent ranks exposed sites/resources. The maintenance agent returns
diagnosis and repair/replace recommendation. Deterministic activities convert
recommendations into bounded command payloads; model failure results in HITL
or visible workflow failure, never fabricated advice.

- [ ] **Step 6: Run focused tests**

```bash
pytest \
  tests/api/world/actor/test_telco_risk_maintenance.py \
  tests/api/server/services/test_world_bridge_outage_maintenance.py -q
```

- [ ] **Step 7: Commit**

```bash
git add verticals/telco api/functions/workflows \
  tests/api/world/actor/test_telco_risk_maintenance.py \
  tests/api/server/services/test_world_bridge_outage_maintenance.py
git commit -m "feat(telco): prevent predicted outages"
```

---

### Task 4: Implement field-repair dispatch and finite resources

**Files:**

- Create: `verticals/telco/skills/field-resource-matching/SKILL.md`
- Modify: field workflow/activity modules
- Modify: `verticals/telco/world.py`
- Test: `tests/api/world/actor/test_telco_field_dispatch.py`
- Test: `tests/api/server/services/test_world_bridge_field_dispatch.py`

- [ ] **Step 1: Write failing finite-resource tests**

Cover:

- nearest skilled available technician chosen;
- spare reservation decremented once;
- west radio shortage rejects dispatch;
- duplicate command is idempotent;
- failed approval releases reservations;
- completed repair increases health and clears failure risk.

- [ ] **Step 2: Implement deterministic candidate ranking**

```python
candidates = sorted(
    (
        technician
        for technician in self.technicians.values()
        if technician.status == "available"
        and work.required_skill in technician.skills
    ),
    key=lambda tech: (
        tech.region != self.sites[work.site_id].region,
        tech.id,
    ),
)
```

The agent may explain/rank candidates, but deterministic validation selects the
first feasible candidate from the declared list.

- [ ] **Step 3: Implement `dispatch_field_repair`**

Batch-validate work order, technician, spare, cross-region/overtime authority,
and no existing assignment. Mutate technician/work-order/spare state and emit
`work_order.dispatched`.

Schedule a SimPy process that emits `technician.arrived`, advances work, then:

```python
asset.health = max(asset.health, 0.96)
asset.failure_probability = min(asset.failure_probability, 0.05)
asset.status = "healthy"
work.status = "completed"
technician.status = "available"
```

Emit `asset.repaired` or `asset.replaced`.

- [ ] **Step 4: Implement dispatch HITL**

Suspend for `delivery_lead_decision` when:

- technician is cross-region;
- overtime cost exceeds £2,500;
- no local spare and emergency transfer is requested.

Escalate above £10k to `network_ops_director_decision`.

- [ ] **Step 5: Run dispatch tests**

```bash
pytest \
  tests/api/world/actor/test_telco_field_dispatch.py \
  tests/api/server/services/test_world_bridge_field_dispatch.py -q
```

- [ ] **Step 6: Commit**

```bash
git add verticals/telco api/functions/workflows \
  tests/api/world/actor/test_telco_field_dispatch.py \
  tests/api/server/services/test_world_bridge_field_dispatch.py
git commit -m "feat(telco): dispatch finite field resources"
```

---

### Task 5: Implement capacity optimisation and order re-feasibility

**Files:**

- Create: `verticals/telco/skills/capacity-action-planner/SKILL.md`
- Modify: capacity workflow/activity modules
- Modify: `verticals/telco/world.py`
- Modify: `api/functions/workflows/order_to_activate.py`
- Test: `tests/api/world/actor/test_telco_capacity_optimization.py`
- Test: `tests/api/server/services/test_world_bridge_capacity_order.py`

- [ ] **Step 1: Write failing capacity/order test**

```python
def test_capacity_action_retriggers_infeasible_order():
    world = service()
    world.inject_capacity_pressure("SITE-12", utilization=0.95)
    order_id = world.submit_service_order(
        account_id="ACC-00004",
        product="fiber-1gb",
        requested_site_id="SITE-12",
    )
    world.runtime.run_until(world.runtime.now + 2)
    assert world.scenario.orders[order_id].status == "infeasible"

    world.apply_command(capacity_command("SITE-12", added_mbps=250))

    sensor = next(
        e for e in reversed(world.runtime.journal)
        if e.type == "sensor.tripped"
        and e.actor_id == "sensor:service_order"
        and e.payload["order_id"] == order_id
    )
    assert sensor.payload["parent_trace_id"] == "capacity-trace"
```

- [ ] **Step 2: Add congestion sensor**

Trip per healthy site when utilisation exceeds 0.88 or packet loss exceeds
3%. Observation includes site, neighbours, sessions, pending orders, energy
draw, and allowed actions.

- [ ] **Step 3: Make order feasibility state explicit**

When `submit_service_order` targets a site with utilisation `>= 0.9`, create
the order with:

```python
order.status = "infeasible"
order.reason = "insufficient_site_capacity"
```

Emit the first `sensor:service_order` so the original workflow records the
failure. When `site.capacity.stable` re-drives an order, atomically reset it:

```python
if order.status == "infeasible":
    order.status = "pending"
    order.reason = None
```

Then emit the fresh sensor/objective trace. Keep
`_validate_service_order_activation` strict: it accepts only `pending`.

- [ ] **Step 4: Implement `apply_capacity_action`**

Support reversible actions:

- `temporary_carrier`: add bounded temporary capacity;
- `traffic_shift`: move selected sessions using existing atomic reroute rules;
- `energy_override`: wake a sleeping carrier;
- `permanent_augmentation`: add capacity with `network_ops_director` authority.

Emit `site.capacity.stable` only after utilisation falls below 0.8 and packet
loss below 1%.

- [ ] **Step 5: Re-drive pending/infeasible orders**

On `site.capacity.stable`, find orders for the target site whose status is
`pending` or `infeasible`; emit a fresh `sensor:service_order` per order with a
new trace and `parent_trace_id` set to the capacity objective trace.

Do not reuse the failed objective or command ID.

- [ ] **Step 6: Implement capacity advisory/authority**

Agent returns ranked actions with expected QoE, energy, order, and cost impact.
Deterministic guardrail activity rejects capacity overflow, invalid sessions,
or permanent cost without authority.

- [ ] **Step 7: Run capacity/order tests**

```bash
pytest \
  tests/api/world/actor/test_telco_capacity_optimization.py \
  tests/api/server/services/test_world_bridge_capacity_order.py \
  tests/api/functions/workflows/test_order_to_activate.py -q
```

- [ ] **Step 8: Commit**

```bash
git add verticals/telco api/functions/workflows \
  tests/api/world/actor/test_telco_capacity_optimization.py \
  tests/api/server/services/test_world_bridge_capacity_order.py
git commit -m "feat(telco): couple capacity to activation"
```

---

### Task 6: Implement ticket resolution and retention orchestration

**Files:**

- Create: `verticals/telco/skills/ticket-root-cause-correlation/SKILL.md`
- Create: `verticals/telco/skills/churn-driver-analysis/SKILL.md`
- Create: `verticals/telco/skills/retention-offer-selection/SKILL.md`
- Modify: ticket/retention workflow/activity modules
- Modify: `verticals/telco/world.py`
- Test: `tests/api/world/actor/test_telco_customer_lifecycle.py`
- Test: `tests/api/server/services/test_world_bridge_ticket_retention.py`

- [ ] **Step 1: Write failing customer lifecycle tests**

Cover:

- degraded sessions create tickets only for affected accounts;
- tickets retain incident/activation parent trace;
- ticket pressure creates one objective per root cause;
- recovery resolves correlated tickets;
- repeated episodes raise churn risk;
- care credit lowers but does not erase churn risk;
- high-value offer reaches `cs_manager`;
- duplicate offer command is idempotent.

- [ ] **Step 2: Create tickets and experience episodes from material events**

When sessions degrade or activation fails:

```python
ticket = CareTicket(
    id=self._next_ticket_id(),
    account_id=account_id,
    subscription_id=subscription_id,
    incident_trace_id=parent_trace,
    category=category,
    severity=severity,
    status="open",
    root_cause=None,
)
```

Create an `ExperienceEpisode` with impact score derived from duration,
service tier, vulnerability, ticket, and credit.

- [ ] **Step 3: Implement ticket-pressure sensor and resolution command**

Group open tickets by root cause candidate. Trip when group size reaches 5 or
contains a vulnerable account.

`resolve_ticket_batch` validation requires every ticket to be open/correlated
and service evidence to be healthy. Accepted command updates tickets and emits
`ticket_batch.resolved`.

- [ ] **Step 4: Implement churn projection and sensor**

```python
risk = min(
    1.0,
    0.08
    + sum(ep.impact_score for ep in recent_episodes) * 0.12
    + open_ticket_count * 0.08
    - min(account.total_credits / 100.0, 0.15),
)
```

Trip `sensor:churn_risk` on rising edge above 0.65.

- [ ] **Step 5: Implement `apply_retention_offer`**

Validate account, risk, offer policy, consent, duplicate active offer, value,
and authority evidence. Create `RetentionOffer`; emit
`retention_offer.issued`; record a new experience episode with negative impact
only after accepted outcome.

- [ ] **Step 6: Implement advisory agents/HITL**

Ticket agent correlates root cause and proposes auto-resolution/escalation.
Retention agents explain churn drivers and rank bounded offers. Vulnerable
customers and offers above policy reach `cs_manager_decision`.

- [ ] **Step 7: Run customer lifecycle tests**

```bash
pytest \
  tests/api/world/actor/test_telco_customer_lifecycle.py \
  tests/api/server/services/test_world_bridge_ticket_retention.py -q
```

- [ ] **Step 8: Commit**

```bash
git add verticals/telco api/functions/workflows \
  tests/api/world/actor/test_telco_customer_lifecycle.py \
  tests/api/server/services/test_world_bridge_ticket_retention.py
git commit -m "feat(telco): resolve tickets and churn risk"
```

---

### Task 7: Project graph/memory and render five operational lenses

**Files:**

- Modify: `api/server/services/entity_graph.py`
- Modify: `api/shared/kernel_assets.py`
- Create: six `verticals/telco/entity_projections/*.py`
- Modify: `verticals/telco/projections.py`
- Modify: `verticals/telco/ui.json`
- Modify: `web/shared/runtime.ts`
- Modify: `web/client/hooks/useWorldSimulation.ts`
- Modify: `web/client/routes/TelcoWorld.tsx`
- Test: `tests/api/server/services/entity_projections/test_telco_expansion_projections.py`
- Test: `tests/api/server/services/memory/test_telco_expansion_memory.py`
- Test: `web/client/routes/__tests__/TelcoWorld.expansion.test.tsx`

- [ ] **Step 1: Write failing graph schema/projection tests**

Assert the six relationship names exist and one full cascade projects:

```python
graph.link(work_order_id, "WORK_FOR_ASSET", asset_id)
graph.link(work_order_id, "ASSIGNED_TO", technician_id)
graph.link(ticket_id, "TICKET_FOR_SERVICE", subscription_id)
graph.link(offer_id, "OFFER_FOR_ACCOUNT", account_id)
assert graph.linked(work_order_id, "WORK_FOR_ASSET")[0]["node"]["id"] == asset_id
assert graph.linked(ticket_id, "TICKET_FOR_SERVICE")[0]["node"]["id"] == subscription_id
```

- [ ] **Step 2: Add typed graph relationships**

Append DDL:

```python
("ASSET_AT_SITE", "CREATE REL TABLE IF NOT EXISTS ASSET_AT_SITE (FROM Asset TO Asset, decided_at TIMESTAMP)"),
("WORK_FOR_ASSET", "CREATE REL TABLE IF NOT EXISTS WORK_FOR_ASSET (FROM Asset TO Asset, decided_at TIMESTAMP)"),
("ASSIGNED_TO", "CREATE REL TABLE IF NOT EXISTS ASSIGNED_TO (FROM Asset TO Person, decided_at TIMESTAMP)"),
("REQUIRES_SPARE", "CREATE REL TABLE IF NOT EXISTS REQUIRES_SPARE (FROM Asset TO Asset, decided_at TIMESTAMP)"),
("TICKET_FOR_SERVICE", "CREATE REL TABLE IF NOT EXISTS TICKET_FOR_SERVICE (FROM Asset TO Asset, decided_at TIMESTAMP)"),
("OFFER_FOR_ACCOUNT", "CREATE REL TABLE IF NOT EXISTS OFFER_FOR_ACCOUNT (FROM Asset TO Account, decided_at TIMESTAMP)"),
```

- [ ] **Step 3: Add six projections and operational memory**

Each projection writes Workflow, material actors, Decision nodes, typed
relationships, and source workflow provenance. Add the six workflow types to
`memory_workflow_types` through the domain-derived manifest. Memory entries
store outcome summaries keyed by asset/account/action, never raw ticks.

- [ ] **Step 4: Extend runtime/world wire types**

Add TypeScript interfaces matching snapshot fields:

```typescript
export interface WorldWorkOrder {
  id: string;
  site_id: string;
  asset_id: string;
  status: string;
  technician_id: string | null;
}

export interface WorldTechnician {
  id: string;
  region: string;
  status: string;
  assigned_work_order_id: string | null;
}
```

Add assets, weather, work orders, technicians, spares, tickets, experience,
and offers to `WorldState`. Add these hook methods:

```typescript
injectWeatherRisk(region: string, severity: number, durationMinutes: number): Promise<void>;
injectSpareShortage(region: string, partKind: string): Promise<void>;
injectTechnicianUnavailable(technicianId: string): Promise<void>;
runScenario(name: "storm-cascade" | "maintenance-save" | "capacity-revenue" | "vulnerable-retention"): Promise<void>;
```

- [ ] **Step 5: Add Field Operations lens**

Add `"field-operations"` to `KNOWN_LENSES` in
`api/shared/kernel_assets.py`, then update `ui.json`:

Update `ui.json`:

```json
"lenses": [
  "telco-network",
  "field-operations",
  "customer-impact",
  "order",
  "control"
]
```

In `TelcoWorld.tsx`, create tabs/components:

- Network: risk/health/weather/congestion overlays;
- Field: work-order lanes, technician status, spare counts;
- Customer: tickets, churn risk, offers;
- Orders: existing activation state/capacity blockers;
- Control: objectives/evaluations/workflow links/journal.

- [ ] **Step 6: Enforce real-state rendering tests**

For every rendered test ID, assert its actor ID exists in fixture snapshot or
its state transition exists in fixture journal. Add loading/error tests for
each lens. No JSON fallback counts as success.

- [ ] **Step 7: Run graph/memory/UI tests and builds**

```bash
pytest \
  tests/api/server/services/entity_projections/test_telco_expansion_projections.py \
  tests/api/server/services/memory/test_telco_expansion_memory.py -q
npx vitest run web/client/routes/__tests__/TelcoWorld.expansion.test.tsx
npx vite build
npm run build:blueprint
```

- [ ] **Step 8: Commit**

```bash
git add api/server/services/entity_graph.py verticals/telco \
  web/client web/shared tests/api/server/services \
  web/client/routes/__tests__/TelcoWorld.expansion.test.tsx
git commit -m "feat(telco): visualize interconnected operations"
```

---

### Task 8: Add four deterministic scenarios and complete live/replay proof

**Files:**

- Modify: `api/server/routes/world.py`
- Create: `tools/telco_interconnected_e2e_proof.sh`
- Create: `tools/telco_interconnected_e2e_proof.mjs`
- Create: `tests/tools/test_telco_interconnected_e2e_proof.py`
- Add: curated recordings under `verticals/telco/recordings/`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/visualisation.md`

- [ ] **Step 1: Add scenario injection contract tests**

Add endpoints:

```text
POST /api/world/scenarios/storm-cascade
POST /api/world/scenarios/maintenance-save
POST /api/world/scenarios/capacity-revenue
POST /api/world/scenarios/vulnerable-retention
```

Each returns scenario ID, root event ID, seed, and expected first sensor.

- [ ] **Step 2: Implement deterministic scenario setup**

Each method injects only exogenous state; it never emits fake workflow outcomes.
Use fixed hero actors:

```text
storm region: west
degrading asset: AST-SITE-12-radio-unit
capacity site: SITE-12
business account: ACC-00001
vulnerable account: ACC-00002
unavailable technician: TECH-WEST-05
missing spare: SPARE-west-radio-unit
```

- [ ] **Step 3: Define proof contract test**

`--print-contract` must return:

```json
{
  "workflow_types": 9,
  "scenarios": 4,
  "surfaces": ["world", "field", "customer", "orders", "control", "memory", "knowledge", "ag-ui", "constellation"],
  "requires_live_agent_smokes": 5,
  "replay_without_functions": true
}
```

- [ ] **Step 4: Implement isolated full-stack proof**

Reuse `tools/lib/actor_world_proof_stack.sh`. Use configurable non-default
ports, temporary data roots, exact-PID teardown, and condition-based waits.

The deterministic cascade run may use the fake LLM runtime only where the
spec declares safe deterministic action behavior. Separately run one live
agent smoke per reasoning skill and require visible agent/tool events. Never
turn model failure into a successful decision.

- [ ] **Step 5: Cross-check every surface**

For all nine workflow types, assert:

- canonical Workflow/objective/evaluation terminal state;
- Durable instance and typed output;
- command IDs/payload equal world journal mutations;
- expected actors exist in snapshot and DOM;
- graph/memory use same IDs and contributing traces;
- AG-UI reaches `RUN_FINISHED` or truthful `RUN_ERROR`;
- Constellation receives workflow/entity events;
- browser/page/application-network errors are empty.

- [ ] **Step 6: Record and validate replay**

Record real passing traces into `verticals/telco/recordings/`. Run replay-only
mode with Functions unreachable and actor world disabled. Require all nine
workflow types to appear.

- [ ] **Step 7: Run final verification**

```bash
pytest tests/api/world/actor tests/api/server/services tests/tools/test_telco_interconnected_e2e_proof.py -q
npx vitest run web/client web/blueprint/src
bash tools/telco_interconnected_e2e_proof.sh
git diff --check
```

Expected:

- all focused suites pass;
- live proof exits 0;
- replay proof exits 0;
- zero browser errors;
- every proof port is released;
- worktree is clean after evidence/recording commits.

- [ ] **Step 8: Commit documentation and recordings**

```bash
git add tools/telco_interconnected_e2e_proof.* \
  tests/tools/test_telco_interconnected_e2e_proof.py \
  verticals/telco/recordings docs/ARCHITECTURE.md docs/visualisation.md
git commit -m "test(telco): prove interconnected cascade"
```

---

## Completion gate

Do not call the expansion complete until:

- Telco manifest has exactly nine live workflow types;
- all six new processes mutate real actor state;
- every new process has at least two demonstrated causal links;
- prevention, failure, recovery, blocked-order, ticket, and retention outcomes
  all execute;
- process-local traces prevent cross-objective evaluation leakage;
- Agency pack remains unchanged and isolated;
- live/replay browser proof passes with zero errors;
- all changes are committed on the isolated feature branch.
