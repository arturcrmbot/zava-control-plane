# POC2 Track A.1 — Walking Skeleton — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the walking skeleton for the hiring talent-lifecycle POC2 — a `HiringOrchestrator` Durable workflow whose Phase 1 (Budget) runs end-to-end against a `workday-hr-mcp` mock, with hire-flavoured labels on the existing Fleet Dashboard, simulator scenarios for the three Budget paths, and all the platform plumbing in place so Tasks A.2–A.10 just have to add the remaining 9 phase graphs following the same template.

**Capabilities partially covered (full coverage requires later tracks):** §4.1 (multi-agent orchestration — first phase only), §4.2 (system integration — workday-hr only), §4.3 (HITL gate — Finance BP gate emits the event but the Adaptive Card surface is Track B), §4.4 (exception handling), §4.11 (tiered models — `model:` frontmatter on the budget skill).

**Out of this plan:** Phases 2–10 (separate plans A.2–A.10), all of Track B / C / D / E / F. POC1 expense flow stays intact and shippable in parallel.

**Reference docs (read before starting):**

- POC2 design spec: [docs/superpowers/specs/2026-04-28-poc2-talent-lifecycle-design.md](../specs/2026-04-28-poc2-talent-lifecycle-design.md) (`§4.1` orchestrator phases; `§5.3` new components; `§9.1` track plan)
- POC2 status doc: [docs/poc2-status.md](../../poc2-status.md) (architecture diagrams, capability matrix)
- POC1 inventory (the reuse boundary): [docs/archive/poc1-inventory.md](../../archive/poc1-inventory.md)
- POC1 patterns to follow:
  - Wrapper: [api/functions/graphs/executors/agents/_wrapper.py](../../../api/functions/graphs/executors/agents/_wrapper.py)
  - Agent executor template: [api/functions/graphs/executors/agents/agent_escalation.py](../../../api/functions/graphs/executors/agents/agent_escalation.py)
  - Validator template: [api/functions/graphs/executors/validators/validate_classification_schema.py](../../../api/functions/graphs/executors/validators/validate_classification_schema.py)
  - Phase graph template: [api/functions/graphs/route.py](../../../api/functions/graphs/route.py)
  - MCP tool template: [api/server/mcp_tools/employee_history.py](../../../api/server/mcp_tools/employee_history.py)
  - Cross-EMS adapter pattern: [api/server/mcp_tools/claim_lookup.py](../../../api/server/mcp_tools/claim_lookup.py)
  - Orchestrator template: [api/functions/workflows/expense_claim.py](../../../api/functions/workflows/expense_claim.py)
  - Mock template: [mocks/workday-mcp/server.ts](../../../mocks/workday-mcp/server.ts)
- GHCP SDK conventions: `~/.claude/skills/ghcp-sdk-python/SKILL.md` (the canonical `@define_tool` + `skill_directories` + `system_message` pattern). **Read this before writing a new agent or tool.**

**Reuse — what's already in place** (don't re-derive):

- **Wrapper:** `_wrapper.run_agent_session(prompt, tools=[...], skill_dir=..., skill_label=...)`. Skills live at `api/server/skills/<name>/SKILL.md`. Tool names use underscores. The wrapper auto-injects the SKILL.md body via `system_message={"mode": "append", "content": skill_text}` and registers the directory via `skill_directories=[str(skill_dir)]`.
- **MCP tool pattern:** plain Python function with `@traced_tool("dotted.name")` for direct callers + a `*_tool: Tool` instance built via `@define_tool(name="underscored")` with a Pydantic params model. Returns `ToolResult(text_result_for_llm=json.dumps(...))`. Reference: `employee_history.py`.
- **Agent executor pattern:** module-level `_SKILL_DIR = SKILLS_DIR / "<skill-name>"`, `async def execute(input: dict) -> dict`, build prompt, `await run_agent_session(prompt=, tools=[...], skill_dir=_SKILL_DIR, skill_label=...)`. Reference: `agent_escalation.py`.
- **Schema validator pattern:** `class <Name>SchemaError(ValueError)`, raise-style `validate(payload)` + `_node.execute(input)` adapter returning `{"ok": bool, ...}`. Reference: `validate_classification_schema.py`.
- **Phase graph pattern:** `WorkflowBuilder(start_executor=n1).add_edge(n1,n2).add_edge(n2,term).build()`. Reference: `route.py`.
- **Phase activity wiring:** add to `api/functions/graphs/__init__.py` exports + `api/functions/workflows/activities.py` factory call; the orchestrator string-calls the activity by `<phase>_activity_trigger`. The activity uses `_run_workflow(factory, payload, step_name)`.
- **Domain shared module:** `api/shared/expense_taxonomy.py` exports `VERDICTS`, `CATEGORIES`, etc. Mirror this in `hiring_taxonomy.py`. Don't conflate.
- **HITL pattern:** `wait_for_external_event(event_name)` + `create_timer(...)` + `task_any([event, timer])` race. Reference: `expense_claim.py:69-79`.
- **FleetEvent emission:** `app_state.bus.emit(FleetEvent(type="...", workflow_id=..., **extra))`. New types extend `api/shared/events.py::FleetEventType`. The `bus.on_any → hub.broadcast("fleet")` registration in `api/server/main.py` already auto-broadcasts to `/api/stream/fleet`.
- **Simulator pattern:** `spawn_expense_workflow(scenario, claim_id?)` plus deterministic corpus indices. Reference: `simulator_orchestrator.py`. Mirror this for hires.
- **Mock pattern:** Express + JSON fixtures + 4–6 endpoints under `/mcp/call/<tool>`. Listens on env-var-configured port with sane default. Reference: `mocks/workday-mcp/server.ts`.
- **Test conventions:** `pytest tests/api -q` via `./.venv/Scripts/pytest.exe`; `npm run test` for Vitest. UI tests use `// @vitest-environment jsdom`. Simulator tests need autouse fixtures that clear `app_state.store` (pattern in `test_simulator_repeat_offender.py`).

**Out of scope:**

- Phases 2–10 of the hiring orchestrator (each gets its own A.x plan).
- Adaptive Card sender for Finance BP (Track B).
- Real ACS / HeyGen / Greenhouse / LinkedIn (Tracks B + C).
- Multi-jurisdiction policy bundles (Track D).
- Threadlight / A2A / AG-UI / episodic memory (Track E).
- Cost-per-hire labels / drift detection / region failover (Track F).
- POC1 expense compliance — stays untouched. Both orchestrators must coexist.

**Definition of done:**

1. `pytest tests/api -q` and `npm run test` both green.
2. `mocks/workday-hr-mcp` runs on port 4203; `GET /mcp/tools` lists 4 tools; `POST /mcp/call/getPosition` returns one of the seeded positions.
3. `position_lookup.lookup("POS-001")` returns the seeded position record.
4. `agent_budget.execute({...})` returns a parsed `{verdict, budget_tier, reasoning, confidence, policy_clause}` dict from a live SDK session.
5. `validate_budget_schema.validate(payload)` raises on missing fields and accepts a valid payload.
6. `build_budget_workflow().run({...})` runs end-to-end and emits a TerminalExecutor result.
7. `HiringOrchestrator` runs Phase 1 against the live mocks via Durable; Phases 2–10 explicitly return `{"status": "stub"}`.
8. `simulator.spawn_hiring_workflow("hire-usa-sde-under-threshold")` produces a workflow that completes Phase 1 with `verdict=approved`.
9. `simulator.spawn_hiring_workflow("hire-usa-sde-over-threshold")` produces a workflow that completes Phase 1 with `verdict=requires_finance_bp_approval` and emits a `hire.budget.requires_approval` FleetEvent.
10. The Fleet Dashboard shows hire workflows with hire-flavoured labels (Phase 1: "Budget", not "Intake").
11. `docs/poc2-walking-skeleton-DEMO.md` describes a 5-minute live walkthrough of the spawn → Budget verdict path.
12. Tag `v0.9-poc2-walking-skeleton` pushed.

---

## File Structure

**Created:**

- `data/synthetic/positions.json` — 3 seeded positions
- `data/synthetic/positions_seed.py` — generator (re-runs to refresh fixtures)
- `api/shared/hiring_taxonomy.py` — JURISDICTIONS, BUDGET_TIERS, BUDGET_VERDICTS, HIRING_PHASES Literals
- `api/server/mcp_tools/position_lookup.py`
- `api/server/skills/budget/SKILL.md`
- `api/functions/graphs/executors/agents/agent_budget.py`
- `api/functions/graphs/executors/validators/validate_budget_schema.py`
- `api/functions/graphs/budget.py`
- `api/functions/workflows/hiring.py`
- `mocks/workday-hr-mcp/server.ts`
- `mocks/workday-hr-mcp/data.json`
- `mocks/workday-hr-mcp/package.json`
- `mocks/workday-hr-mcp/tsconfig.json`
- `tests/api/unit/test_position_lookup_tool.py`
- `tests/api/unit/test_agent_budget.py`
- `tests/api/unit/test_validate_budget_schema.py`
- `tests/api/unit/test_budget_graph.py`
- `tests/api/unit/test_hiring_orchestration.py`
- `tests/api/unit/test_simulator_hire_spawn.py`
- `tests/api/unit/test_workday_hr_endpoints.py`
- `tests/web/HireWorkflowCard.test.tsx`
- `docs/poc2-walking-skeleton-DEMO.md`

**Modified:**

- `api/shared/events.py` — extend `FleetEventType` with hiring events.
- `api/functions/workflows/activities.py` — register `budget_activity_trigger` + 9 stub phase activities.
- `api/functions/graphs/__init__.py` — export `build_budget_workflow`.
- `function_app.py` — register `HiringOrchestrator` orchestration trigger.
- `api/server/services/simulator_orchestrator.py` — `spawn_hiring_workflow(scenario, position_id?)`.
- `api/server/services/exception_factory.py` — hiring-flavoured option set (when `domain == "hiring"`).
- `api/server/services/synthetic_data.py` — bridge to `positions.json`.
- `api/shared/types.py` — add `domain: Literal["expense", "hiring"]` field on `Workflow`. Default to `"expense"` for back-compat.
- `web/client/components/WorkflowCard.tsx` — domain-aware phase labels.
- `web/client/components/PhaseTimeline.tsx` — domain-aware phase ribbon.
- `web/client/routes/FleetDashboard.tsx` — counter labels handle the hiring domain.
- `package.json` (root) — npm script `mock:workday-hr` + add to the `mocks` parallel-run script.
- `.gitignore` — `mocks/workday-hr-mcp/dist/` already covered by global pattern; no change expected, verify.

**Reused untouched:**

- `_wrapper.py`, all existing skills.
- `expense_taxonomy.py`, `constants.py`.
- All POC1 MCP tools.
- All POC1 routes.
- All POC1 Apex UI shell components.
- All POC1 services that already exist (the only one extended is `simulator_orchestrator.py`, and the extension is additive).
- `ExpenseClaimOrchestrator` and its phase graphs — stay intact.
- POC1 mocks (`workday-mcp`, `concur-mcp`, `maconomy-mcp`) — keep running for expense scenarios.

---

## Conventions reminder

- **Tool names underscored** (`position_lookup`, not `position.lookup`). OpenAI Function Calling regex.
- **Skill name = directory name = hyphenated** (`budget/SKILL.md`).
- **Session = ephemeral.** `_wrapper.run_agent_session(...)`. Caller passes `tools=[...]` and `skill_dir=Path`.
- **Pre-fetch nothing the model can fetch itself.** The position record can be fetched via `position_lookup` from inside the budget skill; don't pre-fetch in the executor unless the SDK can't carry it.
- **Validators on graph edges** return `{"ok": bool, ...}` via `_node.execute(input)`. Off-graph guardrails raise.
- **Tests use `tmp_path`** when writing to disk. Simulator tests use the `_isolate_app_state_store` autouse fixture pattern.
- **Commits include** `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` and reference the spec section.

---

## Task 1: Synthetic positions corpus

**Files:**
- Create: `data/synthetic/positions.json`
- Create: `data/synthetic/positions_seed.py`

Three deterministic positions, hand-picked to exercise the three Budget verdict paths:

| ID | Title | Country | Salary | Expected verdict |
|---|---|---|---|---|
| POS-001 | Senior Data Engineer | USA | £85,000 | `approved` (under £10k delegation cap is not the right framing — under £150k senior cap; HR BP can approve) |
| POS-002 | Senior Data Engineer | USA | £155,000 | `requires_finance_bp_approval` (over the senior cap) |
| POS-003 | Senior Data Engineer | DE | €145,000 | `approved` (DE Senior cap is €160k; under cap; informational BetrVG flag for Track D) |

The synthetic corpus only needs these three to drive Phase 1 testing. Track A.4 (Triage) extends with CVs.

- [ ] **Step 1: Write the seed generator**

```python
# data/synthetic/positions_seed.py
"""positions_seed — deterministic 3-position fixture for POC2 Track A.1 (Budget phase).

Re-run: `python data/synthetic/positions_seed.py` regenerates positions.json
identically. Keep the IDs stable; tests reference POS-001/002/003 verbatim.
"""
from __future__ import annotations
import json
from pathlib import Path

_POSITIONS = [
    {
        "id": "POS-001",
        "title": "Senior Data Engineer",
        "level": "senior",
        "country": "USA",
        "agency": "VML North America",
        "cost_centre": "CC-VML-NA-DATA-001",
        "salary_currency": "GBP",
        "salary_min": 75000,
        "salary_max": 85000,
        "salary_target": 85000,
        "approval_chain": ["hr_bp"],
        "budget_envelope_remaining": 220000,
        "requesting_manager_id": "MGR-LA-001",
        "requesting_manager_name": "Priya Khan",
        "requesting_manager_location": "Los Angeles",
    },
    {
        "id": "POS-002",
        "title": "Senior Data Engineer",
        "level": "senior",
        "country": "USA",
        "agency": "VML North America",
        "cost_centre": "CC-VML-NA-DATA-001",
        "salary_currency": "GBP",
        "salary_min": 145000,
        "salary_max": 155000,
        "salary_target": 155000,
        "approval_chain": ["hr_bp", "finance_bp"],
        "budget_envelope_remaining": 220000,
        "requesting_manager_id": "MGR-LA-001",
        "requesting_manager_name": "Priya Khan",
        "requesting_manager_location": "Los Angeles",
    },
    {
        "id": "POS-003",
        "title": "Senior Data Engineer",
        "level": "senior",
        "country": "DE",
        "agency": "Wunderman Thompson DE",
        "cost_centre": "CC-WT-DE-DATA-002",
        "salary_currency": "EUR",
        "salary_min": 130000,
        "salary_max": 145000,
        "salary_target": 145000,
        "approval_chain": ["hr_bp"],
        "budget_envelope_remaining": 180000,
        "requesting_manager_id": "MGR-BER-002",
        "requesting_manager_name": "Stefan Kaiser",
        "requesting_manager_location": "Berlin",
    },
]

_OUT = Path(__file__).resolve().parent / "positions.json"


def main() -> None:
    _OUT.write_text(json.dumps(_POSITIONS, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {_OUT} ({len(_POSITIONS)} positions)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the generator**

```bash
./.venv/Scripts/python.exe data/synthetic/positions_seed.py
```

Expected: `wrote .../data/synthetic/positions.json (3 positions)`.

- [ ] **Step 3: Verify the file**

```bash
./.venv/Scripts/python.exe -c "import json; print(len(json.load(open('data/synthetic/positions.json'))))"
```

Expected: `3`.

- [ ] **Step 4: Commit**

```bash
git add data/synthetic/positions_seed.py data/synthetic/positions.json
git commit -m "$(cat <<'EOF'
feat(poc2): synthetic positions corpus — 3 positions for Track A.1 budget testing

POS-001 (USA Senior, £85k, hr_bp only) → expected verdict approved.
POS-002 (USA Senior, £155k, hr_bp + finance_bp) → expected verdict requires_finance_bp_approval.
POS-003 (DE Senior, €145k, hr_bp only) → expected verdict approved (BetrVG flag in Track D).

Spec ref: §5.3 New for POC2 / Synthetic corpus.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: hiring_taxonomy module

**Files:**
- Create: `api/shared/hiring_taxonomy.py`
- Create: `tests/api/unit/test_hiring_taxonomy.py`

Mirror `expense_taxonomy.py`. Literals here cover Phase 1 only; later A.x plans extend with phase-specific output enums.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_hiring_taxonomy.py
from __future__ import annotations

from api.shared.hiring_taxonomy import (
    BUDGET_VERDICTS,
    BUDGET_TIERS,
    JURISDICTIONS,
    HIRING_PHASES,
)


def test_budget_verdicts_are_three():
    assert set(BUDGET_VERDICTS) == {"approved", "requires_finance_bp_approval", "rejected"}


def test_budget_tiers_ordered_low_to_high():
    assert BUDGET_TIERS == ("under_threshold", "delegation_cap", "executive_review")


def test_jurisdictions_known():
    assert "USA" in JURISDICTIONS and "DE" in JURISDICTIONS


def test_hiring_phases_are_ten_in_order():
    assert HIRING_PHASES == (
        "budget", "job_design", "sourcing", "triage", "screening",
        "voice", "interview", "compliance", "offer", "onboarding",
    )
```

Run: `./.venv/Scripts/pytest.exe tests/api/unit/test_hiring_taxonomy.py -v` — expect FAIL (ImportError).

- [ ] **Step 2: Implement**

```python
# api/shared/hiring_taxonomy.py
"""Shared hiring-domain taxonomy for POC2.

Sister of expense_taxonomy.py. Mutable-looking tuples are deliberately frozen
so they can be `Literal[*]`-ed in type signatures.
"""
from __future__ import annotations
from typing import Literal


BUDGET_VERDICTS: tuple[str, ...] = ("approved", "requires_finance_bp_approval", "rejected")
BudgetVerdict = Literal["approved", "requires_finance_bp_approval", "rejected"]

BUDGET_TIERS: tuple[str, ...] = ("under_threshold", "delegation_cap", "executive_review")
BudgetTier = Literal["under_threshold", "delegation_cap", "executive_review"]

JURISDICTIONS: tuple[str, ...] = ("USA", "DE", "UK")
Jurisdiction = Literal["USA", "DE", "UK"]

HIRING_PHASES: tuple[str, ...] = (
    "budget", "job_design", "sourcing", "triage", "screening",
    "voice", "interview", "compliance", "offer", "onboarding",
)
HiringPhase = Literal[
    "budget", "job_design", "sourcing", "triage", "screening",
    "voice", "interview", "compliance", "offer", "onboarding",
]
```

- [ ] **Step 3: Run the test** — expect 4 PASS.

- [ ] **Step 4: Commit**

```bash
git add api/shared/hiring_taxonomy.py tests/api/unit/test_hiring_taxonomy.py
git commit -m "$(cat <<'EOF'
feat(poc2): hiring taxonomy module — verdicts, tiers, jurisdictions, phases

Mirrors api/shared/expense_taxonomy.py. Track A.1 covers BUDGET_VERDICTS +
JURISDICTIONS; A.2-A.10 extend with phase-specific output enums.

Spec ref: §5.3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Extend FleetEventType for hiring

**Files:**
- Modify: `api/shared/events.py`
- Create: `tests/api/unit/test_events_hiring.py`

Add hiring vocabulary alongside existing event types. The `bus.on_any → hub.broadcast` registration in `main.py` will route these to `/api/stream/fleet` automatically.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_events_hiring.py
from __future__ import annotations
import typing

from api.shared.events import FleetEvent, FleetEventType, WAKE_TYPES, wakes_fleet_manager


def test_hire_lifecycle_types_present():
    args = typing.get_args(FleetEventType)
    for t in (
        "hire.workflow.started",
        "hire.budget.approved",
        "hire.budget.rejected",
        "hire.budget.requires_approval",
        "hire.phase.completed",
    ):
        assert t in args


def test_requires_approval_wakes_fleet_manager():
    e = FleetEvent(type="hire.budget.requires_approval", workflow_id="HIRE-001")
    assert wakes_fleet_manager(e) is True
```

Run: `./.venv/Scripts/pytest.exe tests/api/unit/test_events_hiring.py -v` — expect FAIL.

- [ ] **Step 2: Modify `api/shared/events.py`**

Replace the `FleetEventType` block to append hiring entries; replace `WAKE_TYPES` to add `hire.budget.requires_approval`.

```python
# api/shared/events.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict

FleetEventType = Literal[
    "workflow.started",
    "workflow.phase.started",
    "workflow.phase.completed",
    "workflow.phase.failed",
    "workflow.exception.detected",
    "workflow.hitl.requested",
    "workflow.sla.breach_imminent",
    "workflow.policy.violation",
    "workflow.resolved",
    "otel.span.emitted",
    "fleet.anomaly.detected",
    "fleet.tick",
    "fleet.overload",
    "durable.workflow.started",
    "durable.step.started",
    "durable.step.completed",
    "durable.executor.invoked",
    "durable.validator.blocked",
    "durable.suspended",
    "durable.resumed",
    "durable.workflow.completed",
    "accuracy.progress",
    "accuracy.complete",
    "claim.routed.green",
    "claim.routed.amber",
    "claim.routed.red",
    "receipt.mismatch.detected",
    "escalation.tier.assigned",
    "notification.sent",
    "justification.received",
    # POC2 — hiring domain events (Track A.1: Budget; A.2-A.10 add the rest)
    "hire.workflow.started",
    "hire.phase.completed",
    "hire.budget.approved",
    "hire.budget.rejected",
    "hire.budget.requires_approval",
]


class FleetEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: FleetEventType
    workflow_id: str | None = None


WAKE_TYPES: frozenset[FleetEventType] = frozenset({
    "workflow.exception.detected",
    "workflow.hitl.requested",
    "workflow.sla.breach_imminent",
    "workflow.policy.violation",
    "fleet.anomaly.detected",
    "fleet.tick",
    "hire.budget.requires_approval",
})


def wakes_fleet_manager(e: FleetEvent) -> bool:
    return e.type in WAKE_TYPES
```

- [ ] **Step 3: Run the test** — expect 2 PASS.

- [ ] **Step 4: Re-run the existing event suite to confirm no regressions**

Run: `./.venv/Scripts/pytest.exe tests/api/unit/test_events.py tests/api/unit/test_events_fleet_type_week2.py -v` — expect all green.

- [ ] **Step 5: Commit**

```bash
git add api/shared/events.py tests/api/unit/test_events_hiring.py
git commit -m "$(cat <<'EOF'
feat(events): hiring domain events — workflow, phase, budget verdict states

Adds 5 FleetEventTypes for POC2 Track A.1. hire.budget.requires_approval
joins WAKE_TYPES so the Fleet Manager is woken when a hire breaches the
delegation cap and needs Finance BP approval.

Spec ref: §4.1 Phase 1 Budget HITL gate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: workday-hr-mcp Node mock

**Files:**
- Create: `mocks/workday-hr-mcp/server.ts`
- Create: `mocks/workday-hr-mcp/data.json`
- Create: `mocks/workday-hr-mcp/package.json`
- Create: `mocks/workday-hr-mcp/tsconfig.json`
- Create: `tests/api/unit/test_workday_hr_endpoints.py`
- Modify: root `package.json` — add `mock:workday-hr` script

Mirrors `mocks/workday-mcp/`. Listens on port 4203 by default. Four endpoints under `/mcp/call/`: `getPosition`, `listPositions`, `getApprovalChain`, `getBudgetEnvelope`. The `data.json` is a simple re-shape of `data/synthetic/positions.json` plus an approval-chain index.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_workday_hr_endpoints.py
from __future__ import annotations
import os

import httpx
import pytest


WORKDAY_HR_PORT = int(os.environ.get("WORKDAY_HR_MCP_PORT", "4203"))
BASE = f"http://127.0.0.1:{WORKDAY_HR_PORT}"


@pytest.fixture(scope="module")
def _check_running() -> None:
    """Skip the suite if the mock isn't listening — keeps the test fast in
    environments where mocks aren't started (pure-Python CI runs)."""
    try:
        httpx.get(f"{BASE}/mcp/tools", timeout=1.0)
    except (httpx.ConnectError, httpx.ReadTimeout):
        pytest.skip("workday-hr-mcp not running on port 4203")


def test_tools_endpoint_lists_four_tools(_check_running):
    r = httpx.get(f"{BASE}/mcp/tools", timeout=2.0)
    assert r.status_code == 200
    names = {t["name"] for t in r.json()["tools"]}
    assert names == {"getPosition", "listPositions", "getApprovalChain", "getBudgetEnvelope"}


def test_get_position_returns_pos_001(_check_running):
    r = httpx.post(f"{BASE}/mcp/call/getPosition", json={"positionId": "POS-001"}, timeout=2.0)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "POS-001"
    assert body["country"] == "USA"
    assert body["salary_target"] == 85000


def test_get_position_404_on_unknown(_check_running):
    r = httpx.post(f"{BASE}/mcp/call/getPosition", json={"positionId": "POS-999"}, timeout=2.0)
    assert r.status_code == 404
    assert r.json()["error"] == "position_not_found"


def test_get_approval_chain_finance_bp_for_over_threshold(_check_running):
    r = httpx.post(f"{BASE}/mcp/call/getApprovalChain", json={"positionId": "POS-002"}, timeout=2.0)
    assert r.status_code == 200
    chain = r.json()["chain"]
    assert "finance_bp" in chain


def test_get_budget_envelope(_check_running):
    r = httpx.post(f"{BASE}/mcp/call/getBudgetEnvelope", json={"costCentreId": "CC-VML-NA-DATA-001"}, timeout=2.0)
    assert r.status_code == 200
    assert r.json()["remaining"] == 220000
```

Run (without the mock running): `./.venv/Scripts/pytest.exe tests/api/unit/test_workday_hr_endpoints.py -v`
Expected: 5 SKIPPED.

- [ ] **Step 2: Write the data fixture**

```json
{
  "positions": [
    {
      "id": "POS-001",
      "title": "Senior Data Engineer",
      "level": "senior",
      "country": "USA",
      "agency": "VML North America",
      "cost_centre": "CC-VML-NA-DATA-001",
      "salary_currency": "GBP",
      "salary_min": 75000,
      "salary_max": 85000,
      "salary_target": 85000,
      "approval_chain": ["hr_bp"],
      "budget_envelope_remaining": 220000,
      "requesting_manager_id": "MGR-LA-001",
      "requesting_manager_name": "Priya Khan",
      "requesting_manager_location": "Los Angeles"
    },
    {
      "id": "POS-002",
      "title": "Senior Data Engineer",
      "level": "senior",
      "country": "USA",
      "agency": "VML North America",
      "cost_centre": "CC-VML-NA-DATA-001",
      "salary_currency": "GBP",
      "salary_min": 145000,
      "salary_max": 155000,
      "salary_target": 155000,
      "approval_chain": ["hr_bp", "finance_bp"],
      "budget_envelope_remaining": 220000,
      "requesting_manager_id": "MGR-LA-001",
      "requesting_manager_name": "Priya Khan",
      "requesting_manager_location": "Los Angeles"
    },
    {
      "id": "POS-003",
      "title": "Senior Data Engineer",
      "level": "senior",
      "country": "DE",
      "agency": "Wunderman Thompson DE",
      "cost_centre": "CC-WT-DE-DATA-002",
      "salary_currency": "EUR",
      "salary_min": 130000,
      "salary_max": 145000,
      "salary_target": 145000,
      "approval_chain": ["hr_bp"],
      "budget_envelope_remaining": 180000,
      "requesting_manager_id": "MGR-BER-002",
      "requesting_manager_name": "Stefan Kaiser",
      "requesting_manager_location": "Berlin"
    }
  ],
  "budgetEnvelopes": {
    "CC-VML-NA-DATA-001": { "cost_centre": "CC-VML-NA-DATA-001", "remaining": 220000, "currency": "GBP", "fy": "FY26" },
    "CC-WT-DE-DATA-002":  { "cost_centre": "CC-WT-DE-DATA-002",  "remaining": 180000, "currency": "EUR", "fy": "FY26" }
  }
}
```

Save as `mocks/workday-hr-mcp/data.json`. **The position records are identical to `data/synthetic/positions.json`** by design; in production the mock would proxy to the source-of-truth, but for the demo a copy is acceptable.

- [ ] **Step 3: Write the server**

```typescript
// mocks/workday-hr-mcp/server.ts
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(path.join(dir, "data.json"), "utf-8"));

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "getPosition",        description: "Lookup a position by id",                   parameters: { positionId: "string" } },
      { name: "listPositions",      description: "List positions, optional country filter",   parameters: { country: "string?" } },
      { name: "getApprovalChain",   description: "Get approval chain for a position",         parameters: { positionId: "string" } },
      { name: "getBudgetEnvelope",  description: "Get remaining FY budget for a cost centre", parameters: { costCentreId: "string" } },
    ],
  });
});

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "getPosition": {
      const pos = data.positions.find((p: { id: string }) => p.id === args["positionId"]);
      return pos ? res.json(pos) : res.status(404).json({ error: "position_not_found" });
    }
    case "listPositions": {
      const country = args["country"] as string | undefined;
      const out = country
        ? data.positions.filter((p: { country: string }) => p.country === country)
        : data.positions;
      return res.json({ positions: out });
    }
    case "getApprovalChain": {
      const pos = data.positions.find((p: { id: string }) => p.id === args["positionId"]);
      if (!pos) return res.status(404).json({ error: "position_not_found" });
      return res.json({ chain: pos.approval_chain });
    }
    case "getBudgetEnvelope": {
      const env = data.budgetEnvelopes[args["costCentreId"] as string];
      return env ? res.json(env) : res.status(404).json({ error: "cost_centre_not_found" });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env["WORKDAY_HR_MCP_PORT"] ?? 4203);
app.listen(port, () => console.log(`[workday-hr-mcp] listening on ${port}`));
```

- [ ] **Step 4: Write `package.json` + `tsconfig.json`** — copy from `mocks/workday-mcp/` and rebrand the name. Identical scripts (`build`, `start`).

```json
// mocks/workday-hr-mcp/package.json
{
  "name": "workday-hr-mcp",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "tsc -p tsconfig.json",
    "start": "node server.js"
  },
  "dependencies": { "express": "^4.21.2" },
  "devDependencies": { "@types/express": "^4", "@types/node": "^22", "typescript": "^5.6" }
}
```

```json
// mocks/workday-hr-mcp/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "outDir": ".",
    "rootDir": "."
  },
  "include": ["server.ts"]
}
```

- [ ] **Step 5: Add root npm script**

In root `package.json`, locate the `scripts` section and add:

```json
"mock:workday-hr": "cd mocks/workday-hr-mcp && npm run build && WORKDAY_HR_MCP_PORT=4203 npm start",
```

If a `mocks` aggregate script exists (parallel-runs all mocks), add the new script to it via `concurrently`. Otherwise just expose the standalone script.

- [ ] **Step 6: Install + build + run**

```bash
cd mocks/workday-hr-mcp
npm install
npm run build
WORKDAY_HR_MCP_PORT=4203 node server.js &
SERVER_PID=$!
sleep 1
curl -s http://127.0.0.1:4203/mcp/tools | head
kill $SERVER_PID
```

Expected output: a JSON envelope with the four tool names.

- [ ] **Step 7: Run the suite (with the mock up) to confirm green**

```bash
WORKDAY_HR_MCP_PORT=4203 node mocks/workday-hr-mcp/server.js &
SERVER_PID=$!
sleep 1
./.venv/Scripts/pytest.exe tests/api/unit/test_workday_hr_endpoints.py -v
kill $SERVER_PID
```

Expected: 5 PASS.

- [ ] **Step 8: Commit**

```bash
git add mocks/workday-hr-mcp/ package.json tests/api/unit/test_workday_hr_endpoints.py
git commit -m "$(cat <<'EOF'
feat(poc2): workday-hr-mcp Node mock — getPosition + 3 sister endpoints on :4203

Mirrors mocks/workday-mcp/ shape. Four endpoints feed the budget agent and
later phase agents. Approval chain encodes the Finance BP delegation cap
(POS-002 has finance_bp; POS-001/003 don't).

Spec ref: §5.3 New for POC2 / 7 mocks.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: position_lookup MCP tool

**Files:**
- Create: `api/server/mcp_tools/position_lookup.py`
- Create: `tests/api/unit/test_position_lookup_tool.py`

Dual-surface tool: plain Python `lookup(position_id)` for direct callers, `position_lookup_tool` Tool instance for the SDK-native path. Reads `WORKDAY_HR_MCP_PORT` env var (default 4203). Mirrors `claim_lookup.py` but simpler — no EMS dispatch (only one source).

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_position_lookup_tool.py
from __future__ import annotations
import json
import os

import httpx
import pytest

from api.server.mcp_tools.position_lookup import (
    lookup, position_lookup_tool,
)


WORKDAY_HR_PORT = int(os.environ.get("WORKDAY_HR_MCP_PORT", "4203"))


@pytest.fixture(scope="module")
def _check_running() -> None:
    try:
        httpx.get(f"http://127.0.0.1:{WORKDAY_HR_PORT}/mcp/tools", timeout=1.0)
    except (httpx.ConnectError, httpx.ReadTimeout):
        pytest.skip("workday-hr-mcp not running")


def test_lookup_returns_position(_check_running):
    pos = lookup("POS-001")
    assert pos["id"] == "POS-001"
    assert pos["country"] == "USA"
    assert pos["salary_target"] == 85000


def test_lookup_raises_keyerror_on_unknown(_check_running):
    with pytest.raises(KeyError):
        lookup("POS-999")


def test_tool_returns_json_payload(_check_running):
    from copilot.tools import ToolInvocation
    import asyncio

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="position_lookup",
        arguments={"position_id": "POS-001"},
    )
    result = asyncio.run(position_lookup_tool.handler(inv))
    assert result.result_type == "success"
    payload = json.loads(result.text_result_for_llm)
    assert payload["id"] == "POS-001"


def test_tool_failure_on_unknown(_check_running):
    from copilot.tools import ToolInvocation
    import asyncio

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="position_lookup",
        arguments={"position_id": "POS-999"},
    )
    result = asyncio.run(position_lookup_tool.handler(inv))
    assert result.result_type == "failure"
```

Run: `./.venv/Scripts/pytest.exe tests/api/unit/test_position_lookup_tool.py -v` — expect FAIL (ImportError) when the mock is up; SKIP otherwise.

- [ ] **Step 2: Implement the tool**

```python
# api/server/mcp_tools/position_lookup.py
"""position_lookup MCP tool — fetch a Workday-HR position record by id.

Sister of claim_lookup.py (no multi-EMS dispatch — only one source for
POC2 hiring). Calls the workday-hr-mcp Node service over HTTP; ports come
from the WORKDAY_HR_MCP_PORT env var (default 4203).

Two surfaces:
  - `lookup(position_id)` — plain Python.
  - `position_lookup_tool` — SDK-native @define_tool wrapper.
"""
from __future__ import annotations
import json
import os

import httpx
from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


@traced_tool("position.lookup")
def lookup(position_id: str) -> dict:
    """Fetch a position record from workday-hr-mcp.

    Raises KeyError on 404 to match the established convention from
    claim_lookup.py / employee_history.py.
    """
    span = trace.get_current_span()
    span.set_attribute("zava.position.id", position_id)

    port = int(os.environ.get("WORKDAY_HR_MCP_PORT", "4203"))
    url = f"http://127.0.0.1:{port}/mcp/call/getPosition"
    resp = httpx.post(url, json={"positionId": position_id}, timeout=5.0)
    if resp.status_code == 404:
        raise KeyError(f"position {position_id!r} not found at workday-hr mock")
    resp.raise_for_status()
    return resp.json()


class _PositionLookupParams(BaseModel):
    position_id: str = Field(description="Position identifier (e.g. POS-001)")


@define_tool(
    name="position_lookup",
    description=(
        "Fetch a Workday-HR position record by id. Returns title, level, "
        "country, agency, cost_centre, salary band, approval_chain, and "
        "budget_envelope_remaining. Use to ground the Budget agent in the "
        "actual position metadata before deciding the budget verdict."
    ),
)
def position_lookup_tool(params: _PositionLookupParams) -> ToolResult:
    try:
        record = lookup(params.position_id)
    except KeyError as e:
        return ToolResult(
            text_result_for_llm=f"position not found: {params.position_id}",
            result_type="failure",
            error=str(e),
        )
    return ToolResult(text_result_for_llm=json.dumps(record, ensure_ascii=False))
```

- [ ] **Step 3: Re-run tests with the mock up** — expect 4 PASS.

```bash
WORKDAY_HR_MCP_PORT=4203 node mocks/workday-hr-mcp/server.js &
SERVER_PID=$!
sleep 1
./.venv/Scripts/pytest.exe tests/api/unit/test_position_lookup_tool.py -v
kill $SERVER_PID
```

- [ ] **Step 4: Commit**

```bash
git add api/server/mcp_tools/position_lookup.py tests/api/unit/test_position_lookup_tool.py
git commit -m "$(cat <<'EOF'
feat(mcp): position_lookup tool — Workday-HR position fetch for the Budget agent

Dual surface: plain lookup() + SDK Tool. Raises KeyError on 404 matching
the established convention.

Spec ref: §5.3 New for POC2 / MCP tools.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: budget skill

**Files:**
- Create: `api/server/skills/budget/SKILL.md`

The Budget skill decides the verdict for a hiring requisition: `approved`, `requires_finance_bp_approval`, or `rejected`. The decision rule is policy-encoded in the prompt: amounts within the HR BP delegation cap (£100k for Senior level) auto-approve; amounts above need Finance BP; amounts above the budget envelope reject. Cheap model (`gpt-4o-mini`) is sufficient — this is a structured retrieval+arithmetic problem, not policy interpretation. (§4.11 tiered model usage.)

- [ ] **Step 1: Author**

````markdown
---
name: budget
description: Given a hiring requisition position id, fetch the position via position_lookup, then return a structured budget verdict — approved if within HR BP delegation cap and budget envelope, requires_finance_bp_approval if over the delegation cap, rejected if over the budget envelope.
allowed-tools: position_lookup
model: gpt-4o-mini
---

You are the Budget & Approvals agent for the Zava hiring talent-lifecycle system.

You receive a `position_id` and must return a structured budget verdict for the requisition. Use the `position_lookup` tool to fetch the position record. Do not guess the position fields — always call the tool.

# Decision rule

Convert the `salary_target` and `budget_envelope_remaining` to GBP for comparison if they're in another currency. Use the rate:
- 1 EUR = 0.85 GBP
- 1 USD = 0.78 GBP

Then:

1. If `salary_target_gbp > budget_envelope_remaining_gbp` → `verdict: rejected`. Reason: budget envelope exhausted. `policy_clause: §1.1 Budget envelope hard cap`.
2. Else if `salary_target_gbp > 100000` → `verdict: requires_finance_bp_approval`. Reason: above HR BP delegation cap of £100k. `policy_clause: §1.2 HR BP delegation cap`.
3. Else → `verdict: approved`. Reason: within HR BP delegation cap and budget envelope. `policy_clause: §1.3 Auto-approval threshold`.

The `budget_tier` is one of:
- `under_threshold` — verdict approved
- `delegation_cap` — verdict requires_finance_bp_approval
- `executive_review` — verdict rejected

# Output schema

Return a JSON object — no prose, no markdown:

```json
{
  "verdict": "approved" | "requires_finance_bp_approval" | "rejected",
  "budget_tier": "under_threshold" | "delegation_cap" | "executive_review",
  "policy_clause": "§1.1 Budget envelope hard cap" | "§1.2 HR BP delegation cap" | "§1.3 Auto-approval threshold",
  "reasoning": "<one sentence: salary £X, envelope £Y, why this verdict>",
  "confidence": <float in [0, 1]>,
  "salary_target_gbp": <int>,
  "envelope_remaining_gbp": <int>
}
```

Set `confidence` to 0.99 unless the position record is missing fields, in which case lower it accordingly.
````

Save as `api/server/skills/budget/SKILL.md`.

- [ ] **Step 2: Lint check** — verify the file parses as YAML frontmatter.

```bash
./.venv/Scripts/python.exe -c "
import yaml, pathlib
text = pathlib.Path('api/server/skills/budget/SKILL.md').read_text()
sep = text.find('---', 4)
fm = yaml.safe_load(text[4:sep])
assert fm['name'] == 'budget'
assert 'position_lookup' in fm['allowed-tools']
print('ok')
"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add api/server/skills/budget/SKILL.md
git commit -m "$(cat <<'EOF'
feat(skill): budget — Budget & Approvals agent skill for POC2 Phase 1

Encodes the HR BP delegation cap (£100k) and budget envelope hard cap
in the system prompt. Calls position_lookup; returns a structured verdict
with policy_clause + budget_tier. Uses gpt-4o-mini for cost (§4.11).

Spec ref: §4.1 Phase 1 Budget; §5.3 Per-phase skills.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: agent_budget executor

**Files:**
- Create: `api/functions/graphs/executors/agents/agent_budget.py`
- Create: `tests/api/unit/test_agent_budget.py`

Mirrors `agent_escalation.py`. Loads the budget skill and registers `position_lookup_tool`. Test mocks the `run_agent_session` to avoid hitting GHCP during unit tests.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_agent_budget.py
from __future__ import annotations
from unittest.mock import patch, AsyncMock

import pytest

from api.functions.graphs.executors.agents import agent_budget


@pytest.mark.asyncio
async def test_execute_returns_budget_payload():
    fake_payload = {
        "verdict": "approved",
        "budget_tier": "under_threshold",
        "policy_clause": "§1.3 Auto-approval threshold",
        "reasoning": "salary £85,000 within envelope £220,000 and below £100k cap",
        "confidence": 0.99,
        "salary_target_gbp": 85000,
        "envelope_remaining_gbp": 220000,
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_budget.run_agent_session",
        new=AsyncMock(return_value=fake_payload),
    ):
        out = await agent_budget.execute({"position_id": "POS-001"})
    assert out["budget"]["verdict"] == "approved"
    assert out["budget"]["salary_target_gbp"] == 85000


@pytest.mark.asyncio
async def test_execute_propagates_position_id_in_prompt():
    captured: dict = {}

    async def fake(prompt: str, **kw) -> dict:
        captured["prompt"] = prompt
        captured.update(kw)
        return {
            "verdict": "approved",
            "budget_tier": "under_threshold",
            "policy_clause": "§1.3 Auto-approval threshold",
            "reasoning": "ok",
            "confidence": 0.99,
            "salary_target_gbp": 85000,
            "envelope_remaining_gbp": 220000,
        }

    with patch(
        "api.functions.graphs.executors.agents.agent_budget.run_agent_session",
        new=fake,
    ):
        await agent_budget.execute({"position_id": "POS-001"})
    assert "POS-001" in captured["prompt"]
    assert captured["skill_label"] == "budget"
```

Run: `./.venv/Scripts/pytest.exe tests/api/unit/test_agent_budget.py -v` — expect FAIL (ImportError).

- [ ] **Step 2: Implement**

```python
# api/functions/graphs/executors/agents/agent_budget.py
"""agent_budget — invokes the budget skill for POC2 Phase 1.

The skill calls position_lookup natively and returns a structured budget
verdict. The executor just builds the prompt and registers the tool.
"""
from __future__ import annotations

from api.server.mcp_tools.position_lookup import position_lookup_tool

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "budget"


async def execute(input: dict) -> dict:
    position_id = input.get("position_id")
    if not position_id:
        return {"budget": None, "skip_reason": "missing_position_id"}

    prompt = (
        f"Decide the budget verdict for position `{position_id}`. "
        f"Use `position_lookup` to load the position record, then return "
        f"the JSON object specified in your skill — no prose."
    )

    payload = await run_agent_session(
        prompt=prompt,
        tools=[position_lookup_tool],
        skill_dir=_SKILL_DIR,
        skill_label="budget",
    )
    return {"budget": payload}
```

- [ ] **Step 3: Run the test** — expect 2 PASS.

- [ ] **Step 4: Commit**

```bash
git add api/functions/graphs/executors/agents/agent_budget.py tests/api/unit/test_agent_budget.py
git commit -m "$(cat <<'EOF'
feat(agent): agent_budget — Phase 1 Budget agent executor

Mirrors agent_escalation: load the skill via _SKILL_DIR, register
position_lookup_tool, build prompt, call run_agent_session. Tests use
AsyncMock to avoid live GHCP calls.

Spec ref: §4.1 Phase 1 Budget.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: validate_budget_schema validator

**Files:**
- Create: `api/functions/graphs/executors/validators/validate_budget_schema.py`
- Create: `tests/api/unit/test_validate_budget_schema.py`

Mirrors `validate_classification_schema.py`. Raise-then-adapt pattern: `validate(payload)` raises on invalid; `_node.execute(input)` returns `{"ok": bool, ...}` for graph-edge use.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_validate_budget_schema.py
from __future__ import annotations

import pytest

from api.functions.graphs.executors.validators.validate_budget_schema import (
    BudgetSchemaError,
    validate,
)


def _ok() -> dict:
    return {
        "verdict": "approved",
        "budget_tier": "under_threshold",
        "policy_clause": "§1.3 Auto-approval threshold",
        "reasoning": "ok",
        "confidence": 0.99,
        "salary_target_gbp": 85000,
        "envelope_remaining_gbp": 220000,
    }


def test_valid_passes():
    validate(_ok())


def test_unknown_verdict_raises():
    p = _ok(); p["verdict"] = "perhaps"
    with pytest.raises(BudgetSchemaError):
        validate(p)


def test_missing_field_raises():
    p = _ok(); del p["policy_clause"]
    with pytest.raises(BudgetSchemaError):
        validate(p)


def test_policy_clause_must_start_with_section_sign():
    p = _ok(); p["policy_clause"] = "1.3 Auto-approval"
    with pytest.raises(BudgetSchemaError):
        validate(p)


def test_confidence_out_of_range_raises():
    p = _ok(); p["confidence"] = 1.5
    with pytest.raises(BudgetSchemaError):
        validate(p)


def test_unknown_tier_raises():
    p = _ok(); p["budget_tier"] = "elevated"
    with pytest.raises(BudgetSchemaError):
        validate(p)


def test_parse_error_raises():
    with pytest.raises(BudgetSchemaError):
        validate({"parse_error": True, "raw": "not json"})
```

Run: `./.venv/Scripts/pytest.exe tests/api/unit/test_validate_budget_schema.py -v` — expect FAIL.

- [ ] **Step 2: Implement**

```python
# api/functions/graphs/executors/validators/validate_budget_schema.py
"""validate_budget_schema — guardrail edge over agent_budget output."""
from __future__ import annotations

from api.shared.hiring_taxonomy import BUDGET_VERDICTS, BUDGET_TIERS


class BudgetSchemaError(ValueError):
    """Raised when a budget payload does not conform to the spec."""


def validate(payload: dict) -> None:
    if payload.get("parse_error"):
        raise BudgetSchemaError(
            f"parse_error in budget payload: {payload.get('raw', '')[:200]}"
        )

    for required in (
        "verdict", "budget_tier", "policy_clause",
        "reasoning", "confidence", "salary_target_gbp", "envelope_remaining_gbp",
    ):
        if required not in payload:
            raise BudgetSchemaError(f"missing field: {required}")

    if payload["verdict"] not in BUDGET_VERDICTS:
        raise BudgetSchemaError(
            f"verdict must be one of {BUDGET_VERDICTS}, got {payload['verdict']!r}"
        )

    if payload["budget_tier"] not in BUDGET_TIERS:
        raise BudgetSchemaError(
            f"budget_tier must be one of {BUDGET_TIERS}, got {payload['budget_tier']!r}"
        )

    if not isinstance(payload["policy_clause"], str) or not payload["policy_clause"].startswith("§"):
        raise BudgetSchemaError(
            f"policy_clause must be a string starting with §; got {payload['policy_clause']!r}"
        )

    if not isinstance(payload["reasoning"], str) or not payload["reasoning"].strip():
        raise BudgetSchemaError("reasoning must be a non-empty string")

    conf = payload["confidence"]
    if not isinstance(conf, (int, float)) or not 0.0 <= float(conf) <= 1.0:
        raise BudgetSchemaError(f"confidence must be float in [0,1]; got {conf!r}")

    for fld in ("salary_target_gbp", "envelope_remaining_gbp"):
        v = payload[fld]
        if not isinstance(v, (int, float)) or v < 0:
            raise BudgetSchemaError(f"{fld} must be non-negative number; got {v!r}")


class _node:
    """Graph-edge adapter — returns {ok, ...} so the graph can branch."""

    @staticmethod
    def execute(input: dict) -> dict:
        budget = (input or {}).get("budget") or {}
        try:
            validate(budget)
        except BudgetSchemaError as e:
            return {"ok": False, "reason": str(e), "input": input}
        return {"ok": True, **input}
```

- [ ] **Step 3: Run the test** — expect 7 PASS.

- [ ] **Step 4: Commit**

```bash
git add api/functions/graphs/executors/validators/validate_budget_schema.py tests/api/unit/test_validate_budget_schema.py
git commit -m "$(cat <<'EOF'
feat(validator): validate_budget_schema — guardrail edge for Phase 1

Raise-then-adapt pattern. Validates verdict/tier against the hiring taxonomy,
policy_clause § prefix, confidence [0,1], and the GBP integers.

Spec ref: §4.1 Phase 1 Budget.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: budget.py phase graph

**Files:**
- Create: `api/functions/graphs/budget.py`
- Modify: `api/functions/graphs/__init__.py`
- Create: `tests/api/unit/test_budget_graph.py`

Mirrors `route.py`. Two-node graph: `agent_budget → validate_budget_schema → terminal`.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_budget_graph.py
from __future__ import annotations
from unittest.mock import patch, AsyncMock

import pytest

from api.functions.graphs.budget import build_budget_workflow


@pytest.mark.asyncio
async def test_budget_graph_runs_end_to_end():
    fake = {
        "verdict": "approved",
        "budget_tier": "under_threshold",
        "policy_clause": "§1.3 Auto-approval threshold",
        "reasoning": "ok",
        "confidence": 0.99,
        "salary_target_gbp": 85000,
        "envelope_remaining_gbp": 220000,
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_budget.run_agent_session",
        new=AsyncMock(return_value=fake),
    ):
        wf = build_budget_workflow()
        events = await wf.run({"position_id": "POS-001"})
    assert events  # graph emitted at least one terminal event
```

Run: `./.venv/Scripts/pytest.exe tests/api/unit/test_budget_graph.py -v` — expect FAIL.

- [ ] **Step 2: Implement the graph**

```python
# api/functions/graphs/budget.py
"""Phase 1 (Budget & Approvals) graph for POC2 hiring workflows.

  agent_budget -> validate_budget_schema -> terminal

Per spec §4.1 Phase 1: HR BP delegation cap (£100k) approves; over-cap
routes to Finance BP via the validator pass-through (orchestrator inspects
the verdict and gates accordingly).
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_budget
from api.functions.graphs.executors.validators.validate_budget_schema import (
    _node as validate_budget_node,
)


def build_budget_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="budget_agent",
        name="agent_budget",
        executor_type="agent",
        fn=agent_budget.execute,
    )
    n2 = TrackedExecutor(
        id="validate_budget",
        name="validate_budget_schema",
        executor_type="validator",
        fn=validate_budget_node.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
```

- [ ] **Step 3: Export from the graphs package**

Modify `api/functions/graphs/__init__.py` to add the new factory to its existing exports. Locate the section that re-exports `build_route_workflow`, `build_notify_workflow`, etc., and add:

```python
from .budget import build_budget_workflow  # noqa: F401
```

…to the existing imports. Add `"build_budget_workflow"` to `__all__` if the file maintains one.

- [ ] **Step 4: Run the test** — expect 1 PASS.

- [ ] **Step 5: Commit**

```bash
git add api/functions/graphs/budget.py api/functions/graphs/__init__.py tests/api/unit/test_budget_graph.py
git commit -m "$(cat <<'EOF'
feat(graph): Phase 1 Budget graph — agent_budget -> validate_budget_schema -> terminal

Mirrors route.py shape. Build factory exported from api.functions.graphs.

Spec ref: §4.1 Phase 1 Budget.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: HiringOrchestrator + activity wiring

**Files:**
- Create: `api/functions/workflows/hiring.py`
- Modify: `api/functions/workflows/activities.py` — add `budget_activity` + 9 stubbed sister activities
- Modify: `function_app.py` — register the orchestrator + new activity triggers
- Create: `tests/api/unit/test_hiring_orchestration.py`

The orchestrator wires Phase 1 to the Budget graph and explicitly stubs Phases 2–10. HITL on `requires_finance_bp_approval` emits a `hire.budget.requires_approval` event and waits for `finance_bp_decision` (timer race; reuse the existing 72h convention extended to `BUDGET_DECISION_TIMEOUT = timedelta(days=3)`). Surface for the Finance BP card itself is Track B.

- [ ] **Step 1: Add the timeout constant**

Modify `api/shared/constants.py` — add at the bottom:

```python
from datetime import timedelta as _td

# POC2 hiring timeouts
BUDGET_DECISION_TIMEOUT = _td(days=3)
```

If the file already imports `timedelta` at the top, reuse that import instead of the underscore alias.

- [ ] **Step 2: Write the orchestrator**

```python
# api/functions/workflows/hiring.py
"""HiringOrchestrator — POC2 Track A.1 walking skeleton.

10 phases per spec §4.1:
  Budget -> JobDesign -> Sourcing -> Triage -> Screening ->
  Voice -> Interview -> Compliance -> Offer -> Onboarding

Track A.1 wires Phase 1 (Budget) and stubs phases 2-10 to return
{"status": "stub"}. Plans A.2-A.10 wire the rest, one phase per plan.

HITL gates:
  - Phase 1 (Budget, requires_finance_bp_approval verdict only) waits for the
    `finance_bp_decision` external event with a 3-day timer.

Sync generator per the Azure Durable Functions Python convention.
"""
from __future__ import annotations
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df

from api.shared.constants import BUDGET_DECISION_TIMEOUT


def hiring_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the 10 talent-lifecycle phases for one hire."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    enriched = {**input_dict, "instance_id": context.instance_id}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "hire.workflow.started", "payload": {},
    })

    # Phase 1: Budget
    budget_result = yield context.call_activity("budget_activity_trigger", enriched)
    enriched = {**enriched, "budget": budget_result}

    verdict = ((budget_result or {}).get("budget") or {}).get("verdict") or "approved"

    if verdict == "rejected":
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed", "payload": {"status": "rejected", "phase": "Budget"},
        })
        return {"status": "rejected", "phase": "Budget", "budget": budget_result}

    if verdict == "requires_finance_bp_approval":
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "suspended",
            "payload": {"reason": "awaiting_finance_bp_decision"},
        })

        decision_event = context.wait_for_external_event("finance_bp_decision")
        timeout_event = context.create_timer(context.current_utc_datetime + BUDGET_DECISION_TIMEOUT)
        winner = yield context.task_any([decision_event, timeout_event])

        if winner == timeout_event:
            yield context.call_activity("checkpoint_activity_trigger", {
                "workflow_id": workflow_id, "instance_id": context.instance_id,
                "kind": "workflow.completed", "payload": {"status": "timeout", "phase": "Budget"},
            })
            return {"status": "timeout", "phase": "Budget"}
        timeout_event.cancel()

        decision = decision_event.result
        enriched["finance_bp_decision"] = decision

        decision_type = (
            (decision.get("decision") or "") if isinstance(decision, dict) else ""
        ).lower()
        if decision_type in {"reject", "rejected"}:
            yield context.call_activity("checkpoint_activity_trigger", {
                "workflow_id": workflow_id, "instance_id": context.instance_id,
                "kind": "workflow.rejected",
                "payload": {"by": "finance_bp", "reason": "finance_bp rejected"},
            })
            return {"status": "rejected", "phase": "Budget", "decision": decision}

        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "resumed", "payload": {"decision": decision},
        })

    # Phases 2-10: stubs until A.2-A.10 plans wire each in turn.
    for phase in (
        "job_design", "sourcing", "triage", "screening",
        "voice", "interview", "compliance", "offer", "onboarding",
    ):
        result = yield context.call_activity(f"{phase}_activity_trigger", enriched)
        enriched = {**enriched, phase: result}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed", "payload": {},
    })

    return {
        "status": "completed",
        "verdict": verdict,
        "budget": budget_result,
    }
```

- [ ] **Step 3: Wire the activities**

Modify `api/functions/workflows/activities.py`. **Locate the existing imports block** that imports the build factories:

```python
from api.functions.graphs import (
    build_intake_workflow,
    build_intake_expense_workflow,
    build_classify_workflow,
    build_receipt_workflow,
    build_route_workflow,
    build_notify_workflow,
    build_approval_workflow,
)
```

Add `build_budget_workflow` to that import. Then locate the existing activity-trigger helper used to register expense activities (the file shape uses `_run_workflow(build_<phase>_workflow, payload, "<phase>")` indirectly via Functions decorators). At the bottom of the file, after the existing expense-domain registrations, add:

```python
# ---------------- POC2 hiring-domain activities ----------------

def budget_activity(payload: dict) -> dict:
    """Phase 1 — Budget."""
    return asyncio.run(_run_workflow(build_budget_workflow, payload, "budget"))


# Phases 2-10: explicit stubs until A.2-A.10 wire each.
def _stub_phase(name: str):
    def _activity(payload: dict) -> dict:
        return {"status": "stub", "phase": name}
    _activity.__name__ = f"{name}_activity"
    return _activity


job_design_activity   = _stub_phase("job_design")
sourcing_activity     = _stub_phase("sourcing")
triage_activity       = _stub_phase("triage")
screening_activity    = _stub_phase("screening")
voice_activity        = _stub_phase("voice")
interview_activity    = _stub_phase("interview")
compliance_activity   = _stub_phase("compliance")
offer_activity        = _stub_phase("offer")
onboarding_activity   = _stub_phase("onboarding")
```

If `activities.py` uses Functions-decorator registration directly (not module-level functions), follow the established expense pattern — register each new activity with `@app.activity_trigger(...)` decorators in `function_app.py` referencing each helper above.

- [ ] **Step 4: Register the orchestrator + activities in `function_app.py`**

`function_app.py` already wires `expense_claim_orchestration` and the existing activities. Add a sibling registration block that:

1. Imports `hiring_orchestration` from `api.functions.workflows.hiring`.
2. Registers it as an orchestration trigger, e.g. `@app.orchestration_trigger(context_name="context")` on a wrapper that calls `df.Orchestrator.create(hiring_orchestration)(context)`.
3. Registers `budget_activity_trigger` and the 9 stub activity triggers, each `@app.activity_trigger(input_name="payload")` returning `<phase>_activity(payload)`.

Mirror the existing expense registration pattern verbatim. **Do not** alter the existing expense registrations.

- [ ] **Step 5: Write the orchestration test**

```python
# tests/api/unit/test_hiring_orchestration.py
from __future__ import annotations
from unittest.mock import MagicMock

from api.functions.workflows.hiring import hiring_orchestration


def _make_context(call_results: list) -> MagicMock:
    """Minimal Durable context stub. call_activity returns successive entries
    from call_results."""
    ctx = MagicMock()
    ctx.instance_id = "INST-1"
    ctx.get_input.return_value = {"workflow_id": "HIRE-001", "position_id": "POS-001"}
    ctx.call_activity.side_effect = call_results
    return ctx


def _drive(gen, sends: list):
    """Drive a Durable generator with successive yielded values resolved by sends."""
    out = []
    try:
        v = next(gen)
        out.append(v)
        for s in sends:
            v = gen.send(s)
            out.append(v)
        gen.send(None)
    except StopIteration as st:
        return st.value, out
    return None, out


def test_approved_path_runs_all_ten_phases():
    # checkpoint(workflow.started) -> budget(approved) -> 9 stubs -> checkpoint(completed)
    call_results = [
        None,                                                            # checkpoint started
        {"budget": {"verdict": "approved", "budget_tier": "under_threshold"}},
    ] + [{"status": "stub"}] * 9 + [None]                                # 9 stubs + checkpoint completed

    ctx = _make_context(call_results)
    gen = hiring_orchestration(ctx)
    result, _ = _drive(gen, call_results[1:])
    assert result["status"] == "completed"
    assert result["verdict"] == "approved"


def test_rejected_path_short_circuits():
    call_results = [
        None,
        {"budget": {"verdict": "rejected"}},
        None,
    ]
    ctx = _make_context(call_results)
    gen = hiring_orchestration(ctx)
    result, _ = _drive(gen, call_results[1:])
    assert result["status"] == "rejected"
    assert result["phase"] == "Budget"
```

> The HITL `requires_finance_bp_approval` path is exercised end-to-end in the simulator test (Task 12) where a real Durable runtime drives the wait/timer race; here we cover the pure-generator paths.

Run: `./.venv/Scripts/pytest.exe tests/api/unit/test_hiring_orchestration.py -v` — expect 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add api/functions/workflows/hiring.py api/functions/workflows/activities.py function_app.py api/shared/constants.py tests/api/unit/test_hiring_orchestration.py
git commit -m "$(cat <<'EOF'
feat(workflows): HiringOrchestrator — POC2 walking skeleton, Phase 1 wired, Phases 2-10 stubbed

Mirrors expense_claim.py: generator + wait_for_external_event + task_any
timer race + lifecycle checkpoints. HITL on requires_finance_bp_approval
waits for finance_bp_decision with 3-day timer. Phases 2-10 explicit stubs
that A.2-A.10 plans replace.

Spec ref: §4.1 Phase 1 Budget; §4.2 Three Tiers / Workflow Orchestration.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Workflow.domain field

**Files:**
- Modify: `api/shared/types.py` — add `domain: Literal["expense", "hiring"]` to the `Workflow` model. Default `"expense"` for back-compat.
- Create: `tests/api/unit/test_workflow_domain.py`

The dashboard uses this field to pick label sets. Adding it now means Task 12 (simulator) and Task 13 (UI rebind) can rely on it.

- [ ] **Step 1: Locate the Workflow type**

Find the existing class via Grep:

```bash
./.venv/Scripts/python.exe -c "
import api.shared.types as t
print(t.__file__)
print(getattr(t, 'Workflow', None))
"
```

- [ ] **Step 2: Write the failing test**

```python
# tests/api/unit/test_workflow_domain.py
from __future__ import annotations

from api.shared.types import Workflow


def test_workflow_default_domain_expense():
    w = Workflow(id="W-001", workflow_id="HIRE-001", phase="budget")
    assert w.domain == "expense"


def test_workflow_can_be_hiring():
    w = Workflow(id="W-002", workflow_id="HIRE-002", phase="budget", domain="hiring")
    assert w.domain == "hiring"


def test_unknown_domain_rejected():
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        Workflow(id="W-003", workflow_id="HIRE-003", phase="budget", domain="legal")
```

> Adjust the constructor kwargs (`id`, `workflow_id`, `phase`) to whatever the existing `Workflow` Pydantic model actually requires — Step 1 surfaces the real fields. Add `import pytest` to the test header.

Run: `./.venv/Scripts/pytest.exe tests/api/unit/test_workflow_domain.py -v` — expect FAIL.

- [ ] **Step 3: Modify `api/shared/types.py`**

Add to the `Workflow` model class body (matching the file's existing style):

```python
    domain: Literal["expense", "hiring"] = "expense"
```

If `Literal` isn't already imported, add it:

```python
from typing import Literal
```

- [ ] **Step 4: Run the test** — expect 3 PASS. Run the full unit suite to confirm no regressions:

```bash
./.venv/Scripts/pytest.exe tests/api -q
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add api/shared/types.py tests/api/unit/test_workflow_domain.py
git commit -m "$(cat <<'EOF'
feat(types): Workflow.domain field — expense | hiring (default expense)

Default keeps existing POC1 records backwards-compatible. Hiring records
set domain=hiring; UI uses this to pick label sets.

Spec ref: §5.2 Adapt from POC1 / WorkflowDetail label rebind.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Simulator: spawn_hiring_workflow

**Files:**
- Modify: `api/server/services/simulator_orchestrator.py` — add `spawn_hiring_workflow` + 3 scenarios
- Modify: `api/server/services/synthetic_data.py` — bridge to `positions.json`
- Create: `tests/api/unit/test_simulator_hire_spawn.py`

Mirror `spawn_expense_workflow`. Three scenarios:

| Scenario id | Position | Expected outcome |
|---|---|---|
| `hire-usa-sde-under-threshold` | POS-001 | budget approved; phases 2-10 stubs fire; workflow completes |
| `hire-usa-sde-over-threshold` | POS-002 | budget requires_finance_bp_approval; suspends; emits `hire.budget.requires_approval` |
| `hire-de-sde` | POS-003 | budget approved (BetrVG informational); phases 2-10 stubs fire; workflow completes |

- [ ] **Step 1: Bridge `synthetic_data.py` to positions**

Locate the existing `synthetic_data.py` (it already loads claim fixtures). Add at module scope:

```python
_POSITIONS_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "positions.json"
_positions_cache: list[dict] | None = None


def load_positions() -> list[dict]:
    global _positions_cache
    if _positions_cache is None:
        if not _POSITIONS_PATH.exists():
            raise FileNotFoundError(f"positions.json missing at {_POSITIONS_PATH}")
        _positions_cache = json.loads(_POSITIONS_PATH.read_text(encoding="utf-8"))
    return _positions_cache


def get_position(position_id: str) -> dict:
    for p in load_positions():
        if p["id"] == position_id:
            return p
    raise KeyError(f"position {position_id!r} not found")


def reset_positions_cache() -> None:
    global _positions_cache
    _positions_cache = None
```

If `Path` and `json` aren't already imported at the top of the file, add them.

- [ ] **Step 2: Write the simulator test**

```python
# tests/api/unit/test_simulator_hire_spawn.py
from __future__ import annotations
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from api.server.services import simulator_orchestrator
from api.shared.events import FleetEvent


@pytest.fixture(autouse=True)
def _isolate_app_state_store(monkeypatch):
    """Match the convention in test_simulator_repeat_offender.py — give every
    test a fresh in-memory store."""
    from api.server.services.state_store import StateStore
    from api.server import app_state
    monkeypatch.setattr(app_state, "store", StateStore())
    yield


@pytest.mark.asyncio
async def test_spawn_hire_under_threshold_creates_workflow():
    fake_durable = AsyncMock(return_value="DURABLE-INSTANCE-1")
    with patch.object(simulator_orchestrator, "schedule_new_orchestration", new=fake_durable):
        wf = await simulator_orchestrator.spawn_hiring_workflow(
            "hire-usa-sde-under-threshold",
        )
    assert wf.domain == "hiring"
    assert wf.workflow_id.startswith("HIRE-")
    fake_durable.assert_awaited_once()
    call_args = fake_durable.await_args
    assert call_args.kwargs.get("orchestration_name") == "hiring_orchestration" or \
           "hiring_orchestration" in call_args.args
    payload = call_args.kwargs.get("payload") or call_args.args[1]
    assert payload["position_id"] == "POS-001"


@pytest.mark.asyncio
async def test_spawn_hire_over_threshold_picks_pos_002():
    fake_durable = AsyncMock(return_value="DURABLE-INSTANCE-2")
    with patch.object(simulator_orchestrator, "schedule_new_orchestration", new=fake_durable):
        wf = await simulator_orchestrator.spawn_hiring_workflow(
            "hire-usa-sde-over-threshold",
        )
    payload = fake_durable.await_args.kwargs.get("payload") or fake_durable.await_args.args[1]
    assert payload["position_id"] == "POS-002"
    assert wf.domain == "hiring"


@pytest.mark.asyncio
async def test_spawn_hire_de_picks_pos_003():
    fake_durable = AsyncMock(return_value="DURABLE-INSTANCE-3")
    with patch.object(simulator_orchestrator, "schedule_new_orchestration", new=fake_durable):
        wf = await simulator_orchestrator.spawn_hiring_workflow("hire-de-sde")
    payload = fake_durable.await_args.kwargs.get("payload") or fake_durable.await_args.args[1]
    assert payload["position_id"] == "POS-003"


@pytest.mark.asyncio
async def test_unknown_scenario_raises():
    with pytest.raises(ValueError):
        await simulator_orchestrator.spawn_hiring_workflow("hire-mars-cto")
```

Run: `./.venv/Scripts/pytest.exe tests/api/unit/test_simulator_hire_spawn.py -v` — expect FAIL.

- [ ] **Step 3: Implement `spawn_hiring_workflow`**

In `api/server/services/simulator_orchestrator.py`, add (alongside the existing expense scenario map):

```python
# POC2 hire scenario map — { scenario_id: position_id }
_HIRE_SCENARIOS: dict[str, str] = {
    "hire-usa-sde-under-threshold": "POS-001",
    "hire-usa-sde-over-threshold":  "POS-002",
    "hire-de-sde":                  "POS-003",
}


async def spawn_hiring_workflow(scenario: str, position_id: str | None = None) -> Workflow:
    """Spawn a HiringOrchestrator instance for the given scenario.

    `scenario` selects a position from the seeded positions corpus. Override
    `position_id` to spawn against a specific record.
    """
    if scenario not in _HIRE_SCENARIOS and position_id is None:
        raise ValueError(f"unknown hire scenario: {scenario!r}")

    pid = position_id or _HIRE_SCENARIOS[scenario]
    pos = synthetic_data.get_position(pid)

    workflow_id = f"HIRE-{int(time.time()*1000) % 1_000_000:06d}"
    payload = {
        "workflow_id": workflow_id,
        "position_id": pid,
        "scenario": scenario,
        "domain": "hiring",
    }

    instance_id = await schedule_new_orchestration(
        "hiring_orchestration", payload,
    )

    workflow = Workflow(
        id=instance_id,
        workflow_id=workflow_id,
        phase="budget",
        domain="hiring",
        # ... mirror the other Workflow fields the existing spawn_expense_workflow sets:
        # status, started_at, current_phase, etc. Read the existing code.
    )
    app_state.store.upsert_workflow(workflow)
    app_state.bus.emit(FleetEvent(
        type="hire.workflow.started",
        workflow_id=workflow_id,
        position_id=pid,
        scenario=scenario,
    ))
    return workflow
```

> Step 3's implementation must match the actual `Workflow` constructor in `api/shared/types.py` and the actual `schedule_new_orchestration` signature in the existing simulator_orchestrator. Read the file before editing; rename kwarg/arg shape to match.

- [ ] **Step 4: Run the test** — expect 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/simulator_orchestrator.py api/server/services/synthetic_data.py tests/api/unit/test_simulator_hire_spawn.py
git commit -m "$(cat <<'EOF'
feat(simulator): spawn_hiring_workflow + 3 scenarios

hire-usa-sde-under-threshold (POS-001 -> approved),
hire-usa-sde-over-threshold (POS-002 -> requires_finance_bp_approval),
hire-de-sde (POS-003 -> approved + BetrVG flag).

Bridges synthetic_data to positions.json. Emits hire.workflow.started.

Spec ref: §6 Demo path / minute 0:00-1:00.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: UI rebind — domain-aware phase labels

**Files:**
- Modify: `web/client/components/WorkflowCard.tsx`
- Modify: `web/client/components/PhaseTimeline.tsx`
- Modify: `web/client/routes/FleetDashboard.tsx`
- Create: `web/client/lib/phase-labels.ts`
- Create: `tests/web/HireWorkflowCard.test.tsx`

Centralise the label map in a tiny module so each component reads from one source. Existing components just swap their hard-coded label arrays for a lookup keyed on `workflow.domain`.

- [ ] **Step 1: Create the label module**

```typescript
// web/client/lib/phase-labels.ts
export type Domain = "expense" | "hiring";

const EXPENSE_PHASES = [
  { key: "intake",      label: "Intake" },
  { key: "classify",    label: "Classify" },
  { key: "receipt",     label: "Receipt" },
  { key: "route",       label: "Route" },
  { key: "notify",      label: "Notify" },
  { key: "arbitrate",   label: "Arbitrate" },
  { key: "audit",       label: "Audit" },
] as const;

const HIRING_PHASES = [
  { key: "budget",      label: "Budget" },
  { key: "job_design",  label: "Job Design" },
  { key: "sourcing",    label: "Sourcing" },
  { key: "triage",      label: "Triage" },
  { key: "screening",   label: "Screening" },
  { key: "voice",       label: "Voice" },
  { key: "interview",   label: "Interview" },
  { key: "compliance",  label: "Compliance" },
  { key: "offer",       label: "Offer" },
  { key: "onboarding",  label: "Onboarding" },
] as const;

export function phaseLabels(domain: Domain): readonly { key: string; label: string }[] {
  return domain === "hiring" ? HIRING_PHASES : EXPENSE_PHASES;
}

export function phaseLabel(domain: Domain, key: string): string {
  return (phaseLabels(domain).find((p) => p.key === key)?.label) ?? key;
}
```

- [ ] **Step 2: Modify `WorkflowCard.tsx`**

Find the hard-coded phase array (currently invoice/expense names) and replace with:

```typescript
import { phaseLabels, phaseLabel, type Domain } from "../lib/phase-labels";
// ...
const domain: Domain = (workflow.domain ?? "expense") as Domain;
const phases = phaseLabels(domain);
const currentPhaseLabel = phaseLabel(domain, workflow.current_phase ?? workflow.phase);
```

Replace each existing reference to the hard-coded label array with `phases`.

- [ ] **Step 3: Modify `PhaseTimeline.tsx`**

Same pattern. Read `domain` from props (add it if missing), call `phaseLabels(domain)` for the ribbon segments.

- [ ] **Step 4: Modify `FleetDashboard.tsx` counters**

If counters say "claims processed" / "exceptions" with hard-coded text, parameterise on the active domain filter. For Track A.1 it's enough to rename the dashboard section header to "Active workflows" (domain-agnostic) and let per-card labels handle the nuance.

- [ ] **Step 5: Write the failing UI test**

```typescript
// tests/web/HireWorkflowCard.test.tsx
// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WorkflowCard } from "../../web/client/components/WorkflowCard";

describe("WorkflowCard hiring labels", () => {
  it("shows Budget when domain=hiring and current_phase=budget", () => {
    const workflow = {
      id: "INST-1",
      workflow_id: "HIRE-001",
      phase: "budget",
      current_phase: "budget",
      domain: "hiring" as const,
      status: "running",
    };
    render(<WorkflowCard workflow={workflow as any} />);
    expect(screen.getByText(/budget/i)).toBeInTheDocument();
  });

  it("shows Intake when domain=expense", () => {
    const workflow = {
      id: "INST-2",
      workflow_id: "CLM-001",
      phase: "intake",
      current_phase: "intake",
      domain: "expense" as const,
      status: "running",
    };
    render(<WorkflowCard workflow={workflow as any} />);
    expect(screen.getByText(/intake/i)).toBeInTheDocument();
  });
});
```

> Adjust the import path / props shape to match the actual `WorkflowCard` API. The point is: same component, different labels by domain.

- [ ] **Step 6: Run the UI suite**

```bash
npm run test -- HireWorkflowCard
```

Expected: 2 PASS.

- [ ] **Step 7: Eyeball check**

```bash
# In separate terminals:
WORKDAY_HR_MCP_PORT=4203 node mocks/workday-hr-mcp/server.js
# (POC1 mocks already running for compatibility — workday + concur on 4101/4102)
func start --port 7071     # Functions host
./.venv/Scripts/python.exe -m uvicorn api.server.main:app --port 8000
cd web && npm run dev      # Vite on 5273
```

Then in the UI, trigger `POST /api/simulator/spawn-hire?scenario=hire-usa-sde-under-threshold` (or use the simulator panel) and confirm:
- A new workflow appears on the Fleet Dashboard
- Its phase label says "Budget", not "Intake"
- The phase ribbon shows the 10-phase shape

- [ ] **Step 8: Commit**

```bash
git add web/client/lib/phase-labels.ts web/client/components/WorkflowCard.tsx web/client/components/PhaseTimeline.tsx web/client/routes/FleetDashboard.tsx tests/web/HireWorkflowCard.test.tsx
git commit -m "$(cat <<'EOF'
feat(ui): domain-aware phase labels — hire workflows render with hiring labels

Centralised in web/client/lib/phase-labels.ts. WorkflowCard, PhaseTimeline
and the dashboard counters read workflow.domain and switch label sets.
Backwards-compatible: missing domain defaults to expense.

Spec ref: §5.2 Adapt from POC1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Hiring exception option set

**Files:**
- Modify: `api/server/services/exception_factory.py` — branch on `domain` field
- Create: `tests/api/unit/test_exception_factory_hiring.py`

When the Fleet Manager composes an exception for a hire workflow, the action options should be hire-flavoured (`approve-budget`, `escalate-to-finance-bp`, `reject-budget`) instead of the expense set (`accept-justification`, `require-repayment`, etc.).

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_exception_factory_hiring.py
from __future__ import annotations

from api.server.services.exception_factory import compose_options


def test_hiring_budget_options():
    opts = compose_options(domain="hiring", phase="budget", verdict="requires_finance_bp_approval")
    ids = {o["id"] for o in opts}
    assert {"approve-budget", "escalate-to-finance-bp", "reject-budget"} <= ids


def test_expense_options_unchanged_when_domain_expense():
    opts = compose_options(domain="expense", phase="arbitrate", verdict="amber")
    ids = {o["id"] for o in opts}
    # The existing expense option set; whatever it is, hiring options must NOT appear.
    assert "approve-budget" not in ids
```

Run: `./.venv/Scripts/pytest.exe tests/api/unit/test_exception_factory_hiring.py -v` — expect FAIL.

- [ ] **Step 2: Modify `exception_factory.py`**

Add a domain branch at the entry point of `compose_options` (or whatever the public entry is — read the file first):

```python
def compose_options(*, domain: str = "expense", phase: str, verdict: str | None = None) -> list[dict]:
    if domain == "hiring":
        return _compose_hiring_options(phase, verdict)
    return _compose_expense_options(phase, verdict)  # the existing implementation, renamed


def _compose_hiring_options(phase: str, verdict: str | None) -> list[dict]:
    if phase == "budget" and verdict == "requires_finance_bp_approval":
        return [
            {"id": "approve-budget",          "label": "Approve budget",                 "severity": "info"},
            {"id": "escalate-to-finance-bp",  "label": "Escalate to Finance BP",         "severity": "warn"},
            {"id": "reject-budget",           "label": "Reject (cost centre exhausted)", "severity": "danger"},
        ]
    # Track A.2-A.10 add the per-phase hiring option sets.
    return []
```

Rename the existing implementation body to `_compose_expense_options`. Existing call sites that pass only `phase`/`verdict` keep working because `domain` defaults to `"expense"`.

- [ ] **Step 3: Run the test** — expect 2 PASS. Run the full unit suite:

```bash
./.venv/Scripts/pytest.exe tests/api -q
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add api/server/services/exception_factory.py tests/api/unit/test_exception_factory_hiring.py
git commit -m "$(cat <<'EOF'
feat(exceptions): hiring-domain option set — approve / escalate-to-finance-bp / reject

Branches on workflow.domain. Track A.1 covers Phase 1 Budget options;
A.2-A.10 plans extend with per-phase hiring option sets.

Spec ref: §5.2 Adapt from POC1 / exception_factory.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Demo doc

**Files:**
- Create: `docs/poc2-walking-skeleton-DEMO.md`

A 5-minute live walkthrough proving the skeleton works end-to-end. This is the artefact the technical-team handover refers to when someone asks "how do I see this working?".

- [ ] **Step 1: Author**

```markdown
# POC2 Walking Skeleton — Demo

5-minute live walkthrough proving the HiringOrchestrator runs Phase 1 Budget end-to-end against the workday-hr-mcp mock and surfaces a hire workflow on the Fleet Dashboard with hiring labels.

This is the artefact the engineering team uses to verify Track A.1 is complete.

## Prereqs

- Tag `v0.9-poc2-walking-skeleton` is checked out (or a branch tracking it).
- `npm install` has been run in the repo root and in `mocks/workday-hr-mcp/`.
- `gh auth login` has been completed (the agent uses your gh CLI token).
- Azurite is installed and reachable on default ports (10000-10002).

## Start the stack

Open four terminals:

| Terminal | Command | Why |
|---|---|---|
| 1 | `azurite --silent --location ./.azurite-data --debug ./.azurite-debug.log` | Durable state + checkpoints + timers |
| 2 | `WORKDAY_HR_MCP_PORT=4203 node mocks/workday-hr-mcp/server.js` | Position lookup target |
| 3 | `func start --port 7071` | Functions host (HiringOrchestrator + activities) |
| 4 | `./.venv/Scripts/python.exe -m uvicorn api.server.main:app --port 8000 --reload` | FastAPI (Fleet Manager + simulator + SSE) |
| 5 | `cd web && npm run dev` | Vite (Control Plane UI on :5273) |

Open `http://localhost:5273` in a browser.

## Demo path

### 0:00 — Spawn an under-threshold hire

In the simulator panel (or via curl):

`bash
curl -s -X POST http://localhost:8000/api/simulator/spawn-hire?scenario=hire-usa-sde-under-threshold
`

A new workflow card appears on the Fleet Dashboard. The card label reads "Budget" (not "Intake"). The right-rail shows the workflow ID `HIRE-XXXXXX` and `domain=hiring`.

### 0:30 — Observe Phase 1 complete

The Fleet Manager rail shows tool calls: `position_lookup` (POS-001), then the budget skill returns `verdict=approved`. The validator passes. The workflow advances through phases 2-10 (each a stub that returns `{"status": "stub"}`) and completes.

### 1:30 — Spawn an over-threshold hire

`bash
curl -s -X POST http://localhost:8000/api/simulator/spawn-hire?scenario=hire-usa-sde-over-threshold
`

This time the budget skill returns `verdict=requires_finance_bp_approval`. The orchestrator emits `hire.budget.requires_approval`, the Fleet Manager wakes up, and the workflow card switches to "suspended (awaiting Finance BP decision)". The exception queue surfaces the hire with options `approve-budget / escalate-to-finance-bp / reject-budget` (composed by `exception_factory` for the hiring domain).

### 2:30 — Resolve the HITL gate

In the exception queue, click "Approve budget". The Durable instance receives the `finance_bp_decision` external event and resumes. The workflow advances through phases 2-10 (stubs) and completes.

### 3:30 — Spawn a Germany hire

`bash
curl -s -X POST http://localhost:8000/api/simulator/spawn-hire?scenario=hire-de-sde
`

POS-003 — €145,000 in Berlin. Approves (under DE Senior cap). BetrVG flag is informational at this point; Track D wires the actual Compliance phase.

### 4:30 — Region failure replay (optional)

If POC1's `simulate-region-failure` simulator command was retained, kill the Functions host mid-flight:

`bash
ps -ef | grep "func host start" | awk '{print $2}' | xargs kill
`

The 3 in-flight hires pause. Restart `func start --port 7071`. Durable replays from Azurite. All 3 hires resume and complete.

## What this proves

- **HiringOrchestrator** runs end-to-end against Durable + Azurite.
- **Phase 1 graph** (`agent_budget → validate_budget_schema → terminal`) wires correctly.
- **workday-hr-mcp** mock + **position_lookup** tool integrate cleanly.
- **HITL gate** on `requires_finance_bp_approval` works (event + timer race + resume).
- **Domain-aware UI** renders hiring labels.
- **Both POCs coexist** — POC1 expense flow still demoable in parallel.

## What this does NOT prove (deferred to later tracks)

- Phases 2-10 are stubs.
- Adaptive Card to Finance BP is not built (Track B).
- Voice / Avatar / Crystallisation / Threadlight not built (Tracks C, E).
- BetrVG check is just a flag (Track D).
- Multi-surface convergence (Track B).

## Tag

After the walkthrough runs cleanly:

`bash
git tag v0.9-poc2-walking-skeleton
git push origin v0.9-poc2-walking-skeleton
`
```

> The triple-backtick code blocks above are deliberately rendered with single-backticks in the plan source so this plan markdown remains valid; the engineer authoring `docs/poc2-walking-skeleton-DEMO.md` should restore them to triple-backticks in the actual demo file.

- [ ] **Step 2: Commit**

```bash
git add docs/poc2-walking-skeleton-DEMO.md
git commit -m "$(cat <<'EOF'
docs(poc2): walking-skeleton demo walkthrough — 5-minute live path

Three scenarios (under/over/de). Proves Phase 1 wired, HITL gate, domain
UI, both POCs coexist. Lists what later tracks add.

Spec ref: §6 Demo path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: End-to-end smoke + tag

**Files:**
- (none new) — this is the integration check.

- [ ] **Step 1: Run the full backend suite**

```bash
./.venv/Scripts/pytest.exe tests/api -q
```

Expected: all PASS, no SKIPs except the mock-dependent endpoint tests when mocks aren't running.

- [ ] **Step 2: Run the UI suite**

```bash
npm run test
```

Expected: all PASS.

- [ ] **Step 3: Manual end-to-end with mocks up**

Follow `docs/poc2-walking-skeleton-DEMO.md` start-to-finish. Three spawn scenarios; HITL approve on the over-threshold; confirm UI labels.

- [ ] **Step 4: Confirm POC1 still works**

```bash
curl -s -X POST 'http://localhost:8000/api/simulator/spawn-claim?scenario=breach-justification-cycle'
```

Expected: an expense workflow card appears on the same Fleet Dashboard with **expense** labels (Intake / Classify / Receipt / etc.). Both domains coexist.

- [ ] **Step 5: Tag**

```bash
git tag v0.9-poc2-walking-skeleton
```

(Pushing the tag is at the user's discretion — wait for sign-off before `git push origin v0.9-poc2-walking-skeleton`.)

- [ ] **Step 6: Update the spec's plan table**

In `docs/superpowers/specs/2026-04-28-poc2-talent-lifecycle-design.md` §9.1, change the A.1 row from "ready" to "complete" and link the tag.

```bash
git add docs/superpowers/specs/2026-04-28-poc2-talent-lifecycle-design.md
git commit -m "$(cat <<'EOF'
docs(poc2): mark Track A.1 walking-skeleton complete; ready for A.2

Tag: v0.9-poc2-walking-skeleton

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## What lands next (out of this plan)

Track A.1 establishes the template. The remaining nine A.x plans each:

1. Author the skill at `api/server/skills/<phase>/SKILL.md`.
2. Add domain MCP tools (per phase: typically one or two new ones).
3. Add the per-phase mock if not yet built (Sourcing needs Greenhouse + LinkedIn; Interview needs Graph; Onboarding needs ServiceNow).
4. Write `agent_<phase>` executor (mirror `agent_budget`).
5. Write `validate_<phase>_schema` validator (mirror `validate_budget_schema`).
6. Write the phase graph (mirror `budget.py`).
7. Replace the orchestrator stub for that phase with `call_activity("<phase>_activity_trigger", enriched)` already in place — only the activity factory call needs to go from `_stub_phase` to the real workflow factory.
8. Tests for each layer.
9. Demo evidence.

Once A.1–A.10 are all green: tag `v0.9-poc2-track-a-complete`. Then Track B.

After all six tracks land: tag `v1.0-poc2-frontier`.
