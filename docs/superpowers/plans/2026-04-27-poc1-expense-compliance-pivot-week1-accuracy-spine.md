# POC1 Expense Compliance Pivot — Week 1: Accuracy Spine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the 40%-weight accuracy story end-to-end — synthetic T&E policy + 300 labelled claims + 300 receipts + RAG classifier skill + parallel-fan-out accuracy harness MAF Workflow + AccuracyReport UI panel — and demonstrate ≥95% R/A/G classification on the synthetic set with policy-driven (not hard-coded) reasoning.

**Architecture:** Skills-first. The classifier behaviour lives in `rag_classifier.skill.md` grounded on `policy.md` via the `policy.search` MCP tool. The accuracy harness is a MAF Pregel graph (`claim_splitter → [N × rag_classifier_executor] → confusion_matrix_aggregator`) streaming progress over the existing event bus → SSE → React panel. Live policy edits change classifier behaviour with zero code change — the literal acceptance #4 demonstration.

**Tech Stack:** Python 3.11 (FastAPI + Azure Durable Functions + Microsoft Agent Framework Pregel graphs + GHCP SDK), Pillow (PIL) for receipt PNGs, sentence-transformers + FAISS in-memory for `policy.search`, React + Vite + TypeScript + Vitest for UI, pytest + pytest-asyncio for backend tests.

**Reference docs (read before starting):**
- Spec: [docs/superpowers/specs/2026-04-27-poc1-expense-compliance-pivot-design.md](../specs/2026-04-27-poc1-expense-compliance-pivot-design.md)
- Inventory grading: [docs/poc1-inventory.md](../../poc1-inventory.md) — defines what's R / A / D
- Brief: [docs/poc1-brief.md](../../poc1-brief.md) — §4.5 (accuracy = 40%), §7 acceptance criteria

**Out of scope for this plan (covered in later plans):**
- Orchestrator reshape to 7 phases (Week 2)
- Concur mock, receipt validator, escalation, notification (Week 2)
- Reviewer queue, arbitration, Fleet Manager extensions, audit summariser, region failover (Week 3)

**Definition of done for Week 1:** Run `pytest tests/api -q` green; run the harness end-to-end on 300 claims via the AccuracyReport panel; confusion matrix renders; overall accuracy ≥95%; edit `policy.md` meal threshold from $75 to $50, re-run, observe accuracy shift on meal-category claims with no code change. Tag the result `v0.6-poc1-accuracy-spine` for the Week 2 entry point.

---

## File Structure

**Created:**
- `data/synthetic/__init__.py`
- `data/synthetic/policy.md` — hand-written T&E policy markdown (4 markets × 5 categories)
- `data/synthetic/employees.json` — ~30 employee records, ≥3 with seeded breach histories
- `data/synthetic/precedents.json` — ~50 historical SSC reviewer decisions (seeds Week 3 behaviour-change loop; written here while we're in this directory)
- `data/synthetic/generate.py` — deterministic claim generator producing `claims/*.json` and `labels.csv`
- `data/synthetic/receipt_generator.py` — PIL-templated PNG receipt generator producing `receipts/*.png`
- `data/synthetic/claims/` — emitted, committed
- `data/synthetic/receipts/` — emitted, committed
- `data/synthetic/labels.csv` — emitted, committed
- `api/server/mcp_tools/policy_search.py` — in-memory chunked retriever over policy.md
- `api/server/mcp_tools/claim_get_structured.py` — read claim JSON by id
- `api/server/skills/rag_classifier.skill.md` — R/A/G verdict + policy clause + confidence + competing_interpretations
- `api/functions/graphs/executors/agents/agent_rag_classifier.py` — wraps the skill via `_wrapper.run_agent_skill`
- `api/functions/graphs/executors/validators/validate_classification_schema.py` — schema guardrail
- `api/functions/workflows/accuracy_harness_workflow.py` — MAF Pregel graph: splitter → fan-out → aggregator
- `api/server/routes/accuracy.py` — POST /api/accuracy/run, GET /api/accuracy/last
- `web/client/components/AccuracyReport.tsx` — confusion matrix + drill-down + run button
- `tests/api/unit/test_synthetic_generate.py`
- `tests/api/unit/test_receipt_generator.py`
- `tests/api/unit/test_policy_search.py`
- `tests/api/unit/test_claim_get_structured.py`
- `tests/api/unit/test_validate_classification_schema.py`
- `tests/api/unit/test_accuracy_harness_workflow.py`
- `tests/api/unit/test_accuracy_route.py`
- `tests/web/AccuracyReport.test.tsx`

**Modified:**
- `web/client/routes/Evaluations.tsx` — mount AccuracyReport panel
- `api/server/main.py` — register the `accuracy` router
- `tests/api/unit/test_invoice_p2p_rejection.py` — delete or rename (invoice-only); decision in Task 2

**Deleted (Day 1 cleanup — D-grade per [poc1-inventory.md](../../poc1-inventory.md)):**
- `mocks/d365-mcp/`, `mocks/payment-mcp/`
- `api/functions/graphs/validation.py`, `payment.py`, `reconciliation.py`
- `api/functions/graphs/executors/deterministic/three_way_match.py`, `generate_payment_file.py`, `submit_payment.py`, `bank_statement_match.py`, `lookup_active_gls.py`, `lookup_cost_centre_policy.py`, `lookup_vendor_context.py`
- `api/functions/graphs/executors/agents/agent_invoice_classifier.py`, `agent_gl_coder.py`, `agent_cost_centre_assigner.py`
- `api/functions/graphs/executors/validators/validate_gl_active.py`
- `api/server/skills/gl_coder.skill.md`, `cost_centre_assigner.skill.md`, `invoice_classifier.skill.md`
- Imports/registrations referencing the above (chase compile errors)

**Reused untouched:**
- `api/functions/graphs/_common.py`, `_tracked_executor.py`
- `api/functions/graphs/executors/agents/_wrapper.py` (the `run_agent_skill` loader)
- `api/server/services/event_bus.py`, `sse_hub.py`, `state_store.py`
- `api/server/routes/evals.py`, `stream.py`
- `web/client/routes/Evaluations.tsx` shell (we add the panel inside)

---

## Conventions and house style

- **Single agent identity:** every agent executor calls `run_agent_skill(skill_name, prompt)` from `api/functions/graphs/executors/agents/_wrapper.py`. Don't open new GHCP sessions inline.
- **TrackedExecutor pattern:** new executors that drive workflow phases inherit from `TrackedExecutor` in `_tracked_executor.py` and emit step events. Pure unit-callable functions (used by the harness via direct call rather than as graph nodes) can stay as plain async functions.
- **MCP tool style:** match the existing tools in `api/server/mcp_tools/` — small Python module exporting a function, OTEL span via `_otel.py`. Read one of the existing tools (e.g. `query_fleet.py`) before authoring a new one.
- **Validator-as-guardrail edge:** validators raise on bad data; they don't quietly fix. The orchestrator catches and emits a `validator.blocked` event.
- **JSON output from agents:** `_wrapper.run_agent_skill` already extracts the first JSON object/array from the response and returns a parsed dict. Do not add second-pass extraction.
- **Determinism:** every generator uses `random.Random(seed)` (seed = 20260427), never `random` module-level, so reruns are bit-stable and tests can assert exact counts.
- **Test runner:** `pytest tests/api -q` — pytest is configured in `pyproject.toml` with `testpaths = ["tests/api"]`. UI tests run via `npx vitest run`.

---

## Task 1: Tag invoice POC and create branch hygiene

**Files:** none modified — git operations only.

- [ ] **Step 1: Verify clean working tree before tagging**

Run: `git status --porcelain`
Expected: empty output, OR only the tracked spec/plan markdown files we just authored under `docs/superpowers/`.

If there is uncommitted work that is not the spec/plan, stop and ask the user. We tag a known-good `main`.

- [ ] **Step 2: Create the historical tag**

```bash
git tag -a v0.5-invoice-poc -m "Snapshot of invoice P2P implementation before expense-compliance pivot"
git push origin v0.5-invoice-poc
```

Expected: `* [new tag] v0.5-invoice-poc -> v0.5-invoice-poc` from `git push`.

- [ ] **Step 3: Verify tag exists**

Run: `git tag -l v0.5-invoice-poc`
Expected: prints `v0.5-invoice-poc`.

- [ ] **Step 4: Commit (no code change — tag-only task; nothing to commit). Skip commit step.**

---

## Task 2: Delete invoice-only code (D-grade items)

**Files:**
- Delete: `mocks/d365-mcp/`, `mocks/payment-mcp/`
- Delete: `api/functions/graphs/validation.py`, `payment.py`, `reconciliation.py`
- Delete: `api/functions/graphs/executors/deterministic/{three_way_match,generate_payment_file,submit_payment,bank_statement_match,lookup_active_gls,lookup_cost_centre_policy,lookup_vendor_context}.py`
- Delete: `api/functions/graphs/executors/agents/{agent_invoice_classifier,agent_gl_coder,agent_cost_centre_assigner}.py`
- Delete: `api/functions/graphs/executors/validators/validate_gl_active.py`
- Delete: `api/server/skills/{gl_coder,cost_centre_assigner,invoice_classifier}.skill.md`
- Modify: any `__init__.py` that re-exports the above
- Modify: `api/functions/workflows/invoice_p2p.py` — comment out or delete the imports of the deleted phase graphs (the file itself stays for now; reshaping happens in Week 2). Replace the deleted phase calls with a placeholder `raise NotImplementedError("expense pivot — see Week 2 plan")` so the orchestrator can still be parsed but won't accidentally run.
- Delete or rename: `tests/api/unit/test_invoice_p2p_rejection.py` — keep it but skip with `pytest.skip("invoice phases removed; revisit in Week 2", allow_module_level=True)` at the top so it doesn't block the test run.

- [ ] **Step 1: Establish failing baseline — run full test suite, expect failures only from removed-import side effects (don't delete yet)**

Run: `pytest tests/api -q --co -q 2>&1 | tail -20`
Expected: collection succeeds (we haven't deleted anything yet). Note any tests that import the soon-to-delete modules.

- [ ] **Step 2: Delete the D-grade source files and directories**

```bash
rm -rf "mocks/d365-mcp" "mocks/payment-mcp"
rm "api/functions/graphs/validation.py" "api/functions/graphs/payment.py" "api/functions/graphs/reconciliation.py"
rm "api/functions/graphs/executors/deterministic/three_way_match.py"
rm "api/functions/graphs/executors/deterministic/generate_payment_file.py"
rm "api/functions/graphs/executors/deterministic/submit_payment.py"
rm "api/functions/graphs/executors/deterministic/bank_statement_match.py"
rm "api/functions/graphs/executors/deterministic/lookup_active_gls.py"
rm "api/functions/graphs/executors/deterministic/lookup_cost_centre_policy.py"
rm "api/functions/graphs/executors/deterministic/lookup_vendor_context.py"
rm "api/functions/graphs/executors/agents/agent_invoice_classifier.py"
rm "api/functions/graphs/executors/agents/agent_gl_coder.py"
rm "api/functions/graphs/executors/agents/agent_cost_centre_assigner.py"
rm "api/functions/graphs/executors/validators/validate_gl_active.py"
rm "api/server/skills/gl_coder.skill.md"
rm "api/server/skills/cost_centre_assigner.skill.md"
rm "api/server/skills/invoice_classifier.skill.md"
```

- [ ] **Step 3: Chase import errors**

Run: `python -c "import api.functions.graphs"` and `python -c "import api.functions.workflows.invoice_p2p"` (each as a separate command).

For each `ImportError`, open the offending file and either delete the import or replace it with `# removed in expense pivot — see plan Task 2`. Common spots:
- `api/functions/graphs/__init__.py` (re-exports)
- `api/functions/graphs/executors/deterministic/__init__.py`
- `api/functions/graphs/executors/agents/__init__.py`
- `api/functions/graphs/executors/validators/__init__.py`
- `api/functions/workflows/invoice_p2p.py` (calls into deleted phase graphs — replace each call with `raise NotImplementedError("expense pivot — Week 2")`)
- `api/functions/workflows/activities.py` (activity registrations of deleted phases — comment out)

Repeat until imports succeed.

- [ ] **Step 4: Skip the orchestrator-rejection test until Week 2**

Open `tests/api/unit/test_invoice_p2p_rejection.py` and prepend at the top of the file (after any docstring, before imports of the now-broken module):

```python
import pytest
pytest.skip("Invoice phases removed in expense pivot; revisit in Week 2 orchestrator reshape.", allow_module_level=True)
```

- [ ] **Step 5: Run the test suite — expect green**

Run: `pytest tests/api -q`
Expected: all remaining tests pass; `test_invoice_p2p_rejection.py` is reported as skipped.

If a different test fails because of a stale import that wasn't caught in Step 3, fix it in the same way (delete the import or skip the test with a clear reason).

- [ ] **Step 6: Verify the FastAPI app and Functions host still import**

Run (each separately): `python -c "from api.server.main import app; print('ok')"` and `python -c "import function_app; print('ok')"`.
Expected: both print `ok`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore(pivot): delete invoice-only code (D-grade per inventory)

Removes three-way match, GL coding, cost-centre assignment, payment
file generation, bank reconciliation, D365 mock, payment-mcp mock,
and the three invoice-only skills. Invoice orchestrator and the
rejection test are stubbed/skipped pending Week 2 reshape.

Pivot reference: docs/superpowers/specs/2026-04-27-poc1-expense-compliance-pivot-design.md §5.1"
```

---

## Task 3: Hand-write the synthetic T&E policy

**Files:**
- Create: `data/synthetic/__init__.py` (empty)
- Create: `data/synthetic/policy.md`

This task is content authoring, not TDD-able. The policy is the single source of truth that grounds *both* the classifier and the gold labels — its richness determines whether ≥95% accuracy is meaningful or trivial.

- [ ] **Step 1: Create the data directory**

```bash
mkdir -p "data/synthetic/claims" "data/synthetic/receipts"
touch "data/synthetic/__init__.py"
```

- [ ] **Step 2: Write `data/synthetic/policy.md`**

Required structure (the generator and classifier both rely on this):

```markdown
# WPP Group T&E Policy (Synthetic — POC1)

> Effective 2026-04-01. Applies to all WPP agencies and markets unless market-specific overrides apply. This is the single authoritative source for R/A/G classification of expense claims.

## 1. Scope

Covers meals, travel, accommodation, entertainment, and miscellaneous business expenses incurred by WPP employees in the course of client work or internal operations across the UK, US, DE, and IN markets.

## 2. Markets and currencies

| Market | Currency | Tax treatment | Receipt threshold |
|---|---|---|---|
| UK | GBP | VAT receipts required ≥£25 | £25 |
| US | USD | Receipts required ≥$25 | $25 |
| DE | EUR | VAT receipts required for all amounts | €0 |
| IN | INR | GST receipts required ≥₹500 | ₹500 |

## 3. Categories and per-market R/A/G rules

### 3.1 Meals

| Market | Solo cap | Per-attendee cap | Alcohol | After-hours |
|---|---|---|---|---|
| UK | £40 | £75 | Permitted at client dinner only | Permitted |
| US | $50 | $75 | Permitted at client dinner only | Permitted |
| DE | €45 | €70 | Prohibited on entertainment | Permitted |
| IN | ₹2,500 | ₹4,000 | Prohibited | Permitted |

**Green (auto-approve):** within solo cap, with receipt, attendees ≤1, no alcohol; or within per-attendee cap with receipt and named attendees ≥2.
**Amber (review):** within 110% of cap with receipt; or attendees > per-attendee count claimed; or alcohol present at non-client meal in UK/US; or weekend/public-holiday meal without business reason annotated.
**Red (breach):** above 110% of cap; alcohol where prohibited; missing receipt above receipt-threshold; group meal with no attendee names.

### 3.2 Travel

[same shape — air/rail/taxi/personal-vehicle, market-specific caps, R/A/G triggers]

### 3.3 Accommodation

[same — per-night caps, weekend stay rules, market-overrides]

### 3.4 Entertainment

[same — client-only, alcohol rules, per-head caps]

### 3.5 Miscellaneous

[same — stationery, software subscriptions, conference fees]

## 4. Receipt and documentation requirements

- Below market receipt threshold: a self-attested line is sufficient (Green eligible).
- At or above threshold: itemised receipt required. Missing receipt = Red unless auto-reclaim applies (§5).
- Receipt must show: vendor name, date, amount, currency, line items if itemised meal/entertainment.

## 5. Auto-reclaim (cash, no receipt)

Cash transactions below the market receipt threshold qualify for auto-reclaim with a self-attested line: amount, date, vendor, business reason. Above threshold and missing receipt = Red.

## 6. Repeat-offender progressive enforcement

[for Week 3 escalation_advisor — define warning / escalation / major-violation tiers as a function of prior breach count and category]

## 7. Examples (illustrative — not authoritative)

[3-5 worked examples per category — these become regression test cases]
```

Fill in the bracketed sections with concrete numbers and rule prose. Aim for 8-12 pages when rendered. Make boundary thresholds (e.g. "within 110% of cap") explicit so the generator can synthesise genuinely-Amber claims rather than blurry ones.

- [ ] **Step 3: Verify the policy renders cleanly**

Run: `wc -l "data/synthetic/policy.md"`
Expected: at least 200 lines.

- [ ] **Step 4: Commit**

```bash
git add data/synthetic/__init__.py data/synthetic/policy.md
git commit -m "feat(data): synthetic T&E policy markdown (4 markets x 5 categories)

8-12 page hand-written policy with explicit R/A/G thresholds at
110% boundary so the generator can synthesise genuinely ambiguous
Amber claims. Single source of truth for classifier grounding and
gold-label generation.

Spec ref: §5.4 'Synthetic data'."
```

---

## Task 4: Employee and precedent fixtures

**Files:**
- Create: `data/synthetic/employees.json`
- Create: `data/synthetic/precedents.json`
- Create: `tests/api/unit/test_synthetic_fixtures.py`

These fixtures are static JSON — schema-driven rather than algorithmically generated. The test enforces shape invariants the rest of Week 1 + Week 2 code will rely on.

- [ ] **Step 1: Write the failing schema test**

Create `tests/api/unit/test_synthetic_fixtures.py`:

```python
"""Shape and invariant tests for the static synthetic fixtures."""
from __future__ import annotations
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "data" / "synthetic"


def test_employees_json_shape():
    employees = json.loads((DATA / "employees.json").read_text(encoding="utf-8"))
    assert isinstance(employees, list)
    assert len(employees) >= 25, "need a small population (≥25)"
    repeat_offenders = [e for e in employees if e.get("breach_history") and len(e["breach_history"]) >= 2]
    assert len(repeat_offenders) >= 3, "spec §5.4 requires ≥3 repeat-offender profiles"
    for e in employees:
        assert {"id", "name", "market", "department", "agency", "breach_history"} <= set(e), f"missing keys on {e.get('id')!r}"
        assert e["market"] in {"UK", "US", "DE", "IN"}, e["market"]
        for b in e["breach_history"]:
            assert {"date", "category", "tier"} <= set(b), b


def test_precedents_json_shape():
    precedents = json.loads((DATA / "precedents.json").read_text(encoding="utf-8"))
    assert isinstance(precedents, list)
    assert len(precedents) >= 50, "spec §5.4 requires ~50 historical decisions"
    for p in precedents:
        assert {"id", "claim_summary", "policy_clause", "reviewer_decision", "rationale", "decided_at"} <= set(p), p
        assert p["reviewer_decision"] in {"accept-justification", "require-repayment", "issue-warning", "escalate"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/api/unit/test_synthetic_fixtures.py -v`
Expected: FAIL with `FileNotFoundError` on `employees.json`.

- [ ] **Step 3: Write `data/synthetic/employees.json`**

Hand-author ~30 employees spread across UK/US/DE/IN, varied agencies (e.g. Mindshare, Wavemaker, Ogilvy, VML, GroupM Central) and departments (Account, Creative, Strategy, Production). At least 3 must have ≥2 prior breaches in `breach_history` with diverse categories and tiers (`warning`, `escalation`, `major-violation`).

Schema per record:
```json
{"id": "EMP-0001", "name": "Aisha Khan", "market": "UK", "department": "Account", "agency": "Mindshare",
 "breach_history": [{"date": "2026-02-14", "category": "meals", "tier": "warning"}]}
```

- [ ] **Step 4: Write `data/synthetic/precedents.json`**

Hand-author or script ≥50 historical SSC reviewer decisions referencing real policy clauses from `policy.md`. Schema per record:
```json
{"id": "PREC-0001",
 "claim_summary": "London client dinner, 4 attendees, £312 total, alcohol present",
 "policy_clause": "§3.1 Meals — UK per-attendee cap £75",
 "reviewer_decision": "accept-justification",
 "rationale": "Client present, named senior stakeholder, within 110% per-head cap",
 "decided_at": "2026-03-08"}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/api/unit/test_synthetic_fixtures.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add data/synthetic/employees.json data/synthetic/precedents.json tests/api/unit/test_synthetic_fixtures.py
git commit -m "feat(data): synthetic employees + precedents fixtures with shape tests

30 employees across UK/US/DE/IN with 3+ repeat-offender profiles seeded.
50 historical SSC reviewer decisions for the Week 3 behaviour-change loop
and precedents.search MCP tool. Shape invariants enforced in tests."
```

---

## Task 5: Synthetic claim generator (deterministic, 300 claims)

**Files:**
- Create: `data/synthetic/generate.py`
- Create: `tests/api/unit/test_synthetic_generate.py`

The generator walks the policy and emits 300 labelled claims with deterministic seeding. Distribution target: ~70% Green / ~20% Amber / ~10% Red. Each claim carries the *literal policy clause text* that triggered its label as `gold_reasoning` — so when the classifier later cites a clause, accuracy is measured against text matching, not rule-code matching.

- [ ] **Step 1: Write the failing test**

Create `tests/api/unit/test_synthetic_generate.py`:

```python
"""Determinism and distribution tests for the claim generator."""
from __future__ import annotations
import csv
import json
import shutil
from pathlib import Path

import pytest

from data.synthetic import generate

DATA = Path(generate.__file__).parent
CLAIMS = DATA / "claims"
LABELS = DATA / "labels.csv"


@pytest.fixture(autouse=True)
def _clean_outputs():
    if CLAIMS.exists():
        shutil.rmtree(CLAIMS)
    if LABELS.exists():
        LABELS.unlink()
    yield


def test_generates_300_claims():
    generate.run(seed=20260427, count=300)
    claim_files = sorted(CLAIMS.glob("CLM-*.json"))
    assert len(claim_files) == 300


def test_distribution_within_5pct_of_target():
    generate.run(seed=20260427, count=300)
    rows = list(csv.DictReader(LABELS.open(encoding="utf-8")))
    assert len(rows) == 300
    counts = {"green": 0, "amber": 0, "red": 0}
    for r in rows:
        counts[r["gold_label"]] += 1
    # Target 70/20/10 ± 5pp absolute (i.e. ≥65% green, 15-25% amber, 5-15% red).
    assert 195 <= counts["green"] <= 225, counts
    assert 45 <= counts["amber"] <= 75, counts
    assert 15 <= counts["red"] <= 45, counts


def test_deterministic_seed():
    generate.run(seed=20260427, count=300)
    first = sorted(CLAIMS.glob("CLM-*.json"))
    first_payloads = [p.read_text(encoding="utf-8") for p in first]
    shutil.rmtree(CLAIMS)
    LABELS.unlink()
    generate.run(seed=20260427, count=300)
    second = sorted(CLAIMS.glob("CLM-*.json"))
    second_payloads = [p.read_text(encoding="utf-8") for p in second]
    assert first_payloads == second_payloads


def test_claim_schema():
    generate.run(seed=20260427, count=300)
    sample = json.loads(next(CLAIMS.glob("CLM-*.json")).read_text(encoding="utf-8"))
    required = {"claim_id", "employee_id", "submitted_at", "market", "currency", "category",
                "vendor", "amount", "attendees", "receipt_filename", "ems_source",
                "gold_label", "gold_reasoning", "gold_policy_clause"}
    assert required <= set(sample), sorted(required - set(sample))
    assert sample["gold_label"] in {"green", "amber", "red"}
    assert sample["ems_source"] in {"workday", "concur"}
    # Gold reasoning is literal policy text, not code-style rule expression.
    assert "§" in sample["gold_policy_clause"]


def test_categories_distributed():
    generate.run(seed=20260427, count=300)
    rows = list(csv.DictReader(LABELS.open(encoding="utf-8")))
    cats = {r["category"] for r in rows}
    assert {"meals", "travel", "accommodation", "entertainment", "miscellaneous"} <= cats


def test_markets_distributed():
    generate.run(seed=20260427, count=300)
    rows = list(csv.DictReader(LABELS.open(encoding="utf-8")))
    markets = {r["market"] for r in rows}
    assert {"UK", "US", "DE", "IN"} <= markets
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/api/unit/test_synthetic_generate.py -v`
Expected: FAIL with `ImportError: cannot import name 'generate'`.

- [ ] **Step 3: Implement `data/synthetic/generate.py`**

```python
"""Deterministic synthetic expense claim generator.

Walks the synthetic T&E policy and emits 300 labelled claims with literal
policy-clause gold reasoning. Reading order: see policy.md §3 for the
R/A/G rules driving label selection.
"""
from __future__ import annotations
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

DATA = Path(__file__).parent
CLAIMS = DATA / "claims"
LABELS = DATA / "labels.csv"
EMPLOYEES = DATA / "employees.json"

CATEGORIES = ("meals", "travel", "accommodation", "entertainment", "miscellaneous")
MARKETS = ("UK", "US", "DE", "IN")
CURRENCY = {"UK": "GBP", "US": "USD", "DE": "EUR", "IN": "INR"}
EMS = ("workday", "concur")

# Per-market meal caps mirroring policy.md §3.1. Tests assert the policy text
# is present; the generator uses these structured copies of the same numbers.
MEAL_SOLO_CAP = {"UK": 40, "US": 50, "DE": 45, "IN": 2500}
MEAL_PER_ATTENDEE_CAP = {"UK": 75, "US": 75, "DE": 70, "IN": 4000}
RECEIPT_THRESHOLD = {"UK": 25, "US": 25, "DE": 0, "IN": 500}

# (similar caps for travel/accommodation/entertainment/miscellaneous — mirror policy.md)


def _gen_meals_claim(rng: random.Random, target: str, market: str) -> dict:
    """Return a meals claim engineered to land on `target` in {green, amber, red}."""
    solo_cap = MEAL_SOLO_CAP[market]
    per_att_cap = MEAL_PER_ATTENDEE_CAP[market]
    if target == "green":
        attendees = rng.choice([1, 2, 3])
        amount = round(rng.uniform(0.4, 0.95) * (solo_cap if attendees == 1 else per_att_cap * attendees), 2)
        clause = f"§3.1 Meals — {market} solo cap {solo_cap} / per-attendee cap {per_att_cap}"
        reasoning = f"Within cap with receipt and {attendees} named attendee(s); auto-approve."
    elif target == "amber":
        attendees = rng.choice([2, 3, 4])
        # Boundary: 100-110% of per-attendee cap.
        amount = round(rng.uniform(1.0, 1.1) * per_att_cap * attendees, 2)
        clause = f"§3.1 Meals — {market} per-attendee cap {per_att_cap} (110% boundary)"
        reasoning = "Within 110% of per-attendee cap; reviewer should confirm attendee count."
    else:  # red
        attendees = rng.choice([1, 2])
        amount = round(rng.uniform(1.5, 2.5) * per_att_cap * max(attendees, 1), 2)
        clause = f"§3.1 Meals — {market} per-attendee cap {per_att_cap}"
        reasoning = f"Above 110% of per-attendee cap by significant margin; breach."
    return {
        "category": "meals",
        "amount": amount,
        "attendees": attendees,
        "gold_label": target,
        "gold_policy_clause": clause,
        "gold_reasoning": reasoning,
    }


# Implement parallel generators for travel/accommodation/entertainment/miscellaneous.
# Each must produce gold_label, gold_policy_clause (with §-section reference), and
# gold_reasoning that quotes the relevant policy line.

_GENERATORS = {
    "meals": _gen_meals_claim,
    # "travel": _gen_travel_claim,
    # "accommodation": _gen_accommodation_claim,
    # "entertainment": _gen_entertainment_claim,
    # "miscellaneous": _gen_misc_claim,
}


def _label_for_index(i: int) -> str:
    # Stable sequence: 70/20/10 by deterministic walk, not random sampling.
    if i % 10 in {0, 1, 2, 3, 4, 5, 6}:
        return "green"
    if i % 10 in {7, 8}:
        return "amber"
    return "red"


def run(seed: int = 20260427, count: int = 300) -> None:
    rng = random.Random(seed)
    CLAIMS.mkdir(parents=True, exist_ok=True)
    employees = json.loads(EMPLOYEES.read_text(encoding="utf-8"))

    base_dt = datetime(2026, 4, 1)
    rows = []
    for i in range(count):
        target = _label_for_index(i)
        category = rng.choice(CATEGORIES)
        market = rng.choice(MARKETS)
        emp = rng.choice([e for e in employees if e["market"] == market]) if any(e["market"] == market for e in employees) else rng.choice(employees)
        gen = _GENERATORS.get(category, _gen_meals_claim)  # fall back to meals shape until all 5 are written
        body = gen(rng, target, market)
        claim_id = f"CLM-{i:04d}"
        receipt_filename = f"{claim_id}.png"
        submitted_at = (base_dt + timedelta(days=i // 10, hours=rng.randrange(8, 19))).isoformat()
        ems_source = rng.choice(EMS)
        claim = {
            "claim_id": claim_id,
            "employee_id": emp["id"],
            "submitted_at": submitted_at,
            "market": market,
            "currency": CURRENCY[market],
            "vendor": _vendor_for(rng, body["category"], market),
            "receipt_filename": receipt_filename,
            "ems_source": ems_source,
            **body,
        }
        (CLAIMS / f"{claim_id}.json").write_text(json.dumps(claim, indent=2, ensure_ascii=False), encoding="utf-8")
        rows.append({
            "claim_id": claim_id,
            "category": claim["category"],
            "market": market,
            "amount": claim["amount"],
            "currency": CURRENCY[market],
            "gold_label": claim["gold_label"],
            "gold_policy_clause": claim["gold_policy_clause"],
        })

    with LABELS.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _vendor_for(rng: random.Random, category: str, market: str) -> str:
    # Small static pool per (category, market) — keeps determinism and makes
    # receipt rendering predictable.
    pools = {
        ("meals", "UK"): ["Côte Brasserie", "Pret A Manger", "The Ivy"],
        ("meals", "US"): ["Sweetgreen", "Joe's Pizza", "The Standard Grill"],
        # ... fill in remaining (category, market) pairs
    }
    return rng.choice(pools.get((category, market), [f"Generic {category} vendor"]))


if __name__ == "__main__":
    run()
    print(f"Wrote {len(list(CLAIMS.glob('CLM-*.json')))} claims and labels.csv")
```

Note: the example above only fully implements `meals`. **Implement all five category generators before moving on.** Each must:
- Use the policy.md numbers as constants (or re-read policy.md if you prefer; constants are fine for determinism and speed).
- Engineer `green` claims comfortably within caps; `amber` claims at 100-110% boundary or with one missing soft requirement; `red` claims clearly above 110% or with a hard breach (alcohol where prohibited, missing receipt above threshold, etc.).
- Set `gold_policy_clause` to a `§N.M Category — Market description` string that references real policy.md sections.
- Set `gold_reasoning` to one or two sentences quoting policy text — this is what the classifier's reasoning will be string-similarity-compared against in the harness.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/api/unit/test_synthetic_generate.py -v`
Expected: all 6 tests PASS. Distribution counts may shift slightly — adjust the `_label_for_index` walk if the 195/225 envelope is missed.

- [ ] **Step 5: Spot-check three sample claims by eye**

Run: `cat data/synthetic/claims/CLM-0000.json data/synthetic/claims/CLM-0007.json data/synthetic/claims/CLM-0009.json`
Expected: a Green, an Amber, and a Red respectively, with policy-text gold reasoning that you'd recognise as correct if you read policy.md.

- [ ] **Step 6: Commit**

```bash
git add data/synthetic/generate.py data/synthetic/claims/ data/synthetic/labels.csv tests/api/unit/test_synthetic_generate.py
git commit -m "feat(data): deterministic 300-claim generator with gold reasoning

Walks policy.md and emits 70/20/10 Green/Amber/Red distribution.
Amber claims sit at the 110% boundary so the classifier has to
genuinely reason about thresholds, not pattern-match. Gold reasoning
is the literal policy clause text — defeats 'rules tested against
rules' tautology charge.

Spec ref: §5.4 + §6."
```

---

## Task 6: Receipt PNG generator with mismatch flavours

**Files:**
- Create: `data/synthetic/receipt_generator.py`
- Create: `tests/api/unit/test_receipt_generator.py`
- Create: `data/synthetic/receipts/` (output dir)

Generates 300 PNGs from the 300 claims, with a controlled distribution of six mismatch flavours: `correct`, `wrong-amount`, `wrong-date`, `wrong-vendor`, `missing-line-item`, `missing-receipt`. The mismatch type is recorded back into the claim JSON as `receipt_mismatch_flavour` (added field — generator updates the file).

This receipt set seeds the Week 2 receipt validator. We generate it now while we're in the synthetic-data directory and so the AccuracyReport panel can show receipt thumbnails on cell drill-down.

- [ ] **Step 1: Add Pillow to dependencies**

Open `pyproject.toml`, add `"pillow>=10.0"` to the project dependencies array.

Run: `uv sync` (or `pip install -e .` if using pip).
Expected: Pillow installs without error.

- [ ] **Step 2: Write the failing test**

Create `tests/api/unit/test_receipt_generator.py`:

```python
"""Receipt PNG generator tests."""
from __future__ import annotations
import json
import shutil
from collections import Counter
from pathlib import Path

import pytest

from data.synthetic import generate, receipt_generator

DATA = Path(generate.__file__).parent
CLAIMS = DATA / "claims"
RECEIPTS = DATA / "receipts"


@pytest.fixture(autouse=True)
def _ensure_claims():
    if not CLAIMS.exists() or len(list(CLAIMS.glob("CLM-*.json"))) != 300:
        generate.run(seed=20260427, count=300)
    if RECEIPTS.exists():
        shutil.rmtree(RECEIPTS)


def test_generates_receipt_for_every_claim():
    receipt_generator.run(seed=20260427)
    pngs = sorted(RECEIPTS.glob("CLM-*.png"))
    assert len(pngs) == 300


def test_pngs_are_valid_image_files():
    receipt_generator.run(seed=20260427)
    from PIL import Image
    sample = next(RECEIPTS.glob("CLM-*.png"))
    with Image.open(sample) as img:
        assert img.format == "PNG"
        assert img.size[0] >= 200 and img.size[1] >= 300


def test_six_mismatch_flavours_present():
    receipt_generator.run(seed=20260427)
    flavours = Counter()
    for f in CLAIMS.glob("CLM-*.json"):
        c = json.loads(f.read_text(encoding="utf-8"))
        flavours[c["receipt_mismatch_flavour"]] += 1
    expected = {"correct", "wrong-amount", "wrong-date", "wrong-vendor", "missing-line-item", "missing-receipt"}
    assert expected <= set(flavours), flavours
    # Most receipts should be correct so the harness has a true Green baseline.
    assert flavours["correct"] >= 200, flavours


def test_missing_receipt_flavour_emits_zero_byte_marker():
    receipt_generator.run(seed=20260427)
    # missing-receipt claims have an explicit zero-byte marker file so the
    # classifier and validator can distinguish "no receipt submitted" from
    # "receipt file missing on disk by accident".
    missing = [json.loads(f.read_text()) for f in CLAIMS.glob("CLM-*.json")
               if json.loads(f.read_text())["receipt_mismatch_flavour"] == "missing-receipt"]
    assert missing, "no missing-receipt claims generated"
    sample = missing[0]
    receipt_path = RECEIPTS / sample["receipt_filename"]
    assert receipt_path.exists()
    assert receipt_path.stat().st_size == 0
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest tests/api/unit/test_receipt_generator.py -v`
Expected: FAIL with `ImportError: cannot import name 'receipt_generator'`.

- [ ] **Step 4: Implement `data/synthetic/receipt_generator.py`**

```python
"""PIL-templated receipt PNG generator with controlled mismatch flavours."""
from __future__ import annotations
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DATA = Path(__file__).parent
CLAIMS = DATA / "claims"
RECEIPTS = DATA / "receipts"

FLAVOURS = ("correct", "wrong-amount", "wrong-date", "wrong-vendor", "missing-line-item", "missing-receipt")
# 80/4/4/4/4/4 — most claims have correct receipts so accuracy can be measured.
FLAVOUR_WEIGHTS = (240, 12, 12, 12, 12, 12)

WIDTH, HEIGHT = 480, 720
BG = (255, 255, 255)
FG = (10, 10, 10)


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _render(claim: dict, flavour: str) -> Image.Image | None:
    if flavour == "missing-receipt":
        return None  # caller writes a zero-byte file

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    title = _font(28)
    body = _font(16)

    vendor = claim["vendor"] if flavour != "wrong-vendor" else f"NOT-{claim['vendor']}"
    submitted = datetime.fromisoformat(claim["submitted_at"])
    date_str = (submitted - timedelta(days=400)).date().isoformat() if flavour == "wrong-date" else submitted.date().isoformat()
    amount = claim["amount"] * 1.5 if flavour == "wrong-amount" else claim["amount"]

    draw.text((20, 20), vendor, fill=FG, font=title)
    draw.text((20, 70), f"Date: {date_str}", fill=FG, font=body)
    draw.text((20, 100), f"Currency: {claim['currency']}", fill=FG, font=body)
    draw.text((20, 130), f"Total: {amount:.2f}", fill=FG, font=body)

    y = 180
    if flavour != "missing-line-item":
        draw.text((20, y), "Line items:", fill=FG, font=body); y += 30
        draw.text((40, y), f"- {claim['category']} x {claim.get('attendees', 1)}: {amount:.2f}", fill=FG, font=body)
    return img


def run(seed: int = 20260427) -> None:
    rng = random.Random(seed)
    RECEIPTS.mkdir(parents=True, exist_ok=True)

    claim_files = sorted(CLAIMS.glob("CLM-*.json"))
    flavour_pool = []
    for flavour, weight in zip(FLAVOURS, FLAVOUR_WEIGHTS):
        flavour_pool.extend([flavour] * weight)
    rng.shuffle(flavour_pool)
    # Ensure pool length matches claim count.
    while len(flavour_pool) < len(claim_files):
        flavour_pool.append("correct")
    flavour_pool = flavour_pool[:len(claim_files)]

    for path, flavour in zip(claim_files, flavour_pool):
        claim = json.loads(path.read_text(encoding="utf-8"))
        claim["receipt_mismatch_flavour"] = flavour
        path.write_text(json.dumps(claim, indent=2, ensure_ascii=False), encoding="utf-8")
        out = RECEIPTS / claim["receipt_filename"]
        img = _render(claim, flavour)
        if img is None:
            out.write_bytes(b"")  # zero-byte marker for missing-receipt
        else:
            img.save(out, format="PNG", optimize=True)


if __name__ == "__main__":
    run()
    print(f"Wrote {len(list(RECEIPTS.glob('CLM-*.png')))} receipts")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/api/unit/test_receipt_generator.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 6: Spot-check a sample receipt visually**

Run: `python -c "from PIL import Image; Image.open('data/synthetic/receipts/CLM-0000.png').show()"` (or open the file in any image viewer).
Expected: a recognisable receipt with vendor / date / amount / line item.

- [ ] **Step 7: Commit**

```bash
git add data/synthetic/receipt_generator.py data/synthetic/receipts/ data/synthetic/claims/ tests/api/unit/test_receipt_generator.py pyproject.toml uv.lock
git commit -m "feat(data): receipt PNG generator with 6 mismatch flavours

PIL-templated 480x720 receipts; 80% correct, 4% each of wrong-amount,
wrong-date, wrong-vendor, missing-line-item, missing-receipt. Zero-byte
marker file for missing-receipt so validator can distinguish 'no receipt
submitted' from 'file missing by accident'. Mismatch flavour written
back into each claim JSON for the Week 2 receipt validator.

Spec ref: §5.4 + §6.3."
```

---

## Task 7: MCP tool — `policy.search`

**Files:**
- Create: `api/server/mcp_tools/policy_search.py`
- Create: `tests/api/unit/test_policy_search.py`

In-memory chunked retriever over `data/synthetic/policy.md` using `sentence-transformers` (`all-MiniLM-L6-v2`) + an in-memory cosine-similarity search (no FAISS dependency in week 1 — list comprehension is fast enough for an 8-12 page document chunked at ~200 words). Foundry IQ binding is a later swap (spec §11 open question).

Read [api/server/mcp_tools/query_fleet.py](../../../api/server/mcp_tools/query_fleet.py) before authoring this one, to match the existing tool/OTEL conventions.

- [ ] **Step 1: Add `sentence-transformers` to dependencies**

Open `pyproject.toml`, add `"sentence-transformers>=3.0"` to dependencies.

Run: `uv sync`
Expected: installs (large download — model weights are pulled at first use, not at install).

- [ ] **Step 2: Write the failing test**

Create `tests/api/unit/test_policy_search.py`:

```python
"""policy.search MCP tool tests."""
from __future__ import annotations
from pathlib import Path
import pytest

from api.server.mcp_tools import policy_search

POLICY = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "policy.md"


def test_search_returns_top_k_chunks():
    results = policy_search.search("UK meals per attendee cap", k=3)
    assert isinstance(results, list)
    assert 1 <= len(results) <= 3
    for r in results:
        assert {"text", "section", "score"} <= set(r), r
        assert isinstance(r["score"], float)
        assert r["section"].startswith("§"), r["section"]


def test_search_finds_meal_clause_first():
    results = policy_search.search("UK meals per attendee cap £75", k=5)
    top_text = results[0]["text"].lower()
    assert "meal" in top_text and ("75" in top_text or "per-attendee" in top_text)


def test_search_finds_alcohol_rule():
    results = policy_search.search("alcohol prohibited Germany", k=5)
    assert any("alcohol" in r["text"].lower() for r in results)


def test_search_handles_missing_policy_gracefully(tmp_path, monkeypatch):
    monkeypatch.setattr(policy_search, "_POLICY_PATH", tmp_path / "missing.md")
    monkeypatch.setattr(policy_search, "_index_cache", None)
    with pytest.raises(FileNotFoundError):
        policy_search.search("anything", k=3)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest tests/api/unit/test_policy_search.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 4: Implement `api/server/mcp_tools/policy_search.py`**

```python
"""policy.search MCP tool — in-memory chunked retriever over the synthetic
T&E policy. Foundry IQ swap-in is a later detail; this is the demo-grade
implementation."""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from opentelemetry import trace

_tracer = trace.get_tracer("wpp.mcp.policy_search")
_POLICY_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "policy.md"


@dataclass
class _Chunk:
    section: str
    text: str
    embedding: np.ndarray


_index_cache: Optional[list[_Chunk]] = None
_model_cache: Optional[SentenceTransformer] = None


def _load_model() -> SentenceTransformer:
    global _model_cache
    if _model_cache is None:
        _model_cache = SentenceTransformer("all-MiniLM-L6-v2")
    return _model_cache


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown by ## or ### headers, retaining the section label."""
    chunks: list[tuple[str, str]] = []
    current_label = "§0 Preamble"
    current: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^#+\s+(.*)$", line)
        if m:
            if current:
                chunks.append((current_label, "\n".join(current).strip()))
                current = []
            heading = m.group(1).strip()
            num = re.match(r"^([\d.]+)\s+(.*)", heading)
            current_label = f"§{num.group(1)} {num.group(2)}" if num else f"§ {heading}"
        else:
            current.append(line)
    if current:
        chunks.append((current_label, "\n".join(current).strip()))
    # Drop empty chunks.
    return [(label, body) for label, body in chunks if body]


def _ensure_index() -> list[_Chunk]:
    global _index_cache
    if _index_cache is not None:
        return _index_cache
    if not _POLICY_PATH.exists():
        raise FileNotFoundError(f"policy.md not found at {_POLICY_PATH}")
    text = _POLICY_PATH.read_text(encoding="utf-8")
    model = _load_model()
    chunks = _split_into_sections(text)
    embeddings = model.encode([body for _, body in chunks], convert_to_numpy=True, normalize_embeddings=True)
    _index_cache = [_Chunk(section=label, text=body, embedding=emb) for (label, body), emb in zip(chunks, embeddings)]
    return _index_cache


def reset_cache() -> None:
    """Invalidate the index — call when policy.md is edited at runtime."""
    global _index_cache
    _index_cache = None


def search(query: str, k: int = 5) -> list[dict]:
    """Return top-k policy chunks ranked by cosine similarity to query."""
    with _tracer.start_as_current_span("mcp.policy.search") as span:
        span.set_attribute("wpp.mcp.tool", "policy.search")
        span.set_attribute("wpp.mcp.query", query)
        span.set_attribute("wpp.mcp.k", k)
        chunks = _ensure_index()
        model = _load_model()
        q_emb = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]
        scored = [(float(np.dot(q_emb, c.embedding)), c) for c in chunks]
        scored.sort(key=lambda t: t[0], reverse=True)
        out = [{"section": c.section, "text": c.text, "score": s} for s, c in scored[:k]]
        span.set_attribute("wpp.mcp.result_count", len(out))
        return out
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/api/unit/test_policy_search.py -v`
Expected: all 4 tests PASS. First run will download the MiniLM model (~80MB) — be patient.

If `test_search_finds_meal_clause_first` fails on top-result, increase the section split granularity (e.g. paragraph-level not section-level for §3).

- [ ] **Step 6: Commit**

```bash
git add api/server/mcp_tools/policy_search.py tests/api/unit/test_policy_search.py pyproject.toml uv.lock
git commit -m "feat(mcp): policy.search tool — in-memory chunked retriever

MiniLM embeddings over policy.md sections, cosine ranked. reset_cache()
called by the policy editor when policy.md is mutated at runtime.
Foundry IQ binding is a later swap.

Spec ref: §11 open question."
```

---

## Task 8: MCP tool — `claim.getStructured`

**Files:**
- Create: `api/server/mcp_tools/claim_get_structured.py`
- Create: `tests/api/unit/test_claim_get_structured.py`

Reads a claim JSON by id from `data/synthetic/claims/`. Trivial wrapper but the classifier needs it as a discrete tool call so the OTEL trace shows policy.search and claim.getStructured side-by-side per claim.

- [ ] **Step 1: Write the failing test**

Create `tests/api/unit/test_claim_get_structured.py`:

```python
from __future__ import annotations
import pytest

from api.server.mcp_tools import claim_get_structured


def test_returns_claim_for_valid_id():
    claim = claim_get_structured.get_structured("CLM-0000")
    assert claim["claim_id"] == "CLM-0000"
    assert "amount" in claim and "category" in claim and "market" in claim


def test_raises_for_unknown_id():
    with pytest.raises(KeyError):
        claim_get_structured.get_structured("CLM-9999")


def test_redacts_gold_fields_by_default():
    claim = claim_get_structured.get_structured("CLM-0000")
    # The classifier must not see the gold label or reasoning — that would
    # invalidate the accuracy benchmark.
    assert "gold_label" not in claim
    assert "gold_reasoning" not in claim
    assert "gold_policy_clause" not in claim


def test_include_gold_flag_for_test_paths():
    claim = claim_get_structured.get_structured("CLM-0000", include_gold=True)
    assert "gold_label" in claim
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/api/unit/test_claim_get_structured.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `api/server/mcp_tools/claim_get_structured.py`**

```python
"""claim.getStructured MCP tool — returns a normalised claim record by id."""
from __future__ import annotations
import json
from pathlib import Path

from opentelemetry import trace

_tracer = trace.get_tracer("wpp.mcp.claim_get_structured")
_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"

_GOLD_FIELDS = ("gold_label", "gold_reasoning", "gold_policy_clause")


def get_structured(claim_id: str, include_gold: bool = False) -> dict:
    """Return claim JSON. By default redacts gold-* fields so the classifier
    cannot accidentally cheat. Tests pass include_gold=True for assertions."""
    with _tracer.start_as_current_span("mcp.claim.getStructured") as span:
        span.set_attribute("wpp.mcp.tool", "claim.getStructured")
        span.set_attribute("wpp.claim.id", claim_id)
        path = _CLAIMS_DIR / f"{claim_id}.json"
        if not path.exists():
            raise KeyError(f"claim {claim_id!r} not found")
        claim = json.loads(path.read_text(encoding="utf-8"))
        if not include_gold:
            for f in _GOLD_FIELDS:
                claim.pop(f, None)
        return claim
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/api/unit/test_claim_get_structured.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add api/server/mcp_tools/claim_get_structured.py tests/api/unit/test_claim_get_structured.py
git commit -m "feat(mcp): claim.getStructured tool with gold-field redaction

Default redacts gold_* so the classifier cannot accidentally cheat.
Tests opt in via include_gold=True."
```

---

## Task 9: `rag_classifier` skill

**Files:**
- Create: `api/server/skills/rag_classifier.skill.md`

Hand-authored skill markdown. No test on the file itself — its correctness is measured downstream by the harness.

- [ ] **Step 1: Author `api/server/skills/rag_classifier.skill.md`**

```markdown
---
name: rag-classifier
description: Classify expense claim lines as Red/Amber/Green against the synthetic T&E policy, citing the literal policy clause and exposing competing interpretations for boundary cases.
allowed-tools: policy.search, claim.getStructured
---

You classify expense claims under WPP's T&E policy.

For each claim id you receive:
1. Call `claim.getStructured(claim_id)` once. The returned record has category, market, currency, amount, attendees, vendor, and metadata.
2. Call `policy.search` with a query targeting the relevant policy section. Use the claim's category and market in the query. Make at most three searches. If the first result clearly answers the question, do not search again.
3. Decide the verdict:
   - **green** — claim is comfortably within policy with required documentation.
   - **amber** — boundary case (within ~110% of a cap, missing optional context, ambiguous attendee count, weekend without business reason annotated) — a human reviewer should confirm.
   - **red** — clear breach (above 110% of a cap, alcohol where prohibited, missing receipt above the market threshold, or any explicit policy violation).

Return exactly one JSON object, no prose:

```json
{
  "verdict": "green" | "amber" | "red",
  "policy_clause": "§3.1 Meals — UK per-attendee cap £75",
  "reasoning": "One-to-three sentences quoting the relevant policy text and stating why the claim falls on this side of the boundary.",
  "confidence": 0.0 to 1.0,
  "competing_interpretations": [
    {"verdict": "amber", "reasoning": "If the attendees count is contested, this could be Amber instead.", "confidence": 0.2}
  ]
}
```

Rules:
- `policy_clause` must begin with `§` and reference the section number you actually based the verdict on.
- `reasoning` must quote at least one phrase from the policy text returned by `policy.search`. Do not paraphrase the threshold numbers — copy them.
- `competing_interpretations` may be empty for clear Green or clear Red. For Amber, surface at least one alternative.
- `confidence` is the model's own self-assessment, not a downstream gate.
- Never set the verdict from the gold label — the gold label is not exposed to you.
```

- [ ] **Step 2: Verify the skill is loadable**

Run: `python -c "from api.functions.graphs.executors.agents._wrapper import _load_skill; print(len(_load_skill('rag_classifier')))"`
Expected: prints a positive integer (the byte count of the skill file).

- [ ] **Step 3: Commit**

```bash
git add api/server/skills/rag_classifier.skill.md
git commit -m "feat(skill): rag_classifier — R/A/G verdict with policy clause + competing interpretations

Structured output enforced via JSON schema in the skill body.
Reasoning must quote policy text returned by policy.search — defeats
paraphrase drift in the accuracy benchmark.

Spec ref: §5.4."
```

---

## Task 10: `agent_rag_classifier` executor

**Files:**
- Create: `api/functions/graphs/executors/agents/agent_rag_classifier.py`
- Create: `tests/api/unit/test_agent_rag_classifier.py`

Wraps the skill via `run_agent_skill` from `_wrapper.py`. Takes a `claim_id` (not the full claim — the skill calls `claim.getStructured` itself so the tool calls are visible in OTEL).

Read `api/functions/graphs/executors/agents/agent_invoice_classifier.py` (recently deleted — reference the spec or the v0.5 tag) for the original wrapping pattern. The spec preserves the simple shape: build a prompt, call `run_agent_skill`, return the dict.

- [ ] **Step 1: Write the failing test**

Create `tests/api/unit/test_agent_rag_classifier.py`:

```python
"""agent_rag_classifier executor tests — mocks the GHCP wrapper."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.executors.agents import agent_rag_classifier


@pytest.mark.asyncio
async def test_returns_classifier_payload(monkeypatch):
    fake = {
        "verdict": "amber",
        "policy_clause": "§3.1 Meals — UK per-attendee cap £75",
        "reasoning": "Within 110% of cap with named attendees; reviewer should confirm.",
        "confidence": 0.7,
        "competing_interpretations": [],
    }
    with patch.object(agent_rag_classifier, "run_agent_skill", AsyncMock(return_value=fake)) as mock_run:
        result = await agent_rag_classifier.execute({"claim_id": "CLM-0007"})
    assert result["classification"] == fake
    mock_run.assert_awaited_once()
    args, kwargs = mock_run.call_args
    assert args[0] == "rag_classifier"
    assert "CLM-0007" in args[1]


@pytest.mark.asyncio
async def test_passes_through_parse_error(monkeypatch):
    parse_err = {"raw": "model talked instead of JSON", "parse_error": True}
    with patch.object(agent_rag_classifier, "run_agent_skill", AsyncMock(return_value=parse_err)):
        result = await agent_rag_classifier.execute({"claim_id": "CLM-0001"})
    assert result["classification"]["parse_error"] is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/api/unit/test_agent_rag_classifier.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `api/functions/graphs/executors/agents/agent_rag_classifier.py`**

```python
"""agent_rag_classifier — invokes the rag_classifier skill via the GHCP wrapper."""
from __future__ import annotations

from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    claim_id = input["claim_id"]
    prompt = (
        f"Classify expense claim {claim_id} per your role.\n\n"
        f"Call claim.getStructured to load the claim, then policy.search to ground "
        f"your verdict in the relevant policy clause. Return the JSON object specified "
        f"in your skill instructions — no prose."
    )
    classification = await run_agent_skill("rag_classifier", prompt)
    return {"classification": classification}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/api/unit/test_agent_rag_classifier.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add api/functions/graphs/executors/agents/agent_rag_classifier.py tests/api/unit/test_agent_rag_classifier.py
git commit -m "feat(agent): agent_rag_classifier executor wraps rag_classifier skill"
```

---

## Task 11: `validate_classification_schema` validator

**Files:**
- Create: `api/functions/graphs/executors/validators/validate_classification_schema.py`
- Create: `tests/api/unit/test_validate_classification_schema.py`

Validator-as-guardrail edge: blocks the workflow if the classifier returned malformed structured output, so a bad classification never silently propagates downstream.

- [ ] **Step 1: Write the failing test**

```python
"""validate_classification_schema tests."""
from __future__ import annotations
import pytest

from api.functions.graphs.executors.validators import validate_classification_schema as v


def test_valid_payload_passes():
    v.validate({
        "verdict": "amber",
        "policy_clause": "§3.1 Meals — UK per-attendee cap £75",
        "reasoning": "Within 110% of per-attendee cap.",
        "confidence": 0.7,
        "competing_interpretations": [],
    })


def test_missing_verdict_raises():
    with pytest.raises(v.ClassificationSchemaError):
        v.validate({"policy_clause": "§1", "reasoning": "x", "confidence": 0.5, "competing_interpretations": []})


def test_invalid_verdict_raises():
    with pytest.raises(v.ClassificationSchemaError):
        v.validate({
            "verdict": "yellow",
            "policy_clause": "§1", "reasoning": "x", "confidence": 0.5, "competing_interpretations": [],
        })


def test_policy_clause_must_start_with_section_marker():
    with pytest.raises(v.ClassificationSchemaError):
        v.validate({
            "verdict": "green",
            "policy_clause": "Meals UK", "reasoning": "x", "confidence": 0.5, "competing_interpretations": [],
        })


def test_parse_error_payload_raises():
    with pytest.raises(v.ClassificationSchemaError, match="parse_error"):
        v.validate({"raw": "...", "parse_error": True})


def test_confidence_out_of_range_raises():
    with pytest.raises(v.ClassificationSchemaError):
        v.validate({
            "verdict": "amber", "policy_clause": "§1", "reasoning": "x",
            "confidence": 1.5, "competing_interpretations": [],
        })
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/api/unit/test_validate_classification_schema.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the validator**

```python
"""validate_classification_schema — guardrail edge over rag_classifier output."""
from __future__ import annotations


class ClassificationSchemaError(ValueError):
    """Raised when a classifier payload does not conform to the spec."""


_VALID_VERDICTS = {"green", "amber", "red"}


def validate(payload: dict) -> None:
    if payload.get("parse_error"):
        raise ClassificationSchemaError(f"parse_error in classifier payload: {payload.get('raw', '')[:200]}")

    for required in ("verdict", "policy_clause", "reasoning", "confidence", "competing_interpretations"):
        if required not in payload:
            raise ClassificationSchemaError(f"missing field: {required}")

    if payload["verdict"] not in _VALID_VERDICTS:
        raise ClassificationSchemaError(f"verdict must be one of {_VALID_VERDICTS}, got {payload['verdict']!r}")

    if not isinstance(payload["policy_clause"], str) or not payload["policy_clause"].startswith("§"):
        raise ClassificationSchemaError(f"policy_clause must be a string starting with §; got {payload['policy_clause']!r}")

    if not isinstance(payload["reasoning"], str) or not payload["reasoning"].strip():
        raise ClassificationSchemaError("reasoning must be a non-empty string")

    conf = payload["confidence"]
    if not isinstance(conf, (int, float)) or not 0.0 <= float(conf) <= 1.0:
        raise ClassificationSchemaError(f"confidence must be float in [0,1]; got {conf!r}")

    if not isinstance(payload["competing_interpretations"], list):
        raise ClassificationSchemaError("competing_interpretations must be a list")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/api/unit/test_validate_classification_schema.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add api/functions/graphs/executors/validators/validate_classification_schema.py tests/api/unit/test_validate_classification_schema.py
git commit -m "feat(validator): validate_classification_schema guardrail over classifier output"
```

---

## Task 12: Single-claim end-to-end smoke test

**Files:**
- Create: `tests/api/unit/test_classifier_e2e_smoke.py` (marked `@pytest.mark.smoke` — opt-in)

This is the first integration test that calls the real GHCP SDK. It runs five claims through the classifier and asserts that the schema validator passes on each. **It does not assert correctness** — that's the harness's job in Task 13–18. This test is the early signal that the wiring works.

- [ ] **Step 1: Add a `smoke` marker to pytest config**

Edit `pyproject.toml` — extend `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests/api"]
markers = ["smoke: requires GHCP credentials and live model calls; opt-in via -m smoke"]
```

- [ ] **Step 2: Write the smoke test**

```python
"""End-to-end smoke: 5 real classifier calls, assert schema validity only.

Run: pytest tests/api/unit/test_classifier_e2e_smoke.py -m smoke -v
Skipped by default — requires `gh auth` and live model calls."""
from __future__ import annotations
import pytest

from api.functions.graphs.executors.agents import agent_rag_classifier
from api.functions.graphs.executors.validators import validate_classification_schema as schema

pytestmark = pytest.mark.smoke

CLAIM_IDS = ["CLM-0000", "CLM-0007", "CLM-0009", "CLM-0014", "CLM-0019"]


@pytest.mark.asyncio
@pytest.mark.parametrize("claim_id", CLAIM_IDS)
async def test_real_classifier_returns_valid_payload(claim_id):
    result = await agent_rag_classifier.execute({"claim_id": claim_id})
    payload = result["classification"]
    schema.validate(payload)  # raises if malformed
    assert payload["verdict"] in {"green", "amber", "red"}
```

- [ ] **Step 3: Run the smoke test**

Prereq: `gh auth status` shows authenticated (the wrapper calls `gh auth token`).

Run: `pytest tests/api/unit/test_classifier_e2e_smoke.py -m smoke -v`
Expected: 5 PASS, taking 10–60 seconds total depending on model latency.

If any of the five fails the schema validator, **read the raw model output**, refine the skill prompt (Task 9), and retry. This is the early signal for whether the prompt is correct before investing in the harness.

- [ ] **Step 4: Commit**

```bash
git add tests/api/unit/test_classifier_e2e_smoke.py pyproject.toml
git commit -m "test(smoke): 5-claim end-to-end classifier wiring check

Opt-in via -m smoke. Asserts schema validity, not correctness — the
harness measures correctness on 300 claims in Task 13."
```

---

## Task 13: Accuracy harness MAF Workflow — splitter and aggregator scaffolding

**Files:**
- Create: `api/functions/workflows/accuracy_harness_workflow.py`
- Create: `tests/api/unit/test_accuracy_harness_workflow.py`

The harness is a Pregel graph: `claim_splitter → [N × rag_classifier_executor] → confusion_matrix_aggregator`. Match the existing MAF graph pattern in `api/functions/graphs/intake.py` etc.

This task lands the splitter, the per-claim executor adaptor, and the aggregator with TDD against an *injected* classifier. Task 14 wires real progress streaming.

- [ ] **Step 1: Write the failing test**

```python
"""Accuracy harness — uses a synchronous fake classifier so we can assert
the splitter/fan-out/aggregator pipeline without making real model calls."""
from __future__ import annotations
import asyncio
import pytest

from api.functions.workflows import accuracy_harness_workflow as harness


@pytest.mark.asyncio
async def test_aggregator_builds_confusion_matrix():
    # Inject a perfect classifier — gold and predicted match every time.
    async def perfect(claim_id: str) -> dict:
        from api.server.mcp_tools.claim_get_structured import get_structured
        gold = get_structured(claim_id, include_gold=True)
        return {
            "verdict": gold["gold_label"],
            "policy_clause": gold["gold_policy_clause"],
            "reasoning": gold["gold_reasoning"],
            "confidence": 0.99,
            "competing_interpretations": [],
        }

    report = await harness.run(
        claim_ids=["CLM-0000", "CLM-0001", "CLM-0002", "CLM-0003"],
        classifier=perfect,
        concurrency=2,
    )
    assert report["overall_accuracy"] == 1.0
    cm = report["confusion_matrix"]
    # Diagonal-only.
    assert sum(cm[label][label] for label in ("green", "amber", "red")) == 4
    assert all(cm[r][c] == 0 for r in cm for c in cm[r] if r != c)


@pytest.mark.asyncio
async def test_aggregator_handles_misclassification():
    # Always predicts green.
    async def always_green(claim_id: str) -> dict:
        return {
            "verdict": "green",
            "policy_clause": "§3.1 Meals",
            "reasoning": "predicted green",
            "confidence": 0.5,
            "competing_interpretations": [],
        }

    report = await harness.run(
        claim_ids=["CLM-0000", "CLM-0007", "CLM-0009"],  # one each of green/amber/red ideally
        classifier=always_green,
        concurrency=1,
    )
    # The gold labels are decided by `_label_for_index` from generate.py — index 0,7,9 → green/amber/red.
    assert report["overall_accuracy"] < 1.0
    assert report["confusion_matrix"]["green"]["green"] >= 1
    # At least one off-diagonal cell populated.
    off_diag = [(r, c, v) for r in report["confusion_matrix"] for c, v in report["confusion_matrix"][r].items() if r != c and v > 0]
    assert off_diag


@pytest.mark.asyncio
async def test_per_claim_records_attached():
    async def perfect(claim_id: str):
        from api.server.mcp_tools.claim_get_structured import get_structured
        gold = get_structured(claim_id, include_gold=True)
        return {"verdict": gold["gold_label"], "policy_clause": gold["gold_policy_clause"],
                "reasoning": gold["gold_reasoning"], "confidence": 0.99, "competing_interpretations": []}

    report = await harness.run(claim_ids=["CLM-0000"], classifier=perfect, concurrency=1)
    assert len(report["per_claim"]) == 1
    rec = report["per_claim"][0]
    assert {"claim_id", "gold_label", "predicted_label", "gold_reasoning", "predicted_reasoning",
            "policy_clause", "correct"} <= set(rec)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/api/unit/test_accuracy_harness_workflow.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the harness**

```python
"""Accuracy harness — parallel-fan-out workflow over the claim corpus.

Pregel-style shape:
    claim_splitter → [concurrency × classifier] → confusion_matrix_aggregator

We use asyncio.Semaphore for the fan-out concurrency rather than a full MAF
Pregel graph because the harness is invoked as a one-shot evaluation, not
as a per-claim Durable workflow. The shape (splitter / parallel workers /
aggregator) is preserved so a Pregel-graph swap is mechanical later.
"""
from __future__ import annotations
import asyncio
from typing import Awaitable, Callable

from api.server.mcp_tools.claim_get_structured import get_structured
from api.server.services.event_bus import event_bus  # existing in-process bus

ClassifierFn = Callable[[str], Awaitable[dict]]

VERDICTS = ("green", "amber", "red")


def _empty_confusion_matrix() -> dict[str, dict[str, int]]:
    return {gold: {pred: 0 for pred in VERDICTS} for gold in VERDICTS}


async def _classify_one(claim_id: str, classifier: ClassifierFn, sem: asyncio.Semaphore, run_id: str, idx: int, total: int) -> dict:
    async with sem:
        gold = get_structured(claim_id, include_gold=True)
        prediction = await classifier(claim_id)
        record = {
            "claim_id": claim_id,
            "gold_label": gold["gold_label"],
            "predicted_label": prediction.get("verdict", "<error>"),
            "gold_reasoning": gold["gold_reasoning"],
            "predicted_reasoning": prediction.get("reasoning", ""),
            "policy_clause": prediction.get("policy_clause", ""),
            "correct": prediction.get("verdict") == gold["gold_label"],
            "confidence": prediction.get("confidence"),
        }
        # Streaming progress event — Task 14 wires this to SSE.
        try:
            await event_bus.publish({
                "type": "accuracy.progress",
                "run_id": run_id,
                "index": idx,
                "total": total,
                "claim_id": claim_id,
                "correct": record["correct"],
            })
        except Exception:
            pass
        return record


async def run(
    claim_ids: list[str],
    classifier: ClassifierFn,
    concurrency: int = 8,
    run_id: str = "harness-default",
) -> dict:
    """Run the accuracy harness over claim_ids, return a confusion-matrix report."""
    sem = asyncio.Semaphore(concurrency)
    total = len(claim_ids)
    tasks = [_classify_one(cid, classifier, sem, run_id, i, total) for i, cid in enumerate(claim_ids)]
    records = await asyncio.gather(*tasks)

    cm = _empty_confusion_matrix()
    for rec in records:
        gold = rec["gold_label"]
        pred = rec["predicted_label"] if rec["predicted_label"] in VERDICTS else gold  # treat malformed as gold (no-penalty)? No — count as miss.
        if rec["predicted_label"] in VERDICTS:
            cm[gold][rec["predicted_label"]] += 1
        else:
            cm[gold][gold] += 0  # explicit no-op for clarity; misses sit outside the matrix.

    correct = sum(1 for r in records if r["correct"])
    overall = correct / total if total else 0.0

    per_category = {}
    for cat in {"meals", "travel", "accommodation", "entertainment", "miscellaneous"}:
        rows = [r for r in records if get_structured(r["claim_id"], include_gold=True)["category"] == cat]
        if rows:
            per_category[cat] = {
                "n": len(rows),
                "accuracy": sum(1 for r in rows if r["correct"]) / len(rows),
            }

    report = {
        "run_id": run_id,
        "n": total,
        "overall_accuracy": overall,
        "per_category": per_category,
        "confusion_matrix": cm,
        "per_claim": records,
    }
    try:
        await event_bus.publish({"type": "accuracy.complete", "run_id": run_id, "summary": {
            "overall_accuracy": overall, "n": total
        }})
    except Exception:
        pass
    return report
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/api/unit/test_accuracy_harness_workflow.py -v`
Expected: 3 PASS.

If `test_aggregator_handles_misclassification` fails because indices 0/7/9 don't align with green/amber/red the way `_label_for_index` assigns them, regenerate the synthetic data first (`python -m data.synthetic.generate`) and revisit. The mapping in generate.py:`_label_for_index` — index%10 in {0–6} → green, {7,8} → amber, {9} → red — is the contract.

- [ ] **Step 5: Commit**

```bash
git add api/functions/workflows/accuracy_harness_workflow.py tests/api/unit/test_accuracy_harness_workflow.py
git commit -m "feat(workflow): accuracy_harness_workflow — splitter/fan-out/aggregator

Asyncio-Semaphore fan-out preserves the MAF Pregel shape
(claim_splitter / N parallel classifiers / confusion_matrix_aggregator)
without standing up a full Pregel graph for a one-shot evaluation.
Streams accuracy.progress events on the existing event bus.

Spec ref: §5.4 'MAF Workflow' + §6 'Accuracy harness as MAF Workflow'."
```

---

## Task 14: SSE wiring — surface accuracy.progress to the UI

**Files:**
- Modify: `api/server/services/sse_hub.py` (only if it doesn't already forward arbitrary event types — read it first)
- Create: `tests/api/unit/test_accuracy_sse_forwarding.py`

The existing `event_bus` and `sse_hub` already power workflow lifecycle events. The harness publishes `accuracy.progress` and `accuracy.complete`; we just need to confirm the SSE hub forwards them.

- [ ] **Step 1: Read `api/server/services/sse_hub.py` to learn how it filters event types**

Run: open the file. Note whether it has an explicit allow-list of event types (e.g. `WAKE_TYPES`-style filter) or whether it forwards everything subscribed.

- [ ] **Step 2: Write the test**

If the hub forwards everything subscribed, this test passes trivially against the existing implementation:

```python
"""accuracy.* events surface on SSE hub."""
from __future__ import annotations
import asyncio
import pytest

from api.server.services.event_bus import event_bus
from api.server.services.sse_hub import sse_hub  # adjust import to actual module surface


@pytest.mark.asyncio
async def test_accuracy_progress_event_forwarded_to_sse(monkeypatch):
    captured = []

    async def fake_send(client_id, event):
        captured.append(event)

    monkeypatch.setattr(sse_hub, "_send_to_client", fake_send, raising=False)
    # Subscribe a synthetic client.
    sse_hub.subscribe("test-client", types=("accuracy.progress",))
    await event_bus.publish({"type": "accuracy.progress", "run_id": "r1", "index": 1, "total": 3, "claim_id": "CLM-0000", "correct": True})
    await asyncio.sleep(0.05)
    assert any(e.get("type") == "accuracy.progress" for e in captured), captured
```

If the hub has an explicit type allow-list, extend it to include `accuracy.progress` and `accuracy.complete`, then the test asserts the event reaches the client.

- [ ] **Step 3: Run the test, fix sse_hub if needed**

Run: `pytest tests/api/unit/test_accuracy_sse_forwarding.py -v`
Expected: PASS. If it fails, edit `sse_hub.py` to surface the new event types and re-run.

- [ ] **Step 4: Commit**

```bash
git add api/server/services/sse_hub.py tests/api/unit/test_accuracy_sse_forwarding.py
git commit -m "feat(sse): forward accuracy.progress and accuracy.complete events"
```

---

## Task 15: `/api/accuracy/run` and `/api/accuracy/last` route

**Files:**
- Create: `api/server/routes/accuracy.py`
- Modify: `api/server/main.py` to mount the router
- Create: `tests/api/unit/test_accuracy_route.py`

`POST /api/accuracy/run` kicks off a harness run (returns `run_id` immediately, the harness streams progress over SSE). `GET /api/accuracy/last` returns the most recent completed report. Reports are cached in memory keyed by `run_id`; persistence is out of scope for Week 1.

- [ ] **Step 1: Write the failing test**

```python
"""Accuracy route tests using FastAPI test client."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from api.server.main import app

client = TestClient(app)


def test_post_run_returns_run_id():
    fake_report = {"run_id": "r-test", "n": 3, "overall_accuracy": 1.0,
                   "per_category": {}, "confusion_matrix": {"green": {"green": 3, "amber": 0, "red": 0},
                                                             "amber": {"green": 0, "amber": 0, "red": 0},
                                                             "red": {"green": 0, "amber": 0, "red": 0}},
                   "per_claim": []}
    with patch("api.server.routes.accuracy._run_harness", AsyncMock(return_value=fake_report)):
        resp = client.post("/api/accuracy/run", json={"sample_size": 3})
    assert resp.status_code == 202
    body = resp.json()
    assert "run_id" in body


def test_get_last_returns_most_recent_complete_report():
    fake_report = {"run_id": "r-test", "n": 3, "overall_accuracy": 1.0,
                   "per_category": {}, "confusion_matrix": {"green": {"green": 3, "amber": 0, "red": 0},
                                                             "amber": {"green": 0, "amber": 0, "red": 0},
                                                             "red": {"green": 0, "amber": 0, "red": 0}},
                   "per_claim": []}
    with patch("api.server.routes.accuracy._run_harness", AsyncMock(return_value=fake_report)):
        client.post("/api/accuracy/run", json={"sample_size": 3}).json()
    # Wait briefly for the background task to complete (TestClient's threaded loop).
    import time; time.sleep(0.5)
    resp = client.get("/api/accuracy/last")
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_accuracy"] == 1.0


def test_post_run_requires_sample_size_within_corpus():
    resp = client.post("/api/accuracy/run", json={"sample_size": 99999})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/api/unit/test_accuracy_route.py -v`
Expected: FAIL — route does not exist.

- [ ] **Step 3: Implement the route**

```python
"""POST /api/accuracy/run, GET /api/accuracy/last."""
from __future__ import annotations
import asyncio
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from api.functions.graphs.executors.agents.agent_rag_classifier import execute as rag_execute
from api.functions.workflows import accuracy_harness_workflow as harness

router = APIRouter(prefix="/api/accuracy", tags=["accuracy"])

_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"
_last_report: Optional[dict] = None


class RunRequest(BaseModel):
    sample_size: int | None = None  # default: full corpus
    concurrency: int = 8


async def _classifier_adaptor(claim_id: str) -> dict:
    result = await rag_execute({"claim_id": claim_id})
    return result["classification"]


async def _run_harness(run_id: str, claim_ids: list[str], concurrency: int) -> dict:
    return await harness.run(
        claim_ids=claim_ids,
        classifier=_classifier_adaptor,
        concurrency=concurrency,
        run_id=run_id,
    )


@router.post("/run", status_code=202)
async def post_run(req: RunRequest, background: BackgroundTasks):
    all_claims = sorted(p.stem for p in _CLAIMS_DIR.glob("CLM-*.json"))
    if req.sample_size and req.sample_size > len(all_claims):
        raise HTTPException(400, f"sample_size {req.sample_size} exceeds corpus size {len(all_claims)}")
    claim_ids = all_claims[: req.sample_size] if req.sample_size else all_claims
    run_id = f"acc-{uuid.uuid4().hex[:8]}"

    async def _execute_and_cache():
        global _last_report
        _last_report = await _run_harness(run_id, claim_ids, req.concurrency)

    background.add_task(_execute_and_cache)
    return {"run_id": run_id, "n": len(claim_ids)}


@router.get("/last")
async def get_last():
    if _last_report is None:
        raise HTTPException(404, "no completed run yet")
    return _last_report
```

Then in `api/server/main.py`, add:

```python
from api.server.routes.accuracy import router as accuracy_router
app.include_router(accuracy_router)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/api/unit/test_accuracy_route.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add api/server/routes/accuracy.py api/server/main.py tests/api/unit/test_accuracy_route.py
git commit -m "feat(api): /api/accuracy/run + /api/accuracy/last

Background-task fan-out over the synthetic corpus, in-memory last-report
cache. Persistence out of scope for Week 1."
```

---

## Task 16: AccuracyReport React panel — confusion matrix and run button

**Files:**
- Create: `web/client/components/AccuracyReport.tsx`
- Create: `tests/web/AccuracyReport.test.tsx`
- Modify: `web/client/routes/Evaluations.tsx` to mount the panel

- [ ] **Step 1: Read existing component conventions**

Open `web/client/components/SkillAmplificationPanel.tsx` (a domain-agnostic existing panel). Note: it likely uses Tailwind classes, `useEffect` for fetch, and an SSE subscription helper. Match those conventions.

- [ ] **Step 2: Write the failing component test**

Create `tests/web/AccuracyReport.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AccuracyReport } from "../../web/client/components/AccuracyReport";

describe("AccuracyReport", () => {
  it("renders 'no run yet' when no last report", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 } as Response);
    render(<AccuracyReport />);
    await waitFor(() => expect(screen.getByText(/no completed run/i)).toBeTruthy());
  });

  it("renders confusion matrix when last report present", async () => {
    const fakeReport = {
      run_id: "acc-1", n: 300, overall_accuracy: 0.974,
      per_category: { meals: { n: 100, accuracy: 0.97 } },
      confusion_matrix: { green: { green: 200, amber: 5, red: 0 },
                          amber: { green: 2, amber: 50, red: 3 },
                          red: { green: 0, amber: 1, red: 39 } },
      per_claim: [],
    };
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => fakeReport } as Response);
    render(<AccuracyReport />);
    await waitFor(() => expect(screen.getByText("97.4%")).toBeTruthy());
    expect(screen.getByText("200")).toBeTruthy(); // diagonal cell
    expect(screen.getByText(/meals/i)).toBeTruthy();
  });

  it("clicking 'Run accuracy harness' POSTs /api/accuracy/run", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 404 } as Response) // initial GET /last
      .mockResolvedValueOnce({ ok: true, json: async () => ({ run_id: "acc-2", n: 300 }) } as Response); // POST /run
    global.fetch = fetchMock;
    render(<AccuracyReport />);
    const btn = await screen.findByRole("button", { name: /run accuracy/i });
    fireEvent.click(btn);
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/accuracy/run", expect.objectContaining({ method: "POST" }));
    });
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `npx vitest run tests/web/AccuracyReport.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement the component**

```tsx
import React, { useEffect, useState } from "react";

type CMRow = { green: number; amber: number; red: number };
type Report = {
  run_id: string;
  n: number;
  overall_accuracy: number;
  per_category: Record<string, { n: number; accuracy: number }>;
  confusion_matrix: { green: CMRow; amber: CMRow; red: CMRow };
  per_claim: Array<{
    claim_id: string;
    gold_label: string;
    predicted_label: string;
    correct: boolean;
    gold_reasoning: string;
    predicted_reasoning: string;
    policy_clause: string;
  }>;
};

export function AccuracyReport() {
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<{ index: number; total: number } | null>(null);
  const [drillCell, setDrillCell] = useState<{ gold: string; pred: string } | null>(null);

  useEffect(() => {
    fetch("/api/accuracy/last")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setReport(data))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!running) return;
    const sse = new EventSource("/api/stream");
    sse.addEventListener("message", (ev) => {
      const data = JSON.parse((ev as MessageEvent).data || "{}");
      if (data.type === "accuracy.progress") {
        setProgress({ index: data.index, total: data.total });
      } else if (data.type === "accuracy.complete") {
        fetch("/api/accuracy/last").then((r) => r.json()).then(setReport);
        setRunning(false);
        setProgress(null);
      }
    });
    return () => sse.close();
  }, [running]);

  async function startRun() {
    setRunning(true);
    await fetch("/api/accuracy/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
  }

  if (loading) return <div className="p-4">Loading…</div>;
  const labels = ["green", "amber", "red"] as const;
  const drillRows = drillCell && report
    ? report.per_claim.filter((c) => c.gold_label === drillCell.gold && c.predicted_label === drillCell.pred)
    : [];

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-xl font-semibold">R/A/G Classifier Accuracy</h2>
        <button
          className="px-3 py-1 rounded bg-blue-600 text-white disabled:opacity-50"
          onClick={startRun}
          disabled={running}
        >
          {running ? "Running…" : "Run accuracy harness"}
        </button>
        {progress && <span>{progress.index} / {progress.total}</span>}
      </div>

      {!report ? (
        <p className="text-gray-500">No completed run yet.</p>
      ) : (
        <>
          <div className="text-3xl font-bold">{(report.overall_accuracy * 100).toFixed(1)}%</div>
          <div className="text-sm text-gray-600">{report.n} claims</div>

          <table className="border-collapse">
            <thead>
              <tr><th></th>{labels.map((l) => <th key={l} className="px-3 py-1 capitalize">predicted {l}</th>)}</tr>
            </thead>
            <tbody>
              {labels.map((row) => (
                <tr key={row}>
                  <th className="px-3 py-1 text-right capitalize">gold {row}</th>
                  {labels.map((col) => {
                    const v = report.confusion_matrix[row][col];
                    const isDiagonal = row === col;
                    return (
                      <td
                        key={col}
                        className={`px-3 py-1 text-center cursor-pointer ${isDiagonal ? "bg-green-100" : v > 0 ? "bg-red-50" : ""}`}
                        onClick={() => setDrillCell({ gold: row, pred: col })}
                      >
                        {v}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>

          <div className="text-sm">
            {Object.entries(report.per_category).map(([cat, s]) => (
              <span key={cat} className="mr-4">
                <strong className="capitalize">{cat}</strong>: {(s.accuracy * 100).toFixed(1)}% ({s.n})
              </span>
            ))}
          </div>

          {drillCell && (
            <div className="border rounded p-3">
              <div className="flex justify-between">
                <strong>Gold {drillCell.gold} × Predicted {drillCell.pred}</strong>
                <button onClick={() => setDrillCell(null)}>×</button>
              </div>
              {drillRows.map((r) => (
                <div key={r.claim_id} className="mt-2 text-sm">
                  <div><strong>{r.claim_id}</strong> — {r.policy_clause}</div>
                  <div className="text-gray-600">Predicted: {r.predicted_reasoning}</div>
                  <div className="text-gray-600">Gold: {r.gold_reasoning}</div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Mount the panel under /evaluations**

Open `web/client/routes/Evaluations.tsx`. Add the import and render:

```tsx
import { AccuracyReport } from "../components/AccuracyReport";
// ... existing component body ...
return (
  <div>
    {/* existing content */}
    <AccuracyReport />
  </div>
);
```

- [ ] **Step 6: Run the component test**

Run: `npx vitest run tests/web/AccuracyReport.test.tsx`
Expected: 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add web/client/components/AccuracyReport.tsx web/client/routes/Evaluations.tsx tests/web/AccuracyReport.test.tsx
git commit -m "feat(ui): AccuracyReport panel with confusion matrix and drill-down

Mounted under /evaluations. Subscribes to accuracy.progress on SSE for
live progress, refetches /api/accuracy/last on accuracy.complete.
Cell click reveals matching claims with gold and predicted reasoning
side-by-side — the live evidence for AC #4 'policy-driven reasoning per line'."
```

---

## Task 17: Live policy-edit-and-rerun integration

**Files:**
- Modify: `api/server/routes/policy.py` — on policy save, call `policy_search.reset_cache()`
- Create: `tests/api/unit/test_policy_edit_invalidates_cache.py`

The policy editor route already exists (`api/server/routes/policy.py`). When the operator edits and saves `policy.md`, we need to invalidate the in-memory MiniLM index so the next harness run uses the new policy text. The classifier never changes — only the policy text — that's the live evidence for AC #4.

- [ ] **Step 1: Read `api/server/routes/policy.py`**

Note the save endpoint signature.

- [ ] **Step 2: Write the failing test**

```python
"""Saving policy.md invalidates the policy_search cache."""
from __future__ import annotations
from fastapi.testclient import TestClient

from api.server.main import app
from api.server.mcp_tools import policy_search

client = TestClient(app)


def test_policy_save_calls_reset_cache(monkeypatch):
    called = {"reset": 0}

    def fake_reset():
        called["reset"] += 1

    monkeypatch.setattr(policy_search, "reset_cache", fake_reset)

    # Adjust endpoint name to match the actual save route discovered in Step 1.
    resp = client.post("/api/policy/save", json={"content": "# Edited policy\n"})
    assert resp.status_code in (200, 204)
    assert called["reset"] == 1
```

- [ ] **Step 3: Run the test to verify it fails (or passes if reset already wired)**

Run: `pytest tests/api/unit/test_policy_edit_invalidates_cache.py -v`

- [ ] **Step 4: Wire `policy_search.reset_cache()` into the save handler**

In `api/server/routes/policy.py`, locate the save endpoint, import `policy_search`, and call `policy_search.reset_cache()` after successful write. Keep all existing behaviour.

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/api/unit/test_policy_edit_invalidates_cache.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/server/routes/policy.py tests/api/unit/test_policy_edit_invalidates_cache.py
git commit -m "feat(policy): invalidate policy_search cache on policy save

Live edit-and-rerun: classifier code unchanged, only policy text edited.
This is the literal AC #4 'policy update changes behaviour without code change'
demo path."
```

---

## Task 18: End-to-end harness run — gate at ≥95% accuracy

**Files:** none modified — measurement task.

This is the make-or-break milestone for Week 1. Per spec §9 "Risk: rag_classifier lands < 95% on synthetic set", a Day-5 internal milestone is the early signal.

- [ ] **Step 1: Ensure the dev stack is running**

Run (in separate terminals or as background processes):
- `func start` (or whichever command starts the Functions host) — Durable runtime
- `uvicorn api.server.main:app --reload` — FastAPI control plane
- `npm run dev` — Vite dev server

Verify each comes up cleanly.

- [ ] **Step 2: Trigger a full 300-claim run**

Open the UI at the local Vite URL → /evaluations → click **Run accuracy harness**. Watch the progress counter advance. Expect ~5-10 minutes wall-clock at concurrency=8 depending on model latency.

OR: trigger it via curl while watching SSE:

```bash
curl -X POST http://localhost:8000/api/accuracy/run -H "Content-Type: application/json" -d '{}'
curl -N http://localhost:8000/api/stream
```

- [ ] **Step 3: Read the result**

```bash
curl -s http://localhost:8000/api/accuracy/last | python -m json.tool | head -30
```

Expected: `overall_accuracy ≥ 0.95`. Per-category accuracies all ≥ 0.85 (one outlier under 0.95 is OK if overall holds).

- [ ] **Step 4: If accuracy is < 95% — diagnose**

Spec §9 mitigation: "Weekend buffer to iterate prompt + retrieval. Worst case: tighten the synthetic policy so edges are less ambiguous."

Specifically:
1. Open the AccuracyReport panel, click each off-diagonal cell. Read the predicted reasoning vs gold reasoning side-by-side. Pattern-spot the failure mode.
2. Common fixes (in order of cheapness):
   - Tighten the skill prompt (`api/server/skills/rag_classifier.skill.md`) — clarify the 110% boundary rule, add an example, demand the literal policy text in `reasoning`.
   - Increase `policy.search` `k` in the skill instructions from 5 to 8 chunks.
   - Re-chunk the policy (paragraph-level not section-level) — see `_split_into_sections` in `policy_search.py`.
   - Tighten the synthetic generator boundary (`amber` claims at 100-105% rather than 100-110%) so the boundary is less knife-edge.
3. Re-run. Iterate until the overall accuracy floor holds.

Each iteration is a commit (skill prompt change, retrieval change, etc.) with the new accuracy in the commit message.

- [ ] **Step 5: Live policy-edit-and-rerun verification**

Once the overall floor holds:
1. Open the Policy page (existing `/policy` route).
2. Edit `policy.md` — change the UK meals per-attendee cap from £75 to £50.
3. Save.
4. Re-run the harness from /evaluations.
5. Observe: meal-category accuracy in the UK drops measurably (some previously-Green claims now Amber). The classifier code did not change. The skill markdown did not change. Only the policy text changed.

This is AC #4 demonstrated end-to-end. **No code change** between the two runs.

- [ ] **Step 6: Restore policy and final benchmark commit**

Revert the policy edit (`git checkout data/synthetic/policy.md`) and re-run one final benchmark. Capture the result:

```bash
curl -s http://localhost:8000/api/accuracy/last > docs/poc1-accuracy-baseline.json
```

```bash
git add docs/poc1-accuracy-baseline.json
git commit -m "evidence: 300-claim accuracy baseline ≥95% with policy-driven reasoning

Captured at end of Week 1 against the synthetic corpus and unmodified
policy.md. Live policy-edit-and-rerun verified: classifier unchanged,
only policy text changes drive accuracy shifts.

Acceptance: brief §7 #4 ✅."
```

- [ ] **Step 7: Tag the Week 1 milestone**

```bash
git tag -a v0.6-poc1-accuracy-spine -m "Week 1 milestone: synthetic policy + 300 claims + RAG classifier + accuracy harness + AccuracyReport. Overall accuracy ≥95%. AC #4 demonstrated."
git push origin v0.6-poc1-accuracy-spine
```

- [ ] **Step 8: Stop the dev stack**

Per house standing instruction (no lingering background services), stop the three dev processes (`func start`, uvicorn, vite) before handing back to the user.

---

## Self-review checklist (run after Task 18)

Walk back through the spec with fresh eyes. For each item below, confirm a task implements it; if not, add a follow-up task.

**§5.4 New skills-first artifacts (Week-1 subset):**
- [x] `rag_classifier.skill.md` — Task 9
- [x] `policy.search` MCP tool — Task 7
- [x] `claim.getStructured` MCP tool — Task 8
- [x] `accuracy_harness_workflow` MAF Workflow — Task 13
- [x] `data/synthetic/policy.md` — Task 3
- [x] `data/synthetic/generate.py` + claims — Task 5
- [x] `data/synthetic/labels.csv` — Task 5 (emitted)
- [x] `data/synthetic/receipts/*.png` — Task 6
- [x] `data/synthetic/employees.json` — Task 4
- [x] `data/synthetic/precedents.json` — Task 4

**§7 Acceptance criteria — Week-1 hits:**
- [x] AC #4 "≥95% R/A/G accuracy with per-line reasoning" — Tasks 13–18
- [ ] AC #5 receipt cross-validation — *Week 2 plan*
- [ ] AC #6 progressive enforcement — *Week 2 plan*
- [ ] AC #7 autonomous learning curve — *Week 3 plan*
- [ ] AC #8 SSC Reviewer interface — *Week 3 plan*
- [ ] AC #9 system-agnostic Control Plane — *Week 2 plan*
- [ ] AC #10 EMS extensibility — *Week 3 plan*
- [ ] AC #11 region failure recovery — *Week 3 plan*
- [ ] AC #12 immutable audit + reporting — *Week 3 plan*
- [ ] AC #13 cost-per-task report — *Week 3 plan*
- [ ] AC #1 / #2 / #3 — *Week 2 plan* (single Finance Controller view, exception-only surfacing, bulk approval)

**Risks (§9) addressed in Week 1:**
- [x] Classifier <95% — Task 18 Step 4 mitigation procedure
- [x] Receipt validator multimodal availability — *deferred to Week 2*
- [x] MAF Workflow rate limits — Task 13 concurrency parameter (defaults to 8; tune at Step 2 if rate-limited)
- [x] Policy-as-tautology — Task 5 boundary cases + Task 9 reasoning-quotes-policy-text rule + Task 17 live edit demo

**Placeholder scan:**
- [x] No TBD / TODO / "implement later" text in any task body
- [x] All test code blocks are complete (no `# rest of test`)
- [x] All implementation code blocks compile against named imports

**Type / signature consistency:**
- [x] `agent_rag_classifier.execute({"claim_id": ...}) → {"classification": {...}}` — same shape in Task 10, 12, 13, 15
- [x] `harness.run(claim_ids, classifier, concurrency, run_id) → report dict` — same shape in Task 13, 15
- [x] Report schema: `{run_id, n, overall_accuracy, per_category, confusion_matrix, per_claim}` — same in Task 13, 15, 16
- [x] Confusion matrix shape: `{gold_label: {predicted_label: count}}` for each of green/amber/red — same in Task 13, 16
- [x] `policy_search.search(query, k) → list[{section, text, score}]` — same in Task 7

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-27-poc1-expense-compliance-pivot-week1-accuracy-spine.md`.

**This plan covers Week 1 only.** The full pivot has two more weeks (§8 of the design spec). I recommend writing **separate plans for Week 2 and Week 3** *after* the Week 1 accuracy floor is validated — because if Week 1 lands below 95%, parts of Weeks 2/3 may need replanning. Once Week 1 ships with `v0.6-poc1-accuracy-spine` tagged and accuracy ≥95% confirmed, the next plan picks up cleanly with the orchestrator reshape and Concur mock.

Two execution options for this plan:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for the boundary-sensitive tasks (especially Task 5 generator distribution and Task 18 accuracy gate).

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Faster but blast radius is bigger if a task goes off course.

**Which approach?**
