# Fashion Trading Shock Executive Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a quota-independent executive Fashion demo in which one visible trading shock causally drives all eight existing workflows, changes commercial KPIs, replays from a real substrate tape, and passes Telco-level cross-surface proof.

**Architecture:** A pack-owned `TradingShockState` models stage dependencies and synthetic executive KPIs while `FashionScenario` remains the authoritative world. The generic world bridge binds workflow IDs back to optional scenario story state. A generic React story panel renders the projection, and the existing recorder/player captures the exact live state for read-only replay.

**Tech Stack:** Python 3.11, SimPy actor world, FastAPI, Azure Durable Functions, Chroma/Mem0, React 19, TypeScript, Vitest, Playwright, Bash, Zava replay tapes.

---

## File map

### New files

- `verticals/fashion/trading_shock.py` — story state, dependency graph and KPI projection.
- `tests/api/fashion/test_trading_shock.py` — story unit and deterministic cascade tests.
- `web/client/components/world/TradingShockPanel.tsx` — generic executive briefing, KPI ribbon and journey rail.
- `web/client/components/world/__tests__/TradingShockPanel.test.tsx` — story-panel rendering and drill-in tests.
- `tools/fashion_trading_shock_video.mjs` — polished Playwright screencast.

### Modified files

- `verticals/fashion/world.py` — start, advance, bind and project the story.
- `verticals/fashion/durable.py` — carry `story_id` through typed command evidence.
- `api/server/world/service.py` — optional generic workflow-binding callback.
- `api/server/services/world_bridge.py` — bind the deterministic workflow ID after scheduling.
- `api/server/services/world_workflow_adapter.py` — write scalar-safe operational-memory metadata.
- `web/client/hooks/useWorldSimulation.ts` — typed story projection.
- `web/client/components/world/SpatialWorld.tsx` — render the story panel above the live world.
- `web/client/hooks/useResolutionStore.tsx` — retain workflow identity with a resolved action.
- `web/client/hooks/useFeedItems.ts` — recover resolved cards from stored workflow identity.
- `web/client/hooks/__tests__/useFeedItems.test.tsx` — resolved Fashion identity regression.
- `tools/fashion_zava_e2e_proof.sh` — record a real tape, capture visibility snapshots and boot true replay.
- `tools/fashion_zava_e2e_proof.mjs` — validate the connected story, all surfaces and replay.
- `tools/fashion_proof_manifest.py` — require memory, visibility and tape evidence.
- `tests/api/fashion/test_proof_contract.py` — permanent proof contract.
- `tests/tools/test_fashion_zava_e2e_proof.py` — runner and artifact assertions.

---

### Task 1: Repair operational memory

**Files:**
- Modify: `api/server/services/world_workflow_adapter.py:363-415`
- Test: `tests/api/server/services/test_world_workflow_adapter.py`

- [ ] **Step 1: Write the failing scalar-metadata test**

Add a capturing memory store and assert that no nested object reaches
`DomainMemory.add`:

```python
def test_resolved_workflow_writes_scalar_safe_operational_memory() -> None:
    captured: dict = {}

    class Memory:
        def add(self, text: str, **kwargs) -> None:
            captured["text"] = text
            captured.update(kwargs)

    state, _ = _app_state()
    state.domain_memories = {"network-incident": Memory()}
    adapter = WorldWorkflowAdapter(state)
    workflow_id = adapter.start(
        _sensor(),
        _objective(),
        resolve_responder("network_service_recovery"),
        _observation(),
    )
    workflow = state.store.get_workflow(workflow_id)
    workflow.status = "completed"
    workflow.payload.update({
        "evidence": {"digest": "sha256:42"},
        "observation": {"actor_ids": ["SITE-01"]},
    })
    state.store.upsert_workflow(workflow)

    adapter._capture_operational_memory(
        workflow,
        {"status": "resolved", "final_measurements": {"availability_pct": 94}},
    )

    metadata = captured["extra_metadata"]
    assert metadata["workflow_type"] == "network-incident"
    assert metadata["evidence_json"] == '{"digest":"sha256:42"}'
    assert metadata["observation_json"] == '{"actor_ids":["SKU-42"]}'
    assert metadata["outcome_json"].startswith('{"final_measurements"')
    assert all(isinstance(value, (str, int, float, bool)) for value in metadata.values())
    assert workflow_id in captured["text"]
```

- [ ] **Step 2: Run the test and confirm the Chroma-shape failure**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/server/services/test_world_workflow_adapter.py::test_resolved_workflow_writes_scalar_safe_operational_memory -q
```

Expected: FAIL because `evidence`, `observation` and `outcome` are dictionaries.

- [ ] **Step 3: Add one scalar-normalisation helper**

Add:

```python
def _memory_metadata_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
```

Replace the nested metadata fields with:

```python
extra_metadata={
    "source": "world_outcome_evaluator",
    "evidence_event_type": str(evidence_kind),
    "workflow_type": str(workflow.type),
    "workflow_status": str(workflow.status),
    "evidence_json": _memory_metadata_json(evidence),
    "observation_json": _memory_metadata_json(observation),
    "outcome_json": _memory_metadata_json(outcome),
},
```

Do not catch or reshape the top-level `workflow_id`; `DomainMemory.add` already
stores it as structured metadata.

- [ ] **Step 4: Run focused memory tests**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/server/services/test_world_workflow_adapter.py \
  tests/api/fashion/test_mcp_and_projections.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the memory repair**

```bash
git add api/server/services/world_workflow_adapter.py \
  tests/api/server/services/test_world_workflow_adapter.py
git commit -m "fix(memory): preserve workflow evidence"
```

---

### Task 2: Add the pack-owned Trading Shock model

**Files:**
- Create: `verticals/fashion/trading_shock.py`
- Create: `tests/api/fashion/test_trading_shock.py`

- [ ] **Step 1: Write failing dependency and identity tests**

```python
from verticals.fashion.trading_shock import TradingShockState


def test_trading_shock_starts_with_two_causal_root_stages() -> None:
    story = TradingShockState(seed=42)

    story.start(
        cause_event_id="evt-shock",
        trace_id="fashion-trading-shock-42",
        sim_time=54.0,
        baseline={"availability_pct": 61.0, "projected_lost_sales_gbp": 48_000.0},
    )

    assert story.id == "fashion-trading-shock-42"
    assert story.ready_to_trigger() == (
        "demand-spike-response",
        "inventory-rebalancing",
    )
    assert story.view()["status"] == "running"


def test_trading_shock_unlocks_only_satisfied_dependencies() -> None:
    story = TradingShockState(seed=42)
    story.start(
        cause_event_id="evt-shock",
        trace_id="fashion-trading-shock-42",
        sim_time=54.0,
        baseline={},
    )
    story.mark_triggered("demand-spike-response", "evt-demand")
    story.mark_triggered("inventory-rebalancing", "evt-stock")

    story.complete("demand-spike-response", workflow_id="demand-1")
    assert story.ready_to_trigger() == (
        "supplier-delay-recovery",
        "marketplace-seller-exception",
    )
    story.mark_triggered("supplier-delay-recovery", "evt-supplier")
    story.mark_triggered("marketplace-seller-exception", "evt-seller")

    story.complete("inventory-rebalancing", workflow_id="rebalance-1")
    assert story.ready_to_trigger() == (
        "promotion-readiness",
        "markdown-governance",
    )


def test_story_fails_dependants_without_reporting_success() -> None:
    story = TradingShockState(seed=42)
    story.start(
        cause_event_id="evt-shock",
        trace_id="fashion-trading-shock-42",
        sim_time=54.0,
        baseline={},
    )

    story.fail("inventory-rebalancing", workflow_id="rebalance-1", reason="rejected")

    assert story.status == "failed"
    assert story.view()["failure"]["reason"] == "rejected"
```

- [ ] **Step 2: Run tests and verify the module is absent**

Run:

```bash
uv run --frozen --no-sync pytest tests/api/fashion/test_trading_shock.py -q
```

Expected: collection FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement focused story state**

Create:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


STAGE_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "demand-spike-response": (),
    "inventory-rebalancing": (),
    "promotion-readiness": ("demand-spike-response", "inventory-rebalancing"),
    "supplier-delay-recovery": ("demand-spike-response",),
    "marketplace-seller-exception": ("demand-spike-response",),
    "fulfilment-exception-resolution": (
        "inventory-rebalancing",
        "supplier-delay-recovery",
        "marketplace-seller-exception",
    ),
    "markdown-governance": ("inventory-rebalancing",),
    "returns-disposition": (
        "promotion-readiness",
        "fulfilment-exception-resolution",
    ),
}


@dataclass(slots=True)
class StoryStage:
    workflow_type: str
    dependency_ids: tuple[str, ...]
    status: str = "waiting"
    sensor_event_id: str | None = None
    workflow_id: str | None = None
    autonomy: str = "human-approved"
    reason: str | None = None


@dataclass(slots=True)
class TradingShockState:
    seed: int
    id: str | None = None
    status: str = "idle"
    cause_event_id: str | None = None
    started_at_sim_time: float | None = None
    baseline: dict[str, float] = field(default_factory=dict)
    outcome: dict[str, float] = field(default_factory=dict)
    stages: dict[str, StoryStage] = field(default_factory=lambda: {
        workflow_type: StoryStage(workflow_type, dependencies)
        for workflow_type, dependencies in STAGE_DEPENDENCIES.items()
    })
    failure: dict[str, str] | None = None

    def start(
        self,
        *,
        cause_event_id: str,
        trace_id: str,
        sim_time: float,
        baseline: dict[str, float],
    ) -> None:
        if self.status != "idle":
            return
        self.id = trace_id
        self.status = "running"
        self.cause_event_id = cause_event_id
        self.started_at_sim_time = sim_time
        self.baseline = dict(baseline)

    def ready_to_trigger(self) -> tuple[str, ...]:
        completed = {
            name for name, stage in self.stages.items()
            if stage.status == "completed"
        }
        return tuple(
            name for name, stage in self.stages.items()
            if stage.status == "waiting"
            and all(dependency in completed for dependency in stage.dependency_ids)
        )

    def mark_triggered(self, workflow_type: str, event_id: str) -> None:
        stage = self.stages[workflow_type]
        stage.status = "triggered"
        stage.sensor_event_id = event_id

    def bind_workflow(self, workflow_type: str, workflow_id: str) -> None:
        stage = self.stages[workflow_type]
        stage.workflow_id = workflow_id
        stage.status = "active"

    def complete(self, workflow_type: str, *, workflow_id: str) -> None:
        stage = self.stages[workflow_type]
        stage.workflow_id = workflow_id
        stage.status = "completed"
        if all(item.status == "completed" for item in self.stages.values()):
            self.status = "completed"

    def fail(self, workflow_type: str, *, workflow_id: str, reason: str) -> None:
        stage = self.stages[workflow_type]
        stage.workflow_id = workflow_id
        stage.status = "failed"
        stage.reason = reason
        self.status = "failed"
        self.failure = {"workflow_type": workflow_type, "reason": reason}

    def view(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "trading-shock",
            "title": "The viral summer drop",
            "status": self.status,
            "cause_event_id": self.cause_event_id,
            "started_at_sim_time": self.started_at_sim_time,
            "stages": [
                {
                    "workflow_type": stage.workflow_type,
                    "workflow_id": stage.workflow_id,
                    "status": stage.status,
                    "dependency_ids": list(stage.dependency_ids),
                    "autonomy": stage.autonomy,
                    "reason": stage.reason,
                }
                for stage in self.stages.values()
            ],
            "kpis": {
                key: {"before": value, "after": self.outcome.get(key)}
                for key, value in self.baseline.items()
            },
            "failure": self.failure,
        }
```

- [ ] **Step 4: Run story tests**

Run:

```bash
uv run --frozen --no-sync pytest tests/api/fashion/test_trading_shock.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the story model**

```bash
git add verticals/fashion/trading_shock.py tests/api/fashion/test_trading_shock.py
git commit -m "feat(fashion): model trading shock story"
```

---

### Task 3: Drive all eight workflows from the causal world

**Files:**
- Modify: `verticals/fashion/world.py:82-118,486-560,595-617,728-846,909-938`
- Modify: `verticals/fashion/durable.py:96-178`
- Modify: `api/server/world/service.py`
- Modify: `api/server/services/world_bridge.py:396-403`
- Test: `tests/api/fashion/test_living_world.py`
- Test: `tests/api/server/services/test_world_bridge_actor.py`

- [ ] **Step 1: Write a failing connected-cascade world test**

Add:

```python
def test_trading_shock_emits_only_ready_story_sensors() -> None:
    runtime, scenario = _scenario()
    runtime.run_until(60)

    story = scenario.render_state()["story"]
    assert story["id"] == "fashion-trading-shock-42"
    assert {
        event.payload["workflow_type"]
        for event in runtime.journal
        if event.type == "sensor.tripped"
        and event.payload.get("story_id") == story["id"]
    } == {"demand-spike-response", "inventory-rebalancing"}


def test_completed_story_commands_unlock_all_eight_workflows() -> None:
    runtime, scenario = _scenario()
    runtime.run_until(60)
    story_id = scenario.trading_shock.id

    for workflow_type in (
        "demand-spike-response",
        "inventory-rebalancing",
        "supplier-delay-recovery",
        "marketplace-seller-exception",
        "promotion-readiness",
        "markdown-governance",
        "fulfilment-exception-resolution",
        "returns-disposition",
    ):
        stage = scenario.trading_shock.stages[workflow_type]
        if stage.status == "waiting":
            scenario.emit_ready_story_stages()
            stage = scenario.trading_shock.stages[workflow_type]
        scenario.bind_story_workflow(
            {
                "payload": {
                    "story_id": story_id,
                    "workflow_type": workflow_type,
                }
            },
            f"{workflow_type}-wf",
        )
        scenario.complete_story_stage(
            workflow_type,
            workflow_id=f"{workflow_type}-wf",
            cause_event_id=stage.sensor_event_id,
        )

    story = scenario.render_state()["story"]
    assert story["status"] == "completed"
    assert {stage["workflow_type"] for stage in story["stages"]} == set(
        FASHION_PROCESS_PROFILES
    )
    assert all(stage["workflow_id"] for stage in story["stages"])
```

- [ ] **Step 2: Write a failing bridge workflow-binding test**

Add to `tests/api/server/services/test_world_bridge_actor.py`. Extend
`FakeWorld` with a `bind_workflow` capture and assert it receives the scheduled
identity:

```python
async def test_bridge_binds_scheduled_workflow_to_optional_story_scenario(
    monkeypatch,
) -> None:
    state = app_state()
    state.world_service.bound = []
    state.world_service.bind_workflow = (
        lambda sensor_event, workflow_id:
        state.world_service.bound.append((sensor_event, workflow_id))
    )
    bridge = WorldBridge(state)
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration",
        AsyncMock(return_value={"id": "durable-1", "statusQueryGetUri": "status://1"}),
    )
    bridge._await_output = AsyncMock(return_value={"command": None, "reasoning": "stop"})
    bridge.start()
    event = sensor()
    state.bus.emit(event)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert state.world_service.bound == [
        (event.simulation_event, "surge-evt-sensor")
    ]
```

- [ ] **Step 3: Run the tests and confirm story integration is missing**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/fashion/test_living_world.py \
  tests/api/server/services/test_world_bridge_actor.py -q
```

Expected: FAIL on missing story methods and bridge callback.

- [ ] **Step 4: Integrate story state into `FashionScenario`**

In `__init__`:

```python
self.trading_shock = TradingShockState(seed=runtime.seed)
```

Add helpers:

```python
def _executive_kpis(self) -> dict[str, float]:
    destination = self.inventory[(DESTINATION_LOCATION, HERO_SKU)]
    completed = {
        name for name, case in self.process_cases.items()
        if case.status == "completed"
    }
    return {
        "availability_pct": min(
            100.0,
            round((destination.available / max(destination.safety_stock, 1)) * 100, 1),
        ),
        "projected_lost_sales_gbp": float(
            max(0, (12 - destination.available)) * destination.retail_price_gbp
        ),
        "full_price_sell_through_pct": 68.0 + (8.0 if "promotion-readiness" in completed else 0.0),
        "fulfilment_success_pct": 91.0 + (6.0 if "fulfilment-exception-resolution" in completed else 0.0),
        "markdown_exposure_gbp": 62_000.0 - (21_000.0 if "markdown-governance" in completed else 0.0),
        "recovery_value_gbp": 14_500.0 if "returns-disposition" in completed else 0.0,
    }

def _emit_story_sensor(
    self,
    workflow_type: str,
    *,
    cause_event_id: str,
) -> SimulationEvent:
    profile = FASHION_PROCESS_PROFILES[workflow_type]
    case = self.process_cases[workflow_type]
    event = self.runtime.emit(
        "sensor.tripped",
        actor_id=profile.sensor_id,
        target_id=case.subject_ids[0],
        cause_event_id=cause_event_id,
        trace_id=self.trading_shock.id,
        payload={
            "workflow_type": workflow_type,
            "case_id": case.id,
            "story_id": self.trading_shock.id,
            "diagnostic": False,
            "measurements": {"risk_score": float(case.facts.get("risk_score") or 0.75)},
        },
    )
    self.trading_shock.mark_triggered(workflow_type, event.event_id)
    return event

def emit_ready_story_stages(self, *, cause_event_id: str | None = None) -> None:
    cause = cause_event_id or self.trading_shock.cause_event_id
    if not cause:
        return
    for workflow_type in self.trading_shock.ready_to_trigger():
        self._emit_story_sensor(workflow_type, cause_event_id=cause)

def bind_story_workflow(self, sensor_event: dict[str, Any], workflow_id: str) -> None:
    payload = sensor_event.get("payload") or {}
    if payload.get("story_id") != self.trading_shock.id:
        return
    self.trading_shock.bind_workflow(str(payload["workflow_type"]), workflow_id)

def complete_story_stage(
    self,
    workflow_type: str,
    *,
    workflow_id: str,
    cause_event_id: str | None,
) -> None:
    self.trading_shock.complete(workflow_type, workflow_id=workflow_id)
    self.trading_shock.outcome = self._executive_kpis()
    self.emit_ready_story_stages(cause_event_id=cause_event_id)
```

When the inventory threshold crosses, emit
`retail.trading-shock.detected`, initialise the baseline, then emit the two root
story sensors. Do not call the old standalone inventory sensor in addition.

- [ ] **Step 5: Carry story identity through observations and commands**

In `build_observation` add:

```python
story_id = (sensor_event.get("payload") or {}).get("story_id")
if story_id:
    observation["story_id"] = story_id
```

In `fashion_command_activity`, add `story_id` to both command payload shapes:

```python
"story_id": observation.get("story_id"),
```

After an accepted command and real success event, call
`complete_story_stage` using the command's `workflow_id` and emitted success
event ID.

- [ ] **Step 6: Add a generic optional binding seam**

In `ActorWorldService`:

```python
def bind_workflow(self, sensor_event: dict, workflow_id: str) -> None:
    bind = getattr(self.scenario, "bind_story_workflow", None)
    if callable(bind):
        bind(sensor_event, workflow_id)

def fail_workflow(self, workflow_id: str, reason: str) -> None:
    fail = getattr(self.scenario, "fail_story_workflow", None)
    if callable(fail):
        fail(workflow_id, reason)
```

In `WorldBridge._drive`, immediately after `_adapter.start(...)`:

```python
service.bind_workflow(simulation_event, workflow_id)
```

Before every bridge-side `adapter.failed(...)` call made after a workflow ID
exists, call:

```python
service.fail_workflow(workflow_id, reason)
```

`FashionScenario.fail_story_workflow` resolves the stage by workflow ID and
calls `TradingShockState.fail`. No vertical-name branch is allowed.

- [ ] **Step 7: Project story state**

Add to `FashionScenario.render_state()`:

```python
"story": self.trading_shock.view(),
```

- [ ] **Step 8: Run world and bridge tests**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/fashion/test_living_world.py \
  tests/api/fashion/test_durable_workflows.py \
  tests/api/server/services/test_world_bridge_actor.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit the causal cascade**

```bash
git add verticals/fashion/world.py verticals/fashion/durable.py \
  api/server/world/service.py api/server/services/world_bridge.py \
  tests/api/fashion/test_living_world.py \
  tests/api/server/services/test_world_bridge_actor.py
git commit -m "feat(fashion): connect trading shock workflows"
```

---

### Task 4: Produce canonical quota-free reasoning rows

**Files:**
- Create: `api/functions/graphs/executors/agents/runtime_deterministic.py`
- Modify: `api/functions/graphs/executors/agents/runtime.py:58-72`
- Modify: `verticals/fashion/mcp_tools/retail.py`
- Modify: `verticals/fashion/durable.py:51-88`
- Test: `tests/api/functions/graphs/executors/agents/test_runtime_deterministic.py`
- Test: `tests/api/fashion/test_durable_workflows.py`

- [ ] **Step 1: Write a failing deterministic-runtime test**

```python
import json

from api.functions.graphs.executors.agents.runtime_deterministic import (
    DeterministicRuntime,
)


async def test_deterministic_runtime_returns_the_prompt_contract() -> None:
    expected = {"recommendation": "inventory.transfer", "reasoning": "bounded"}
    runtime = DeterministicRuntime()

    result = await runtime.run_session(
        prompt=(
            "Assess the supplied evidence.\n"
            "<deterministic-response>"
            f"{json.dumps(expected, sort_keys=True)}"
            "</deterministic-response>"
        ),
        model="deterministic-fashion-v1",
    )

    assert json.loads(result.text) == expected
    assert result.tool_calls == []
    assert result.input_tokens is not None
    assert result.output_tokens is not None
```

- [ ] **Step 2: Run and confirm the provider is absent**

```bash
uv run --frozen --no-sync pytest \
  tests/api/functions/graphs/executors/agents/test_runtime_deterministic.py -q
```

Expected: collection FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the provider**

Create an `LLMRuntime` implementation that:

- requires exactly one `<deterministic-response>...</deterministic-response>`
  block
- parses the block as a JSON object
- returns canonical compact JSON in `LLMRuntimeResult.text`
- estimates input/output tokens from character counts
- rejects missing, duplicate or non-object response blocks
- never invokes a network or tool itself

Add this runtime branch:

```python
if name == "deterministic":
    from api.functions.graphs.executors.agents.runtime_deterministic import (
        DeterministicRuntime,
    )
    return DeterministicRuntime()
```

Update the error message to list `deterministic`.

- [ ] **Step 4: Add a Fashion MCP tool registry**

In `verticals/fashion/mcp_tools/retail.py`:

```python
TOOL_BY_NAME = {
    "fashion_read_inventory": fashion_read_inventory,
    "fashion_prepare_inventory_transfer": fashion_prepare_inventory_transfer,
    "fashion_assess_promotion": fashion_assess_promotion,
    "fashion_prepare_markdown_recommendation": fashion_prepare_markdown_recommendation,
    "fashion_prepare_supplier_recovery": fashion_prepare_supplier_recovery,
    "fashion_prepare_fulfilment_resolution": fashion_prepare_fulfilment_resolution,
    "fashion_prepare_seller_suppression": fashion_prepare_seller_suppression,
    "fashion_prepare_return_disposition": fashion_prepare_return_disposition,
}
```

- [ ] **Step 5: Route Fashion agent phases through `run_agent_session`**

Keep the existing deterministic decision builder as the validated fallback.
Add:

```python
async def run_agent_session(prompt: str, **kwargs) -> dict[str, Any]:
    from api.functions.graphs.executors.agents._wrapper import (
        run_agent_session as run,
    )
    return await run(prompt, **kwargs)


async def _session_decision(payload: dict[str, Any]) -> dict[str, Any]:
    deterministic = fashion_decision_activity_deterministic(payload)
    skill = str(payload["skill"])
    tool_name = FASHION_AGENTS[skill].allowed_tools[0]
    prompt = (
        "Return one JSON object only. Do not invent actor or event IDs.\n"
        f"workflow_type={payload['type']}\n"
        f"skill={skill}\n"
        f"observation={json.dumps(payload['observation'], sort_keys=True)}\n"
    )
    if os.environ.get("LLM_RUNTIME", "ghcp") == "deterministic":
        prompt += (
            "<deterministic-response>"
            f"{json.dumps(deterministic, sort_keys=True)}"
            "</deterministic-response>"
        )
    return await run_agent_session(
        prompt,
        tools=[TOOL_BY_NAME[tool_name]],
        skill_dir=PACK_ROOT / "skills" / skill,
        skill_label=skill,
        workflow_id=payload.get("workflow_id"),
        instance_id=payload.get("instance_id"),
        phase=payload.get("phase"),
        model=(
            "deterministic-fashion-v1"
            if os.environ.get("LLM_RUNTIME") == "deterministic"
            else os.environ.get("ZAVA_FASHION_MODEL", "gpt-5.4-mini")
        ),
    )
```

`fashion_decision_activity` supports:

- `ZAVA_FASHION_AGENT_MODE=session` — use `run_agent_session`
- `ZAVA_FASHION_AGENT_MODE=deterministic` — retain the current explicitly
  deterministic activity for emergency live fallback

Permanent proof sets:

```bash
ZAVA_FASHION_AGENT_MODE=session
LLM_RUNTIME=deterministic
```

This creates canonical reasoning rows through the real wrapper without a model
or quota dependency. A release tape may instead set `LLM_RUNTIME=aoai` or
`ghcp` once, then replay the captured evidence without further calls.

- [ ] **Step 6: Test canonical session invocation**

Monkeypatch `run_agent_session` and assert the activity passes the exact
workflow ID, phase, skill directory and allowed tool. Also retain one test for
the emergency deterministic mode.

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/functions/graphs/executors/agents/test_runtime_deterministic.py \
  tests/api/fashion/test_durable_workflows.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit canonical reasoning**

```bash
git add api/functions/graphs/executors/agents/runtime.py \
  api/functions/graphs/executors/agents/runtime_deterministic.py \
  verticals/fashion/mcp_tools/retail.py \
  verticals/fashion/durable.py \
  tests/api/functions/graphs/executors/agents/test_runtime_deterministic.py \
  tests/api/fashion/test_durable_workflows.py
git commit -m "feat(fashion): record deterministic reasoning"
```

---

### Task 5: Render the executive briefing and journey rail

**Files:**
- Create: `web/client/components/world/TradingShockPanel.tsx`
- Create: `web/client/components/world/__tests__/TradingShockPanel.test.tsx`
- Modify: `web/client/hooks/useWorldSimulation.ts:246-289`
- Modify: `web/client/components/world/SpatialWorld.tsx:154-240`

- [ ] **Step 1: Add failing component tests**

```tsx
it("shows commercial risk, KPI movement and all story stages", () => {
  render(
    <MemoryRouter>
      <TradingShockPanel story={storyFixture} />
    </MemoryRouter>,
  );
  expect(screen.getByText("The viral summer drop")).toBeTruthy();
  expect(screen.getByText("GBP 48,000")).toBeTruthy();
  expect(screen.getByText("GBP 9,000")).toBeTruthy();
  expect(screen.getAllByTestId(/^story-stage-/)).toHaveLength(8);
});

it("links a bound stage to its exact workflow", () => {
  render(
    <MemoryRouter>
      <TradingShockPanel story={storyFixture} />
    </MemoryRouter>,
  );
  expect(
    screen.getByRole("link", { name: /inventory rebalancing/i }).getAttribute("href"),
  ).toBe("/workflows/rebalance-evt-42");
});

it("does not claim success when a required stage failed", () => {
  render(
    <MemoryRouter>
      <TradingShockPanel story={{ ...storyFixture, status: "failed" }} />
    </MemoryRouter>,
  );
  expect(screen.getByRole("alert").textContent).toContain("Story interrupted");
});
```

- [ ] **Step 2: Run and confirm the component is absent**

Run:

```bash
npx vitest run \
  web/client/components/world/__tests__/TradingShockPanel.test.tsx
```

Expected: FAIL with unresolved component import.

- [ ] **Step 3: Add typed story interfaces**

In `useWorldSimulation.ts`:

```ts
export interface WorldStoryStage {
  workflow_type: string;
  workflow_id: string | null;
  status: "waiting" | "triggered" | "active" | "completed" | "failed";
  dependency_ids: string[];
  autonomy: "autonomous" | "policy-safe" | "human-approved";
  reason: string | null;
}

export interface WorldStoryKpi {
  before: number;
  after: number | null;
}

export interface WorldStory {
  id: string;
  type: string;
  title: string;
  status: "idle" | "running" | "completed" | "failed";
  cause_event_id: string;
  started_at_sim_time: number;
  stages: WorldStoryStage[];
  kpis: Record<string, WorldStoryKpi>;
  failure: { workflow_type: string; reason: string } | null;
}
```

Add `story?: WorldStory` to `WorldState`.

- [ ] **Step 4: Implement the generic panel**

The component must:

- render nothing when `story.status === "idle"`
- format GBP values with `Intl.NumberFormat`
- humanise workflow and KPI slugs
- render a before → after KPI ribbon
- render stage dependencies and autonomy
- use `<Link>` only when `workflow_id` exists
- expose `data-testid="story-stage-<workflow_type>"`

Use this shape:

```tsx
export default function TradingShockPanel({ story }: { story: WorldStory }) {
  if (story.status === "idle") return null;
  return (
    <section aria-label="Executive trading story" className="rounded-xl border ...">
      <header>
        <p className="text-xs uppercase tracking-wide">Executive briefing</p>
        <h2>{story.title}</h2>
        <p>Demand accelerated while stock, supplier and seller conditions diverged.</p>
      </header>
      {story.status === "failed" && (
        <div role="alert">Story interrupted · {story.failure?.reason}</div>
      )}
      <div aria-label="Commercial KPI movement">{/* KPI cards */}</div>
      <ol aria-label="Causal workflow journey">{/* eight stages */}</ol>
    </section>
  );
}
```

- [ ] **Step 5: Mount the panel above the spatial map**

In `SpatialWorld.tsx`, after the header and error:

```tsx
{state.story && <TradingShockPanel story={state.story} />}
```

- [ ] **Step 6: Run component and world tests**

Run:

```bash
npx vitest run \
  web/client/components/world/__tests__/TradingShockPanel.test.tsx \
  web/client/components/world/__tests__/SpatialWorld.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit the executive UI**

```bash
git add web/client/components/world/TradingShockPanel.tsx \
  web/client/components/world/__tests__/TradingShockPanel.test.tsx \
  web/client/components/world/SpatialWorld.tsx \
  web/client/hooks/useWorldSimulation.ts
git commit -m "feat(fashion): add executive story view"
```

---

### Task 6: Preserve workflow identity on resolved cards

**Files:**
- Modify: `web/client/hooks/useResolutionStore.tsx`
- Modify: `web/client/hooks/useFeedItems.ts`
- Modify: all resolution call sites returned by:
  `rg 'store\\.record\\(' web/client -n`
- Test: `web/client/hooks/__tests__/useFeedItems.test.tsx`
- Test: `web/client/components/feed/__tests__/cards/ResolvedCard.test.tsx`

- [ ] **Step 1: Write the failing orphan-resolution identity test**

```tsx
it("retains the workflow id after the live exception leaves the stream", () => {
  resolutionStore.record("exception:EXC-42", {
    verb: "Approved",
    actor: "you",
    actedAt: 100,
    workflowId: "rebalance-evt-42",
    domain: "inventory-rebalancing",
  });

  const items = renderHook(() => useFeedItems({
    workflows: [completedFashionWorkflow],
    exceptions: [],
    events: [],
  })).result.current;

  const resolved = items.find((item) => item.type === "resolved");
  expect(resolved?.workflowId).toBe("rebalance-evt-42");
  expect(resolved?.domain).toBe("inventory-rebalancing");
});
```

- [ ] **Step 2: Run and verify the test produces the em-dash regression**

Run:

```bash
npx vitest run \
  web/client/hooks/__tests__/useFeedItems.test.tsx \
  web/client/components/feed/__tests__/cards/ResolvedCard.test.tsx
```

Expected: FAIL because the persisted resolution has no workflow identity.

- [ ] **Step 3: Extend the resolution record**

Add:

```ts
interface ResolutionRecord {
  verb: string;
  actor: string;
  actedAt: number;
  undoable?: boolean;
  workflowId?: string;
  domain?: string;
}
```

Every HITL/exception/external-wait resolution call must pass the current
`workflowId` and `domain`.

- [ ] **Step 4: Use stored identity for orphan cards**

Replace:

```ts
workflowId: wf?.id,
domain: wf?.type,
```

with:

```ts
workflowId: r.workflowId ?? wf?.id,
domain: r.domain ?? wf?.type,
```

- [ ] **Step 5: Run feed tests**

Run:

```bash
npx vitest run \
  web/client/hooks/__tests__/useFeedItems.test.tsx \
  web/client/components/feed/__tests__/cards/ResolvedCard.test.tsx \
  web/client/components/feed/__tests__/integration.test.tsx
```

Expected: PASS and no resolved Fashion card renders `—`.

- [ ] **Step 6: Commit identity persistence**

```bash
git add web/client/hooks/useResolutionStore.tsx \
  web/client/hooks/useFeedItems.ts \
  web/client/hooks/__tests__/useFeedItems.test.tsx \
  web/client/components/feed
git commit -m "fix(feed): retain resolved workflow identity"
```

---

### Task 7: Record and replay the real Fashion story

**Files:**
- Modify: `tools/fashion_zava_e2e_proof.sh`
- Test: `tests/tools/test_fashion_zava_e2e_proof.py`

- [ ] **Step 1: Add failing tape-contract tests**

```python
def test_fashion_proof_records_and_replays_a_real_tape() -> None:
    script = PROOF_SCRIPT.read_text(encoding="utf-8")
    assert "ZAVA_RECORD_TO" in script
    assert "fashion-trading-shock.tar.gz" in script
    assert "ZAVA_MODE=replay" in script
    assert "ZAVA_TAPE_PATH" in script
    assert "workflow_visibility_proof.py" in script


def test_fashion_proof_does_not_label_blueprint_only_mode_as_replay() -> None:
    script = PROOF_SCRIPT.read_text(encoding="utf-8")
    assert "ZAVA_BLUEPRINT_REPLAY_ONLY" not in script
```

- [ ] **Step 2: Run and confirm the current degraded replay fails the contract**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/tools/test_fashion_zava_e2e_proof.py -q
```

Expected: FAIL because the current runner uses `ZAVA_BLUEPRINT_REPLAY_ONLY`.

- [ ] **Step 3: Add tape and visibility paths**

At the top of the runner:

```bash
STORY_PROOF_DIR="$PROOF_DIR/fashion-trading-shock"
TAPE_PATH="$STORY_PROOF_DIR/fashion-trading-shock.tar.gz"
LIVE_DETAILS="$STORY_PROOF_DIR/workflow-details/live"
REPLAY_DETAILS="$STORY_PROOF_DIR/workflow-details/replay"
```

Before live FastAPI starts:

```bash
export ZAVA_RECORD_TO="$TAPE_PATH"
export ZAVA_RECORD_WARMUP_S=1
export ZAVA_APP_SHA="$(git rev-parse --short HEAD)"
export ZAVA_FASHION_AGENT_MODE=session
export LLM_RUNTIME=deterministic
```

The Fashion world naturally crosses its threshold after the recorder arms.
Keep the existing Playwright/HITL proof active until all eight workflows and the
story are terminal.

- [ ] **Step 4: Capture live visibility before teardown**

Run inside the live phase:

```bash
ZAVA_VERTICAL=fashion \
  .venv/bin/python tools/workflow_visibility_proof.py \
  --vertical fashion \
  --base-url "http://127.0.0.1:$API_PORT" \
  --save-dir "$LIVE_DETAILS"
```

Expected: PASS and eight JSON snapshots.

- [ ] **Step 5: Finalise the tape through graceful API shutdown**

Terminate the live FastAPI PID with `kill_tree` and wait until:

```bash
test -s "$TAPE_PATH"
```

Do not use SIGKILL before the FastAPI lifespan has packed the tape. If packing
fails, the proof exits non-zero.

- [ ] **Step 6: Start true replay**

Replace the replay API environment with:

```bash
ZAVA_VERTICAL=fashion \
ZAVA_MODE=replay \
ZAVA_TAPE_PATH="$TAPE_PATH" \
ENTITY_PLANE_ENABLED=0 \
SIMULATOR_RAMP_ENABLED=0 \
uv run --frozen --no-sync uvicorn api.server.main:app \
  --host 127.0.0.1 --port "$API_PORT"
```

Assert `/api/replay/meta` reports replay mode and the expected tape ID.

- [ ] **Step 7: Capture and compare replay visibility**

```bash
ZAVA_VERTICAL=fashion \
  .venv/bin/python tools/workflow_visibility_proof.py \
  --vertical fashion \
  --base-url "http://127.0.0.1:$API_PORT" \
  --compare-dir "$LIVE_DETAILS" \
  --save-dir "$REPLAY_DETAILS"
```

Expected: PASS for the same eight workflow IDs.

- [ ] **Step 8: Run runner contract tests**

```bash
uv run --frozen --no-sync pytest \
  tests/tools/test_fashion_zava_e2e_proof.py \
  tests/tools/test_workflow_visibility_proof.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit true replay support**

```bash
git add tools/fashion_zava_e2e_proof.sh \
  tests/tools/test_fashion_zava_e2e_proof.py
git commit -m "feat(fashion): record trading shock replay"
```

---

### Task 8: Strengthen the Fashion Playwright proof and manifest

**Files:**
- Modify: `tools/fashion_zava_e2e_proof.mjs`
- Modify: `tools/fashion_proof_manifest.py`
- Modify: `tests/api/fashion/test_proof_contract.py`
- Modify: `tests/tools/test_fashion_zava_e2e_proof.py`

- [ ] **Step 1: Write failing proof-contract assertions**

The exported contract must include:

```python
assert contract["story"] == "fashion-trading-shock"
assert contract["surfaces"] == [
    "world",
    "workflow-api",
    "drawer",
    "memory",
    "knowledge",
    "ag-ui",
    "graph",
    "constellation",
]
assert contract["evidence"] >= {
    "fashion-trading-shock.tar.gz",
    "memory.json",
    "workflow-details/live",
    "workflow-details/replay",
    "executive-video.mp4",
}
```

- [ ] **Step 2: Run and verify the reduced current contract fails**

Run:

```bash
uv run --frozen --no-sync pytest \
  tests/api/fashion/test_proof_contract.py \
  tests/tools/test_fashion_zava_e2e_proof.py -q
```

Expected: FAIL on missing story, memory and visibility evidence.

- [ ] **Step 3: Validate the connected story in live mode**

In the Playwright driver:

- capture baseline before `retail.trading-shock.detected`
- wait for `state.story.status === "completed"`
- assert eight distinct stage workflow IDs
- assert every stage is `completed`
- assert each KPI has a non-null `after` value
- assert lost sales and markdown exposure decrease
- assert availability, sell-through, fulfilment and recovery value increase

Write `story-evidence.json`.

- [ ] **Step 4: Restore all cross-surface gates**

For every story workflow ID:

```js
const memories = await getJson(
  `/api/memory/v2/memories?domain=${encodeURIComponent(workflow.type)}`,
);
need(
  workflowMemoryIdMatched(memories.memories || [], workflow.id),
  `memory omitted exact workflow ${workflow.id}`,
);

const entity = await getJson(`/api/entities/${encodeURIComponent(workflow.id)}`);
need(entity.id === workflow.id, `Knowledge omitted ${workflow.id}`);

const agui = await collectAgui(workflow.id);
need(agui.includes("RUN_FINISHED"), `AG-UI omitted terminal frame for ${workflow.id}`);

await page.goto(`${CONTROL_PLANE}/workflows/${encodeURIComponent(workflow.id)}`);
await page.getByText(workflow.id, { exact: false }).first().waitFor();
await page.getByText("Workflow completed", { exact: false }).waitFor();
```

Write `memory.json`, `entity-graph.json`, `agui-evidence/` and browser
screenshots.

- [ ] **Step 5: Validate true replay**

Replay must:

- report `mode: replay`
- reject a representative POST with 403
- show the same completed story and KPI projection
- expose the same eight workflow IDs
- expose eight exact memories and Knowledge nodes
- produce zero browser errors and zero dropped workflow events

- [ ] **Step 6: Harden the manifest**

`build_manifest` must require:

```python
required = (
    proof_dir / "fashion-trading-shock" / "fashion-trading-shock.tar.gz",
    proof_dir / "fashion-trading-shock" / "memory.json",
    proof_dir / "fashion-trading-shock" / "story-evidence.json",
    proof_dir / "fashion-trading-shock" / "workflow-details" / "live",
    proof_dir / "fashion-trading-shock" / "workflow-details" / "replay",
)
```

`permanent_result` is PASS only when source is clean, source commit matches,
live passes, real replay passes, visibility comparison passes, memory has eight
exact matches, browser errors are empty and teardown is clean.

- [ ] **Step 7: Run proof-unit tests**

```bash
uv run --frozen --no-sync pytest \
  tests/api/fashion/test_proof_contract.py \
  tests/tools/test_fashion_zava_e2e_proof.py \
  tests/tools/test_workflow_visibility_proof.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit proof hardening**

```bash
git add tools/fashion_zava_e2e_proof.mjs \
  tools/fashion_proof_manifest.py \
  tests/api/fashion/test_proof_contract.py \
  tests/tools/test_fashion_zava_e2e_proof.py
git commit -m "test(fashion): prove live replay parity"
```

---

### Task 9: Produce the permanent executive walkthrough

**Files:**
- Create: `tools/fashion_trading_shock_video.mjs`
- Modify: `tools/fashion_zava_e2e_proof.sh`
- Test: `tests/tools/test_fashion_zava_e2e_proof.py`

- [ ] **Step 1: Add the video artifact contract**

```python
def test_fashion_proof_requires_executive_video() -> None:
    contract = json.loads(
        subprocess.check_output(
            ["node", "tools/fashion_zava_e2e_proof.mjs", "--print-contract"],
            text=True,
        )
    )
    assert "executive-video.mp4" in contract["evidence"]
```

- [ ] **Step 2: Create the Playwright screencast**

Use `page.screencast` with these acts:

1. executive briefing and baseline KPIs
2. state-derived trading shock
3. eight-stage causal journey
4. human approval and execution timeline
5. measured KPI outcome
6. Knowledge graph
7. Constellation

The script must use condition waits, not arbitrary assumptions, and end with:

```js
await page.screencast.showChapter("Fashion Trading Shock resolved", {
  description:
    "Eight connected workflows, governed decisions and measured commercial value — replayed quota-free.",
  duration: 3000,
});
```

- [ ] **Step 3: Invoke video generation against replay**

After replay proof passes:

```bash
CONTROL_PLANE_BASE="http://127.0.0.1:$CONTROL_PLANE_PORT" \
BLUEPRINT_BASE="http://127.0.0.1:$BLUEPRINT_PORT" \
VIDEO_OUT="$STORY_PROOF_DIR/executive-video.webm" \
  node tools/fashion_trading_shock_video.mjs

ffmpeg -hide_banner -loglevel error -y \
  -i "$STORY_PROOF_DIR/executive-video.webm" \
  -c:v libx264 -crf 20 -pix_fmt yuv420p -movflags +faststart -an \
  "$STORY_PROOF_DIR/executive-video.mp4"
```

- [ ] **Step 4: Validate the video**

```bash
test -s proof/fashion-trading-shock/executive-video.mp4
duration="$(
  ffprobe -v error -show_entries format=duration \
    -of default=nk=1:nw=1 \
    proof/fashion-trading-shock/executive-video.mp4
)"
awk -v duration="$duration" 'BEGIN { exit !(duration >= 40 && duration <= 360) }'
```

Expected: H.264 MP4, 40–360 seconds, non-zero size.

- [ ] **Step 5: Run focused UI and proof tests**

```bash
npx vitest run \
  web/client/components/world/__tests__/TradingShockPanel.test.tsx \
  web/client/components/world/__tests__/SpatialWorld.test.tsx \
  web/client/hooks/__tests__/useFeedItems.test.tsx

uv run --frozen --no-sync pytest \
  tests/api/fashion \
  tests/tools/test_fashion_zava_e2e_proof.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the executive walkthrough**

```bash
git add tools/fashion_trading_shock_video.mjs \
  tools/fashion_zava_e2e_proof.sh \
  tests/tools/test_fashion_zava_e2e_proof.py
git commit -m "feat(fashion): add executive demo film"
```

---

### Task 10: Run the permanent acceptance gate

**Files:**
- Verify: `proof/manifest.json`
- Verify: `proof/fashion-trading-shock/**`

- [ ] **Step 1: Run targeted backend and frontend suites**

```bash
uv run --frozen --no-sync pytest \
  tests/api/fashion \
  tests/api/server/services/test_world_workflow_adapter.py \
  tests/api/server/services/test_world_bridge_actor.py \
  tests/tools/test_workflow_visibility_proof.py \
  tests/tools/test_fashion_zava_e2e_proof.py -q

npx vitest run \
  web/client/components/world/__tests__/TradingShockPanel.test.tsx \
  web/client/components/world/__tests__/SpatialWorld.test.tsx \
  web/client/hooks/__tests__/useFeedItems.test.tsx \
  web/client/components/feed/__tests__/cards/ResolvedCard.test.tsx
```

Expected: all selected tests PASS.

- [ ] **Step 2: Build the UI**

```bash
npm run build
```

Expected: TypeScript and Vite build exit 0.

- [ ] **Step 3: Run the clean permanent proof**

```bash
make prove VERTICAL=fashion
```

Expected:

```text
FASHION ZAVA E2E PROOF PASSED (seller review remains PENDING)
```

- [ ] **Step 4: Inspect the manifest**

```bash
jq -e --arg head "$(git rev-parse HEAD)" '
  .source_commit == $head
  and .permanent_result == "PASS"
  and .live_result == "PASS"
  and .replay_result == "PASS"
  and .visibility_result == "PASS"
  and .memory_exact_matches == 8
  and (.browserErrors | length) == 0
  and .droppedWorkflowEvents == 0
  and .criteria.replay.clean_teardown == "PASS"
' proof/manifest.json
```

Expected: exit 0.

- [ ] **Step 5: Confirm no leaked services**

```bash
for port in 12000 12001 12002 13201 15373 15375 17271; do
  ! lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
done
```

Expected: exit 0.

- [ ] **Step 6: Commit final acceptance updates if any were required**

```bash
git status --short
```

Expected: only ignored `proof/` artifacts; no source changes. If an acceptance
fix changed source, commit only that focused fix after rerunning the affected
gate.
