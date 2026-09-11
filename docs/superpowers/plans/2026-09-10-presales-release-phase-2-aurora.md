# Real Durable Aurora Implementation Plan

> **For agentic workers:** Use `executing-plans` and the installed-pack `add-domain` procedure after implementation approval. Follow the [master plan](2026-09-10-presales-release-readiness.md). Do not create another vertical.

**Goal:** Replace the advertised Aurora shortcut with a real Agency workflow whose decisions, child invoices and final summary are inspectable.

**Architecture:** Register one Agency-owned parent orchestration, reuse the existing AP-invoice child engine and governance resolver, and execute business effects through idempotent activities. Keep the control-plane route as an asynchronous starter. Use canonical agent-session recording for actual model work.

**Tech Stack:** Python, Azure Durable Functions, current governance/agent contracts, pytest, existing workflow APIs and AG-UI.

**Status:** Superseded by [master plan v2](2026-09-10-presales-release-readiness.md). Reference only; real Aurora remains in scope, but the old Phase 1 dependency and detailed design are not automatic requirements.

---

## Contract

```python
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field

class AuroraStart(BaseModel):
    request_id: UUID
    scenario: Literal["aurora-budget-overrun"] = "aurora-budget-overrun"
    approval_mode: Literal["operator", "synthetic-persona"] = "operator"
    invoice_count: int = Field(default=3, ge=1, le=20)

class AuroraAccepted(BaseModel):
    workflow_id: str
    instance_id: str
    status_url: str
    events_url: str
```

The selected source is synthetic Agency finance data. Do not accept arbitrary customer system URLs or privileged roles from this payload. `synthetic-persona` is an explicitly permitted local/private proof configuration, never a claim that a person approved.

`ZAVA_AURORA_ALLOW_SYNTHETIC_APPROVAL=0` is the default. A caller cannot select
`synthetic-persona` unless the operator has enabled that flag for a synthetic
proof run. It controls the new Aurora root only; it does not silently change the
existing persona behaviour of other workflows.

Root ID is `AUR-` plus `request_id.hex`; use that same value as the Durable instance ID. Child IDs are root ID plus `-AP-` and the zero-based, two-digit invoice index. An identical start request returns the same root; different content under the same request ID returns HTTP 409.

Declared phases:

| Phase | Truth mode | Required evidence |
|---|---|---|
| `observe` | deterministic | Input financial snapshot, source signal and computed threshold comparison |
| `recommend` | agent | Actual `run_agent_session`, approved tools, proposal and validation |
| `approve` | hitl | Authority result, persisted context, actor provenance and external event |
| `apply_policy` | deterministic | Idempotent command receipt and actual policy/entity change |
| `process_invoices` | sub_orchestrator | Real AP child instance IDs and their observed outcomes |
| `synthesise` | agent | Actual summary session grounded in the accepted policy/child results |

The existing workflow-detail endpoint returns an Agency `packDetail` with
`kind="aurora-budget-response"`, `source_event_id`, `baseline`, `proposal`,
`governance`, `policy_result`, `invoice_results`, `summary` and `evidence_refs`.
An invoice result contains its actual `workflow_id`, terminal status and business
outcome. Evidence references identify persistent rows/events, not descriptive
strings. Pending fields are null or explicitly pending; zero is not a substitute
for missing evidence.

## Task 2.1: Graduate the existing story as a real Agency domain

**Files**

- Create: `verticals/agency/aurora/contracts.py`
- Create: `verticals/agency/aurora/workflow.py`
- Create: `verticals/agency/aurora/activities.py`
- Create: `verticals/agency/aurora/detail.py`
- Create: `verticals/agency/spawners.py`
- Create: `verticals/agency/skills/aurora-budget-recommendation/SKILL.md`
- Create: `verticals/agency/skills/aurora-executive-summary/SKILL.md`
- Modify: `verticals/agency/{domains,functions,agents,manifest,durable}.py`
- Create: `tests/api/agency/test_aurora_contract.py`
- Create: `tests/api/agency/test_aurora_orchestration.py`

- [ ] Write a pack-scoped brief for `workflow_type=aurora-budget-response`, prefix `AUR`, orchestrator `AuroraBudgetResponseOrchestrator`, and the six phases above. Use a compose-domain sandbox and `graduate.sh`; inspect generated changes before graduation. Global compatibility registries remain read-only.
- [ ] Add registration/isolation cases: Agency includes the root and its actual orchestrator; another selected pack does not. Call the real authority resolver for the emitted CFO action/category/value before accepting the generated gate.
- [ ] Implement the contracts above. Add serialization and duplicate-start tests, including invalid invoice counts and a non-Agency active pack.
- [ ] Register the parent and activities through `verticals/agency/durable.py`. Use deterministic orchestration APIs only inside the generator: context time, Durable timers, activity calls and real sub-orchestrator calls. No HTTP, model work, graph mutation, `datetime.now()`, random UUID generation or `asyncio.sleep()` inside it.
- [ ] Run the actual recommendation/summary skills through `run_agent_session`. Keep deterministic calculations deterministic; never emit an Agent row for a compiled persona policy or fixed response.
- [ ] Add `make test-aurora` using existing offline test configuration, the new Agency cases and the existing AP/policy/persona cases affected by this work.

**Acceptance:** a declared, non-stub workflow exists only in Agency; its phase truth modes match executed code.

## Task 2.2: Make approval and policy application real

**Files**

- Modify: `verticals/agency/aurora/{workflow,activities,contracts}.py`
- Modify: `api/server/services/persona_responder.py`
- Modify: `api/server/services/policy_application.py`
- Modify: `verticals/agency/authority.py` only if the emitted action lacks an existing matching rule
- Modify: `tests/api/server/services/test_policy_application.py`
- Modify: `tests/api/server/services/test_persona_responder_edge_cases.py`
- Create: `tests/api/agency/test_aurora_approval.py`
- Create: `tests/api/agency/test_aurora_commands.py`
- Create: `scripts/profile-aurora.sh`

- [ ] Add a pending-CFO test that runs persona handling and its recovery sweep repeatedly. With `approval_mode=operator`, no decision is manufactured and no external event is raised.
- [ ] Persist `approval_mode`, expected external-event name, phase, persona, source evidence and proposed action under `payload.hitl_context`. Apply the same mode guard in initial persona handling, escalation and restart sweeps; log the deliberate operator wait.
- [ ] Validate the actual authenticated actor and authority matrix before accepting an operator decision. Do not trust `persona=cfo` supplied by a caller. Use existing exception/approval routes rather than adding a bypass endpoint.
- [ ] Branch explicitly on approve, reject and timeout. Only approve reaches `apply_policy`; rejection and timeout retain their own reason/outcome and do not report a freeze.
- [ ] Extract the deterministic policy-write operation from the inline shim into an idempotent activity. Its receipt key is `(root_workflow_id, "apply_policy")`; a retry returns the same accepted result. A projection/audit failure raises and cannot return `APPLIED`.
- [ ] Prevent the independent summary cadence from auto-applying this scenario's proposal before the real gate. The flagship profile sets existing `INSIGHT_LOOP_ENABLED=0`; parent activities own its CFO/CEO observations. Preserve the normal cadence for other profiles. The scenario route refuses a conflicting automatic-insight configuration with a clear error.
- [ ] Set the flagship profile to Agency, the existing synthetic finance records and the operator-mode root. Other eligible background workflows may still use synthetic personae. Preserve source labels separately for real operator and synthetic decisions.
- [ ] Add crash/duplicate cases around approval delivery and policy application, using Phase 1 receipts. Do not indiscriminately retry arbitrary side-effecting activities.

**Acceptance:** real human mode stays paused until an authorised action; synthetic proof mode is distinct; the policy changes exactly once within the synthetic adapter's documented idempotency contract.

## Task 2.3: Use actual AP children and valid terminal outcomes

**Files**

- Modify: `api/functions/workflows/fleet_ap_invoice.py`
- Modify: `api/functions/workflows/fleet_ap_invoice_activities.py`
- Modify: `verticals/agency/domains.py`
- Modify: `verticals/agency/aurora/{workflow,activities,detail}.py`
- Reuse: `api/server/services/policy_lookup.py`
- Reuse: existing AP-clerk/controller policy-honour handlers
- Create: `tests/api/agency/test_aurora_invoice_children.py`
- Create: `tests/api/unit/test_ap_invoice_decision_outcomes.py`

- [ ] Prepare the selected invoice records before the parent starts and describe them as queued. After the accepted policy write, schedule the actual `FleetAPInvoiceOrchestrator` using stable child IDs and parent/child lineage.
- [ ] Feed the real invoice lookup/matching activities the scenario's source records and brand ID. The policy check must use the committed policy version. Remove any reliance on `_simulate_ap_invoice_decision_cascade`.
- [ ] Repair the existing AP decision fall-through: approve, reject and escalate are distinct. A controller escalation must reach a registered CFO decision gate; it cannot fall through to a completed success. Declare any added conditional phase/gate in Agency's existing AP domain metadata.
- [ ] Preserve timeouts, denied authority and unresolved decisions. Parent waits for actual child terminal results and reports rejected/failed children honestly; it never treats a pending child as paid or resolved.
- [ ] Validate the executive summary's structured facts against persisted results: policy ID/version, actual child IDs, outcome counts and unresolved work. Narrative prose may explain those facts but cannot replace them.
- [ ] Add regression cases for ordinary non-Aurora invoices so the existing approve path and policy behaviour remain compatible.

**Acceptance:** every reported AP decision comes from its real child execution. Evidence identifies synthetic reviewers where used. No new invoice engine or simulated success rows are introduced.

## Task 2.4: Replace the starter and bridge existing clients

**Files**

- Modify: `api/server/routes/demo_triggers.py`
- Modify: `tests/api/server/routes/test_full_arc.py`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/guidedJourney.ts`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/StoryGuide.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/DemoHUD.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/Narrator.tsx`
- Modify: their existing test files
- Create: `tests/api/agency/test_aurora_start_recovery.py`

- [ ] Change `/api/demo/trigger/full-aurora-arc` into an HTTP 202 starter returning `AuroraAccepted`. It starts real execution and returns promptly; it does not await an entire scenario or return prewritten phase summaries.
- [ ] Retain the URL but intentionally migrate its request/response contract with all repository callers. Remove synchronous graph/policy/cascade execution. Reject deprecated `delay_seconds` with a clear validation response; presentation pacing belongs in the viewer, not business execution.
- [ ] Persist a submission intent before contacting Functions. A Functions outage returns an explicit unavailable result without `workflow.started`; retry reconciles the deterministic instance ID before starting again.
- [ ] Update all current callers listed above together. Minimal Phase 2 UI shows accepted/pending/error state and links to `/api/workflows/{id}` plus `/api/workflows/{id}/agui`; Phase 4 supplies the polished guide.
- [ ] Add start, already-started, invalid input, non-Agency, Functions-down and lost-response cases. Use the existing `workflow_detail_hook` for Agency-specific evidence rather than adding business branches to generic workflow routes.

## Phase gate

- [ ] `make test-aurora` passes all positive and negative cases.
- [ ] Real Functions execution supplies the root and child instance IDs.
- [ ] API, drawer, graph, audit and AG-UI agree on actual outcomes.
- [ ] Operator mode, synthetic-persona mode, rejection and timeout have distinct evidence.
- [ ] The legacy fixed-story/cascade shortcut is no longer a successful execution path.

Rollback may disable the new scenario starter with an explicit unavailable state. It must not restore the old simulated path under a real-execution label.
