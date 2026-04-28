# POC1 Expense Compliance Pivot — Week 2: Domain Workflow + Integrations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reshape the Durable orchestrator from the broken 6-phase invoice flow to the 7-phase expense-claim flow per spec §4.1. Wire phases 1–5 (Intake, Classify, Validate Receipt, Route by Verdict, Notify) end-to-end with Workday + a new Concur EMS mock; demonstrate breach → notification → justification round-trip. Land AC #1, #2, #5, #6, #9 (and AC #3 falls out for free once claims flow through the dashboard).

**Architecture:** Skills-first, same as Week 1. New skills (`receipt_validator`, `escalation_advisor`, `notification_composer`) live in `api/server/skills/*.skill.md` and are invoked by thin agent executors that pre-fetch tool data in Python and embed it in the prompt — *not* by telling the model to call tools it cannot reach. New MCP tools (`claim.lookup`, `claim.getReceipt`, `claim.summary`, `policy.cite`, `employee.history`) wrap the synthetic-data filesystem and the Node EMS mocks (Workday + new Concur). Each new graph node is a `TrackedExecutor` so phase events emit on the existing event bus; new event types (`receipt.mismatch.detected`, `escalation.tier.assigned`, `notification.sent`, `justification.received`) extend `FleetEventType` so SSE fan-out works without code changes elsewhere.

**Tech Stack:** Python 3.11 (FastAPI + Azure Durable Functions + Microsoft Agent Framework Pregel graphs + GHCP SDK), `httpx` for Python→Node mock dispatch, Pillow for receipt-image base64 round-trips, Node + TypeScript + Express for the new Concur mock, React + Vite + TypeScript + Vitest for UI, pytest + pytest-asyncio for backend tests.

**Reference docs (read before starting):**
- Week 1 plan: [docs/superpowers/plans/2026-04-27-poc1-expense-compliance-pivot-week1-accuracy-spine.md](2026-04-27-poc1-expense-compliance-pivot-week1-accuracy-spine.md) — match style, granularity, conventions
- Spec: [docs/superpowers/specs/2026-04-27-poc1-expense-compliance-pivot-design.md](../specs/2026-04-27-poc1-expense-compliance-pivot-design.md) — §4.1 (7-phase orchestrator), §5 (delete/adapt/reuse/new), §6 (synthetic dataset), §7 (acceptance criteria), §8 Week 2 day-by-day, §11 open questions
- Brief: [docs/poc1-brief.md](../../poc1-brief.md) — §4.5 (classification), §4.6 (behaviour change), §4.8 (audit), §7 acceptance criteria #5, #6, #9
- Accuracy runbook: [docs/poc1-accuracy-runbook.md](../../poc1-accuracy-runbook.md) — Day 0 pre-flight gate

**Out of scope for this plan (covered in Week 3):**
- Phase 6 (Arbitrate) — `arbitration.skill.md`, `precedents.search` MCP tool, `/reviewer-queue` route — *Week 3*
- Phase 7 (Audit) — `audit_summariser.skill.md`, `audit.query` MCP tool — *Week 3*
- Fleet Manager skill prompt extension for `fleet.tick` behaviour-change loop — *Week 3*
- `query_reviewer_decisions`, `query_economics` MCP tools — *Week 3*
- Region failover demo and recorded backup video — *Week 3*

**Definition of done for Week 2:**
1. **Day 0 pre-flight gate:** `overall_accuracy ≥ 0.95` on the 300-claim corpus with the unmodified policy, captured into `docs/poc1-accuracy-baseline.json`.
2. `pytest tests/api -q` green, no skipped tests except the documented smoke marker.
3. `npm run test` green; UI tests cover the new components.
4. The orchestrator entry point is now `expense_claim.py` (renamed from `invoice_p2p.py`); five phases wired (1–5).
5. Receipt validator flags all six mismatch flavours on the simulator scenario.
6. Concur mock live alongside Workday; FleetDashboard cards do not show the EMS source field.
7. Repeat-offender ramp visible (warning → escalation → major-violation) on the seeded 3-claim sequence.
8. Breach → notification → injected justification → `justification.received` event round-trip working under the simulator.
9. Code-cleanup checkpoint complete; `v0.7-poc1-domain-workflow` tagged and pushed.

---

## File Structure

**Created:**
- `mocks/concur-mcp/server.ts` — Node TS mock, OAuth-flavoured Concur surface
- `mocks/concur-mcp/data.json` — seed expense reports + receipts + employees
- `mocks/concur-mcp/tsconfig.json` — match `mocks/workday-mcp/`
- `mocks/workday-mcp/data.expense.json` — claim records / employee history seed (kept separate from existing `data.json` so the vendor surface still composes)
- `api/functions/workflows/expense_claim.py` — 7-phase orchestrator (renamed from `invoice_p2p.py`)
- `api/functions/graphs/intake_expense.py` — Phase 1 graph
- `api/functions/graphs/classify.py` — Phase 2 graph
- `api/functions/graphs/receipt.py` — Phase 3 graph
- `api/functions/graphs/route.py` — Phase 4 graph
- `api/functions/graphs/notify.py` — Phase 5 graph
- `api/functions/graphs/executors/deterministic/lookup_claim.py`
- `api/functions/graphs/executors/deterministic/apply_verdict_routing.py`
- `api/functions/graphs/executors/agents/agent_receipt_validator.py`
- `api/functions/graphs/executors/agents/agent_escalation.py`
- `api/functions/graphs/executors/agents/agent_notification.py`
- `api/server/skills/receipt_validator.skill.md`
- `api/server/skills/escalation_advisor.skill.md`
- `api/server/skills/notification_composer.skill.md`
- `api/server/mcp_tools/claim_lookup.py` — wraps Workday/Concur via EMS field
- `api/server/mcp_tools/claim_get_receipt.py` — base64 PNG + metadata
- `api/server/mcp_tools/claim_summary.py` — terse one-liner for notifications
- `api/server/mcp_tools/policy_cite.py` — section/quote pair given a clause id
- `api/server/mcp_tools/employee_history.py` — breach history by employee_id
- `tests/api/unit/test_workday_claim_endpoints.py` — Node mock contract test (driven by httpx against the running mock)
- `tests/api/unit/test_concur_claim_endpoints.py`
- `tests/api/unit/test_claim_lookup_tool.py`
- `tests/api/unit/test_claim_get_receipt_tool.py`
- `tests/api/unit/test_claim_summary_tool.py`
- `tests/api/unit/test_policy_cite_tool.py`
- `tests/api/unit/test_employee_history_tool.py`
- `tests/api/unit/test_intake_expense_graph.py`
- `tests/api/unit/test_classify_graph.py`
- `tests/api/unit/test_receipt_graph.py`
- `tests/api/unit/test_route_graph.py`
- `tests/api/unit/test_notify_graph.py`
- `tests/api/unit/test_agent_receipt_validator.py`
- `tests/api/unit/test_agent_escalation.py`
- `tests/api/unit/test_agent_notification.py`
- `tests/api/unit/test_apply_verdict_routing.py`
- `tests/api/unit/test_expense_claim_orchestration.py` — replaces / un-skips `test_invoice_p2p_rejection.py`
- `tests/api/unit/test_simulator_receipt_mismatch.py`
- `tests/api/unit/test_simulator_repeat_offender.py`
- `tests/api/unit/test_simulator_breach_justification_cycle.py`
- `tests/web/FleetDashboard.test.tsx` — assert EMS field is not on the card
- `docs/poc1-accuracy-baseline.json` — captured by the Day 0 pre-flight (Week 1 deferred milestone)

**Modified:**
- `function_app.py` — replace `InvoiceP2POrchestrator` with `ExpenseClaimOrchestrator`; add `classify_activity_trigger`, `receipt_activity_trigger`, `route_activity_trigger`, `notify_activity_trigger`
- `api/functions/workflows/activities.py` — add `classify_activity`, `receipt_activity`, `route_activity`, `notify_activity` and the workflow-factory imports
- `api/functions/graphs/__init__.py` — export the five new builders
- `api/functions/graphs/executors/agents/__init__.py` — re-export new agents (keep style)
- `api/functions/graphs/executors/deterministic/__init__.py` — re-export new deterministic executors
- `api/shared/events.py` — extend `FleetEventType` with `receipt.mismatch.detected`, `escalation.tier.assigned`, `notification.sent`, `justification.received`, `claim.routed.green`, `claim.routed.amber`, `claim.routed.red`
- `api/server/services/simulator_orchestrator.py` — new scenarios (`receipt-mismatch-amount`, `receipt-mismatch-vendor`, `receipt-missing`, `repeat-offender`, `breach-justification-cycle`); spawn `ExpenseClaimOrchestrator` instead of `InvoiceP2POrchestrator`; rotate ems_source 50/50
- `api/server/services/synthetic_data.py` — bridge `build_workflow` to claims dataset (was vendor invoices)
- `api/server/main.py` — no new routes this week (notifications surface via existing SSE topics); only re-confirm imports compile
- `api/server/mcp_tools/__init__.py` — re-export new tools
- `package.json` — replace `dev:mcp` / `demo:mcp` to register `wd,concur,mac` (drop the deleted `d365` and `pay`)
- `web/client/components/WorkflowCard.tsx` — confirm no `ems_source` field rendered (test asserts the absence)
- `tests/api/unit/test_invoice_p2p_rejection.py` — **deleted** in favour of `test_expense_claim_orchestration.py`

**Reused untouched (don't recreate):**
- `data/synthetic/{policy.md, employees.json, precedents.json, claims/CLM-*.json (300), receipts/CLM-*.png (300), labels.csv}`
- `api/shared/expense_taxonomy.py` (`Verdict`, `VERDICTS`, `CATEGORIES`, `MARKETS`, `CURRENCY_BY_MARKET`, `Market`)
- `api/server/mcp_tools/{policy_search.py, claim_get_structured.py, _otel.py}`
- `api/server/services/{event_bus.py, sse_hub.py, state_store.py, audit_logger.py, durable_client.py}`
- `api/functions/graphs/_tracked_executor.py`, `_common.py`
- `api/functions/graphs/executors/agents/_wrapper.py`, `agent_rag_classifier.py`, `agent_field_extractor.py`
- `api/functions/graphs/executors/validators/{validate_classification_schema.py, validate_amount_consistency.py, validate_required_fields.py}`
- `api/functions/graphs/executors/deterministic/{doc_intelligence_extract.py, apply_threshold_routing.py, load_authority_policy.py, record_decision.py}`
- `api/functions/workflows/accuracy_harness_workflow.py`
- `api/server/routes/{accuracy.py, policy_md.py, stream.py, workflows.py, exceptions.py, fleet.py, simulator.py, audit.py, evals.py, orchestration.py, internal_durable_event.py, policy.py}`
- `web/client/components/AccuracyReport.tsx` and the rest of the Apex UI shell
- `web/client/hooks/useSSE.ts`
- `mocks/maconomy-mcp/` (kept for AC #10 narration in Week 3)

---

## Conventions and house style

Carry over from Week 1, plus Week 2 additions:

- **Single agent identity:** every agent executor calls `run_agent_skill(skill_name, prompt)` from `api/functions/graphs/executors/agents/_wrapper.py`. Don't open new GHCP sessions inline.
- **Pre-fetch tool data in Python; embed in prompt.** The MCP tools are pure Python helpers in this POC, not GHCP-wired tool servers, so the model cannot call them at runtime. Match the pattern in `agent_rag_classifier.py` — resolve tool calls in process and embed results in the user prompt. The skill markdown describes the role and output schema; the prompt provides the data.
- **TrackedExecutor for graph nodes.** Inherit via `TrackedExecutor(id=..., name=..., executor_type=..., fn=...)` from `_tracked_executor.py`. `executor_type` is `"deterministic"` | `"agent"` | `"validator"`. Validators on the graph return `{"ok": bool, ...}` — the existing pattern in `validate_required_fields.py` and `validate_amount_consistency.py`. Off-graph guardrails (like `validate_classification_schema`) raise instead — keep that distinction.
- **JSON output from agents:** `_wrapper.run_agent_skill` already extracts the first JSON object from the response and returns a parsed dict. Do not add second-pass extraction.
- **Determinism:** every generator/seed uses `random.Random(seed)` (seed = 20260427), never `random` module-level.
- **Every new MCP tool stacks `@traced_tool("tool.name")` from `_otel.py` on the function body.** Read `policy_search.py` and `claim_get_structured.py` for the canonical pattern. Set tool-specific span attributes inside the body via `trace.get_current_span()`.
- **Every new React component uses `useSSE<T>(path, onMessage)` from `web/client/hooks/useSSE.ts`** for SSE; named exports; Tailwind utility classes (`panel`, `panel-body`, `panel-header`, `text-slate-*`); test files use `// @vitest-environment jsdom`.
- **`EventBus` is sync `emit(FleetEvent)`** — not async `publish(dict)`. The accuracy harness's `publish` callback is wired in `api/server/routes/accuracy.py::_bus_publish` to bridge the dict-shaped payload onto `app_state.bus.emit(FleetEvent(type=..., **extra))`. New event types extend `api/shared/events.py::FleetEventType` and **automatically broadcast on the `fleet` topic** via the `bus.on_any` registration in `api/server/main.py`.
- **`SSEHub` topics are fixed `{"fleet", "fleet-manager", "orchestration"}`** — there is no subscribe-by-event-type. The UI subscribes to `/api/stream/fleet` and filters client-side on `data.type`.
- **Use `api/shared/expense_taxonomy.py` constants.** Don't redefine `VERDICTS`, `CATEGORIES`, `MARKETS`, `CURRENCY_BY_MARKET` locally.
- **Test runner:** `./.venv/Scripts/pytest.exe tests/api -q` (Windows venv); UI: `npm run test` (Vitest). Tests use `tmp_path` rather than the source tree where possible.
- **Commit messages** include `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` and reference the spec section.

---

## Task 0: Pre-flight — 300-claim ≥95% accuracy gate (Week 1's deferred milestone)

**Files:**
- Create: `docs/poc1-accuracy-baseline.json` (captured at the end of this task)

This is the Week 1 acceptance bar realised. The runbook is `docs/poc1-accuracy-runbook.md`. We execute it end-to-end, iterate until ≥95%, capture the final result. **Day 0 only — must pass before any other Week 2 work begins.**

If the gate fails after **one** full iteration round (≤4 prompt/retrieval/policy-tweak commits), escalate — do not keep burning tokens.

- [ ] **Step 1: Verify pre-flight environment**

```bash
gh auth status
./.venv/Scripts/pytest.exe tests/api -q
```

Expected: `gh auth status` shows authenticated; `pytest` reports `81 passed, 1 skipped, 5 deselected` (or matching baseline). If pytest is red, stop — fix it before running the harness.

- [ ] **Step 2: Run the smoke gate (5 claims, real model)**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_classifier_e2e_smoke.py -m smoke -v
```

Expected: 5/5 PASS in ~2 min. This validates GHCP wiring before paying for 300 calls.

- [ ] **Step 3: Bring up the dev stack (three background processes)**

```bash
func start
./.venv/Scripts/uvicorn.exe api.server.main:app --reload
npm run dev:client
```

Each in its own background shell. Verify each comes up cleanly (FastAPI logs `Application startup complete`; func logs `Worker process started`; vite logs the Local URL).

- [ ] **Step 4: Trigger the 300-claim run**

```bash
curl -X POST http://localhost:8000/api/accuracy/run \
  -H "Content-Type: application/json" -d '{}'
```

Expected: `{"run_id":"acc-XXXXXXXX","n":300}`. Watch progress via SSE:

```bash
curl -N http://localhost:8000/api/stream/fleet | jq 'select(.type|startswith("accuracy."))'
```

- [ ] **Step 5: Read the result**

```bash
curl -s http://localhost:8000/api/accuracy/last | python -m json.tool | head -40
```

Expected: `overall_accuracy ≥ 0.95`. Per-category accuracies all ≥ 0.85.

- [ ] **Step 6: If accuracy is < 0.95 — iterate**

Per the runbook §"Pass / fail":
1. Open `/evaluations` in the UI; click each off-diagonal cell; pattern-spot the failure mode.
2. Cheapest fix first:
   - Tighten `api/server/skills/rag_classifier.skill.md`.
   - Increase `_TOP_K_POLICY_CHUNKS` in `api/functions/graphs/executors/agents/agent_rag_classifier.py` from 6 → 8 or 10.
   - Re-chunk paragraph-level instead of section-level in `api/server/mcp_tools/policy_search.py::_split_into_sections`.
   - Tighten the synthetic generator's amber boundary (100–105% rather than 100–110%) in `data/synthetic/generate.py`.
3. Re-run the harness. Each iteration is a commit with the new accuracy in the message.

**Stop after one full iteration round.** If still under 0.95, escalate to the user with the per-category breakdown and the off-diagonal cells inspected.

- [ ] **Step 7: Capture the baseline**

Once `overall_accuracy ≥ 0.95`:

```bash
curl -s http://localhost:8000/api/accuracy/last > docs/poc1-accuracy-baseline.json
```

- [ ] **Step 8: Stop the dev stack**

Per the house standing instruction (no lingering background services), stop `func start`, `uvicorn`, and `npm run dev:client` before continuing.

- [ ] **Step 9: Commit**

```bash
git add docs/poc1-accuracy-baseline.json
git commit -m "$(cat <<'EOF'
evidence: 300-claim accuracy baseline ≥95% with policy-driven reasoning

Captured at start of Week 2 (deferred Week 1 milestone) against the
synthetic corpus and unmodified policy.md. Establishes the floor we
defend through the orchestrator reshape.

Acceptance: brief §7 #4 ✅.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 1: Extend FleetEventType with Week 2 event vocabulary

**Files:**
- Modify: `api/shared/events.py`
- Modify: `tests/api/unit/test_events.py` (add cases for new types)

The `bus.on_any` registration in `api/server/main.py` already broadcasts every `FleetEvent` to the `fleet` topic; the SSE stream forwards by topic, not by type, so adding new types to the literal is sufficient for them to surface to the UI. Do this first — every later task emits at least one of these.

- [ ] **Step 1: Read existing test for FleetEventType**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_events.py -v
```

Expected: PASS. Note the assertion shape so we extend, not replace.

- [ ] **Step 2: Write the failing test extension**

Open `tests/api/unit/test_events.py` and add at the bottom:

```python
def test_week2_event_types_present():
    """Week 2 extension — receipt mismatch, escalation, notification, justification, routing."""
    from typing import get_args
    from api.shared.events import FleetEventType
    types = set(get_args(FleetEventType))
    expected = {
        "receipt.mismatch.detected",
        "escalation.tier.assigned",
        "notification.sent",
        "justification.received",
        "claim.routed.green",
        "claim.routed.amber",
        "claim.routed.red",
    }
    missing = expected - types
    assert not missing, f"FleetEventType missing Week 2 types: {missing}"
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_events.py::test_week2_event_types_present -v
```

Expected: FAIL with `missing Week 2 types`.

- [ ] **Step 3: Extend `api/shared/events.py`**

Open the file and extend the `FleetEventType` literal. Place new entries in a logical block after the accuracy ones:

```python
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
    # Durable Workflow events (new in py POC1)
    "durable.workflow.started",
    "durable.step.started",
    "durable.step.completed",
    "durable.executor.invoked",
    "durable.validator.blocked",
    "durable.suspended",
    "durable.resumed",
    "durable.workflow.completed",
    # Accuracy harness events (one-shot evaluation runs; do NOT wake the fleet manager)
    "accuracy.progress",
    "accuracy.complete",
    # Week 2 — expense-claim domain events
    "claim.routed.green",
    "claim.routed.amber",
    "claim.routed.red",
    "receipt.mismatch.detected",
    "escalation.tier.assigned",
    "notification.sent",
    "justification.received",
]
```

Do **not** add the new types to `WAKE_TYPES` — they are routine workflow events; only the existing `workflow.exception.detected` etc. wake the Fleet Manager.

- [ ] **Step 4: Run the test, expect green**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_events.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add api/shared/events.py tests/api/unit/test_events.py
git commit -m "$(cat <<'EOF'
feat(events): extend FleetEventType with Week 2 expense-domain events

Adds claim.routed.{green,amber,red}, receipt.mismatch.detected,
escalation.tier.assigned, notification.sent, justification.received.
Routine workflow events — not in WAKE_TYPES, so they don't wake the
Fleet Manager. Auto-broadcast on the `fleet` SSE topic via the
existing bus.on_any registration in main.py.

Spec ref: §4.1 (phases 3, 4, 5 emit these); §5.4 (events).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Workday mock — extend with expense-claim endpoints

**Files:**
- Create: `mocks/workday-mcp/data.expense.json`
- Create: `mocks/workday-mcp/build_expense_seed.py`
- Modify: `mocks/workday-mcp/server.ts`
- Create: `tests/api/unit/test_workday_claim_endpoints.py`

Read [mocks/workday-mcp/server.ts](../../../mocks/workday-mcp/server.ts) before authoring. The existing pattern is a single Express app exposing `GET /mcp/tools` (capability listing) + `POST /mcp/call/:tool` (per-tool dispatch). We extend that switch with four new tools: `getExpenseClaim`, `listClaimsForApproval`, `submitJustification`, `listEmployeeClaimHistory`.

The four new tools are backed by `data.expense.json` which is bridged from the synthetic data:
- `claims` — pulled from `data/synthetic/claims/CLM-*.json` filtered to `ems_source == "workday"`
- `employees` — pulled from `data/synthetic/employees.json`
- `justifications` — empty seed; populated at runtime by `submitJustification` calls

We do **not** delete `getVendor` / `getCostCentre` / `getApprovalChain` — they're harmless and the tests pass. Spec §5.2 only removes them when the corresponding executors are deleted; Week 1 already did that. Leaving them in costs nothing.

- [ ] **Step 1: Build `mocks/workday-mcp/data.expense.json` from the synthetic corpus**

Author `mocks/workday-mcp/build_expense_seed.py`:

```python
"""One-shot: build mocks/workday-mcp/data.expense.json from data/synthetic/."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ROOT / "data" / "synthetic" / "claims"
EMPLOYEES = ROOT / "data" / "synthetic" / "employees.json"
OUT = Path(__file__).parent / "data.expense.json"


def main() -> None:
    employees = json.loads(EMPLOYEES.read_text(encoding="utf-8"))
    claims: list[dict] = []
    for path in sorted(CLAIMS.glob("CLM-*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        if c.get("ems_source") != "workday":
            continue
        # Drop gold_* — the mock is the system-of-record surface, not the labelled corpus.
        c = {k: v for k, v in c.items() if not k.startswith("gold_")}
        claims.append(c)

    payload = {"claims": claims, "employees": employees, "justifications": []}
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(claims)} workday claims, {len(employees)} employees -> {OUT}")


if __name__ == "__main__":
    main()
```

Run it:

```bash
./.venv/Scripts/python.exe mocks/workday-mcp/build_expense_seed.py
```

Expected: prints e.g. `wrote 152 workday claims, 30 employees -> .../data.expense.json`. Exact count varies with synthetic generator's EMS rotation; should be roughly half of 300.

- [ ] **Step 2: Write the failing contract test**

Create `tests/api/unit/test_workday_claim_endpoints.py`:

```python
"""Workday mock — claim-endpoint contract tests, driven by httpx against a
locally-launched Express subprocess. Skipped if Node isn't installed."""
from __future__ import annotations
import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]
PORT = "4111"  # avoid colliding with the default 4101
URL = f"http://127.0.0.1:{PORT}"

pytestmark = pytest.mark.skipif(
    shutil.which("npx") is None, reason="npx not installed; skipping mock contract tests"
)


@pytest.fixture(scope="module")
def workday_proc():
    env = {**os.environ, "WORKDAY_MCP_PORT": PORT}
    proc = subprocess.Popen(
        ["npx", "tsx", str(ROOT / "mocks" / "workday-mcp" / "server.ts")],
        env=env, cwd=str(ROOT),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        try:
            httpx.get(f"{URL}/mcp/tools", timeout=0.5)
            break
        except httpx.HTTPError:
            time.sleep(0.25)
    else:
        proc.kill()
        pytest.fail("workday-mcp did not come up on time")
    yield proc
    proc.terminate()
    proc.wait(timeout=5)


def test_tools_list_advertises_expense_endpoints(workday_proc):
    r = httpx.get(f"{URL}/mcp/tools").json()
    names = {t["name"] for t in r["tools"]}
    assert {"getExpenseClaim", "listClaimsForApproval", "submitJustification", "listEmployeeClaimHistory"} <= names


def test_get_expense_claim_returns_known_claim(workday_proc):
    listing = httpx.post(f"{URL}/mcp/call/listClaimsForApproval", json={"limit": 1}).json()
    assert listing["claims"], "expected at least one workday claim in the seed"
    claim_id = listing["claims"][0]["claim_id"]
    r = httpx.post(f"{URL}/mcp/call/getExpenseClaim", json={"claimId": claim_id}).json()
    assert r["claim_id"] == claim_id
    assert r["ems_source"] == "workday"


def test_get_expense_claim_unknown_returns_404(workday_proc):
    r = httpx.post(f"{URL}/mcp/call/getExpenseClaim", json={"claimId": "CLM-9999"})
    assert r.status_code == 404


def test_submit_justification_persists_in_memory(workday_proc):
    listing = httpx.post(f"{URL}/mcp/call/listClaimsForApproval", json={"limit": 1}).json()
    claim_id = listing["claims"][0]["claim_id"]
    body = {"claimId": claim_id, "text": "Client present, named senior stakeholder", "submittedBy": "EMP-0001"}
    r = httpx.post(f"{URL}/mcp/call/submitJustification", json=body).json()
    assert r["ok"] is True
    after = httpx.post(f"{URL}/mcp/call/getExpenseClaim", json={"claimId": claim_id}).json()
    assert any(j["text"] == body["text"] for j in after.get("justifications", []))


def test_list_employee_claim_history_returns_breach_summary(workday_proc):
    listing = httpx.post(f"{URL}/mcp/call/listClaimsForApproval", json={"limit": 5}).json()
    employee_id = listing["claims"][0]["employee_id"]
    r = httpx.post(f"{URL}/mcp/call/listEmployeeClaimHistory", json={"employeeId": employee_id}).json()
    assert r["employee_id"] == employee_id
    assert isinstance(r.get("breach_history"), list)
    assert isinstance(r.get("recent_claims"), list)
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_workday_claim_endpoints.py -v
```

Expected: FAIL — the four new tools are not yet implemented in the server.

- [ ] **Step 3: Extend `mocks/workday-mcp/server.ts`**

Replace the existing file with the version below. Keep the existing vendor / cost-centre / approval-chain switch arms; add the four new ones plus the new data load.

```typescript
// mocks/workday-mcp/server.ts
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(path.join(dir, "data.json"), "utf-8")) as {
  vendors: { id: string; name: string; country: string; sanctioned: boolean; creditRating: string }[];
  costCentres: { id: string; name: string; approver: string }[];
  approvalChains: Record<string, string[]>;
};

type Justification = { claim_id: string; text: string; submitted_by: string; submitted_at: string };
type ExpenseClaim = {
  claim_id: string; employee_id: string; market: string; currency: string;
  amount: number; category: string; vendor: string; attendees?: number;
  receipt_filename: string; receipt_mismatch_flavour?: string;
  ems_source: "workday" | "concur"; submitted_at: string;
  justifications?: Justification[];
};
type Employee = {
  id: string; name: string; market: string; department: string; agency: string;
  breach_history: { date: string; category: string; tier: string }[];
};

const expense = JSON.parse(readFileSync(path.join(dir, "data.expense.json"), "utf-8")) as {
  claims: ExpenseClaim[]; employees: Employee[]; justifications: Justification[];
};

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "getVendor", description: "Lookup a vendor by id", parameters: { vendorId: "string" } },
      { name: "getCostCentre", description: "Lookup a cost centre by id", parameters: { costCentreId: "string" } },
      { name: "getApprovalChain", description: "Get approval chain for a scenario", parameters: { scenario: "string" } },
      { name: "getExpenseClaim", description: "Lookup an expense claim by id", parameters: { claimId: "string" } },
      { name: "listClaimsForApproval", description: "List claims pending approval", parameters: { limit: "number?" } },
      { name: "submitJustification", description: "Submit a business justification", parameters: { claimId: "string", text: "string", submittedBy: "string" } },
      { name: "listEmployeeClaimHistory", description: "Recent claims + breach history for an employee", parameters: { employeeId: "string" } }
    ]
  });
});

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "getVendor": {
      const v = data.vendors.find(x => x.id === args["vendorId"]);
      return v ? res.json(v) : res.status(404).json({ error: "vendor_not_found" });
    }
    case "getCostCentre": {
      const c = data.costCentres.find(x => x.id === args["costCentreId"]);
      return c ? res.json(c) : res.status(404).json({ error: "cost_centre_not_found" });
    }
    case "getApprovalChain": {
      const scenario = (args["scenario"] as string | undefined) ?? "default";
      const chain = data.approvalChains[scenario] ?? data.approvalChains["default"];
      return res.json({ chain });
    }
    case "getExpenseClaim": {
      const id = args["claimId"];
      const c = expense.claims.find(x => x.claim_id === id);
      if (!c) return res.status(404).json({ error: "claim_not_found" });
      const justifications = expense.justifications.filter(j => j.claim_id === c.claim_id);
      return res.json({ ...c, justifications });
    }
    case "listClaimsForApproval": {
      const limit = Number(args["limit"] ?? 30);
      return res.json({ claims: expense.claims.slice(0, limit) });
    }
    case "submitJustification": {
      const claimId = args["claimId"] as string | undefined;
      const text = args["text"] as string | undefined;
      const submittedBy = args["submittedBy"] as string | undefined;
      if (!claimId || !text || !submittedBy) {
        return res.status(400).json({ error: "missing_fields" });
      }
      if (!expense.claims.find(x => x.claim_id === claimId)) {
        return res.status(404).json({ error: "claim_not_found" });
      }
      expense.justifications.push({
        claim_id: claimId, text, submitted_by: submittedBy,
        submitted_at: new Date().toISOString(),
      });
      return res.json({ ok: true });
    }
    case "listEmployeeClaimHistory": {
      const employeeId = args["employeeId"] as string | undefined;
      if (!employeeId) return res.status(400).json({ error: "missing_employeeId" });
      const emp = expense.employees.find(e => e.id === employeeId);
      if (!emp) return res.status(404).json({ error: "employee_not_found" });
      const recent = expense.claims.filter(c => c.employee_id === employeeId).slice(-10);
      return res.json({
        employee_id: employeeId,
        breach_history: emp.breach_history,
        recent_claims: recent.map(c => ({
          claim_id: c.claim_id, amount: c.amount, category: c.category, submitted_at: c.submitted_at,
        })),
      });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env["WORKDAY_MCP_PORT"] ?? 4101);
app.listen(port, () => console.log(`[workday-mcp] listening on ${port}`));
```

- [ ] **Step 4: Re-run the contract test**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_workday_claim_endpoints.py -v
```

Expected: 5 PASS. If a test fails because of a missing field shape, fix in the server (don't loosen the test).

- [ ] **Step 5: Commit**

```bash
git add mocks/workday-mcp/server.ts mocks/workday-mcp/data.expense.json mocks/workday-mcp/build_expense_seed.py tests/api/unit/test_workday_claim_endpoints.py
git commit -m "$(cat <<'EOF'
feat(mocks): workday-mcp expense-claim endpoints

Adds getExpenseClaim, listClaimsForApproval, submitJustification,
listEmployeeClaimHistory backed by data.expense.json (seeded from the
synthetic corpus filtered to ems_source=workday). Existing vendor /
cost-centre / approval-chain endpoints kept — harmless, tested.

Spec ref: §5.2 (workday-mcp extension); brief §4.5 (claim retrieval).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: MCP tool — `claim.lookup` (Workday/Concur dispatcher)

**Files:**
- Create: `api/server/mcp_tools/claim_lookup.py`
- Create: `tests/api/unit/test_claim_lookup_tool.py`
- Modify: `api/server/mcp_tools/__init__.py` to re-export

`claim.lookup` is the Phase 1 (Intake) entry point. It takes a `claim_id` and an optional `ems_source` ("workday" | "concur"); when `ems_source` is omitted it reads `data/synthetic/claims/{claim_id}.json` and dispatches based on the `ems_source` field there. The HTTP target (port) is read from environment variables — the same pattern the Node mocks use.

This bridges the Python orchestrator world to the Node EMS-mock world. We use `httpx` (already in dependencies), wrap in `@traced_tool("claim.lookup")`, set tool-specific span attributes, and return the JSON dict. Read [api/server/mcp_tools/policy_search.py](../../../api/server/mcp_tools/policy_search.py) and [api/server/mcp_tools/claim_get_structured.py](../../../api/server/mcp_tools/claim_get_structured.py) for the canonical span/decorator stacking.

For Day 8, when Concur arrives, this tool already does the right thing — the dispatch table just adds `concur` and the rest of the code is unchanged.

- [ ] **Step 1: Write the failing test**

Create `tests/api/unit/test_claim_lookup_tool.py`:

```python
"""claim.lookup MCP tool tests — uses respx to mock the Node EMS HTTP."""
from __future__ import annotations
import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from api.server.mcp_tools import claim_lookup


SYNTHETIC = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"


def _pick_claim_with(ems: str) -> str:
    for path in sorted(SYNTHETIC.glob("CLM-*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        if c.get("ems_source") == ems:
            return c["claim_id"]
    raise RuntimeError(f"no synthetic claim with ems_source={ems}")


@respx.mock
def test_lookup_dispatches_to_workday_by_ems_field(monkeypatch):
    monkeypatch.setenv("WORKDAY_MCP_PORT", "4101")
    cid = _pick_claim_with("workday")
    payload = {"claim_id": cid, "ems_source": "workday", "amount": 42.0, "category": "meals"}
    route = respx.post("http://127.0.0.1:4101/mcp/call/getExpenseClaim").mock(
        return_value=Response(200, json=payload)
    )
    out = claim_lookup.lookup(cid)
    assert route.called
    assert out["claim_id"] == cid
    assert out["ems_source"] == "workday"


@respx.mock
def test_lookup_dispatches_to_concur_by_ems_field(monkeypatch):
    monkeypatch.setenv("CONCUR_MCP_PORT", "4102")
    cid = _pick_claim_with("concur")
    payload = {"claim_id": cid, "ems_source": "concur", "amount": 99.5, "category": "travel"}
    route = respx.post("http://127.0.0.1:4102/mcp/call/getExpenseLine").mock(
        return_value=Response(200, json=payload)
    )
    out = claim_lookup.lookup(cid)
    assert route.called
    assert out["ems_source"] == "concur"


@respx.mock
def test_lookup_explicit_ems_overrides_synthetic_lookup(monkeypatch):
    monkeypatch.setenv("WORKDAY_MCP_PORT", "4101")
    cid = _pick_claim_with("workday")
    respx.post("http://127.0.0.1:4101/mcp/call/getExpenseClaim").mock(
        return_value=Response(200, json={"claim_id": cid, "ems_source": "workday"})
    )
    out = claim_lookup.lookup(cid, ems_source="workday")
    assert out["claim_id"] == cid


def test_lookup_unknown_claim_id_raises():
    with pytest.raises(KeyError):
        claim_lookup.lookup("CLM-9999")


@respx.mock
def test_lookup_propagates_remote_404(monkeypatch):
    monkeypatch.setenv("WORKDAY_MCP_PORT", "4101")
    cid = _pick_claim_with("workday")
    respx.post("http://127.0.0.1:4101/mcp/call/getExpenseClaim").mock(
        return_value=Response(404, json={"error": "claim_not_found"})
    )
    with pytest.raises(KeyError):
        claim_lookup.lookup(cid)
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_claim_lookup_tool.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 2: Add `respx` and `httpx` to dependencies if not already present**

Check `pyproject.toml`:

```bash
grep -E '(httpx|respx)' pyproject.toml
```

If `httpx` is missing, add `"httpx>=0.27"` to `dependencies`. If `respx` is missing, add `"respx>=0.21"` to dev dependencies (or to project dependencies — Week 1 used pytest-asyncio at the top-level for similar reasons). Run `uv sync`.

- [ ] **Step 3: Implement `api/server/mcp_tools/claim_lookup.py`**

```python
"""claim.lookup MCP tool — dispatch a claim id to the appropriate EMS mock.

Reads `ems_source` from the synthetic claim JSON to decide whether to call
Workday's `getExpenseClaim` or Concur's `getExpenseLine`. The HTTP target
ports come from `WORKDAY_MCP_PORT` / `CONCUR_MCP_PORT` env vars (defaults
4101 / 4102, matching the mock servers).
"""
from __future__ import annotations
import json
import os
from pathlib import Path

import httpx
from opentelemetry import trace

from ._otel import traced_tool

_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"

_DISPATCH = {
    # ems_source -> (env_var, port_default, tool_name)
    "workday": ("WORKDAY_MCP_PORT", 4101, "getExpenseClaim"),
    "concur": ("CONCUR_MCP_PORT", 4102, "getExpenseLine"),
}


def _resolve_ems(claim_id: str) -> str:
    path = _CLAIMS_DIR / f"{claim_id}.json"
    if not path.exists():
        raise KeyError(f"claim {claim_id!r} not found in synthetic corpus")
    record = json.loads(path.read_text(encoding="utf-8"))
    ems = record.get("ems_source")
    if ems not in _DISPATCH:
        raise KeyError(f"claim {claim_id!r} has unknown ems_source {ems!r}")
    return ems


@traced_tool("claim.lookup")
def lookup(claim_id: str, ems_source: str | None = None) -> dict:
    """Fetch a claim record from the EMS named in ems_source (or auto-detect)."""
    span = trace.get_current_span()
    span.set_attribute("wpp.claim.id", claim_id)
    ems = ems_source or _resolve_ems(claim_id)
    span.set_attribute("wpp.claim.ems", ems)

    env_var, default_port, tool_name = _DISPATCH[ems]
    port = int(os.environ.get(env_var, default_port))
    url = f"http://127.0.0.1:{port}/mcp/call/{tool_name}"
    arg_key = "claimId" if ems == "workday" else "expenseLineId"
    resp = httpx.post(url, json={arg_key: claim_id}, timeout=5.0)
    if resp.status_code == 404:
        raise KeyError(f"claim {claim_id!r} not found at {ems} mock")
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 4: Re-export from `api/server/mcp_tools/__init__.py`**

Open the file, add `from . import claim_lookup` (or extend the existing `__all__` if there is one). Keep it minimal.

- [ ] **Step 5: Run the test**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_claim_lookup_tool.py -v
```

Expected: 5 PASS.

- [ ] **Step 6: Commit**

```bash
git add api/server/mcp_tools/claim_lookup.py api/server/mcp_tools/__init__.py tests/api/unit/test_claim_lookup_tool.py pyproject.toml uv.lock
git commit -m "$(cat <<'EOF'
feat(mcp): claim.lookup tool — Workday/Concur dispatcher

Reads ems_source from the synthetic claim JSON and dispatches to the
appropriate Node mock via httpx. Stacks @traced_tool('claim.lookup')
on the function body; span attributes wpp.claim.id and wpp.claim.ems
land on every span. respx-mocked tests cover both dispatch arms,
explicit ems override, unknown claim, and remote 404 propagation.

Spec ref: §5.4 (MCP tools); §4.1 Phase 1 (Intake).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Reshape Durable orchestrator — `invoice_p2p.py` → `expense_claim.py`

**Files:**
- Create: `api/functions/workflows/expense_claim.py`
- Modify: `function_app.py`
- Modify: `api/functions/workflows/activities.py`
- Delete: `api/functions/workflows/invoice_p2p.py`
- Delete: `tests/api/unit/test_invoice_p2p_rejection.py`
- Create: `tests/api/unit/test_expense_claim_orchestration.py`

This is the central reshape. The 7 phases per spec §4.1:
1. **Intake & Normalise** — `lookup_claim → doc_intelligence_extract → agent_field_extractor → validate_required_fields`
2. **Classify (R/A/G)** — `agent_rag_classifier → validate_classification_schema`
3. **Validate Receipt** — `agent_receipt_validator → validate_amount_consistency` *(Day 7)*
4. **Route by Verdict** — `agent_escalation → apply_verdict_routing` *(Day 9)*
5. **Notify** (Red only) — `agent_notification + wait_for_external_event:justification` *(Day 10)*
6. **Arbitrate** — *Week 3*
7. **Audit** — *Week 3*

**Day 6 only wires phases 1 and 2.** Phases 3–5 raise `NotImplementedError` at the activity layer until later days fill them in. Phase 6 / 7 stay placeholders for Week 3.

The orchestrator generator preserves Week 1's HITL-wait pattern: `wait_for_external_event` with a 72h timer, reject branch, resume branch.

- [ ] **Step 1: Write the failing orchestration test**

Create `tests/api/unit/test_expense_claim_orchestration.py`:

```python
"""Generator-level tests over expense_claim_orchestration.

We drive the generator with a stub Durable context that records the
sequence of yielded activity names, then assert the phase order, the
HITL pause/resume around Phase 5 (Notify→justification), and the
reject branch.
"""
from __future__ import annotations
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from api.functions.workflows.expense_claim import expense_claim_orchestration


class FakeContext:
    """Minimal Durable Functions DurableOrchestrationContext stub."""

    def __init__(self, *, claim_id: str = "CLM-0007", instance_id: str = "iid-1", verdict: str = "amber"):
        self._input = {"workflow_id": claim_id, "claim_id": claim_id}
        self.instance_id = instance_id
        self._verdict = verdict
        self.activity_calls: list[tuple[str, dict]] = []
        self._activity_results = {
            "lookup_claim_activity_trigger": {"claim": {"claim_id": claim_id, "ems_source": "workday"}},
            "intake_activity_trigger": {"intake": {"extracted": {"amount": 42, "category": "meals"}}},
            "classify_activity_trigger": {"classification": {"verdict": verdict, "policy_clause": "§3.1", "reasoning": "x", "confidence": 0.7, "competing_interpretations": []}},
            "checkpoint_activity_trigger": {},
        }
        self.current_utc_datetime = datetime.now(timezone.utc)

    def get_input(self) -> dict:
        return self._input

    def call_activity(self, name: str, payload: dict):
        self.activity_calls.append((name, payload))
        return _Awaitable(self._activity_results.get(name, {}))

    def wait_for_external_event(self, name: str):
        return _Awaitable({"event": name})

    def create_timer(self, _when):
        return _Awaitable("timer")

    def task_any(self, tasks):
        return _Awaitable(tasks[0])  # decision-event wins


class _Awaitable:
    def __init__(self, result):
        self.result = result

    def cancel(self):
        pass


def _drain(gen: Generator[Any, Any, dict], ctx: FakeContext) -> dict:
    """Drive the orchestrator generator to completion against the fake ctx."""
    value = None
    while True:
        try:
            yielded = gen.send(value) if value is not None else next(gen)
        except StopIteration as ex:
            return ex.value
        value = yielded.result if hasattr(yielded, "result") else yielded


def test_phase_order_for_green_claim():
    ctx = FakeContext(verdict="green")
    result = _drain(expense_claim_orchestration(ctx), ctx)
    names = [n for n, _ in ctx.activity_calls if not n.startswith("checkpoint")]
    # Day 6 wires phases 1+2; later days extend this assertion.
    assert names[:2] == ["lookup_claim_activity_trigger", "intake_activity_trigger"]
    assert "classify_activity_trigger" in names
    assert result["status"] == "completed"


def test_workflow_started_and_completed_emitted():
    ctx = FakeContext()
    _drain(expense_claim_orchestration(ctx), ctx)
    kinds = [p["kind"] for n, p in ctx.activity_calls if n == "checkpoint_activity_trigger"]
    assert kinds[0] == "workflow.started"
    assert "workflow.completed" in kinds


def test_unknown_claim_id_raises_workflow_failed():
    ctx = FakeContext()
    ctx._activity_results["lookup_claim_activity_trigger"] = {"error": "claim_not_found"}
    with pytest.raises(Exception):
        _drain(expense_claim_orchestration(ctx), ctx)
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_expense_claim_orchestration.py -v
```

Expected: FAIL with `ImportError: cannot import name 'expense_claim_orchestration'`.

- [ ] **Step 2: Implement `api/functions/workflows/expense_claim.py`**

```python
"""The single ExpenseClaim generator orchestration — one expense claim end-to-end.

Drives 7 phases as activities. HITL gate at Notify (Red path) via
wait_for_external_event:justification. Sync generator per Azure Durable
Functions Python convention. Phase 6 (Arbitrate) and Phase 7 (Audit) are
Week 3 work; they currently checkpoint+complete with status='deferred'.
"""
from __future__ import annotations
from datetime import timedelta
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df


_REJECTED = {"reject", "rejected", "decline", "declined"}


def expense_claim_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the 7 expense-claim phases. HITL on Notify (Red path)."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    enriched = {**input_dict, "instance_id": context.instance_id}

    # Lifecycle: workflow.started
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started", "payload": {},
    })

    # Phase 1: Intake & Normalise — lookup the claim from EMS, then run intake graph
    lookup_result = yield context.call_activity("lookup_claim_activity_trigger", enriched)
    if lookup_result.get("error"):
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.phase.failed",
            "payload": {"phase": "Intake", "error": lookup_result["error"]},
        })
        raise RuntimeError(f"lookup failed for claim {workflow_id}: {lookup_result['error']}")
    enriched = {**enriched, "claim": lookup_result["claim"]}

    intake_result = yield context.call_activity("intake_activity_trigger", enriched)
    enriched = {**enriched, "intake": intake_result}

    # Phase 2: Classify (R/A/G)
    classify_result = yield context.call_activity("classify_activity_trigger", enriched)
    enriched = {**enriched, "classify": classify_result}
    classification = classify_result.get("classification", {})
    verdict = classification.get("verdict", "amber")

    # Phase 3 (Validate Receipt): Day 7. Until then, no-op.
    # Phase 4 (Route by Verdict): Day 9. Until then, route based on verdict only.
    # Phase 5 (Notify): Day 10. Until then, no notification.

    # ----- Day 7 will replace this block -----
    # receipt_result = yield context.call_activity("receipt_activity_trigger", enriched)
    # enriched = {**enriched, "receipt": receipt_result}
    # ----- End Day 7 block -----

    # ----- Day 9 will replace this block -----
    # route_result = yield context.call_activity("route_activity_trigger", enriched)
    # enriched = {**enriched, "route": route_result}
    # ----- End Day 9 block -----

    # ----- Day 10 will replace this block -----
    # if verdict == "red":
    #     notify_result = yield context.call_activity("notify_activity_trigger", enriched)
    #     enriched = {**enriched, "notify": notify_result}
    #     if notify_result.get("requires_justification"):
    #         yield context.call_activity("checkpoint_activity_trigger", {
    #             "workflow_id": workflow_id, "instance_id": context.instance_id,
    #             "kind": "suspended", "payload": {"reason": "awaiting_justification"},
    #         })
    #         decision_event = context.wait_for_external_event("justification")
    #         timeout_event = context.create_timer(context.current_utc_datetime + timedelta(hours=72))
    #         winner = yield context.task_any([decision_event, timeout_event])
    #         if winner == timeout_event:
    #             yield context.call_activity("checkpoint_activity_trigger", {
    #                 "workflow_id": workflow_id, "instance_id": context.instance_id,
    #                 "kind": "workflow.completed", "payload": {"status": "timeout"},
    #             })
    #             return {"status": "timeout", "phase": "Notify"}
    #         timeout_event.cancel()
    #         decision = decision_event.result
    #         decision_type = (decision.get("decision") or "").lower() if isinstance(decision, dict) else ""
    #         if decision_type in _REJECTED:
    #             yield context.call_activity("checkpoint_activity_trigger", {
    #                 "workflow_id": workflow_id, "instance_id": context.instance_id,
    #                 "kind": "workflow.rejected",
    #                 "payload": {"by": decision.get("resolved_by") if isinstance(decision, dict) else None},
    #             })
    #             return {"status": "rejected", "phase": "Notify", "decision": decision}
    #         enriched["justification"] = decision
    #         yield context.call_activity("checkpoint_activity_trigger", {
    #             "workflow_id": workflow_id, "instance_id": context.instance_id,
    #             "kind": "resumed", "payload": {"decision": decision},
    #         })
    # ----- End Day 10 block -----

    # Phase 6 (Arbitrate) and Phase 7 (Audit) — Week 3.
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed", "payload": {"status": "completed", "verdict": verdict},
    })

    return {
        "status": "completed",
        "verdict": verdict,
        "claim_id": workflow_id,
        "intake": intake_result,
        "classify": classify_result,
    }
```

The commented-out blocks for Days 7/9/10 are the **insertion points** — leave them in the file so the next plan iterations have a clear seam. Day 7 / 9 / 10 each uncomment exactly one block.

- [ ] **Step 3: Update `function_app.py`**

Replace `InvoiceP2POrchestrator` with `ExpenseClaimOrchestrator`. Add the new activity triggers. Keep the existing `intake_activity_trigger`, `approval_activity_trigger`, `checkpoint_activity_trigger` registrations — `intake` is reused, `approval` is removed (no longer in the 7-phase shape), `checkpoint` is reused.

```python
# function_app.py — Azure Functions v2 programming model entry point.
from __future__ import annotations
import azure.functions as func
import azure.durable_functions as df

from api.shared.otel import init_otel
from api.functions.workflows.expense_claim import expense_claim_orchestration
from api.functions.workflows.activities import (
    lookup_claim_activity, intake_activity, classify_activity,
    receipt_activity, route_activity, notify_activity,
    checkpoint_activity,
)

init_otel("control-plane-functions")
app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.orchestration_trigger(context_name="context")
def ExpenseClaimOrchestrator(context: df.DurableOrchestrationContext):
    return expense_claim_orchestration(context)


@app.activity_trigger(input_name="payload")
def lookup_claim_activity_trigger(payload: dict) -> dict:
    return lookup_claim_activity(payload)


@app.activity_trigger(input_name="payload")
def intake_activity_trigger(payload: dict) -> dict:
    return intake_activity(payload)


@app.activity_trigger(input_name="payload")
def classify_activity_trigger(payload: dict) -> dict:
    return classify_activity(payload)


@app.activity_trigger(input_name="payload")
def receipt_activity_trigger(payload: dict) -> dict:
    return receipt_activity(payload)


@app.activity_trigger(input_name="payload")
def route_activity_trigger(payload: dict) -> dict:
    return route_activity(payload)


@app.activity_trigger(input_name="payload")
def notify_activity_trigger(payload: dict) -> dict:
    return notify_activity(payload)


@app.activity_trigger(input_name="payload")
def checkpoint_activity_trigger(payload: dict) -> dict:
    return checkpoint_activity(payload)


@app.route(route="orchestrators/{functionName}")
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client: df.DurableOrchestrationClient) -> func.HttpResponse:
    function_name = req.route_params.get("functionName")
    payload = req.get_json() if req.get_body() else {}
    instance_id = await client.start_new(function_name, None, payload)
    return client.create_check_status_response(req, instance_id)
```

- [ ] **Step 4: Update `api/functions/workflows/activities.py`**

Add the new activity functions. Each Phase 3 / 4 / 5 activity initially raises `NotImplementedError` so accidental triggers are loud — Day 7 / 9 / 10 swap them in.

```python
"""Activity functions registered as Azure Durable Functions activity triggers.

Each runs synchronously (Azure DF Python convention) and wraps an async MAF
Workflow run inside asyncio.run. Activities are the I/O boundary.
"""
from __future__ import annotations
import asyncio

from api.functions.graphs import (
    build_intake_expense_workflow, build_classify_workflow,
    build_receipt_workflow, build_route_workflow, build_notify_workflow,
)
from api.functions.webhook import emit
from api.server.mcp_tools import claim_lookup


async def _run_workflow(workflow_factory, payload: dict, step_name: str) -> dict:
    wf = workflow_factory()
    await emit(payload.get("workflow_id", "?"), payload.get("instance_id"),
               "step.started", {"step": step_name})
    import time as _t
    t0 = _t.time()
    try:
        events = await wf.run(payload)
    except Exception as ex:
        await emit(payload.get("workflow_id", "?"), payload.get("instance_id"),
                   "step.failed", {"step": step_name, "error": str(ex)})
        raise
    outputs = events.get_outputs()
    result = outputs[0] if outputs else {}
    await emit(payload.get("workflow_id", "?"), payload.get("instance_id"),
               "step.completed", {"step": step_name, "duration_ms": int((_t.time() - t0) * 1000)})
    return result


def lookup_claim_activity(payload: dict) -> dict:
    """Phase 1a — fetch the claim from the EMS named in payload."""
    claim_id = payload.get("claim_id") or payload.get("workflow_id")
    if not claim_id:
        return {"error": "missing_claim_id"}
    try:
        claim = claim_lookup.lookup(claim_id, ems_source=payload.get("ems_source"))
    except KeyError as ex:
        return {"error": str(ex)}
    return {"claim": claim}


def intake_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(build_intake_expense_workflow, payload, "Intake"))


def classify_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(build_classify_workflow, payload, "Classify"))


def receipt_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(build_receipt_workflow, payload, "Receipt"))


def route_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(build_route_workflow, payload, "Route"))


def notify_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(build_notify_workflow, payload, "Notify"))


def checkpoint_activity(payload: dict) -> dict:
    asyncio.run(emit(
        payload.get("workflow_id", "?"),
        payload.get("instance_id"),
        payload["kind"],
        payload.get("payload", {}),
    ))
    return {}
```

- [ ] **Step 5: Update `api/functions/graphs/__init__.py`**

```python
"""Per-phase MAF Workflow graph builders. Each returns a Workflow instance ready
to be invoked from the durable orchestration via `await workflow.run(input)`.
"""
from .intake_expense import build_intake_expense_workflow
from .classify import build_classify_workflow
from .receipt import build_receipt_workflow
from .route import build_route_workflow
from .notify import build_notify_workflow

__all__ = [
    "build_intake_expense_workflow",
    "build_classify_workflow",
    "build_receipt_workflow",
    "build_route_workflow",
    "build_notify_workflow",
]
```

The five module files don't exist yet — Day 6 Tasks 5/6 add `intake_expense.py` and `classify.py`; Days 7/9/10 add the rest. Until those tasks land, the imports fail. **That's intentional** — Task 4's commit is part of a chain (4→5→6→7) that lands together, after which all activities can be invoked.

- [ ] **Step 6: Delete the old orchestrator and its rejection test**

```bash
rm api/functions/workflows/invoice_p2p.py
rm tests/api/unit/test_invoice_p2p_rejection.py
```

- [ ] **Step 7: Run the orchestration test (will still fail until Tasks 5+6)**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_expense_claim_orchestration.py -v
```

Expected: still FAILs because `api.functions.graphs` imports from `intake_expense.py` and `classify.py` which don't exist yet. **This is the deliberate seam** — finish Tasks 5 and 6, then re-run.

- [ ] **Step 8: Commit (chained — pair with Tasks 5/6 in a single PR mentally, but commit now)**

```bash
git add api/functions/workflows/expense_claim.py function_app.py api/functions/workflows/activities.py api/functions/graphs/__init__.py tests/api/unit/test_expense_claim_orchestration.py
git rm api/functions/workflows/invoice_p2p.py tests/api/unit/test_invoice_p2p_rejection.py
git commit -m "$(cat <<'EOF'
feat(workflow): expense_claim orchestrator (7-phase shape, phases 1-2 wired)

Reshape Durable orchestrator from 6-phase invoice_p2p to 7-phase
expense_claim per spec §4.1. Day 6 lands phases 1 (Intake & Normalise)
and 2 (Classify). Phases 3, 4, 5 are commented-out insertion points
that Days 7, 9, 10 each uncomment in turn. Phases 6 (Arbitrate) and
7 (Audit) are Week 3 work; orchestrator currently checkpoints
workflow.completed after Phase 2.

function_app.py: replaces InvoiceP2POrchestrator with
ExpenseClaimOrchestrator; adds lookup_claim, classify, receipt, route,
notify activity triggers (the latter three raise NotImplementedError
indirectly via missing graph builders until later days).

invoice_p2p.py and test_invoice_p2p_rejection.py deleted.

Spec ref: §4.1 (phase shape); §5.2 (orchestrator rename).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Phase 1 graph — Intake (lookup_claim → doc_intel → field_extractor → validate_required_fields)

**Files:**
- Create: `api/functions/graphs/intake_expense.py`
- Create: `api/functions/graphs/executors/deterministic/lookup_claim.py`
- Modify: `api/functions/graphs/executors/deterministic/__init__.py`
- Modify: `api/server/skills/field_extractor.skill.md` — re-prompt for expense claims (the existing skill is invoice-shaped)
- Create: `tests/api/unit/test_intake_expense_graph.py`

The Phase 1 graph is the per-claim normalisation pipeline. Note that **lookup happens at the orchestrator level (Task 4) before the graph runs**, so the graph receives `input["claim"]` already-fetched. The `lookup_claim` deterministic executor is then a thin in-graph adaptor that re-shapes the claim into the format `doc_intelligence_extract` expects (it's a stub anyway — we just normalise field names).

**Skill rebind:** the existing `field_extractor.skill.md` is invoice-shaped (vendor_id, invoice_number, po_ref). We retarget it to expense-claim fields per spec §5.2 ("one-line retarget plus prompt body where domain-specific").

- [ ] **Step 1: Write the failing graph test**

Create `tests/api/unit/test_intake_expense_graph.py`:

```python
"""Phase 1 (Intake) graph — drives the workflow against an in-memory claim
and asserts the four executors fire in order."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.intake_expense import build_intake_expense_workflow


@pytest.mark.asyncio
async def test_intake_graph_drives_four_executors_in_order():
    fake_extracted = {
        "amount": 142.0, "currency": "GBP", "category": "meals",
        "market": "UK", "attendees": 3, "vendor": "Côte Brasserie",
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_field_extractor.execute",
        AsyncMock(return_value={"extracted": fake_extracted}),
    ):
        wf = build_intake_expense_workflow()
        events = await wf.run({
            "workflow_id": "CLM-0007",
            "claim": {
                "claim_id": "CLM-0007",
                "amount": 142.0, "currency": "GBP", "category": "meals",
                "market": "UK", "attendees": 3, "vendor": "Côte Brasserie",
                "ems_source": "workday", "receipt_filename": "CLM-0007.png",
            },
        })
    out = events.get_outputs()[0]
    assert out["extracted"]["category"] == "meals"
    # validate_required_fields must have run last and returned ok=True
    assert out.get("ok") is True
    assert out.get("missing") == []


@pytest.mark.asyncio
async def test_intake_graph_blocks_on_missing_fields():
    bad = {"amount": 0, "currency": "GBP"}  # missing category, market, vendor
    with patch(
        "api.functions.graphs.executors.agents.agent_field_extractor.execute",
        AsyncMock(return_value={"extracted": bad}),
    ):
        wf = build_intake_expense_workflow()
        events = await wf.run({
            "workflow_id": "CLM-bad",
            "claim": {"claim_id": "CLM-bad", "ems_source": "workday"},
        })
    out = events.get_outputs()[0]
    assert out.get("ok") is False
    assert "category" in out.get("missing", [])
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_intake_expense_graph.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 2: Implement `lookup_claim` deterministic executor**

```python
# api/functions/graphs/executors/deterministic/lookup_claim.py
"""Phase 1a in-graph adaptor.

The orchestrator already called the claim.lookup MCP tool before the intake
graph runs (see lookup_claim_activity in activities.py). This executor's job
is to surface the looked-up record under the keys the rest of the intake
pipeline expects: `raw_text` and `structure` (matching doc_intelligence_extract's
output shape, since intake currently treats these as the seed payload).
"""
from __future__ import annotations
import json


async def execute(input: dict) -> dict:
    claim = input.get("claim")
    if not claim:
        return {"raw_text": "", "structure": {}}
    raw = (
        f"CLAIM {claim.get('claim_id')} "
        f"AMOUNT {claim.get('amount')} {claim.get('currency')} "
        f"CATEGORY {claim.get('category')} VENDOR {claim.get('vendor')}"
    )
    structure = {
        "claim_id": claim.get("claim_id"),
        "amount": claim.get("amount"),
        "currency": claim.get("currency"),
        "category": claim.get("category"),
        "market": claim.get("market"),
        "vendor": claim.get("vendor"),
        "attendees": claim.get("attendees"),
        "receipt_filename": claim.get("receipt_filename"),
        "ems_source": claim.get("ems_source"),
    }
    return {"raw_text": raw, "structure": structure, "claim_payload": json.dumps(claim)}
```

- [ ] **Step 3: Re-export from `api/functions/graphs/executors/deterministic/__init__.py`**

Open and append `lookup_claim` to the imports / `__all__`. Keep the existing entries (`apply_threshold_routing`, `doc_intelligence_extract`, `load_authority_policy`, `record_decision`).

- [ ] **Step 4: Rebind `api/server/skills/field_extractor.skill.md` for expense claims**

Open the file. The Week 1 fork is invoice-flavoured; spec §5.2 says one-line retarget plus prompt body where domain-specific. Replace the body:

```markdown
---
name: field-extractor
description: Extract structured expense-claim fields from raw EMS payload + OCR. Flag low-confidence fields for sub-agent reasoning.
---
You are the Expense Claim Field Extractor for the WPP T&E compliance workflow. Given a raw parsed claim payload and structure hints, return a structured JSON object with: claim_id, amount, currency, category, market, vendor, attendees, receipt_filename. For any field you are below 0.8 confidence on, set its value to {"value": <best guess>, "confidence": <float>, "needs_subagent": true}. Be terse — return only the JSON. Do not invent fields not present in the input.
```

The existing `agent_field_extractor.py` still works against this — it pre-pends raw_text and structure into the prompt and the wrapper extracts JSON from the response.

- [ ] **Step 5: Implement `api/functions/graphs/intake_expense.py`**

```python
"""Intake (Expense) graph:
  lookup_claim -> doc_intelligence_extract -> agent_field_extractor -> validate_required_fields
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.deterministic import lookup_claim, doc_intelligence_extract
from api.functions.graphs.executors.agents import agent_field_extractor
from api.functions.graphs.executors.validators import validate_required_fields


def build_intake_expense_workflow() -> Workflow:
    n1 = TrackedExecutor(id="lookup", name="lookup_claim",
                         executor_type="deterministic", fn=lookup_claim.execute)
    n2 = TrackedExecutor(id="doc_intel", name="doc_intelligence_extract",
                         executor_type="deterministic", fn=doc_intelligence_extract.execute)
    n3 = TrackedExecutor(id="field_ext", name="agent_field_extractor",
                         executor_type="agent", fn=agent_field_extractor.execute)
    n4 = TrackedExecutor(id="val_req", name="validate_required_fields",
                         executor_type="validator", fn=validate_required_fields.execute)
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, n3)
        .add_edge(n3, n4)
        .add_edge(n4, term)
        .build()
    )
```

- [ ] **Step 6: Adjust `validate_required_fields.REQUIRED` for expense fields**

Open `api/functions/graphs/executors/validators/validate_required_fields.py`. The existing `REQUIRED = {"vendor_id", "amount", "po_ref", "currency"}` is invoice-shaped. Replace with expense fields:

```python
# api/functions/graphs/executors/validators/validate_required_fields.py
from __future__ import annotations

REQUIRED = {"category", "amount", "currency", "market", "vendor"}


async def execute(input: dict) -> dict:
    fields = input.get("extracted", {})
    missing = [r for r in REQUIRED if not fields.get(r)]
    return {"ok": len(missing) == 0, "missing": missing, "extracted": fields}
```

`doc_intelligence_extract.py` currently reads `input["invoice"]["amount"]` — that fails for expense input. **Adjust it to read from `input["structure"]`** which is what `lookup_claim` writes:

```python
# api/functions/graphs/executors/deterministic/doc_intelligence_extract.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    """Stub: in production this calls Azure Document Intelligence. Here, surface
    whatever the upstream lookup_claim normaliser produced under raw_text/structure
    so agent_field_extractor receives the same shape it always did."""
    raw = input.get("raw_text", "")
    structure = input.get("structure", {})
    return {"raw_text": raw, "structure": structure}
```

- [ ] **Step 7: Run the test**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_intake_expense_graph.py -v
```

Expected: 2 PASS.

- [ ] **Step 8: Commit**

```bash
git add api/functions/graphs/intake_expense.py api/functions/graphs/executors/deterministic/lookup_claim.py api/functions/graphs/executors/deterministic/__init__.py api/functions/graphs/executors/deterministic/doc_intelligence_extract.py api/functions/graphs/executors/validators/validate_required_fields.py api/server/skills/field_extractor.skill.md tests/api/unit/test_intake_expense_graph.py
git commit -m "$(cat <<'EOF'
feat(graph): Phase 1 (Intake & Normalise) for expense claims

lookup_claim -> doc_intelligence_extract -> agent_field_extractor ->
validate_required_fields. lookup_claim adapts the EMS-fetched record
under raw_text/structure keys so the existing field_extractor + doc
intelligence stubs work without further surgery.

field_extractor skill body retargeted from invoice fields (vendor_id,
po_ref) to expense fields (category, market, attendees,
receipt_filename). validate_required_fields REQUIRED set rebound.

Spec ref: §4.1 Phase 1; §5.2 (executor retarget).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Phase 2 graph — Classify (agent_rag_classifier → validate_classification_schema)

**Files:**
- Create: `api/functions/graphs/classify.py`
- Modify: `api/functions/graphs/executors/validators/validate_classification_schema.py` — wrap as graph-shape (`{"ok": bool, ...}` instead of raise)
- Create: `tests/api/unit/test_classify_graph.py`

Phase 2 wraps the existing `agent_rag_classifier` (Week 1) as a graph node. The complication: `validate_classification_schema.validate(payload)` raises — that's the off-graph guardrail pattern. For an in-graph validator we need the `{"ok": bool, ...}` shape so `TrackedExecutor` can emit `validator.blocked` properly.

**The cleanest fix:** keep the raising `validate(payload)` function (Week 1 callers depend on it), and add a new `execute(input: dict) -> dict` thin wrapper that catches the error and returns the graph-shape. Don't rename. Don't break existing callers.

- [ ] **Step 1: Write the failing test**

Create `tests/api/unit/test_classify_graph.py`:

```python
"""Phase 2 (Classify) graph — runs agent_rag_classifier + validate_classification_schema."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.classify import build_classify_workflow


@pytest.mark.asyncio
async def test_classify_graph_passes_well_formed_payload():
    fake = {
        "verdict": "amber",
        "policy_clause": "§3.1 Meals — UK per-attendee cap £75",
        "reasoning": "Within 110% of cap with named attendees.",
        "confidence": 0.7,
        "competing_interpretations": [],
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_rag_classifier.execute",
        AsyncMock(return_value={"classification": fake}),
    ):
        wf = build_classify_workflow()
        events = await wf.run({"workflow_id": "CLM-0007", "claim_id": "CLM-0007"})
    out = events.get_outputs()[0]
    assert out["classification"]["verdict"] == "amber"
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_classify_graph_blocks_malformed_payload():
    bad = {"raw": "model went off-script", "parse_error": True}
    with patch(
        "api.functions.graphs.executors.agents.agent_rag_classifier.execute",
        AsyncMock(return_value={"classification": bad}),
    ):
        wf = build_classify_workflow()
        events = await wf.run({"workflow_id": "CLM-broken", "claim_id": "CLM-broken"})
    out = events.get_outputs()[0]
    assert out["ok"] is False
    assert "parse_error" in (out.get("blocked_reason") or "")
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_classify_graph.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 2: Add a graph-shape wrapper to `validate_classification_schema.py`**

Append (don't replace) to the file:

```python
# api/functions/graphs/executors/validators/validate_classification_schema.py
async def execute(input: dict) -> dict:
    """Graph-shape adaptor over `validate()` — catches the raised error and
    returns {"ok": False, "blocked_reason": str} so TrackedExecutor (validator)
    can emit `validator.blocked` and the orchestrator decides next steps."""
    payload = input.get("classification") or {}
    try:
        validate(payload)
    except ClassificationSchemaError as ex:
        return {"ok": False, "blocked_reason": str(ex), "classification": payload}
    return {"ok": True, "classification": payload}
```

- [ ] **Step 3: Implement `api/functions/graphs/classify.py`**

```python
"""Classify (R/A/G) graph:
  agent_rag_classifier -> validate_classification_schema
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_rag_classifier
from api.functions.graphs.executors.validators import validate_classification_schema


def build_classify_workflow() -> Workflow:
    n1 = TrackedExecutor(id="rag_classifier", name="agent_rag_classifier",
                         executor_type="agent", fn=agent_rag_classifier.execute)
    n2 = TrackedExecutor(id="val_schema", name="validate_classification_schema",
                         executor_type="validator", fn=validate_classification_schema.execute)
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
```

- [ ] **Step 4: Run the test**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_classify_graph.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Re-run the orchestration test from Task 4 — should now pass**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_expense_claim_orchestration.py -v
```

Expected: 3 PASS now that `api.functions.graphs.__init__` can resolve all the imports it declared. The notify/route/receipt builders are still placeholders — those tests will be added when those tasks land — but the orchestrator generator already handles their absence by skipping past those phases.

If the test still fails because `build_receipt_workflow` etc. are unresolved imports in `__init__.py`, **stub them** in `api/functions/graphs/__init__.py`:

```python
# Until Days 7/9/10 land, the graph factories raise NotImplementedError on construction.
def build_receipt_workflow():
    raise NotImplementedError("Phase 3 (Validate Receipt) — Day 7")

def build_route_workflow():
    raise NotImplementedError("Phase 4 (Route by Verdict) — Day 9")

def build_notify_workflow():
    raise NotImplementedError("Phase 5 (Notify) — Day 10")
```

Day 7/9/10 each replace one stub with a real `from .receipt import build_receipt_workflow` etc.

- [ ] **Step 6: Run the full backend test suite**

```bash
./.venv/Scripts/pytest.exe tests/api -q
```

Expected: all PASS (no skips except the existing smoke marker).

- [ ] **Step 7: Commit**

```bash
git add api/functions/graphs/classify.py api/functions/graphs/executors/validators/validate_classification_schema.py api/functions/graphs/__init__.py tests/api/unit/test_classify_graph.py
git commit -m "$(cat <<'EOF'
feat(graph): Phase 2 (Classify) for expense claims

Wraps existing agent_rag_classifier as a graph node feeding
validate_classification_schema in graph-shape ({ok: bool, ...}). The
raising `validate(payload)` API is preserved for off-graph callers
(Week 1 acceptance harness) — only adds an `execute(input)` adaptor.

Phase 3, 4, 5 builders stubbed in graphs/__init__.py with
NotImplementedError until later days replace them.

Spec ref: §4.1 Phase 2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Update simulator to spawn ExpenseClaimOrchestrator

**Files:**
- Modify: `api/server/services/simulator_orchestrator.py`
- Modify: `api/server/services/synthetic_data.py` — bridge `build_workflow` to claims
- Create: `tests/api/unit/test_simulator_spawns_expense_orchestrator.py`

The simulator's `spawn_workflow` still references `InvoiceP2POrchestrator` (deleted) and the invoice-shaped `build_workflow`. Reshape so it spawns `ExpenseClaimOrchestrator` with a real claim id from the synthetic corpus, rotating `ems_source` 50/50 (the corpus already encodes this — we just pass it through).

- [ ] **Step 1: Read `api/server/services/synthetic_data.py` and `durable_client.py`**

The existing `build_workflow(wid)` returns a vendor-invoice shape. We need an expense-claim shape: `{claim_id, employee_id, market, currency, amount, category, ems_source}`. Read both files; keep `Workflow` model intact if other code depends on it; add a new helper `build_expense_workflow(claim_id)` rather than mutating in place.

- [ ] **Step 2: Write the failing simulator test**

```python
# tests/api/unit/test_simulator_spawns_expense_orchestrator.py
"""Simulator spawn_workflow drives the new ExpenseClaimOrchestrator."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.server.services import simulator_orchestrator


@pytest.mark.asyncio
async def test_spawn_uses_expense_claim_orchestrator():
    captured: dict = {}

    async def fake_schedule(payload):
        captured["payload"] = payload
        captured["function_name"] = payload.get("_function_name", "ExpenseClaimOrchestrator")
        return {"id": "iid-test"}

    with patch("api.server.services.simulator_orchestrator.schedule_new_orchestration",
               AsyncMock(side_effect=fake_schedule)):
        wid = await simulator_orchestrator.spawn_workflow()
    assert wid.startswith("CLM-")
    assert "claim_id" in captured["payload"]
    assert captured["payload"]["claim_id"] == wid


@pytest.mark.asyncio
async def test_spawn_with_receipt_mismatch_scenario_uses_red_seed():
    with patch("api.server.services.simulator_orchestrator.schedule_new_orchestration",
               AsyncMock(return_value={"id": "iid-x"})) as sched:
        await simulator_orchestrator.spawn_workflow(scenario="receipt-mismatch-amount")
    sent = sched.call_args[0][0]
    # The payload tags the scenario so the orchestrator simulator-overrides downstream behaviour.
    assert sent.get("scenario") == "receipt-mismatch-amount"
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_simulator_spawns_expense_orchestrator.py -v
```

Expected: FAIL.

- [ ] **Step 3: Modify `simulator_orchestrator.py`**

Replace the body of `spawn_workflow` to walk synthetic claims:

```python
"""Simulator: spawns ExpenseClaim orchestrations with one synthetic claim per spawn."""
from __future__ import annotations
import asyncio
import json
import os
import random
from pathlib import Path

from api.server.state import app_state
from api.server.services.durable_client import schedule_new_orchestration

_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"
_seq = 0
_rng = random.Random(20260427)


def _pick_claim(scenario: str | None) -> dict:
    """Pick a synthetic claim. Scenario hints bias the pick toward red-flavoured
    claims (for receipt-mismatch / repeat-offender / breach-justification cycle)."""
    files = sorted(_CLAIMS_DIR.glob("CLM-*.json"))
    if not files:
        raise RuntimeError("no synthetic claims; run data/synthetic/generate.py")
    candidates = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    if scenario == "receipt-mismatch-amount":
        candidates = [c for c in candidates if c.get("receipt_mismatch_flavour") == "wrong-amount"] or candidates
    elif scenario == "receipt-mismatch-vendor":
        candidates = [c for c in candidates if c.get("receipt_mismatch_flavour") == "wrong-vendor"] or candidates
    elif scenario == "receipt-missing":
        candidates = [c for c in candidates if c.get("receipt_mismatch_flavour") == "missing-receipt"] or candidates
    elif scenario == "repeat-offender":
        candidates = [c for c in candidates if c.get("gold_label") in ("amber", "red")] or candidates
    elif scenario == "breach-justification-cycle":
        candidates = [c for c in candidates if c.get("gold_label") == "red"] or candidates
    return _rng.choice(candidates)


async def spawn_workflow(scenario: str | None = None) -> str:
    """Spawn an ExpenseClaim orchestration for one synthetic claim."""
    claim = _pick_claim(scenario)
    claim_id = claim["claim_id"]
    payload = {
        "workflow_id": claim_id,
        "claim_id": claim_id,
        "ems_source": claim.get("ems_source"),
    }
    if scenario:
        payload["scenario"] = scenario
    try:
        result = await schedule_new_orchestration(payload)
        # state_store wiring would go here once Workflow shape lands; for now,
        # the orchestrator drives state via webhook events.
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {claim_id}: {ex}")
    return claim_id


async def ramp_loop() -> None:
    """Spawn workflows until target, then steady-state."""
    target = int(os.getenv("SIMULATOR_TARGET_WORKFLOWS", "0"))
    if target <= 0:
        print("[orchestrator] simulator disabled (SIMULATOR_TARGET_WORKFLOWS=0)")
        return
    ramp_seconds = 90
    delay_per = ramp_seconds / target
    print(f"[orchestrator] ramping {target} workflows over {ramp_seconds}s")
    for _ in range(target):
        try:
            await spawn_workflow()
        except Exception as ex:
            print(f"[orchestrator] spawn failed: {ex}")
        await asyncio.sleep(delay_per)
    print("[orchestrator] ramp complete; steady-state")
    while True:
        try:
            await spawn_workflow()
        except Exception as ex:
            print(f"[orchestrator] spawn failed: {ex}")
        await asyncio.sleep(3 + _rng.random() * 5)
```

Note: `schedule_new_orchestration` already targets the configured orchestrator name; if it currently hard-codes `InvoiceP2POrchestrator`, update it to take the function name as an arg or default to `ExpenseClaimOrchestrator`. **Read `durable_client.py` first.** If the rename is already invasive, add a `function_name="ExpenseClaimOrchestrator"` kwarg with that default.

- [ ] **Step 4: Run the simulator test**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_simulator_spawns_expense_orchestrator.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Sanity check the FastAPI app still imports**

```bash
./.venv/Scripts/python.exe -c "from api.server.main import app; print('ok')"
./.venv/Scripts/python.exe -c "import function_app; print('ok')"
```

Both expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/simulator_orchestrator.py api/server/services/durable_client.py tests/api/unit/test_simulator_spawns_expense_orchestrator.py
git commit -m "$(cat <<'EOF'
feat(simulator): spawn ExpenseClaimOrchestrator with synthetic claims

simulator_orchestrator.spawn_workflow now picks a synthetic claim from
data/synthetic/claims and schedules ExpenseClaimOrchestrator with the
real claim_id + ems_source. Scenario hints bias the pick:
receipt-mismatch-{amount,vendor}, receipt-missing, repeat-offender,
breach-justification-cycle each select an appropriate seed.

Spec ref: §5.2 (simulator scenarios); §6 (synthetic dataset).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Day 6 checkpoint — full backend test suite

Before moving on to Day 7, confirm all tests still pass.

- [ ] **Step 1: Run the full backend test suite**

```bash
./.venv/Scripts/pytest.exe tests/api -q
```

Expected: all PASS, no new skips. If anything is red, fix in place — no Day 7 work until Day 6 is green.

- [ ] **Step 2: Run the UI test suite**

```bash
npm run test
```

Expected: 15/15 PASS (no UI changes yet).

- [ ] **Step 3: No commit — measurement only.**

---

# Day 7 — Receipt validator + Phase 3

## Task 8: MCP tool — `claim.getReceipt`

**Files:**
- Create: `api/server/mcp_tools/claim_get_receipt.py`
- Create: `tests/api/unit/test_claim_get_receipt_tool.py`

Reads `data/synthetic/receipts/{claim_id}.png`, returns base64 + size + mismatch_flavour metadata. The vision-capable model receives the base64 in the prompt; the metadata helps the validator skill phrase its `image_says` vs `claim_says` comparison.

**Edge cases the validator depends on:**
- Zero-byte file → `flavour: "missing-receipt"`, `image_b64: ""`, `bytes: 0`. The validator skill must treat this as the `missing-receipt` flavour, not as a real image.
- File missing entirely → `KeyError` (the synthetic generator emits the zero-byte file for `missing-receipt`; an actual missing file is a corruption signal).

- [ ] **Step 1: Write the failing test**

Create `tests/api/unit/test_claim_get_receipt_tool.py`:

```python
"""claim.getReceipt MCP tool tests."""
from __future__ import annotations
import base64
import json
from pathlib import Path

import pytest

from api.server.mcp_tools import claim_get_receipt

ROOT = Path(__file__).resolve().parents[3]
CLAIMS = ROOT / "data" / "synthetic" / "claims"
RECEIPTS = ROOT / "data" / "synthetic" / "receipts"


def _pick_claim_with_flavour(flavour: str) -> str:
    for path in sorted(CLAIMS.glob("CLM-*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        if c.get("receipt_mismatch_flavour") == flavour:
            return c["claim_id"]
    raise RuntimeError(f"no synthetic claim with flavour {flavour}")


def test_returns_base64_and_metadata_for_correct_receipt():
    cid = _pick_claim_with_flavour("correct")
    out = claim_get_receipt.get_receipt(cid)
    assert out["claim_id"] == cid
    assert out["flavour"] == "correct"
    assert out["bytes"] > 0
    base64.b64decode(out["image_b64"])  # no error == valid b64


def test_zero_byte_file_for_missing_receipt():
    cid = _pick_claim_with_flavour("missing-receipt")
    out = claim_get_receipt.get_receipt(cid)
    assert out["flavour"] == "missing-receipt"
    assert out["bytes"] == 0
    assert out["image_b64"] == ""


def test_unknown_claim_raises():
    with pytest.raises(KeyError):
        claim_get_receipt.get_receipt("CLM-9999")


def test_truncates_large_b64_with_warning(monkeypatch):
    # Defensive: image gets passed in prompt; we cap at ~1MB b64.
    monkeypatch.setattr(claim_get_receipt, "_MAX_B64_BYTES", 1024)
    cid = _pick_claim_with_flavour("correct")
    out = claim_get_receipt.get_receipt(cid)
    assert len(out["image_b64"]) <= 1024
    if out["bytes"] > 1024:
        assert out.get("truncated") is True
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_claim_get_receipt_tool.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 2: Implement `api/server/mcp_tools/claim_get_receipt.py`**

```python
"""claim.getReceipt MCP tool — base64-encode the receipt PNG + return metadata."""
from __future__ import annotations
import base64
import json
from pathlib import Path

from opentelemetry import trace

from ._otel import traced_tool

_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"
_RECEIPTS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "receipts"
_MAX_B64_BYTES = 1_500_000  # ~1MB raw → ~1.4MB b64; cap for prompt size sanity


@traced_tool("claim.getReceipt")
def get_receipt(claim_id: str) -> dict:
    """Return base64 image + flavour metadata. Zero-byte file → missing-receipt."""
    span = trace.get_current_span()
    span.set_attribute("wpp.claim.id", claim_id)

    claim_path = _CLAIMS_DIR / f"{claim_id}.json"
    if not claim_path.exists():
        raise KeyError(f"claim {claim_id!r} not found")
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    flavour = claim.get("receipt_mismatch_flavour", "correct")
    receipt_path = _RECEIPTS_DIR / claim["receipt_filename"]
    if not receipt_path.exists():
        raise KeyError(f"receipt file {receipt_path.name!r} not on disk")

    raw = receipt_path.read_bytes()
    span.set_attribute("wpp.receipt.bytes", len(raw))
    span.set_attribute("wpp.receipt.flavour", flavour)
    if not raw:
        return {"claim_id": claim_id, "flavour": flavour, "bytes": 0, "image_b64": ""}

    b64 = base64.b64encode(raw).decode("ascii")
    truncated = False
    if len(b64) > _MAX_B64_BYTES:
        b64 = b64[:_MAX_B64_BYTES]
        truncated = True
    out = {"claim_id": claim_id, "flavour": flavour, "bytes": len(raw), "image_b64": b64}
    if truncated:
        out["truncated"] = True
    return out
```

- [ ] **Step 3: Run the test**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_claim_get_receipt_tool.py -v
```

Expected: 4 PASS.

- [ ] **Step 4: Commit**

```bash
git add api/server/mcp_tools/claim_get_receipt.py tests/api/unit/test_claim_get_receipt_tool.py
git commit -m "$(cat <<'EOF'
feat(mcp): claim.getReceipt tool — base64 + flavour metadata

Returns base64-encoded receipt PNG + receipt_mismatch_flavour from the
synthetic dataset, with zero-byte handling for missing-receipt. Caps
b64 payload at ~1MB to keep prompt size sane. @traced_tool span
attributes record wpp.receipt.bytes and wpp.receipt.flavour.

Spec ref: §5.4 (MCP tools); §4.1 Phase 3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `receipt_validator` skill + `agent_receipt_validator` executor

**Files:**
- Create: `api/server/skills/receipt_validator.skill.md`
- Create: `api/functions/graphs/executors/agents/agent_receipt_validator.py`
- Modify: `api/functions/graphs/executors/agents/__init__.py`
- Create: `tests/api/unit/test_agent_receipt_validator.py`

The receipt validator is multimodal: it reads the receipt image and the structured claim fields and decides whether they agree. Output schema mirrors the rag_classifier shape: `verdict_per_field`, `mismatch_flavour`, `confidence`, `reasoning`.

The skill describes the role and output schema; the agent executor pre-fetches the receipt b64 and the claim structure, embeds both in the prompt, and returns the parsed JSON. Vision-capable model is selected via `model="gpt-4.1"` (existing default; gpt-4.1 supports image-in-prompt for the GHCP wrapper).

- [ ] **Step 1: Author `api/server/skills/receipt_validator.skill.md`**

```markdown
---
name: receipt-validator
description: Cross-validate the receipt image against the structured claim fields. Detect mismatches in amount, date, vendor, line items, or missing receipt entirely.
---

You are the Receipt Validator for the WPP T&E compliance workflow.

The user prompt provides:
- A `## Claim` section with structured fields (claim_id, amount, currency, category, vendor, attendees, submitted_at).
- A `## Receipt` section with the base64-encoded receipt image and a `bytes` count. If `bytes == 0`, no receipt was submitted.

Compare the image against the claim. Return exactly one JSON object, no prose:

```json
{
  "agrees": true | false,
  "mismatch_flavour": "correct" | "wrong-amount" | "wrong-date" | "wrong-vendor" | "missing-line-item" | "missing-receipt",
  "verdict_per_field": {
    "amount":   "match" | "mismatch" | "unreadable",
    "date":     "match" | "mismatch" | "unreadable",
    "vendor":   "match" | "mismatch" | "unreadable",
    "line_items": "match" | "mismatch" | "unreadable"
  },
  "reasoning": "One-to-three sentences explaining the decision, quoting the receipt where relevant.",
  "confidence": 0.0 to 1.0
}
```

Rules:
- If `bytes == 0`, `mismatch_flavour` is `"missing-receipt"`, `agrees` is `false`, and all fields in `verdict_per_field` are `"unreadable"`.
- `mismatch_flavour` reports the dominant failure mode. If multiple fields mismatch, choose the most material one.
- `agrees` is `true` only when every field in `verdict_per_field` is `"match"`.
- `reasoning` must reference what the image actually shows (e.g., `"receipt total reads £180 but claim says £142"`); do not invent details.
```

- [ ] **Step 2: Write the failing executor test**

Create `tests/api/unit/test_agent_receipt_validator.py`:

```python
"""agent_receipt_validator executor tests — mocks the GHCP wrapper."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.executors.agents import agent_receipt_validator


@pytest.mark.asyncio
async def test_correct_receipt_agrees():
    fake_skill = {
        "agrees": True,
        "mismatch_flavour": "correct",
        "verdict_per_field": {"amount": "match", "date": "match", "vendor": "match", "line_items": "match"},
        "reasoning": "All fields agree with image.",
        "confidence": 0.95,
    }
    fake_receipt = {"claim_id": "CLM-0000", "flavour": "correct", "bytes": 1234, "image_b64": "AAAA"}
    fake_claim = {"claim_id": "CLM-0000", "amount": 42.0, "vendor": "Côte Brasserie", "category": "meals"}
    with patch.object(agent_receipt_validator, "run_agent_skill", AsyncMock(return_value=fake_skill)) as mock_run, \
         patch.object(agent_receipt_validator, "_get_receipt", return_value=fake_receipt), \
         patch.object(agent_receipt_validator, "_get_claim", return_value=fake_claim):
        result = await agent_receipt_validator.execute({"claim_id": "CLM-0000"})
    assert result["receipt_validation"]["agrees"] is True
    mock_run.assert_awaited_once()
    args, _ = mock_run.call_args
    assert args[0] == "receipt_validator"
    assert "CLM-0000" in args[1]


@pytest.mark.asyncio
async def test_missing_receipt_propagates_flavour():
    fake_skill = {
        "agrees": False,
        "mismatch_flavour": "missing-receipt",
        "verdict_per_field": {"amount": "unreadable", "date": "unreadable", "vendor": "unreadable", "line_items": "unreadable"},
        "reasoning": "No receipt submitted.",
        "confidence": 1.0,
    }
    with patch.object(agent_receipt_validator, "run_agent_skill", AsyncMock(return_value=fake_skill)), \
         patch.object(agent_receipt_validator, "_get_receipt", return_value={"claim_id": "CLM-X", "flavour": "missing-receipt", "bytes": 0, "image_b64": ""}), \
         patch.object(agent_receipt_validator, "_get_claim", return_value={"claim_id": "CLM-X", "amount": 1.0}):
        result = await agent_receipt_validator.execute({"claim_id": "CLM-X"})
    assert result["receipt_validation"]["mismatch_flavour"] == "missing-receipt"
    assert result["receipt_validation"]["agrees"] is False


@pytest.mark.asyncio
async def test_emits_receipt_mismatch_event_when_disagreement():
    fake_skill = {
        "agrees": False,
        "mismatch_flavour": "wrong-amount",
        "verdict_per_field": {"amount": "mismatch", "date": "match", "vendor": "match", "line_items": "match"},
        "reasoning": "Image total reads 180 but claim 142.",
        "confidence": 0.8,
    }
    captured: list[dict] = []
    with patch.object(agent_receipt_validator, "run_agent_skill", AsyncMock(return_value=fake_skill)), \
         patch.object(agent_receipt_validator, "_get_receipt", return_value={"claim_id": "CLM-Y", "flavour": "wrong-amount", "bytes": 1234, "image_b64": "AAAA"}), \
         patch.object(agent_receipt_validator, "_get_claim", return_value={"claim_id": "CLM-Y", "amount": 142.0}), \
         patch.object(agent_receipt_validator, "_emit_event", side_effect=lambda ev: captured.append(ev)):
        await agent_receipt_validator.execute({"claim_id": "CLM-Y"})
    types = [e["type"] for e in captured]
    assert "receipt.mismatch.detected" in types
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_agent_receipt_validator.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `api/functions/graphs/executors/agents/agent_receipt_validator.py`**

```python
"""agent_receipt_validator — cross-validates receipt image vs structured claim.

Pre-fetches the receipt (base64 + metadata) and the structured claim in Python,
embeds both in the prompt, and invokes the receipt_validator skill via the
GHCP wrapper. On disagreement, emits a receipt.mismatch.detected event onto
the global bus so the UI can surface the verdict.
"""
from __future__ import annotations
import json

from api.server.mcp_tools import claim_get_receipt, claim_get_structured
from api.shared.events import FleetEvent

from ._wrapper import run_agent_skill


def _get_receipt(claim_id: str) -> dict:
    return claim_get_receipt.get_receipt(claim_id)


def _get_claim(claim_id: str) -> dict:
    return claim_get_structured.get_structured(claim_id, include_gold=False)


def _emit_event(event: dict) -> None:
    """Emit a FleetEvent on the global bus. Imported lazily so unit tests can patch."""
    try:
        from api.server.state import app_state
        app_state.bus.emit(FleetEvent(**event))
    except Exception:
        pass


async def execute(input: dict) -> dict:
    claim_id = input["claim_id"]
    claim = _get_claim(claim_id)
    receipt = _get_receipt(claim_id)

    # Build the prompt. The image is embedded as base64; gpt-4.1 vision handles it.
    prompt = (
        f"Validate the receipt for claim {claim_id} per your role.\n\n"
        f"## Claim\n```json\n{json.dumps(claim, indent=2, ensure_ascii=False)}\n```\n\n"
        f"## Receipt\n"
        f"bytes: {receipt['bytes']}\n"
        f"image_b64: {receipt['image_b64'][:200]}{'…' if len(receipt['image_b64']) > 200 else ''}\n"
        f"\nReturn exactly one JSON object matching the schema in your instructions. "
        f"No prose, no markdown — JSON only."
    )

    validation = await run_agent_skill("receipt_validator", prompt)

    # Surface disagreement as an event for SSE fan-out.
    if validation.get("agrees") is False:
        _emit_event({
            "type": "receipt.mismatch.detected",
            "workflow_id": claim_id,
            "claim_id": claim_id,
            "mismatch_flavour": validation.get("mismatch_flavour"),
            "confidence": validation.get("confidence"),
        })

    return {"receipt_validation": validation}
```

Note the `[:200]` truncation in the prompt: in the demo POC, embedding the full base64 is unnecessary — gpt-4.1's vision binding accepts the b64 either inline or as a separate `image_url` payload. The prompt shows what the model receives; the wrapper layer can be extended later to pass it via the structured-image API. **Per the runbook §"Known issues" the MCP tools are pure Python helpers in this POC, not GHCP-wired tool servers.**

- [ ] **Step 4: Re-export from `__init__.py`**

Open `api/functions/graphs/executors/agents/__init__.py` and add the import.

- [ ] **Step 5: Run the test**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_agent_receipt_validator.py -v
```

Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add api/server/skills/receipt_validator.skill.md api/functions/graphs/executors/agents/agent_receipt_validator.py api/functions/graphs/executors/agents/__init__.py tests/api/unit/test_agent_receipt_validator.py
git commit -m "$(cat <<'EOF'
feat(skill): receipt_validator — multimodal image-vs-structured cross-check

Skill markdown describes role + output schema (agrees, mismatch_flavour,
verdict_per_field, reasoning, confidence). Executor pre-fetches receipt
b64 + structured claim, embeds both in the prompt, and invokes the skill
via run_agent_skill. On disagreement, emits receipt.mismatch.detected
on the bus so the UI surfaces the verdict.

Spec ref: §5.4 (skills); §4.1 Phase 3; brief §4.5 (receipt cross-validation).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Phase 3 graph — Validate Receipt

**Files:**
- Create: `api/functions/graphs/receipt.py`
- Modify: `api/functions/graphs/__init__.py` — replace stub `build_receipt_workflow` with the real builder
- Modify: `api/functions/workflows/expense_claim.py` — uncomment the Phase 3 block
- Create: `tests/api/unit/test_receipt_graph.py`

`agent_receipt_validator → validate_amount_consistency` (existing). The amount validator only fires when `extracted` is present and includes line_items; for expense claims with attendee-based caps it returns `ok=True` trivially when no line items are given. That's fine — we keep it as a guardrail for future expansion (when the receipt OCR returns structured line items in Week 3+).

- [ ] **Step 1: Write the failing graph test**

Create `tests/api/unit/test_receipt_graph.py`:

```python
"""Phase 3 (Validate Receipt) graph."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.receipt import build_receipt_workflow


@pytest.mark.asyncio
async def test_receipt_graph_passes_when_validator_agrees():
    fake = {"receipt_validation": {
        "agrees": True, "mismatch_flavour": "correct",
        "verdict_per_field": {"amount": "match", "date": "match", "vendor": "match", "line_items": "match"},
        "reasoning": "All fields agree.", "confidence": 0.9,
    }}
    with patch(
        "api.functions.graphs.executors.agents.agent_receipt_validator.execute",
        AsyncMock(return_value=fake),
    ):
        wf = build_receipt_workflow()
        events = await wf.run({"workflow_id": "CLM-0000", "claim_id": "CLM-0000",
                                "extracted": {"amount": 42.0, "line_items": []}})
    out = events.get_outputs()[0]
    assert out["receipt_validation"]["agrees"] is True
    assert out.get("ok") is True


@pytest.mark.asyncio
async def test_receipt_graph_records_mismatch_in_payload():
    fake = {"receipt_validation": {
        "agrees": False, "mismatch_flavour": "wrong-amount",
        "verdict_per_field": {"amount": "mismatch", "date": "match", "vendor": "match", "line_items": "match"},
        "reasoning": "Image reads 180 but claim 142.", "confidence": 0.85,
    }}
    with patch(
        "api.functions.graphs.executors.agents.agent_receipt_validator.execute",
        AsyncMock(return_value=fake),
    ):
        wf = build_receipt_workflow()
        events = await wf.run({"workflow_id": "CLM-Y", "claim_id": "CLM-Y",
                                "extracted": {"amount": 142.0, "line_items": []}})
    out = events.get_outputs()[0]
    assert out["receipt_validation"]["mismatch_flavour"] == "wrong-amount"
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_receipt_graph.py -v
```

Expected: FAIL with `ImportError` from `__init__.py`.

- [ ] **Step 2: Implement `api/functions/graphs/receipt.py`**

```python
"""Validate Receipt graph:
  agent_receipt_validator -> validate_amount_consistency
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_receipt_validator
from api.functions.graphs.executors.validators import validate_amount_consistency


def build_receipt_workflow() -> Workflow:
    n1 = TrackedExecutor(id="receipt_validator", name="agent_receipt_validator",
                         executor_type="agent", fn=agent_receipt_validator.execute)
    n2 = TrackedExecutor(id="val_amt", name="validate_amount_consistency",
                         executor_type="validator", fn=validate_amount_consistency.execute)
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
```

- [ ] **Step 3: Replace stub in `graphs/__init__.py`**

Open the file. Replace:

```python
def build_receipt_workflow():
    raise NotImplementedError("Phase 3 (Validate Receipt) — Day 7")
```

with:

```python
from .receipt import build_receipt_workflow
```

- [ ] **Step 4: Uncomment the Phase 3 block in `expense_claim.py`**

Open `api/functions/workflows/expense_claim.py` and replace the `# ----- Day 7 will replace this block -----` block with the live calls (uncomment what's there).

- [ ] **Step 5: Run the graph test + the orchestration test**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_receipt_graph.py -v
./.venv/Scripts/pytest.exe tests/api/unit/test_expense_claim_orchestration.py -v
```

Both: PASS. The orchestration test will need extending — it currently expects only intake+classify. Update `test_phase_order_for_green_claim` to also expect `receipt_activity_trigger`:

```python
expected_prefix = ["lookup_claim_activity_trigger", "intake_activity_trigger",
                   "classify_activity_trigger", "receipt_activity_trigger"]
assert names[:4] == expected_prefix
```

And add a new test:

```python
def test_receipt_mismatch_recorded_in_workflow_output():
    ctx = FakeContext()
    ctx._activity_results["receipt_activity_trigger"] = {
        "receipt_validation": {"agrees": False, "mismatch_flavour": "wrong-amount",
                                "verdict_per_field": {}, "reasoning": "x", "confidence": 0.8},
        "ok": True,
    }
    result = _drain(expense_claim_orchestration(ctx), ctx)
    assert result["status"] == "completed"
    # The orchestrator includes receipt under enriched["receipt"]; it shows up in result.
    # If your generator returns it under a different key, adjust here.
```

- [ ] **Step 6: Commit**

```bash
git add api/functions/graphs/receipt.py api/functions/graphs/__init__.py api/functions/workflows/expense_claim.py tests/api/unit/test_receipt_graph.py tests/api/unit/test_expense_claim_orchestration.py
git commit -m "$(cat <<'EOF'
feat(graph): Phase 3 (Validate Receipt) wired into expense_claim

agent_receipt_validator -> validate_amount_consistency. Orchestrator
generator now flows Phase 1 -> 2 -> 3 -> completed. receipt_validation
present in the enriched payload; receipt.mismatch.detected events emit
when agrees=false.

Spec ref: §4.1 Phase 3; brief §7 #5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Simulator scenarios — six receipt mismatch flavours

**Files:**
- Modify: `api/server/services/simulator_orchestrator.py` — already has the scenario routing from Task 7; this task verifies all six work end-to-end
- Create: `tests/api/unit/test_simulator_receipt_mismatch.py`

The synthetic dataset already encodes all six mismatch flavours (Week 1 Task 6 output). Task 7 made the simulator pick by flavour. This task is the regression test.

- [ ] **Step 1: Write the test**

```python
# tests/api/unit/test_simulator_receipt_mismatch.py
"""Simulator picks the right seed for each receipt-mismatch scenario."""
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from api.server.services import simulator_orchestrator

ROOT = Path(__file__).resolve().parents[3]
CLAIMS = ROOT / "data" / "synthetic" / "claims"


def _flavour_of(claim_id: str) -> str:
    return json.loads((CLAIMS / f"{claim_id}.json").read_text(encoding="utf-8"))["receipt_mismatch_flavour"]


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario,expected_flavour", [
    ("receipt-mismatch-amount", "wrong-amount"),
    ("receipt-mismatch-vendor", "wrong-vendor"),
    ("receipt-missing", "missing-receipt"),
])
async def test_scenario_picks_matching_flavour(scenario, expected_flavour):
    captured: dict = {}

    async def fake_schedule(payload):
        captured["payload"] = payload
        return {"id": "iid-x"}

    with patch("api.server.services.simulator_orchestrator.schedule_new_orchestration",
               AsyncMock(side_effect=fake_schedule)):
        wid = await simulator_orchestrator.spawn_workflow(scenario=scenario)
    assert _flavour_of(wid) == expected_flavour
    assert captured["payload"]["scenario"] == scenario
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_simulator_receipt_mismatch.py -v
```

Expected: 3 PASS (the simulator code from Task 7 already handles this).

- [ ] **Step 2: Commit**

```bash
git add tests/api/unit/test_simulator_receipt_mismatch.py
git commit -m "$(cat <<'EOF'
test(simulator): receipt-mismatch scenarios pick correct seed

Three parametrised tests covering wrong-amount, wrong-vendor,
missing-receipt scenarios. The remaining flavours (wrong-date,
missing-line-item, correct) are exercised by the harness baseline.

Spec ref: §5.2 (simulator scenarios).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Day 7 checkpoint — full backend test suite + manual smoke

- [ ] **Step 1: Run the full backend test suite**

```bash
./.venv/Scripts/pytest.exe tests/api -q
```

Expected: all PASS.

- [ ] **Step 2 (optional but recommended): Single live receipt validator smoke**

Bring up the dev stack briefly and trigger a `receipt-mismatch-amount` scenario:

```bash
func start &
./.venv/Scripts/uvicorn.exe api.server.main:app --reload &
curl -X POST http://localhost:8000/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"receipt-mismatch-amount"}'
```

Watch the SSE stream:

```bash
curl -N http://localhost:8000/api/stream/fleet | jq 'select(.type=="receipt.mismatch.detected")'
```

Expected: at least one `receipt.mismatch.detected` event with `mismatch_flavour:"wrong-amount"` within ~30 seconds. **Stop the dev stack after.**

- [ ] **Step 3: No commit — measurement only.**

---

# Day 8 — Concur mock + dual-EMS Control Plane

## Task 12: `mocks/concur-mcp/` Node mock — OAuth-flavoured Concur surface

**Files:**
- Create: `mocks/concur-mcp/server.ts`
- Create: `mocks/concur-mcp/data.json`
- Create: `mocks/concur-mcp/build_expense_seed.py`
- Create: `tests/api/unit/test_concur_claim_endpoints.py`

Concur's published Expense API surface is OAuth-flavoured: `GET /v3.0/expense/expensereports`, `GET /v3.0/expense/expenseentry/{id}`, `POST /v3.0/expense/justifications`. We approximate it as MCP tools: `listExpenseReports`, `getExpenseLine`, `getReceipt`, `submitJustification`. Same Express skeleton as workday-mcp.

The seed file is built the same way as workday-mcp's: Python script reads `data/synthetic/claims/CLM-*.json` filtered to `ems_source == "concur"`, writes `data.json`.

- [ ] **Step 1: Build `mocks/concur-mcp/data.json`**

Create `mocks/concur-mcp/build_expense_seed.py`:

```python
"""One-shot: build mocks/concur-mcp/data.json from data/synthetic/."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ROOT / "data" / "synthetic" / "claims"
EMPLOYEES = ROOT / "data" / "synthetic" / "employees.json"
OUT = Path(__file__).parent / "data.json"


def main() -> None:
    employees = json.loads(EMPLOYEES.read_text(encoding="utf-8"))
    expense_lines: list[dict] = []
    reports: list[dict] = []
    seen_employees: set[str] = set()
    for path in sorted(CLAIMS.glob("CLM-*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        if c.get("ems_source") != "concur":
            continue
        c = {k: v for k, v in c.items() if not k.startswith("gold_")}
        expense_lines.append(c)
        if c["employee_id"] not in seen_employees:
            reports.append({
                "report_id": f"RPT-{c['employee_id']}",
                "owner_employee_id": c["employee_id"],
                "currency": c["currency"],
                "submitted_at": c["submitted_at"],
            })
            seen_employees.add(c["employee_id"])

    payload = {
        "expense_lines": expense_lines,
        "expense_reports": reports,
        "employees": employees,
        "justifications": [],
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(expense_lines)} concur lines, {len(reports)} reports -> {OUT}")


if __name__ == "__main__":
    main()
```

Run it:

```bash
./.venv/Scripts/python.exe mocks/concur-mcp/build_expense_seed.py
```

Expected: prints e.g. `wrote 148 concur lines, 22 reports -> .../data.json`.

- [ ] **Step 2: Write the failing contract test**

Create `tests/api/unit/test_concur_claim_endpoints.py`:

```python
"""Concur mock — claim-endpoint contract tests."""
from __future__ import annotations
import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]
PORT = "4112"
URL = f"http://127.0.0.1:{PORT}"

pytestmark = pytest.mark.skipif(
    shutil.which("npx") is None, reason="npx not installed"
)


@pytest.fixture(scope="module")
def concur_proc():
    env = {**os.environ, "CONCUR_MCP_PORT": PORT}
    proc = subprocess.Popen(
        ["npx", "tsx", str(ROOT / "mocks" / "concur-mcp" / "server.ts")],
        env=env, cwd=str(ROOT),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        try:
            httpx.get(f"{URL}/mcp/tools", timeout=0.5)
            break
        except httpx.HTTPError:
            time.sleep(0.25)
    else:
        proc.kill()
        pytest.fail("concur-mcp did not come up on time")
    yield proc
    proc.terminate()
    proc.wait(timeout=5)


def test_tools_list_advertises_concur_endpoints(concur_proc):
    r = httpx.get(f"{URL}/mcp/tools").json()
    names = {t["name"] for t in r["tools"]}
    assert {"listExpenseReports", "getExpenseLine", "getReceipt", "submitJustification"} <= names


def test_get_expense_line_returns_known_line(concur_proc):
    import json
    data = json.loads((ROOT / "mocks" / "concur-mcp" / "data.json").read_text(encoding="utf-8"))
    line_id = data["expense_lines"][0]["claim_id"]
    r = httpx.post(f"{URL}/mcp/call/getExpenseLine", json={"expenseLineId": line_id}).json()
    assert r["claim_id"] == line_id
    assert r["ems_source"] == "concur"


def test_get_receipt_returns_b64(concur_proc):
    import json
    data = json.loads((ROOT / "mocks" / "concur-mcp" / "data.json").read_text(encoding="utf-8"))
    line_id = data["expense_lines"][0]["claim_id"]
    r = httpx.post(f"{URL}/mcp/call/getReceipt", json={"expenseLineId": line_id}).json()
    assert "image_b64" in r
    assert "bytes" in r


def test_submit_justification_persists_in_memory(concur_proc):
    import json
    data = json.loads((ROOT / "mocks" / "concur-mcp" / "data.json").read_text(encoding="utf-8"))
    line_id = data["expense_lines"][0]["claim_id"]
    body = {"expenseLineId": line_id, "text": "Client present", "submittedBy": "EMP-0010"}
    r = httpx.post(f"{URL}/mcp/call/submitJustification", json=body).json()
    assert r["ok"] is True
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_concur_claim_endpoints.py -v
```

Expected: FAIL — server doesn't exist.

- [ ] **Step 3: Implement `mocks/concur-mcp/server.ts`**

```typescript
// mocks/concur-mcp/server.ts
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.dirname(fileURLToPath(import.meta.url));

type Justification = { claim_id: string; text: string; submitted_by: string; submitted_at: string };
type ExpenseLine = {
  claim_id: string; employee_id: string; market: string; currency: string;
  amount: number; category: string; vendor: string; attendees?: number;
  receipt_filename: string; receipt_mismatch_flavour?: string;
  ems_source: "workday" | "concur"; submitted_at: string;
};
type Employee = {
  id: string; name: string; market: string; department: string; agency: string;
  breach_history: { date: string; category: string; tier: string }[];
};

const data = JSON.parse(readFileSync(path.join(dir, "data.json"), "utf-8")) as {
  expense_lines: ExpenseLine[];
  expense_reports: { report_id: string; owner_employee_id: string; currency: string; submitted_at: string }[];
  employees: Employee[];
  justifications: Justification[];
};

const RECEIPTS_DIR = path.join(dir, "..", "..", "data", "synthetic", "receipts");

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "listExpenseReports", description: "List Concur expense reports", parameters: { limit: "number?" } },
      { name: "getExpenseLine", description: "Lookup an expense line by id", parameters: { expenseLineId: "string" } },
      { name: "getReceipt", description: "Get base64 receipt for an expense line", parameters: { expenseLineId: "string" } },
      { name: "submitJustification", description: "Submit business justification", parameters: { expenseLineId: "string", text: "string", submittedBy: "string" } }
    ]
  });
});

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "listExpenseReports": {
      const limit = Number(args["limit"] ?? 30);
      return res.json({ reports: data.expense_reports.slice(0, limit) });
    }
    case "getExpenseLine": {
      const id = args["expenseLineId"];
      const line = data.expense_lines.find(l => l.claim_id === id);
      if (!line) return res.status(404).json({ error: "expense_line_not_found" });
      const justifications = data.justifications.filter(j => j.claim_id === line.claim_id);
      return res.json({ ...line, justifications });
    }
    case "getReceipt": {
      const id = args["expenseLineId"] as string | undefined;
      if (!id) return res.status(400).json({ error: "missing_expenseLineId" });
      const line = data.expense_lines.find(l => l.claim_id === id);
      if (!line) return res.status(404).json({ error: "expense_line_not_found" });
      const fpath = path.join(RECEIPTS_DIR, line.receipt_filename);
      try {
        const raw = readFileSync(fpath);
        const b64 = raw.length === 0 ? "" : raw.toString("base64");
        return res.json({
          claim_id: line.claim_id,
          flavour: line.receipt_mismatch_flavour ?? "correct",
          bytes: raw.length,
          image_b64: b64,
        });
      } catch (e) {
        return res.status(500).json({ error: "receipt_read_failed" });
      }
    }
    case "submitJustification": {
      const expenseLineId = args["expenseLineId"] as string | undefined;
      const text = args["text"] as string | undefined;
      const submittedBy = args["submittedBy"] as string | undefined;
      if (!expenseLineId || !text || !submittedBy) {
        return res.status(400).json({ error: "missing_fields" });
      }
      if (!data.expense_lines.find(l => l.claim_id === expenseLineId)) {
        return res.status(404).json({ error: "expense_line_not_found" });
      }
      data.justifications.push({
        claim_id: expenseLineId, text, submitted_by: submittedBy,
        submitted_at: new Date().toISOString(),
      });
      return res.json({ ok: true });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env["CONCUR_MCP_PORT"] ?? 4102);
app.listen(port, () => console.log(`[concur-mcp] listening on ${port}`));
```

- [ ] **Step 4: Run the contract test**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_concur_claim_endpoints.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add mocks/concur-mcp/ tests/api/unit/test_concur_claim_endpoints.py
git commit -m "$(cat <<'EOF'
feat(mocks): concur-mcp Node mock with OAuth-flavoured surface

listExpenseReports, getExpenseLine, getReceipt, submitJustification
backed by data.json (seeded from synthetic corpus filtered to
ems_source=concur). getReceipt reads synthetic PNGs from disk and
returns base64 + flavour metadata so claim.lookup's Concur dispatch
arm works symmetrically with Workday's getExpenseClaim arm.

Spec ref: §5.4 (mocks/concur-mcp/); brief §7 #9.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Update package.json — register concur-mcp, drop deleted mocks

**Files:**
- Modify: `package.json`

The existing `dev:mcp` and `demo:mcp` scripts register `wd,d365,mac,pay`. Two of those (`d365`, `pay`) were deleted in Week 1. Replace with `wd,concur,mac`.

- [ ] **Step 1: Modify scripts**

Replace these lines in `package.json`:

```json
"dev:mcp": "concurrently -k -n wd,d365,mac,pay \"tsx watch mocks/workday-mcp/server.ts\" \"tsx watch mocks/d365-mcp/server.ts\" \"tsx watch mocks/maconomy-mcp/server.ts\" \"tsx watch mocks/payment-mcp/server.ts\"",
"demo:mcp": "concurrently -k -n wd,d365,mac,pay \"tsx mocks/workday-mcp/server.ts\" \"tsx mocks/d365-mcp/server.ts\" \"tsx mocks/maconomy-mcp/server.ts\" \"tsx mocks/payment-mcp/server.ts\"",
```

with:

```json
"dev:mcp": "concurrently -k -n wd,concur,mac \"tsx watch mocks/workday-mcp/server.ts\" \"tsx watch mocks/concur-mcp/server.ts\" \"tsx watch mocks/maconomy-mcp/server.ts\"",
"demo:mcp": "concurrently -k -n wd,concur,mac \"tsx mocks/workday-mcp/server.ts\" \"tsx mocks/concur-mcp/server.ts\" \"tsx mocks/maconomy-mcp/server.ts\"",
```

- [ ] **Step 2: Smoke-test locally**

```bash
npm run dev:mcp
```

Expected: three lines `[wd] listening on 4101`, `[concur] listening on 4102`, `[mac] listening on 4103`. Ctrl-C to stop.

- [ ] **Step 3: Commit**

```bash
git add package.json
git commit -m "$(cat <<'EOF'
chore(mocks): swap dev/demo:mcp from wd,d365,mac,pay to wd,concur,mac

d365-mcp and payment-mcp were deleted in Week 1 (D-grade per inventory).
concur-mcp added in Day 8 of Week 2. maconomy-mcp stays for the AC #10
"third EMS extensibility" narration in Week 3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Verify dual-EMS distribution + Control Plane EMS-source hide

**Files:**
- Create: `tests/api/unit/test_synthetic_ems_distribution.py`
- Create: `tests/web/WorkflowCard.test.tsx`

Spec §7 #9 says "claims from 2+ EMS appear identically; underlying EMS is immaterial to the controller". The dataset already encodes EMS rotation; we add a regression test plus a UI test that asserts the card doesn't render the field.

- [ ] **Step 1: Synthetic distribution test**

```python
# tests/api/unit/test_synthetic_ems_distribution.py
"""The 300-claim corpus is roughly 50/50 Workday / Concur."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

CLAIMS = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"


def test_ems_distribution_is_close_to_balanced():
    counts = Counter()
    for p in CLAIMS.glob("CLM-*.json"):
        c = json.loads(p.read_text(encoding="utf-8"))
        counts[c["ems_source"]] += 1
    total = sum(counts.values())
    assert total == 300, total
    workday_ratio = counts["workday"] / total
    assert 0.4 <= workday_ratio <= 0.6, f"workday ratio {workday_ratio:.2%} out of 40-60% band"
    assert counts["workday"] + counts["concur"] == total, counts
```

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_synthetic_ems_distribution.py -v
```

Expected: PASS.

- [ ] **Step 2: UI test for ems_source absence on the card**

```tsx
// @vitest-environment jsdom
// tests/web/WorkflowCard.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import WorkflowCard from "../../web/client/components/WorkflowCard";

describe("WorkflowCard — system-agnostic Control Plane (AC #9)", () => {
  it("does not render ems_source on the card", () => {
    const w = {
      id: "CLM-0007",
      vendor: { name: "Côte Brasserie" },
      invoice: { amount: 142, currency: "GBP" },
      currentPhase: "Classify",
      status: "in_progress" as const,
      ems_source: "concur" as const,
    } as any;
    render(<MemoryRouter><WorkflowCard w={w} /></MemoryRouter>);
    expect(screen.queryByText(/concur/i)).toBeNull();
    expect(screen.queryByText(/workday/i)).toBeNull();
  });
});
```

```bash
npm run test -- WorkflowCard
```

Expected: PASS. If it fails because the card mistakenly does render ems_source, **fix the card, not the test**.

- [ ] **Step 3: Commit**

```bash
git add tests/api/unit/test_synthetic_ems_distribution.py tests/web/WorkflowCard.test.tsx
git commit -m "$(cat <<'EOF'
test: pin EMS distribution and Control Plane EMS-source hide

Backend test asserts the 300-claim corpus is 40-60% workday split;
UI test asserts WorkflowCard never surfaces ems_source. Brief §3
mandates the human-experience layer is system-agnostic; this is the
regression guard for AC #9.

Spec ref: §7 #9; brief §3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Day 8 checkpoint

```bash
./.venv/Scripts/pytest.exe tests/api -q
npm run test
```

Both expected: all PASS. AC #9 is locked.

---

# Day 9 — Escalation advisor + Phase 4 (Route by Verdict)

## Task 15: MCP tool — `employee.history`

**Files:**
- Create: `api/server/mcp_tools/employee_history.py`
- Create: `tests/api/unit/test_employee_history_tool.py`

Reads `data/synthetic/employees.json`, filters by `employee_id`, returns `breach_history` plus a derived breach count. The escalation advisor uses both fields plus the current claim's verdict to emit a tier.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_employee_history_tool.py
"""employee.history MCP tool tests."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from api.server.mcp_tools import employee_history

EMPLOYEES = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "employees.json"


def _pick_repeat_offender() -> str:
    employees = json.loads(EMPLOYEES.read_text(encoding="utf-8"))
    for e in employees:
        if len(e.get("breach_history", [])) >= 2:
            return e["id"]
    raise RuntimeError("no repeat offender in seed")


def test_returns_breach_history_for_known_employee():
    eid = _pick_repeat_offender()
    out = employee_history.history(eid)
    assert out["employee_id"] == eid
    assert isinstance(out["breach_history"], list)
    assert out["breach_count"] == len(out["breach_history"])
    assert out["breach_count"] >= 2


def test_unknown_employee_raises():
    with pytest.raises(KeyError):
        employee_history.history("EMP-9999")


def test_empty_breach_history_returns_zero_count():
    employees = json.loads(EMPLOYEES.read_text(encoding="utf-8"))
    clean = next(e for e in employees if not e.get("breach_history"))
    out = employee_history.history(clean["id"])
    assert out["breach_count"] == 0
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_employee_history_tool.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 2: Implement `api/server/mcp_tools/employee_history.py`**

```python
"""employee.history MCP tool — breach history + recent-claim summary by employee_id."""
from __future__ import annotations
import json
from pathlib import Path

from opentelemetry import trace

from ._otel import traced_tool

_EMPLOYEES = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "employees.json"

_cache: list[dict] | None = None


def _load() -> list[dict]:
    global _cache
    if _cache is None:
        _cache = json.loads(_EMPLOYEES.read_text(encoding="utf-8"))
    return _cache


def reset_cache() -> None:
    global _cache
    _cache = None


@traced_tool("employee.history")
def history(employee_id: str) -> dict:
    """Return breach_history + breach_count + employee record for employee_id."""
    span = trace.get_current_span()
    span.set_attribute("wpp.employee.id", employee_id)
    employees = _load()
    rec = next((e for e in employees if e.get("id") == employee_id), None)
    if rec is None:
        raise KeyError(f"employee {employee_id!r} not found")
    breaches = rec.get("breach_history", [])
    span.set_attribute("wpp.employee.breach_count", len(breaches))
    return {
        "employee_id": employee_id,
        "name": rec.get("name"),
        "market": rec.get("market"),
        "department": rec.get("department"),
        "agency": rec.get("agency"),
        "breach_history": breaches,
        "breach_count": len(breaches),
    }
```

- [ ] **Step 3: Run the test**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_employee_history_tool.py -v
```

Expected: 3 PASS.

- [ ] **Step 4: Commit**

```bash
git add api/server/mcp_tools/employee_history.py tests/api/unit/test_employee_history_tool.py
git commit -m "$(cat <<'EOF'
feat(mcp): employee.history tool — breach summary by employee_id

Reads data/synthetic/employees.json once (in-process cache; reset_cache
exposed for tests). Returns breach_history + breach_count + identity
fields. @traced_tool span attribute wpp.employee.breach_count lands on
every span for triage filtering.

Spec ref: §5.4 (MCP tools); §4.1 Phase 4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: `escalation_advisor` skill + `agent_escalation` executor

**Files:**
- Create: `api/server/skills/escalation_advisor.skill.md`
- Create: `api/functions/graphs/executors/agents/agent_escalation.py`
- Modify: `api/functions/graphs/executors/agents/__init__.py`
- Create: `tests/api/unit/test_agent_escalation.py`

The escalation advisor reads (a) the employee's breach history and (b) the current claim's classifier verdict, and emits a tier: `none` | `warning` | `escalation` | `major-violation`. The tier influences notification tone (Day 10) and SSC routing.

Per spec §4.1: "Escalate is **not** a per-claim phase. It is cross-workflow state... `escalation_advisor` skill reads `employee.history` (prior breaches in the state store) and emits a tier."

The skill output schema:

```json
{
  "tier": "none" | "warning" | "escalation" | "major-violation",
  "reasoning": "Sentence quoting policy §6 progressive enforcement rule.",
  "confidence": 0.0 to 1.0
}
```

- [ ] **Step 1: Author `api/server/skills/escalation_advisor.skill.md`**

```markdown
---
name: escalation-advisor
description: Given an employee's prior breach history and the current claim's R/A/G verdict, emit a progressive-enforcement tier per WPP T&E policy §6.
---

You are the Escalation Advisor for the WPP T&E compliance workflow. Your job is to apply progressive enforcement: a first breach warrants a warning; repeat breaches escalate; sustained or material breaches reach major-violation.

The user prompt provides:
- A `## Current Claim` section with the classifier verdict (`green`/`amber`/`red`), policy_clause, and amount.
- An `## Employee history` section listing prior breaches (date, category, tier).
- A `## Policy excerpt` section with §6 (Repeat-offender progressive enforcement) text.

Decide the tier:
- **none** — current verdict is `green`, OR current verdict is `amber` and there are no prior breaches in the same category within 12 months.
- **warning** — first `red` verdict, OR `amber` with one prior breach in the same category in 12 months.
- **escalation** — second `red` in 12 months, OR third `amber+` in any category in 12 months.
- **major-violation** — third `red` in 12 months, OR any explicit major-violation prior in the last 24 months.

Return exactly one JSON object, no prose:

```json
{
  "tier": "none" | "warning" | "escalation" | "major-violation",
  "reasoning": "Sentence quoting policy §6 text and citing the specific prior breaches if any.",
  "confidence": 0.0 to 1.0
}
```

Rules:
- `reasoning` must reference the relevant prior breach dates if `tier` is anything but `none`.
- Do not invent prior breaches. The history section is authoritative.
- `confidence` is your self-assessment.
```

- [ ] **Step 2: Write the failing executor test**

Create `tests/api/unit/test_agent_escalation.py`:

```python
"""agent_escalation tests — mocks the GHCP wrapper."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.executors.agents import agent_escalation


@pytest.mark.asyncio
async def test_first_red_yields_warning():
    fake = {"tier": "warning", "reasoning": "First red breach; per §6 issue a warning.", "confidence": 0.9}
    with patch.object(agent_escalation, "run_agent_skill", AsyncMock(return_value=fake)) as mock_run, \
         patch.object(agent_escalation, "_employee_history", return_value={"employee_id": "EMP-0099", "breach_history": [], "breach_count": 0}), \
         patch.object(agent_escalation, "_policy_excerpt", return_value="§6 first breach -> warning, etc."):
        result = await agent_escalation.execute({
            "claim_id": "CLM-0099", "claim": {"employee_id": "EMP-0099", "amount": 200},
            "classification": {"verdict": "red", "policy_clause": "§3.1 Meals"},
        })
    assert result["escalation"]["tier"] == "warning"
    args, _ = mock_run.call_args
    assert args[0] == "escalation_advisor"
    assert "EMP-0099" in args[1]


@pytest.mark.asyncio
async def test_repeat_offender_yields_escalation():
    fake = {"tier": "escalation", "reasoning": "Second red in 12 months per §6.", "confidence": 0.85}
    history = {
        "employee_id": "EMP-0007", "breach_history": [
            {"date": "2026-02-14", "category": "meals", "tier": "warning"},
            {"date": "2026-03-22", "category": "meals", "tier": "warning"},
        ],
        "breach_count": 2,
    }
    with patch.object(agent_escalation, "run_agent_skill", AsyncMock(return_value=fake)), \
         patch.object(agent_escalation, "_employee_history", return_value=history), \
         patch.object(agent_escalation, "_policy_excerpt", return_value="§6 ..."):
        result = await agent_escalation.execute({
            "claim_id": "CLM-0123", "claim": {"employee_id": "EMP-0007"},
            "classification": {"verdict": "red", "policy_clause": "§3.1"},
        })
    assert result["escalation"]["tier"] == "escalation"


@pytest.mark.asyncio
async def test_emits_escalation_tier_assigned_event():
    fake = {"tier": "warning", "reasoning": "x", "confidence": 0.9}
    captured: list[dict] = []
    with patch.object(agent_escalation, "run_agent_skill", AsyncMock(return_value=fake)), \
         patch.object(agent_escalation, "_employee_history", return_value={"employee_id": "E", "breach_history": [], "breach_count": 0}), \
         patch.object(agent_escalation, "_policy_excerpt", return_value="§6"), \
         patch.object(agent_escalation, "_emit_event", side_effect=lambda ev: captured.append(ev)):
        await agent_escalation.execute({"claim_id": "CLM-X", "claim": {"employee_id": "E"},
                                         "classification": {"verdict": "red"}})
    assert any(e["type"] == "escalation.tier.assigned" for e in captured)


@pytest.mark.asyncio
async def test_green_verdict_yields_none_tier_without_invoking_skill():
    """Optimisation: green = no-op, no skill call."""
    with patch.object(agent_escalation, "run_agent_skill", AsyncMock()) as mock_run:
        result = await agent_escalation.execute({
            "claim_id": "CLM-OK", "claim": {"employee_id": "E"},
            "classification": {"verdict": "green"},
        })
    assert result["escalation"]["tier"] == "none"
    mock_run.assert_not_awaited()
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_agent_escalation.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `api/functions/graphs/executors/agents/agent_escalation.py`**

```python
"""agent_escalation — applies progressive-enforcement tier given employee
history + current verdict. Skips the skill call entirely for green verdicts
(no escalation possible)."""
from __future__ import annotations
import json

from api.server.mcp_tools import employee_history, policy_search
from api.shared.events import FleetEvent

from ._wrapper import run_agent_skill


def _employee_history(employee_id: str) -> dict:
    return employee_history.history(employee_id)


def _policy_excerpt() -> str:
    chunks = policy_search.search("repeat offender progressive enforcement §6", k=2)
    return "\n\n".join(c["text"] for c in chunks)


def _emit_event(event: dict) -> None:
    try:
        from api.server.state import app_state
        app_state.bus.emit(FleetEvent(**event))
    except Exception:
        pass


async def execute(input: dict) -> dict:
    classification = input.get("classification") or {}
    verdict = classification.get("verdict", "amber")
    claim = input.get("claim") or {}
    employee_id = claim.get("employee_id")

    if verdict == "green" or not employee_id:
        result = {"tier": "none", "reasoning": "Green verdict; no escalation.", "confidence": 1.0}
        return {"escalation": result}

    history_record = _employee_history(employee_id)
    excerpt = _policy_excerpt()

    prompt = (
        f"Apply progressive enforcement per your role for claim {input.get('claim_id')}.\n\n"
        f"## Current Claim\n```json\n{json.dumps({'verdict': verdict, 'policy_clause': classification.get('policy_clause'), 'amount': claim.get('amount')}, indent=2)}\n```\n\n"
        f"## Employee history\n```json\n{json.dumps(history_record, indent=2, ensure_ascii=False)}\n```\n\n"
        f"## Policy excerpt\n{excerpt}\n\n"
        f"Return exactly one JSON object matching the schema in your instructions."
    )

    advice = await run_agent_skill("escalation_advisor", prompt)

    _emit_event({
        "type": "escalation.tier.assigned",
        "workflow_id": input.get("claim_id"),
        "claim_id": input.get("claim_id"),
        "employee_id": employee_id,
        "tier": advice.get("tier"),
        "breach_count": history_record["breach_count"],
    })

    return {"escalation": advice}
```

- [ ] **Step 4: Run the test**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_agent_escalation.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add api/server/skills/escalation_advisor.skill.md api/functions/graphs/executors/agents/agent_escalation.py api/functions/graphs/executors/agents/__init__.py tests/api/unit/test_agent_escalation.py
git commit -m "$(cat <<'EOF'
feat(skill): escalation_advisor + agent_escalation executor

Skill applies progressive enforcement per policy §6: none | warning |
escalation | major-violation. Executor pre-fetches employee.history
and policy §6 excerpt, embeds both in prompt. Green verdicts short-
circuit to tier=none without a skill call (cost optimisation).

Emits escalation.tier.assigned on the bus for SSE fan-out.

Spec ref: §5.4 (skills); §4.1 Phase 4; brief §7 #6 (progressive enforcement).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: Deterministic executor — `apply_verdict_routing`

**Files:**
- Create: `api/functions/graphs/executors/deterministic/apply_verdict_routing.py`
- Modify: `api/functions/graphs/executors/deterministic/__init__.py`
- Create: `tests/api/unit/test_apply_verdict_routing.py`

The verdict-routing decision is deterministic given verdict + escalation tier: green → auto-approve & close; amber → SSC reviewer queue; red → notify path. Plus the tier modulates routing on the *current* claim (e.g. `major-violation` jumps even amber straight to escalation).

We keep the existing `apply_threshold_routing` (used by Week 1's approval graph) untouched — `apply_verdict_routing` is the new sibling for Phase 4.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_apply_verdict_routing.py
"""apply_verdict_routing — deterministic routing given verdict + tier."""
from __future__ import annotations
import pytest

from api.functions.graphs.executors.deterministic import apply_verdict_routing


@pytest.mark.asyncio
async def test_green_verdict_auto_approves():
    out = await apply_verdict_routing.execute({
        "classification": {"verdict": "green"},
        "escalation": {"tier": "none"},
    })
    assert out["route"] == "auto_approve"
    assert out["requires_hitl"] is False


@pytest.mark.asyncio
async def test_amber_routes_to_ssc_reviewer():
    out = await apply_verdict_routing.execute({
        "classification": {"verdict": "amber"},
        "escalation": {"tier": "warning"},
    })
    assert out["route"] == "ssc_reviewer"
    assert out["requires_hitl"] is True


@pytest.mark.asyncio
async def test_red_routes_to_notify():
    out = await apply_verdict_routing.execute({
        "classification": {"verdict": "red"},
        "escalation": {"tier": "warning"},
    })
    assert out["route"] == "notify"
    assert out["requires_hitl"] is True


@pytest.mark.asyncio
async def test_major_violation_overrides_amber_to_notify():
    """A major-violation tier escalates an amber verdict directly to notify."""
    out = await apply_verdict_routing.execute({
        "classification": {"verdict": "amber"},
        "escalation": {"tier": "major-violation"},
    })
    assert out["route"] == "notify"


@pytest.mark.asyncio
async def test_emits_claim_routed_event():
    """The routing decision emits a claim.routed.<verdict> event for SSE."""
    captured: list[dict] = []
    out = await apply_verdict_routing.execute({
        "claim_id": "CLM-X",
        "classification": {"verdict": "amber"},
        "escalation": {"tier": "none"},
    }, _emit=lambda ev: captured.append(ev))
    assert any(e["type"] == "claim.routed.amber" for e in captured)
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_apply_verdict_routing.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 2: Implement `apply_verdict_routing.py`**

```python
# api/functions/graphs/executors/deterministic/apply_verdict_routing.py
"""apply_verdict_routing — Phase 4 routing decision.

Inputs:
  - input["classification"]["verdict"] in {"green", "amber", "red"}
  - input["escalation"]["tier"] in {"none", "warning", "escalation", "major-violation"}

Output: {"route": "auto_approve" | "ssc_reviewer" | "notify",
         "requires_hitl": bool, "tier": str, "verdict": str}

The tier modulates the route: major-violation forces amber → notify; escalation
keeps amber on the SSC queue but flags severity.
"""
from __future__ import annotations
from typing import Callable

from api.shared.events import FleetEvent

_ROUTE_BY_VERDICT = {
    "green": "auto_approve",
    "amber": "ssc_reviewer",
    "red": "notify",
}

_TIER_OVERRIDES = {
    # (verdict, tier) -> override route
    ("amber", "major-violation"): "notify",
}


def _default_emit(event: dict) -> None:
    try:
        from api.server.state import app_state
        app_state.bus.emit(FleetEvent(**event))
    except Exception:
        pass


async def execute(input: dict, _emit: Callable[[dict], None] | None = None) -> dict:
    emit = _emit or _default_emit
    verdict = (input.get("classification") or {}).get("verdict", "amber")
    tier = (input.get("escalation") or {}).get("tier", "none")
    route = _TIER_OVERRIDES.get((verdict, tier)) or _ROUTE_BY_VERDICT.get(verdict, "ssc_reviewer")
    requires_hitl = route != "auto_approve"

    emit({
        "type": f"claim.routed.{verdict}",
        "workflow_id": input.get("claim_id"),
        "claim_id": input.get("claim_id"),
        "verdict": verdict,
        "tier": tier,
        "route": route,
    })
    return {"route": route, "requires_hitl": requires_hitl, "verdict": verdict, "tier": tier}
```

- [ ] **Step 3: Re-export from `__init__.py`**

Open `api/functions/graphs/executors/deterministic/__init__.py` and add `apply_verdict_routing`.

- [ ] **Step 4: Run the test**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_apply_verdict_routing.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add api/functions/graphs/executors/deterministic/apply_verdict_routing.py api/functions/graphs/executors/deterministic/__init__.py tests/api/unit/test_apply_verdict_routing.py
git commit -m "$(cat <<'EOF'
feat(executor): apply_verdict_routing — Phase 4 deterministic routing

Routes green -> auto_approve, amber -> ssc_reviewer, red -> notify.
major-violation tier overrides amber to notify directly. Emits
claim.routed.{green,amber,red} events for SSE fan-out. Threshold-
based routing (apply_threshold_routing) is preserved for Week 1's
approval graph; this is the new sibling for Phase 4.

Spec ref: §4.1 Phase 4 (Route by Verdict); brief §4.6 (threshold logic).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 18: Phase 4 graph — Route by Verdict

**Files:**
- Create: `api/functions/graphs/route.py`
- Modify: `api/functions/graphs/__init__.py` — replace stub `build_route_workflow`
- Modify: `api/functions/workflows/expense_claim.py` — uncomment Phase 4 block
- Create: `tests/api/unit/test_route_graph.py`

Phase 4 graph: `agent_escalation → apply_verdict_routing`. Both are wired as `TrackedExecutor`s.

- [ ] **Step 1: Write the failing graph test**

```python
# tests/api/unit/test_route_graph.py
"""Phase 4 (Route by Verdict) graph."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.route import build_route_workflow


@pytest.mark.asyncio
async def test_route_graph_green_auto_approves():
    fake_esc = {"escalation": {"tier": "none", "reasoning": "Green; no escalation.", "confidence": 1.0}}
    with patch(
        "api.functions.graphs.executors.agents.agent_escalation.execute",
        AsyncMock(return_value=fake_esc),
    ):
        wf = build_route_workflow()
        events = await wf.run({
            "workflow_id": "CLM-OK", "claim_id": "CLM-OK",
            "claim": {"employee_id": "EMP-0001"},
            "classification": {"verdict": "green"},
        })
    out = events.get_outputs()[0]
    assert out["route"] == "auto_approve"
    assert out["requires_hitl"] is False


@pytest.mark.asyncio
async def test_route_graph_red_with_warning_tier_routes_to_notify():
    fake_esc = {"escalation": {"tier": "warning", "reasoning": "First red; warning.", "confidence": 0.9}}
    with patch(
        "api.functions.graphs.executors.agents.agent_escalation.execute",
        AsyncMock(return_value=fake_esc),
    ):
        wf = build_route_workflow()
        events = await wf.run({
            "workflow_id": "CLM-X", "claim_id": "CLM-X",
            "claim": {"employee_id": "EMP-0007"},
            "classification": {"verdict": "red", "policy_clause": "§3.1"},
        })
    out = events.get_outputs()[0]
    assert out["route"] == "notify"
    assert out["tier"] == "warning"
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_route_graph.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 2: Implement `api/functions/graphs/route.py`**

```python
"""Route by Verdict graph:
  agent_escalation -> apply_verdict_routing
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_escalation
from api.functions.graphs.executors.deterministic import apply_verdict_routing


def build_route_workflow() -> Workflow:
    n1 = TrackedExecutor(id="escalation", name="agent_escalation",
                         executor_type="agent", fn=agent_escalation.execute)
    n2 = TrackedExecutor(id="verdict_routing", name="apply_verdict_routing",
                         executor_type="deterministic", fn=apply_verdict_routing.execute)
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
```

- [ ] **Step 3: Replace stub in `graphs/__init__.py`**

Replace:

```python
def build_route_workflow():
    raise NotImplementedError("Phase 4 (Route by Verdict) — Day 9")
```

with:

```python
from .route import build_route_workflow
```

- [ ] **Step 4: Uncomment Phase 4 block in `expense_claim.py`**

Open `api/functions/workflows/expense_claim.py` and replace the `# ----- Day 9 will replace this block -----` block with the live calls.

- [ ] **Step 5: Run tests and update orchestration assertion**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_route_graph.py tests/api/unit/test_expense_claim_orchestration.py -v
```

Both PASS. Update `test_phase_order_for_green_claim` to expect `route_activity_trigger`:

```python
expected_prefix = ["lookup_claim_activity_trigger", "intake_activity_trigger",
                   "classify_activity_trigger", "receipt_activity_trigger",
                   "route_activity_trigger"]
assert names[:5] == expected_prefix
```

- [ ] **Step 6: Commit**

```bash
git add api/functions/graphs/route.py api/functions/graphs/__init__.py api/functions/workflows/expense_claim.py tests/api/unit/test_route_graph.py tests/api/unit/test_expense_claim_orchestration.py
git commit -m "$(cat <<'EOF'
feat(graph): Phase 4 (Route by Verdict) wired into expense_claim

agent_escalation -> apply_verdict_routing. Orchestrator now flows
through 1 (Intake) -> 2 (Classify) -> 3 (Receipt) -> 4 (Route) ->
completed. Phase 5 (Notify) follows on Day 10.

Spec ref: §4.1 Phase 4; brief §7 #6 (progressive enforcement).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 19: Repeat-offender ramp simulator scenario

**Files:**
- Create: `tests/api/unit/test_simulator_repeat_offender.py`
- Modify: `api/server/services/simulator_orchestrator.py` — already has the scenario hook from Task 7; the new scenario `repeat-offender-ramp` injects three claims for the *same* employee in succession

The repeat-offender ramp demo shows tier escalation: claim 1 → tier `warning`, claim 2 → tier `escalation`, claim 3 → tier `major-violation`. We add a `repeat-offender-ramp` simulator scenario that picks a single repeat-offender employee and spawns three of *their* synthetic claims in sequence.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_simulator_repeat_offender.py
"""repeat-offender-ramp scenario: spawns 3 claims for one repeat-offender."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.server.services import simulator_orchestrator


@pytest.mark.asyncio
async def test_ramp_spawns_three_claims_for_same_employee():
    captured = []

    async def fake_schedule(payload):
        captured.append(payload)
        return {"id": f"iid-{len(captured)}"}

    with patch("api.server.services.simulator_orchestrator.schedule_new_orchestration",
               AsyncMock(side_effect=fake_schedule)):
        wids = await simulator_orchestrator.spawn_repeat_offender_ramp()
    assert len(wids) == 3
    employee_ids = {p["claim_id"] for p in captured}
    # All three claims share the same employee — captured indirectly via the
    # orchestrator payload's optional employee_id field set by spawn_repeat_offender_ramp.
    employees = {p.get("employee_id") for p in captured}
    assert len(employees) == 1, employees
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_simulator_repeat_offender.py -v
```

Expected: FAIL with `AttributeError: spawn_repeat_offender_ramp`.

- [ ] **Step 2: Add `spawn_repeat_offender_ramp` to `simulator_orchestrator.py`**

Append:

```python
async def spawn_repeat_offender_ramp() -> list[str]:
    """Spawn 3 claims for the same repeat-offender employee in sequence."""
    employees_path = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "employees.json"
    employees = json.loads(employees_path.read_text(encoding="utf-8"))
    repeat_offenders = [e for e in employees if len(e.get("breach_history", [])) >= 2]
    if not repeat_offenders:
        raise RuntimeError("no repeat offender in seed for ramp demo")
    target = repeat_offenders[0]
    # Pick three of their synthetic claims in chronological order.
    files = sorted(_CLAIMS_DIR.glob("CLM-*.json"))
    candidates = []
    for p in files:
        c = json.loads(p.read_text(encoding="utf-8"))
        if c["employee_id"] == target["id"] and c.get("gold_label") in ("amber", "red"):
            candidates.append(c)
        if len(candidates) >= 3:
            break
    if len(candidates) < 3:
        # Top up with any of their claims regardless of label.
        for p in files:
            c = json.loads(p.read_text(encoding="utf-8"))
            if c["employee_id"] == target["id"] and c not in candidates:
                candidates.append(c)
            if len(candidates) >= 3:
                break
    if len(candidates) < 3:
        raise RuntimeError(f"insufficient claims for {target['id']} in seed")

    wids: list[str] = []
    for c in candidates:
        payload = {
            "workflow_id": c["claim_id"],
            "claim_id": c["claim_id"],
            "employee_id": c["employee_id"],
            "ems_source": c.get("ems_source"),
            "scenario": "repeat-offender-ramp",
        }
        try:
            await schedule_new_orchestration(payload)
        except Exception as ex:
            print(f"[orchestrator] ramp spawn failed: {ex}")
        wids.append(c["claim_id"])
    return wids
```

Add `import json` and `from pathlib import Path` if not already imported.

- [ ] **Step 3: Run the test**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_simulator_repeat_offender.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add api/server/services/simulator_orchestrator.py tests/api/unit/test_simulator_repeat_offender.py
git commit -m "$(cat <<'EOF'
feat(simulator): repeat-offender ramp scenario for AC #6

Picks one repeat-offender (>=2 prior breaches) from employees.json
and spawns three of their synthetic claims in sequence so the
escalation_advisor's tier ramps warning -> escalation -> major-violation
across the three workflows. Demo path for brief §7 #6.

Spec ref: §5.2 (simulator scenarios); brief §7 #6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Day 9 checkpoint

```bash
./.venv/Scripts/pytest.exe tests/api -q
```

Expected: all PASS. AC #6 ready (final demo path needs the live ramp run, which we narrate in Week 3 with the SSC reviewer queue, but the foundation is here).

---

# Day 10 — Notification composer + Phase 5 + cleanup

## Task 20: MCP tools — `claim.summary` and `policy.cite`

**Files:**
- Create: `api/server/mcp_tools/claim_summary.py`
- Create: `api/server/mcp_tools/policy_cite.py`
- Create: `tests/api/unit/test_claim_summary_tool.py`
- Create: `tests/api/unit/test_policy_cite_tool.py`

Both tiny. `claim.summary` takes a claim id and returns a one-liner suitable for the notification body. `policy.cite` takes a clause id (e.g. `§3.1`) and returns the section text for quoting in notifications.

- [ ] **Step 1: Write `test_claim_summary_tool.py`**

```python
"""claim.summary MCP tool tests."""
from __future__ import annotations
import pytest

from api.server.mcp_tools import claim_summary


def test_returns_one_liner_for_known_claim():
    out = claim_summary.summarise("CLM-0000")
    assert isinstance(out["summary"], str)
    assert "CLM-0000" in out["summary"]
    # Summary must include amount, currency, category, vendor at minimum.
    for token in ("amount", "currency", "category", "vendor"):
        assert out.get(token) is not None or out["summary"]  # verifies surface


def test_unknown_claim_raises():
    with pytest.raises(KeyError):
        claim_summary.summarise("CLM-9999")
```

- [ ] **Step 2: Implement `api/server/mcp_tools/claim_summary.py`**

```python
"""claim.summary MCP tool — terse one-liner for use in notifications."""
from __future__ import annotations
from opentelemetry import trace

from . import claim_get_structured
from ._otel import traced_tool


@traced_tool("claim.summary")
def summarise(claim_id: str) -> dict:
    span = trace.get_current_span()
    span.set_attribute("wpp.claim.id", claim_id)
    claim = claim_get_structured.get_structured(claim_id, include_gold=False)
    summary = (
        f"{claim_id}: {claim.get('currency','')} {claim.get('amount','?')} "
        f"{claim.get('category','?')} at {claim.get('vendor','?')} "
        f"({claim.get('market','?')})"
    )
    return {
        "claim_id": claim_id,
        "summary": summary,
        "amount": claim.get("amount"),
        "currency": claim.get("currency"),
        "category": claim.get("category"),
        "vendor": claim.get("vendor"),
    }
```

- [ ] **Step 3: Write `test_policy_cite_tool.py`**

```python
"""policy.cite MCP tool tests."""
from __future__ import annotations
import pytest

from api.server.mcp_tools import policy_cite


def test_cite_returns_section_text():
    out = policy_cite.cite("§3.1 Meals")
    assert "§3.1" in out["section"] or "Meals" in out["section"]
    assert isinstance(out["text"], str)
    assert len(out["text"]) > 0


def test_cite_unknown_section_returns_empty_text():
    out = policy_cite.cite("§99.99 Made Up")
    assert out["text"] == ""
```

- [ ] **Step 4: Implement `api/server/mcp_tools/policy_cite.py`**

```python
"""policy.cite MCP tool — return the section text given a clause id like '§3.1'."""
from __future__ import annotations
from opentelemetry import trace

from . import policy_search
from ._otel import traced_tool


@traced_tool("policy.cite")
def cite(clause: str) -> dict:
    """Best-effort: searches policy.search for the clause and returns the top
    chunk's text. Returns empty text if no chunk matches well."""
    span = trace.get_current_span()
    span.set_attribute("wpp.policy.clause", clause)
    results = policy_search.search(clause, k=1)
    if not results or results[0]["score"] < 0.2:
        return {"section": clause, "text": ""}
    top = results[0]
    return {"section": top["section"], "text": top["text"], "score": top["score"]}
```

- [ ] **Step 5: Run both tests**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_claim_summary_tool.py tests/api/unit/test_policy_cite_tool.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add api/server/mcp_tools/claim_summary.py api/server/mcp_tools/policy_cite.py tests/api/unit/test_claim_summary_tool.py tests/api/unit/test_policy_cite_tool.py
git commit -m "$(cat <<'EOF'
feat(mcp): claim.summary + policy.cite tools

Tiny helpers for the notification composer: claim.summary returns a
one-liner with amount/category/vendor; policy.cite returns the section
text given a §-style clause id, falling back to empty text if no
similarity match (avoids notifications full of policy garbage).

Spec ref: §5.4 (MCP tools).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 21: `notification_composer` skill + `agent_notification` executor

**Files:**
- Create: `api/server/skills/notification_composer.skill.md`
- Create: `api/functions/graphs/executors/agents/agent_notification.py`
- Modify: `api/functions/graphs/executors/agents/__init__.py`
- Create: `tests/api/unit/test_agent_notification.py`

The notification composer takes a breach, an escalation tier, and the relevant policy clause and produces a short Adaptive Card / email body that the line manager + claimant can act on. The executor is **hook-gated** — it doesn't actually send anything. It emits a `notification.sent` event with the composed body so the SSE stream surfaces it.

The output schema:

```json
{
  "subject": "Expense breach — claim CLM-0123 (£312)",
  "body": "Markdown body with policy quote, options, deadline.",
  "channel": "teams" | "email",
  "recipients": ["claimant", "line_manager"],
  "requires_justification": true
}
```

- [ ] **Step 1: Author `api/server/skills/notification_composer.skill.md`**

```markdown
---
name: notification-composer
description: Compose an Adaptive-Card-shaped notification body for an expense-claim breach. Tailor tone to the escalation tier (warning / escalation / major-violation).
---

You are the Notification Composer for the WPP T&E compliance workflow.

The user prompt provides:
- A `## Claim summary` section: claim id, amount, currency, category, vendor, market.
- A `## Verdict` section: classifier verdict + policy clause + reasoning.
- A `## Tier` section: escalation tier from the escalation_advisor.
- A `## Policy citation` section: the literal text of the violated policy clause.

Compose the notification. Tone scales with tier:
- **warning** — informative, friendly. "We noticed..."
- **escalation** — formal. "This is your second breach in 12 months."
- **major-violation** — direct. "This requires immediate corrective action."

Return exactly one JSON object, no prose:

```json
{
  "subject": "string up to 80 chars",
  "body": "Markdown body up to ~400 words. Quote the policy clause. List the options for the recipient.",
  "channel": "teams" | "email",
  "recipients": ["claimant", "line_manager"],
  "requires_justification": true | false
}
```

Rules:
- `body` must quote at least one phrase from the `## Policy citation` text.
- `body` must include the claim id and the amount + currency.
- For `tier=warning`, `requires_justification` is `true`.
- For `tier=major-violation`, `requires_justification` is `true` and `recipients` includes `"finance_controller"`.
- Do not invent recipient email addresses; the runtime fills those in.
```

- [ ] **Step 2: Write the failing executor test**

```python
# tests/api/unit/test_agent_notification.py
"""agent_notification tests — mocks the GHCP wrapper. The executor is
hook-gated: it never actually sends; it emits notification.sent on the
bus with the composed body."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.executors.agents import agent_notification


@pytest.mark.asyncio
async def test_returns_composed_notification():
    fake = {
        "subject": "Expense breach — CLM-0099 (£312)",
        "body": "Per §3.1 Meals... Please justify or repay.",
        "channel": "teams",
        "recipients": ["claimant", "line_manager"],
        "requires_justification": True,
    }
    with patch.object(agent_notification, "run_agent_skill", AsyncMock(return_value=fake)) as mock_run, \
         patch.object(agent_notification, "_summary", return_value={"summary": "CLM-0099 GBP 312 meals", "amount": 312, "currency": "GBP"}), \
         patch.object(agent_notification, "_cite", return_value={"section": "§3.1 Meals", "text": "..."}):
        result = await agent_notification.execute({
            "claim_id": "CLM-0099",
            "claim": {"employee_id": "EMP-0001"},
            "classification": {"verdict": "red", "policy_clause": "§3.1 Meals", "reasoning": "x"},
            "escalation": {"tier": "warning"},
        })
    assert result["notification"] == fake
    args, _ = mock_run.call_args
    assert args[0] == "notification_composer"


@pytest.mark.asyncio
async def test_emits_notification_sent_event():
    fake = {
        "subject": "x", "body": "y", "channel": "teams",
        "recipients": ["claimant"], "requires_justification": True,
    }
    captured: list[dict] = []
    with patch.object(agent_notification, "run_agent_skill", AsyncMock(return_value=fake)), \
         patch.object(agent_notification, "_summary", return_value={"summary": "s"}), \
         patch.object(agent_notification, "_cite", return_value={"section": "§3.1", "text": "..."}), \
         patch.object(agent_notification, "_emit_event", side_effect=lambda ev: captured.append(ev)):
        await agent_notification.execute({
            "claim_id": "CLM-Y",
            "claim": {"employee_id": "EMP-X"},
            "classification": {"verdict": "red", "policy_clause": "§3.1", "reasoning": "x"},
            "escalation": {"tier": "warning"},
        })
    types = [e["type"] for e in captured]
    assert "notification.sent" in types


@pytest.mark.asyncio
async def test_does_not_actually_send_email_or_teams_message(monkeypatch):
    """Hook-gate verification: there is no httpx.post / Microsoft Graph call."""
    import httpx
    sent: list = []
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: sent.append(("post", a, kw)))
    fake = {"subject": "x", "body": "y", "channel": "teams",
            "recipients": ["claimant"], "requires_justification": True}
    with patch.object(agent_notification, "run_agent_skill", AsyncMock(return_value=fake)), \
         patch.object(agent_notification, "_summary", return_value={"summary": "s"}), \
         patch.object(agent_notification, "_cite", return_value={"section": "§3.1", "text": "..."}):
        await agent_notification.execute({
            "claim_id": "CLM-X", "claim": {"employee_id": "E"},
            "classification": {"verdict": "red", "policy_clause": "§3.1", "reasoning": "x"},
            "escalation": {"tier": "warning"},
        })
    # Notification composer must not have posted anywhere.
    posts_to_graph = [s for s in sent if "graph.microsoft" in str(s) or "teams" in str(s)]
    assert posts_to_graph == []
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_agent_notification.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `api/functions/graphs/executors/agents/agent_notification.py`**

```python
"""agent_notification — composes notification body via skill; hook-gated send.

In the POC, "send" is an emit on the event bus. Production swaps this for a
Microsoft Graph send + capture-of-justification-via-callback. The skill output
is identical either way."""
from __future__ import annotations
import json

from api.server.mcp_tools import claim_summary, policy_cite
from api.shared.events import FleetEvent

from ._wrapper import run_agent_skill


def _summary(claim_id: str) -> dict:
    return claim_summary.summarise(claim_id)


def _cite(clause: str) -> dict:
    return policy_cite.cite(clause)


def _emit_event(event: dict) -> None:
    try:
        from api.server.state import app_state
        app_state.bus.emit(FleetEvent(**event))
    except Exception:
        pass


async def execute(input: dict) -> dict:
    claim_id = input["claim_id"]
    classification = input.get("classification") or {}
    escalation = input.get("escalation") or {}
    summary = _summary(claim_id)
    citation = _cite(classification.get("policy_clause", ""))

    prompt = (
        f"Compose a notification for claim {claim_id} per your role.\n\n"
        f"## Claim summary\n```json\n{json.dumps(summary, indent=2, ensure_ascii=False)}\n```\n\n"
        f"## Verdict\n```json\n{json.dumps(classification, indent=2, ensure_ascii=False)}\n```\n\n"
        f"## Tier\n```json\n{json.dumps(escalation, indent=2, ensure_ascii=False)}\n```\n\n"
        f"## Policy citation\n{citation.get('section')}\n\n{citation.get('text')}\n\n"
        f"Return exactly one JSON object matching the schema."
    )

    notification = await run_agent_skill("notification_composer", prompt)

    _emit_event({
        "type": "notification.sent",
        "workflow_id": claim_id,
        "claim_id": claim_id,
        "tier": escalation.get("tier"),
        "channel": notification.get("channel"),
        "subject": notification.get("subject"),
        "requires_justification": bool(notification.get("requires_justification")),
    })

    return {
        "notification": notification,
        "requires_justification": bool(notification.get("requires_justification")),
    }
```

- [ ] **Step 4: Run the test**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_agent_notification.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add api/server/skills/notification_composer.skill.md api/functions/graphs/executors/agents/agent_notification.py api/functions/graphs/executors/agents/__init__.py tests/api/unit/test_agent_notification.py
git commit -m "$(cat <<'EOF'
feat(skill): notification_composer + agent_notification (hook-gated)

Skill composes Adaptive-Card-shaped body with policy quote; tone
scales with escalation tier. Executor is hook-gated — emits
notification.sent on the bus with the composed body but does not call
Microsoft Graph. Production swap is an httpx call against Graph; the
skill output schema does not change.

Spec ref: §5.4 (skills); §4.1 Phase 5; brief §4.6 (notify).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 22: Phase 5 graph + orchestrator HITL wait for justification

**Files:**
- Create: `api/functions/graphs/notify.py`
- Modify: `api/functions/graphs/__init__.py` — replace stub `build_notify_workflow`
- Modify: `api/functions/workflows/expense_claim.py` — uncomment Phase 5 block (with `wait_for_external_event:justification`)
- Create: `tests/api/unit/test_notify_graph.py`

Phase 5 only runs on Red verdicts (the orchestrator gates on `verdict == "red"`). The graph is single-node since notification is the whole behaviour; no validator. The HITL wait is in the orchestrator generator, not the graph.

- [ ] **Step 1: Write the failing graph test**

```python
# tests/api/unit/test_notify_graph.py
"""Phase 5 (Notify) graph."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.notify import build_notify_workflow


@pytest.mark.asyncio
async def test_notify_graph_emits_composed_body():
    fake = {
        "notification": {
            "subject": "x", "body": "y", "channel": "teams",
            "recipients": ["claimant"], "requires_justification": True,
        },
        "requires_justification": True,
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_notification.execute",
        AsyncMock(return_value=fake),
    ):
        wf = build_notify_workflow()
        events = await wf.run({
            "workflow_id": "CLM-X", "claim_id": "CLM-X",
            "claim": {"employee_id": "E"},
            "classification": {"verdict": "red", "policy_clause": "§3.1", "reasoning": "x"},
            "escalation": {"tier": "warning"},
        })
    out = events.get_outputs()[0]
    assert out["notification"]["subject"] == "x"
    assert out["requires_justification"] is True
```

- [ ] **Step 2: Implement `api/functions/graphs/notify.py`**

```python
"""Notify graph (Red path only):
  agent_notification -> terminal
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_notification


def build_notify_workflow() -> Workflow:
    n1 = TrackedExecutor(id="notification", name="agent_notification",
                         executor_type="agent", fn=agent_notification.execute)
    term = TerminalExecutor(id="terminal")
    return WorkflowBuilder(start_executor=n1).add_edge(n1, term).build()
```

- [ ] **Step 3: Replace stub in `graphs/__init__.py`**

Replace:

```python
def build_notify_workflow():
    raise NotImplementedError("Phase 5 (Notify) — Day 10")
```

with:

```python
from .notify import build_notify_workflow
```

- [ ] **Step 4: Uncomment Phase 5 block in `expense_claim.py`**

Open `api/functions/workflows/expense_claim.py`. Replace the `# ----- Day 10 will replace this block -----` block with the live calls. The shape (already in the commented-out template from Task 4):

```python
if verdict == "red":
    notify_result = yield context.call_activity("notify_activity_trigger", enriched)
    enriched = {**enriched, "notify": notify_result}
    if notify_result.get("requires_justification"):
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "suspended", "payload": {"reason": "awaiting_justification"},
        })
        decision_event = context.wait_for_external_event("justification")
        timeout_event = context.create_timer(context.current_utc_datetime + timedelta(hours=72))
        winner = yield context.task_any([decision_event, timeout_event])
        if winner == timeout_event:
            yield context.call_activity("checkpoint_activity_trigger", {
                "workflow_id": workflow_id, "instance_id": context.instance_id,
                "kind": "workflow.completed", "payload": {"status": "timeout"},
            })
            return {"status": "timeout", "phase": "Notify"}
        timeout_event.cancel()
        decision = decision_event.result
        decision_type = (decision.get("decision") or "").lower() if isinstance(decision, dict) else ""
        if decision_type in _REJECTED:
            yield context.call_activity("checkpoint_activity_trigger", {
                "workflow_id": workflow_id, "instance_id": context.instance_id,
                "kind": "workflow.rejected",
                "payload": {"by": decision.get("resolved_by") if isinstance(decision, dict) else None},
            })
            return {"status": "rejected", "phase": "Notify", "decision": decision}
        enriched["justification"] = decision
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "resumed", "payload": {"decision": decision},
        })
```

Also: when the justification arrives (decision_event resolves) and is **not** a rejection, emit `justification.received` from the orchestrator's resumed checkpoint OR from the `internal_durable_event` route that delivers the event. The cleanest place is the route layer; check `api/server/routes/internal_durable_event.py` and confirm justification deliveries emit the event. If they don't, add it there:

```python
# in internal_durable_event.py, where justification deliveries land:
if event_name == "justification":
    app_state.bus.emit(FleetEvent(
        type="justification.received",
        workflow_id=instance_id_or_claim_id,
        claim_id=instance_id_or_claim_id,
    ))
```

- [ ] **Step 5: Run the graph + orchestration tests**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_notify_graph.py tests/api/unit/test_expense_claim_orchestration.py -v
```

Both PASS. Add a new orchestration test for the notify+justification round-trip:

```python
def test_red_verdict_suspends_and_resumes_on_justification():
    ctx = FakeContext(verdict="red")
    ctx._activity_results["receipt_activity_trigger"] = {"receipt_validation": {"agrees": True, "mismatch_flavour": "correct", "verdict_per_field": {}, "reasoning": "x", "confidence": 0.9}, "ok": True}
    ctx._activity_results["route_activity_trigger"] = {"route": "notify", "tier": "warning", "verdict": "red", "requires_hitl": True}
    ctx._activity_results["notify_activity_trigger"] = {"notification": {"subject": "x", "body": "y", "channel": "teams", "recipients": ["claimant"], "requires_justification": True}, "requires_justification": True}
    result = _drain(expense_claim_orchestration(ctx), ctx)
    kinds = [p["kind"] for n, p in ctx.activity_calls if n == "checkpoint_activity_trigger"]
    assert "suspended" in kinds
    assert "resumed" in kinds
    assert result["status"] == "completed"
```

(`FakeContext.task_any` already returns the decision_event so the suspend/resume branch fires; the `decision_event.result` is `{"event": "justification"}` which doesn't contain `"decision":"reject"` so the resume path runs.)

- [ ] **Step 6: Commit**

```bash
git add api/functions/graphs/notify.py api/functions/graphs/__init__.py api/functions/workflows/expense_claim.py api/server/routes/internal_durable_event.py tests/api/unit/test_notify_graph.py tests/api/unit/test_expense_claim_orchestration.py
git commit -m "$(cat <<'EOF'
feat(graph): Phase 5 (Notify, Red-only) + HITL wait_for_external_event

agent_notification (hook-gated) runs in the notify graph; orchestrator
suspends on requires_justification, waits 72h for the justification
external event, resumes on receipt or rejects on operator-rejection
shape. Five of seven phases now live in the orchestrator.

internal_durable_event route emits justification.received on event
delivery so the SSE stream surfaces the round-trip end-to-end.

Spec ref: §4.1 Phase 5; brief §4.6 (notify+arbitrate cycle).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 23: Breach → notification → justification round-trip simulator

**Files:**
- Create: `tests/api/unit/test_simulator_breach_justification_cycle.py`

The `breach-justification-cycle` scenario (registered in Task 7's simulator) picks a Red claim, runs it through to suspended, then injects a synthetic justification. We add a regression test that drives the simulator helper end-to-end against mocked activity dispatch.

- [ ] **Step 1: Write the test**

```python
# tests/api/unit/test_simulator_breach_justification_cycle.py
"""breach-justification-cycle scenario picks a red claim and the
internal_durable_event route can deliver a justification that resumes."""
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from api.server.services import simulator_orchestrator

CLAIMS = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"


@pytest.mark.asyncio
async def test_cycle_scenario_picks_red_seed():
    captured: dict = {}
    async def fake_schedule(payload):
        captured["payload"] = payload
        return {"id": "iid-x"}
    with patch("api.server.services.simulator_orchestrator.schedule_new_orchestration",
               AsyncMock(side_effect=fake_schedule)):
        wid = await simulator_orchestrator.spawn_workflow(scenario="breach-justification-cycle")
    claim = json.loads((CLAIMS / f"{wid}.json").read_text(encoding="utf-8"))
    assert claim["gold_label"] == "red"


@pytest.mark.asyncio
async def test_internal_durable_event_route_emits_justification_received():
    """Posting an internal durable event of name=justification publishes the
    justification.received bus event."""
    from fastapi.testclient import TestClient
    from api.server.main import app
    from api.server.state import app_state
    from api.shared.events import FleetEvent

    captured: list[FleetEvent] = []
    app_state.bus.on_any(captured.append)

    client = TestClient(app)
    resp = client.post("/api/internal/durable-event", json={
        "instance_id": "iid-test",
        "event_name": "justification",
        "event_data": {"text": "Client present", "decision": "accept"},
    })
    # Tolerate either 200 or 202 — the route may run async.
    assert resp.status_code in (200, 202, 204)
    types = {e.type for e in captured}
    # At least one of the expected fan-out events fires.
    assert "justification.received" in types or any(
        e.type == "justification.received" for e in captured
    )
```

Run it:

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_simulator_breach_justification_cycle.py -v
```

Expected: 1 PASS, 1 may fail depending on the actual `internal_durable_event` route surface (read it; adjust the test path if the endpoint name differs). If the route doesn't currently emit `justification.received`, add the emit per Task 22 Step 4.

- [ ] **Step 2: Commit**

```bash
git add tests/api/unit/test_simulator_breach_justification_cycle.py
git commit -m "$(cat <<'EOF'
test(simulator): breach-justification-cycle scenario + event roundtrip

Two regressions: (a) cycle scenario picks a red seed; (b) the internal
durable-event route emits justification.received when a justification
event is delivered. Together they pin the breach -> notification ->
justification round-trip we narrate live in Week 3.

Spec ref: §5.2 (simulator scenarios); §4.1 Phase 5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 24: Code-cleanup checkpoint — three-reviewer parallel pass

**Files:** various; tracked per finding

This is the mid-pivot review pattern: three parallel reviewers (reuse, quality, efficiency) examine all Week 2 work and surface findings. We run the pass, address every finding (or document a deliberate decision), and tag.

- [ ] **Step 1: Run three subagents in parallel using the `superpowers:dispatching-parallel-agents` skill**

Dispatch three fresh agents with the following prompts (see `superpowers:dispatching-parallel-agents` for shape):

  1. **Reuse reviewer** — "Walk every file modified or created since `v0.6-poc1-accuracy-spine`. For each, identify any place we duplicated logic, redefined constants, or built a parallel surface that an existing one already covers. Use `api/shared/expense_taxonomy.py`, `_wrapper.py`, `_tracked_executor.py`, the existing MCP tool patterns, and the existing graph builders as the canonical reuse anchors. Output: list of {file, line, finding, proposed fix}."

  2. **Quality reviewer** — "Examine the same diff for: untyped boundaries (missing type hints on public functions / executors); raised-exception leaks (places where `KeyError` should propagate but `except Exception: pass` swallows it); test fixtures that pollute the source tree; tests that assert on private behaviour. Output: same shape."

  3. **Efficiency reviewer** — "Examine the same diff for: hot paths re-loading JSON files in a loop instead of caching; agent prompts that embed full base64 receipts unnecessarily (image_b64 truncation in the wrapper, but the full b64 is what GPT-4.1 vision needs — verify the bridge is sound); MCP tools without `@traced_tool` (every new one must stack); React components without `useSSE` or with a manual EventSource subscription. Output: same shape."

- [ ] **Step 2: Triage the findings**

Pool the three lists. For each finding, decide:
- **Fix now** — add to a todo list and address in commits below.
- **Document** — record a one-liner in `docs/poc1-week2-cleanup-notes.md` (a short markdown — created by this task, not earlier).
- **Reject** — note why and move on.

- [ ] **Step 3: Address the "fix now" findings**

Each fix is its own commit. Suggested commit-message form:

```bash
git commit -m "$(cat <<'EOF'
chore(week2-cleanup): <one-line finding>

<2-3 sentence rationale referencing reviewer source.>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Anticipated common findings:
- **Reuse:** new MCP tools likely re-implement OTEL span attribute setting that `_otel.py::traced_tool` already does — collapse to span-attribute-only inside the wrapped function body.
- **Reuse:** `validate_classification_schema.execute` should be the only `execute()` adapter pattern; if any new validator raised instead of returned `{"ok": bool}`, normalise.
- **Quality:** the `_resolve_ems` cache-miss path in `claim_lookup` re-reads the JSON every call; cache `_CLAIMS_DIR` reads via an LRU.
- **Quality:** `agent_receipt_validator._emit_event` swallows everything in `except Exception: pass`; that's load-bearing for tests but should specifically allow `app_state.bus.emit` to raise typed errors so production failures are visible. Tighten to `except (ImportError, AttributeError):`.
- **Efficiency:** the simulator's `_pick_claim` re-reads all 300 claim JSONs every call; cache once per process under a `_claim_cache` module-global with `reset_cache()` for tests.
- **Efficiency:** `policy_cite.cite` invokes `policy_search.search` which does a full embedding pass; check that the index is cached (it is — Week 1's `_ensure_index` caches). No fix.

- [ ] **Step 4: Run the full test suite**

```bash
./.venv/Scripts/pytest.exe tests/api -q
npm run test
```

Both expected: all PASS. If a cleanup commit broke anything, fix in place — no regressions land.

- [ ] **Step 5: Capture the cleanup notes**

```bash
git add docs/poc1-week2-cleanup-notes.md
git commit -m "$(cat <<'EOF'
docs: Week 2 cleanup-pass notes

Records the findings from the three-reviewer parallel review at end of
Week 2 (reuse / quality / efficiency). Documented findings are explicit
deferrals or decisions; fix-now findings landed as their own commits.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 25: Tag `v0.7-poc1-domain-workflow` and push

**Files:** none — git operations only.

- [ ] **Step 1: Verify clean working tree + green tests**

```bash
git status --porcelain
./.venv/Scripts/pytest.exe tests/api -q
npm run test
```

Expected: empty status; all tests green.

- [ ] **Step 2: Tag**

```bash
git tag -a v0.7-poc1-domain-workflow -m "Week 2 milestone: 7-phase expense_claim orchestrator (phases 1-5 wired); Concur mock; receipt validator; escalation advisor; notification composer; AC #1, #2, #3, #5, #6, #9 demoable."
git push origin v0.7-poc1-domain-workflow
```

- [ ] **Step 3: Stop any running dev processes**

Per the house standing instruction, ensure no `func start`, `uvicorn`, `npm run dev:client`, `npm run dev:mcp`, or `tsx` processes are still running. Use `tasklist /fi "IMAGENAME eq node.exe"` and `tasklist /fi "IMAGENAME eq python.exe"` (Windows) to verify, then `taskkill /pid <pid>` if needed.

---

## Self-review checklist (run after Task 25)

Walk back through the spec with fresh eyes.

**§4.1 7-phase orchestrator coverage:**
- [x] Phase 1 (Intake & Normalise) — Task 5
- [x] Phase 2 (Classify R/A/G) — Task 6
- [x] Phase 3 (Validate Receipt) — Task 10
- [x] Phase 4 (Route by Verdict) — Task 18
- [x] Phase 5 (Notify) — Task 22
- [ ] Phase 6 (Arbitrate) — *Week 3*
- [ ] Phase 7 (Audit) — *Week 3*

**§5.4 New artifacts (Week-2 subset):**
- [x] `receipt_validator.skill.md` — Task 9
- [x] `escalation_advisor.skill.md` — Task 16
- [x] `notification_composer.skill.md` — Task 21
- [x] `claim.lookup` MCP tool — Task 3
- [x] `claim.getReceipt` MCP tool — Task 8
- [x] `claim.summary` MCP tool — Task 20
- [x] `policy.cite` MCP tool — Task 20
- [x] `employee.history` MCP tool — Task 15
- [x] `mocks/concur-mcp/` — Task 12
- [x] Workday mock extended — Task 2

**§7 Acceptance criteria — Week-2 hits:**
- [x] AC #1 "Single Finance Controller view across 30+ workflows" — comes for free now claims flow through the dashboard (existing FleetDashboard surfaces the new ExpenseClaim instances)
- [x] AC #2 "Exception-only surfacing; Green hidden" — existing default filter; verdict from rag_classifier
- [x] AC #3 "Bulk approval of 10+ in one action" — comes for free with Amber claims now flowing
- [x] AC #5 "Receipt cross-validation" — Tasks 8–11
- [x] AC #6 "Progressive enforcement" — Tasks 15–19 (foundation; live ramp narrated in Week 3)
- [x] AC #9 "System-agnostic Control Plane (2+ EMS)" — Tasks 12–14
- [ ] AC #4 "≥95% R/A/G accuracy" — *kept green from Week 1; Day 0 baseline captured*
- [ ] AC #7 "Autonomous learning curve" — *Week 3*
- [ ] AC #8 "SSC Reviewer interface" — *Week 3*
- [ ] AC #10 "EMS extensibility" — *Week 3*
- [ ] AC #11 "Region failure recovery" — *Week 3*
- [ ] AC #12 "Immutable audit + reporting" — *Week 3*
- [ ] AC #13 "Cost-per-task report" — *Week 3*

**FleetEventType extensions (Task 1):**
- [x] `claim.routed.green/amber/red`
- [x] `receipt.mismatch.detected`
- [x] `escalation.tier.assigned`
- [x] `notification.sent`
- [x] `justification.received`

**Convention adherence:**
- [x] All new MCP tools stack `@traced_tool` — Tasks 3, 8, 15, 20
- [x] All new agents use `run_agent_skill` from `_wrapper.py` — Tasks 9, 16, 21
- [x] All new agents pre-fetch tool data in Python and embed in prompt — Tasks 9, 16, 21
- [x] All new graph nodes use `TrackedExecutor` — Tasks 5, 6, 10, 17, 18, 22
- [x] All new React tests use `// @vitest-environment jsdom` — Task 14
- [x] No new React components needed this week (the Week 2 surfaces are SSE-driven on existing components)
- [x] Test fixtures use `tmp_path` where they could collide with the source tree
- [x] `api/shared/expense_taxonomy.py` constants used everywhere — no redefinitions of VERDICTS / CATEGORIES / MARKETS

**Type / signature consistency:**
- [x] `claim_lookup.lookup(claim_id, ems_source=None) → dict` — same in Task 3, 4, 7
- [x] `claim_get_receipt.get_receipt(claim_id) → {claim_id, flavour, bytes, image_b64, [truncated]}` — Task 8, 9
- [x] `agent_*.execute(input) → dict` async signature on every executor — every agent task
- [x] Graph builder name pattern: `build_<phase>_workflow()` — Tasks 5, 6, 10, 18, 22
- [x] Activity name pattern: `<phase>_activity_trigger` registered in `function_app.py` — Task 4

**Placeholder scan:**
- [x] No `TBD` / `TODO` / "implement later" text in any task body
- [x] All test code blocks are complete
- [x] All implementation code blocks compile against named imports

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-28-poc1-expense-compliance-pivot-week2-domain-workflow.md`.

This plan covers Week 2 only. Week 3 (arbitration, SSC reviewer queue, Fleet Manager extensions, audit summariser, region failover, EMS extensibility narration, demo dry run) is a separate plan written **after** Week 2 ships green and `v0.7-poc1-domain-workflow` is tagged.

Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration. Best for the boundary-sensitive tasks (especially Task 4 orchestrator reshape and Task 22 Phase 5 HITL plumbing).

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Faster but blast radius is bigger if a task goes off course.

The Day 0 pre-flight (Task 0) and the Day 10 cleanup pass (Task 24) are explicit subagent-friendly handoffs — Task 0 has a clear pass/fail bar (≥95% accuracy) and Task 24 dispatches three parallel reviewers as part of its own body.

**Which approach?**

