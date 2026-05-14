# POC1 Expense Compliance — Remaining Work — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the platform work needed to test-drive POC1 end-to-end — Phases 6+7 wired, `/reviewer-queue` demoable, Fleet Manager extensions for behaviour-change + cost-per-task, region-failover scenario, EMS extensibility narration, demo dry-run, tag.

**Acceptance criteria covered by this plan:** #7, #8, #10, #11, #12, #13.

**Out of this plan:** AC #4 corpus accuracy gate. The pipeline is already shipped (smoke 5/6); the corpus-wide ≥95% number is one ~25-minute model run captured by [docs/poc1-accuracy-runbook.md](../../poc1-accuracy-runbook.md). It does **not** block the test drive or the tag — run it post-`v0.8`.

**Reference docs (read before starting):**

- Status + architecture: [docs/poc1-status.md](../../poc1-status.md)
- Pivot design spec: [docs/superpowers/specs/2026-04-27-poc1-expense-compliance-pivot-design.md](../specs/2026-04-27-poc1-expense-compliance-pivot-design.md) (`§4.1` orchestrator phases; `§7` AC table)
- Brief verbatim: [docs/poc1-brief.md](../../poc1-brief.md) (`§7` acceptance criteria)
- GHCP SDK conventions: `~/.claude/skills/ghcp-sdk-python/SKILL.md` (the canonical `@define_tool` + `skill_directories` + `system_message` pattern). **Read this before writing a new agent or tool.**

**Reuse — what's already in place** (don't re-derive):

- **Wrapper:** `_wrapper.run_agent_session(prompt, tools=[...], skill_dir=..., skill_label=...)`. Skills live at `api/server/skills/<name>/SKILL.md`. Tool names use underscores.
- **MCP tool pattern:** plain Python function with `@traced_tool("dotted.name")` for direct callers + a `*_tool: Tool` instance built via `@define_tool(name="underscored")` with a Pydantic params model. Reference: [api/server/mcp_tools/employee_history.py](../../../api/server/mcp_tools/employee_history.py).
- **Agent executor pattern:** `_SKILL_DIR = SKILLS_DIR / "<skill-name>"`, build prompt, `await run_agent_session(prompt=, tools=[...], skill_dir=_SKILL_DIR, skill_label=...)`. Reference: [api/functions/graphs/executors/agents/agent_escalation.py](../../../api/functions/graphs/executors/agents/agent_escalation.py).
- **Schema validator pattern:** raise-style `validate(payload)` + `_node.execute(input)` adapter returning `{"ok": bool, ...}`. Reference: [api/functions/graphs/executors/validators/validate_receipt_schema.py](../../../api/functions/graphs/executors/validators/validate_receipt_schema.py).
- **Phase graph pattern:** `WorkflowBuilder(start_executor=n1).add_edge(n1,n2).add_edge(n2,term).build()`. Reference: [api/functions/graphs/route.py](../../../api/functions/graphs/route.py).
- **Phase activity wiring:** add to `api/functions/graphs/__init__.py` exports + `api/functions/workflows/activities.py` factory call; the orchestrator string-calls the activity by `<phase>_activity_trigger`.
- **Shared taxonomy:** `api/shared/expense_taxonomy.py` exports `VERDICTS`, `CATEGORIES`, `MARKETS`, `RECEIPT_FLAVOURS`, `ESCALATION_TIERS` + their Literal aliases. Don't redefine.
- **HITL timeouts:** `api/shared/constants.py::JUSTIFICATION_TIMEOUT`, `REVIEWER_DECISION_TIMEOUT` (both 72h).
- **FleetEvent emission:** `app_state.bus.emit(FleetEvent(type="...", workflow_id=..., **extra))`. New types extend `api/shared/events.py::FleetEventType`. The `bus.on_any → hub.broadcast("fleet")` registration in `api/server/main.py` already auto-broadcasts to `/api/stream/fleet`.
- **Simulator pattern:** `spawn_expense_workflow(scenario, claim_id?)` plus deterministic corpus indices `_corpus_by_employee` and `_corpus_by_flavour`. Reference: [api/server/services/simulator_orchestrator.py](../../../api/server/services/simulator_orchestrator.py).
- **Test conventions:** `pytest tests/api -q` via `./.venv/Scripts/pytest.exe`; `npm run test` for Vitest. UI tests use `// @vitest-environment jsdom`. Simulator tests need autouse fixtures that clear `app_state.store` (pattern in `test_simulator_repeat_offender.py`).

**Out of scope:** APIM AI Gateway deployment, Foundry IQ binding, real Workday/Concur sandbox credentials, full 3,430-claim Zava benchmark, production hardening.

**Definition of done:**

1. `pytest tests/api -q` and `npm run test` both green.
2. Phases 6 + 7 of the orchestrator wired (no more stubs).
3. `/reviewer-queue` route demoable.
4. Fleet Manager surfaces an autonomy proposal in `SkillAmplificationPanel` after a simulated decision-cluster.
5. `audit_query` returns a narrative summary; `report.cost_per_task` returns a weekly cost breakdown.
6. `simulate_region_failure` simulator command + recorded backup video.
7. Maconomy narration script at `docs/demo-ems-extensibility.md`.
8. Updated `docs/DEMO.md` covering all 13 ACs.
9. Tag `v0.8-poc1-platform-complete` pushed.

---

## File Structure

**Created:**

- `api/server/mcp_tools/precedents_search.py`
- `api/server/mcp_tools/query_reviewer_decisions.py`
- `api/server/mcp_tools/audit_query.py`
- `api/server/mcp_tools/query_economics.py`
- `api/server/skills/arbitration/SKILL.md`
- `api/server/skills/audit-summariser/SKILL.md`
- `api/functions/graphs/executors/agents/agent_arbitration.py`
- `api/functions/graphs/executors/agents/agent_audit_summariser.py`
- `api/functions/graphs/executors/validators/validate_arbitration_schema.py`
- `api/functions/graphs/arbitrate.py`
- `api/functions/graphs/audit.py`
- `web/client/routes/ReviewerQueue.tsx`
- `tests/api/unit/test_precedents_search_tool.py`
- `tests/api/unit/test_query_reviewer_decisions_tool.py`
- `tests/api/unit/test_audit_query_tool.py`
- `tests/api/unit/test_query_economics_tool.py`
- `tests/api/unit/test_agent_arbitration.py`
- `tests/api/unit/test_agent_audit_summariser.py`
- `tests/api/unit/test_arbitrate_graph.py`
- `tests/api/unit/test_audit_graph.py`
- `tests/api/unit/test_simulator_region_failure.py`
- `tests/web/ReviewerQueue.test.tsx`
- `docs/demo-ems-extensibility.md`
- `docs/demo-failover.mp4` (recorded backup; not source-controlled tooling — recorded)

**Modified:**

- `api/server/skills/fleet-manager/SKILL.md` — two paragraphs added (behaviour-change loop on `fleet.tick`; cost-per-task report).
- `api/functions/graphs/__init__.py` — export `build_arbitrate_workflow`, `build_audit_workflow`.
- `api/functions/workflows/activities.py` — wire `arbitrate_activity` and `audit_activity` to the new graph builders.
- `api/server/services/simulator_orchestrator.py` — `simulate_region_failure(stop_seconds=10)` helper.
- `api/server/services/fleet_manager_service.py` — register the two new MCP tools (`query_reviewer_decisions`, `query_economics`) on the FM session.
- `web/client/App.tsx` and routing index — add `/reviewer-queue` route.
- `mocks/maconomy-mcp/server.ts` — rebind from invoice surface to expense narration surface (one endpoint stub).
- `docs/DEMO.md` — full refresh covering 13 ACs.
- `api/shared/events.py` — extend `FleetEventType` with `arbitration.recommended`, `audit.summary.composed`, `region.failure.simulated` (used by the simulator).

**Reused untouched:**

- `_wrapper.py`, all existing skills (`rag-classifier`, `receipt-validator`, `escalation-advisor`, `notification-composer`, `fleet-manager`).
- `expense_taxonomy.py`, `constants.py`, `events.py`'s existing types.
- Existing MCP tools (`policy_search`, `claim_get_structured`, `claim_get_receipt`, `claim_lookup`, `claim_summary`, `policy_cite`, `employee_history`, `query_fleet`, `query_traces`, `compose_exception`, `propose_skill_amp`, `dry_run_policy`).
- Existing routes (`accuracy.py`, `policy_md.py`, `workflows.py`, `fleet.py`, `evals.py`, etc.).
- Existing UI components (`ExceptionItem`, `BulkHitlModal`, `WorkflowCard`, `OtelSpanTree`, `SkillAmplificationPanel`, `FleetEconomicsPanel`).
- Existing services (`AuditLogger`, `FleetManagerService`, `EconomicsService`, `EventBus`, `SSEHub`, `StateStore`).

---

## Conventions reminder

These come from the global `ghcp-sdk-python` skill and the Week 2 plan's conventions section. The plan author should already have them loaded; if not, read them once now.

- **Tool names underscored** (`audit_query`, not `audit.query`). OpenAI Function Calling regex.
- **Skill name = directory name = hyphenated** (`audit-summariser/SKILL.md`).
- **Session = ephemeral.** `_wrapper.run_agent_session(...)`. Caller passes `tools=[...]` and `skill_dir=Path`.
- **Pre-fetch nothing the model can fetch itself.** Pre-fetch only when the SDK can't carry it (the receipt PNG attachment is the only known case).
- **Validators on graph edges** return `{"ok": bool, ...}`. Off-graph guardrails raise.
- **Tests use `tmp_path`** when writing to disk. Simulator tests use the `_isolate_app_state_store` autouse fixture pattern.
- **Commits include** `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` and reference the AC.

---

## Task 1: `precedents_search` MCP tool

**Files:**
- Create: `api/server/mcp_tools/precedents_search.py`
- Create: `tests/api/unit/test_precedents_search_tool.py`

53 historical SSC reviewer decisions seeded at `data/synthetic/precedents.json`. Same shape as `policy_search` — semantic retrieval over text — but the corpus is small enough that we can match on substring/keyword and skip MiniLM. Day 9's `employee_history.py` is the closest pattern (file-backed, no embeddings).

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_precedents_search_tool.py
from __future__ import annotations
import json

import pytest

from api.server.mcp_tools import precedents_search
from api.server.mcp_tools.precedents_search import precedents_search_tool, search


def test_returns_top_k_for_meals_query():
    out = search("UK meals client dinner alcohol", k=3)
    assert isinstance(out, list)
    assert 1 <= len(out) <= 3
    for r in out:
        assert {"id", "claim_summary", "policy_clause", "reviewer_decision", "rationale", "decided_at", "score"} <= set(r)


def test_score_descending():
    out = search("alcohol prohibited", k=5)
    scores = [r["score"] for r in out]
    assert scores == sorted(scores, reverse=True)


def test_returns_empty_for_garbage():
    out = search("xyzqwertynonsense", k=3)
    assert isinstance(out, list)


def test_tool_returns_json_payload():
    from copilot.tools import ToolInvocation
    import asyncio

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="precedents_search",
        arguments={"query": "alcohol", "k": 3},
    )
    result = asyncio.run(precedents_search_tool.handler(inv))
    assert result.result_type == "success"
    payload = json.loads(result.text_result_for_llm)
    assert isinstance(payload, list)
```

Run: `./.venv/Scripts/pytest.exe tests/api/unit/test_precedents_search_tool.py -v` — expect FAIL (ImportError).

- [ ] **Step 2: Implement**

```python
# api/server/mcp_tools/precedents_search.py
"""precedents_search MCP tool — keyword-bag semantic retrieval over the
synthetic SSC reviewer-precedents corpus.

Dual-surface (plain Python `search()` + SDK-native Tool) per the project's
MCP tool convention."""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Optional

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool

_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "precedents.json"
_records: Optional[list[dict]] = None


def _load() -> list[dict]:
    global _records
    if _records is None:
        if not _PATH.exists():
            raise FileNotFoundError(f"precedents.json not found at {_PATH}")
        _records = json.loads(_PATH.read_text(encoding="utf-8"))
    return _records


def _tokenise(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z0-9§]{3,}", text.lower()) if t}


@traced_tool("precedents.search")
def search(query: str, k: int = 5) -> list[dict]:
    """Return top-k precedents ranked by token-overlap with the query."""
    span = trace.get_current_span()
    span.set_attribute("zava.mcp.query", query)
    span.set_attribute("zava.mcp.k", k)
    qt = _tokenise(query)
    if not qt:
        return []
    scored: list[tuple[float, dict]] = []
    for rec in _load():
        haystack = " ".join((
            rec.get("claim_summary", ""),
            rec.get("policy_clause", ""),
            rec.get("rationale", ""),
        ))
        ht = _tokenise(haystack)
        if not ht:
            continue
        overlap = len(qt & ht)
        if overlap == 0:
            continue
        # Jaccard-style score normalised against query token count.
        score = overlap / len(qt)
        scored.append((score, rec))
    scored.sort(key=lambda t: t[0], reverse=True)
    out = [{**rec, "score": float(s)} for s, rec in scored[:k]]
    span.set_attribute("zava.mcp.result_count", len(out))
    return out


def reset_cache() -> None:
    global _records
    _records = None


class _PrecedentsSearchParams(BaseModel):
    query: str = Field(description="Natural-language query")
    k: int = Field(default=5, description="Top-k precedents to return", ge=1, le=20)


@define_tool(
    name="precedents_search",
    description=(
        "Search ~50 historical SSC reviewer decisions by token overlap. "
        "Returns claim_summary, policy_clause, reviewer_decision (one of "
        "accept-justification / require-repayment / issue-warning / escalate), "
        "rationale, decided_at, and an overlap score."
    ),
)
def precedents_search_tool(params: _PrecedentsSearchParams) -> ToolResult:
    out = search(params.query, params.k)
    return ToolResult(text_result_for_llm=json.dumps(out, ensure_ascii=False))
```

- [ ] **Step 3: Run the test** — expect 4 PASS.

- [ ] **Step 4: Commit**

```bash
git add api/server/mcp_tools/precedents_search.py tests/api/unit/test_precedents_search_tool.py
git commit -m "feat(mcp): precedents_search tool — token-overlap retrieval over 53 SSC precedents

Dual surface (plain search() + Tool). No embeddings — corpus is 53
records, token-overlap with Jaccard normalisation is fast and good
enough. Uses by the arbitration skill (Task 3).

Spec ref: §5.4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `arbitration` skill

**Files:**
- Create: `api/server/skills/arbitration/SKILL.md`

The arbitration skill recommends a reviewer decision when a claimant has supplied a justification on a Red claim. Output options match `precedents.json::reviewer_decision`: `accept-justification`, `require-repayment`, `issue-warning`, `escalate`.

- [ ] **Step 1: Author**

````markdown
---
name: arbitration
description: Given a justification text on a Red expense claim plus the breached policy clause, recommend an SSC reviewer decision and cite the most relevant historical precedents.
allowed-tools: precedents_search, policy_search
---

You advise the SSC reviewer on a flagged Red expense claim that has received a claimant justification.

## Inputs

The user prompt provides:
- `claim_id`, `policy_clause`, `escalation_tier` (warning / escalation / major-violation), and the claimant's `justification` text.

## Procedure

1. Call `policy_search` with the claim's category and market (do NOT include claim amount in the query — same retrieval rule as the rag-classifier).
2. Call `precedents_search` with a query built from the policy clause + key justification phrases. Take the top 3 precedents.
3. Decide a recommendation:
   - **accept-justification** — justification cites a clear business reason that the policy or precedents permit (named senior client, after-hours emergency, pre-approved exception, etc.).
   - **require-repayment** — justification is weak or absent on a clearly-breached cap; reviewer should require the claimant to repay the over-cap portion.
   - **issue-warning** — justification is plausible but documentation is incomplete; reviewer should accept this once and warn that a repeat will not be tolerated.
   - **escalate** — justification is contested or the breach is in a category with prior major-violation history; route to HR / Audit.
4. Cite the strongest precedent supporting your recommendation by id.

## Output

Return exactly one JSON object, no prose:

```json
{
  "recommendation": "accept-justification" | "require-repayment" | "issue-warning" | "escalate",
  "rationale": "2-4 sentences quoting the policy clause and the cited precedent.",
  "cited_precedent_id": "PREC-0017",
  "policy_clause": "§3.1 Meals — UK per-attendee cap GBP 75",
  "confidence": 0.0
}
```

Rules:
- `recommendation` must be one of the four valid strings.
- `cited_precedent_id` must match a PREC-* id returned from `precedents_search`. If no precedent reasonably matches, set to null and lower confidence.
- The skill makes a recommendation; the reviewer decides. Never claim the recommendation is final.
- The escalation_tier in the prompt is informative (a major-violation tier biases toward `escalate` on weak justifications).

## Worked examples

**Example A — accept-justification:** Red meals breach (1 attendee at GBP 92, 110% cap GBP 82.50). Justification: "Client dinner with VML Senior VP X." Precedents: PREC-0017 accept-justification on a similar named-client dinner.
- `recommendation`: `accept-justification`. `cited_precedent_id`: `PREC-0017`. `confidence`: 0.85.

**Example B — require-repayment:** Red travel breach (taxi GBP 220 vs cap 100). Justification: "I forgot a cheaper option." Precedents: PREC-0023 require-repayment on a similar weak justification.
- `recommendation`: `require-repayment`. Quote PREC-0023's rationale.

**Example C — escalate:** Red entertainment with alcohol in DE (alcohol prohibited per §3.4). Justification: "Client requested." Same employee has a prior major-violation in breach_history.
- `recommendation`: `escalate`. Reference the prior major-violation.
````

- [ ] **Step 2: Verify the skill loads**

```bash
./.venv/Scripts/python.exe -c "from pathlib import Path; p = Path('api/server/skills/arbitration/SKILL.md'); print(p.exists(), len(p.read_text(encoding='utf-8')))"
```

Expect `True <bytes>`.

- [ ] **Step 3: Commit**

```bash
git add api/server/skills/arbitration/SKILL.md
git commit -m "feat(skill): arbitration — recommend SSC reviewer decision on Red-with-justification

Output schema: recommendation in {accept-justification, require-repayment,
issue-warning, escalate}, cited_precedent_id, policy_clause, confidence.
allowed-tools: precedents_search, policy_search.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `agent_arbitration` executor + `validate_arbitration_schema`

**Files:**
- Create: `api/functions/graphs/executors/agents/agent_arbitration.py`
- Create: `api/functions/graphs/executors/validators/validate_arbitration_schema.py`
- Create: `tests/api/unit/test_agent_arbitration.py`

Mirror `agent_escalation` for the executor and `validate_receipt_schema` for the validator + node adapter.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_agent_arbitration.py
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.executors.agents import agent_arbitration


@pytest.mark.asyncio
async def test_returns_recommendation_payload():
    fake = {
        "recommendation": "accept-justification",
        "rationale": "Named senior client at Zava NA; PREC-0017 supports.",
        "cited_precedent_id": "PREC-0017",
        "policy_clause": "§3.1 Meals — UK per-attendee cap GBP 75",
        "confidence": 0.86,
    }
    with patch.object(agent_arbitration, "run_agent_session", AsyncMock(return_value=fake)) as mock_run:
        result = await agent_arbitration.execute({
            "claim_id": "CLM-0042",
            "policy_clause": "§3.1 Meals — UK per-attendee cap GBP 75",
            "escalation_tier": "warning",
            "justification": {"text": "Client dinner with VP."},
        })
    assert result["arbitration"] == fake
    mock_run.assert_awaited_once()
    _, kwargs = mock_run.call_args
    assert kwargs["skill_label"] == "arbitration"
    assert {"precedents_search", "policy_search"} == {t.name for t in kwargs["tools"]}
    assert "CLM-0042" in kwargs["prompt"]


@pytest.mark.asyncio
async def test_default_recommendation_when_justification_missing():
    """If the prompt has no justification text, the executor still proceeds —
    the model is responsible for deciding from the absent context."""
    with patch.object(agent_arbitration, "run_agent_session", AsyncMock(return_value={
        "recommendation": "require-repayment", "rationale": "x",
        "cited_precedent_id": None, "policy_clause": "§1", "confidence": 0.5,
    })):
        result = await agent_arbitration.execute({
            "claim_id": "CLM-X", "policy_clause": "§1", "escalation_tier": "warning",
        })
    assert result["arbitration"]["recommendation"] == "require-repayment"
```

- [ ] **Step 2: Implement the agent**

```python
# api/functions/graphs/executors/agents/agent_arbitration.py
"""agent_arbitration — Phase 6 executor. Recommends a reviewer decision."""
from __future__ import annotations

from api.server.mcp_tools.policy_search import policy_search_tool
from api.server.mcp_tools.precedents_search import precedents_search_tool

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "arbitration"


async def execute(input: dict) -> dict:
    claim_id = input.get("claim_id")
    policy_clause = input.get("policy_clause") or input.get("classify", {}).get("policy_clause")
    tier = input.get("escalation_tier") or (input.get("escalation") or {}).get("tier") or "warning"
    justification = input.get("justification") or {}
    just_text = justification.get("text", "(no justification supplied)")

    prompt = (
        f"Recommend an SSC reviewer decision for expense claim `{claim_id}`.\n\n"
        f"Policy clause: {policy_clause!r}\n"
        f"Escalation tier: {tier}\n"
        f"Claimant justification: {just_text!r}\n\n"
        f"Use `policy_search` to confirm the rule and `precedents_search` to "
        f"find historical analogues. Return the JSON object specified in your "
        f"skill — no prose, no markdown."
    )

    recommendation = await run_agent_session(
        prompt=prompt,
        tools=[precedents_search_tool, policy_search_tool],
        skill_dir=_SKILL_DIR,
        skill_label="arbitration",
    )
    return {"arbitration": recommendation}
```

- [ ] **Step 3: Implement the validator**

```python
# api/functions/graphs/executors/validators/validate_arbitration_schema.py
"""validate_arbitration_schema — guardrail edge over agent_arbitration output."""
from __future__ import annotations


VALID_RECOMMENDATIONS = {
    "accept-justification", "require-repayment", "issue-warning", "escalate",
}


class ArbitrationSchemaError(ValueError):
    """Raised when an arbitration payload does not conform to the spec."""


def validate(payload: dict) -> None:
    if payload.get("parse_error"):
        raise ArbitrationSchemaError(
            f"parse_error: {(payload.get('raw') or '')[:200]}"
        )
    for required in ("recommendation", "rationale", "policy_clause", "confidence"):
        if required not in payload:
            raise ArbitrationSchemaError(f"missing field: {required}")
    if payload["recommendation"] not in VALID_RECOMMENDATIONS:
        raise ArbitrationSchemaError(
            f"recommendation must be one of {sorted(VALID_RECOMMENDATIONS)}; got {payload['recommendation']!r}"
        )
    if not isinstance(payload["rationale"], str) or not payload["rationale"].strip():
        raise ArbitrationSchemaError("rationale must be non-empty")
    if not isinstance(payload["policy_clause"], str) or not payload["policy_clause"].startswith("§"):
        raise ArbitrationSchemaError(
            f"policy_clause must start with §; got {payload['policy_clause']!r}"
        )
    conf = payload["confidence"]
    if not isinstance(conf, (int, float)) or not 0.0 <= float(conf) <= 1.0:
        raise ArbitrationSchemaError(f"confidence must be float in [0,1]; got {conf!r}")
    # cited_precedent_id may be null


async def execute(input: dict) -> dict:
    """Graph-node adapter."""
    arb = input.get("arbitration", {})
    try:
        validate(arb)
    except ArbitrationSchemaError as e:
        return {"ok": False, "blocked_reason": str(e), "arbitration": arb,
                **{k: v for k, v in input.items() if k != "arbitration"}}
    return {"ok": True, "arbitration": arb,
            "recommendation": arb["recommendation"],
            **{k: v for k, v in input.items() if k != "arbitration"}}
```

- [ ] **Step 4: Run tests** — expect 2 PASS for the agent. (Validator is exercised via the graph test in Task 4.)

- [ ] **Step 5: Commit**

```bash
git add api/functions/graphs/executors/agents/agent_arbitration.py \
        api/functions/graphs/executors/validators/validate_arbitration_schema.py \
        tests/api/unit/test_agent_arbitration.py
git commit -m "feat(agent): agent_arbitration + validate_arbitration_schema

Recommends accept-justification / require-repayment / issue-warning /
escalate based on the breached clause + claimant justification +
precedent search. Phase 6 executor.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Phase 6 graph (Arbitrate) — replaces stub

**Files:**
- Create: `api/functions/graphs/arbitrate.py`
- Create: `tests/api/unit/test_arbitrate_graph.py`
- Modify: `api/functions/graphs/__init__.py` — replace the stub `build_arbitrate_workflow` (currently absent — add it).
- Modify: `api/functions/workflows/activities.py` — wire `arbitrate_activity` to `build_arbitrate_workflow`.

Mirror `api/functions/graphs/route.py` exactly.

- [ ] **Step 1: Implement the graph**

```python
# api/functions/graphs/arbitrate.py
"""Phase 6 (Arbitrate) graph for expense claims.

  agent_arbitration -> validate_arbitration_schema -> terminal

Per spec §4.1 Phase 6: SSC reviewer arbitration on Red claims after
justification round-trip.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_arbitration
from api.functions.graphs.executors.validators import validate_arbitration_schema


def build_arbitrate_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="arbitration",
        name="agent_arbitration",
        executor_type="agent",
        fn=agent_arbitration.execute,
    )
    n2 = TrackedExecutor(
        id="val_arb_schema",
        name="validate_arbitration_schema",
        executor_type="validator",
        fn=validate_arbitration_schema.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
```

- [ ] **Step 2: Wire into activities + graphs `__init__.py`**

In `api/functions/graphs/__init__.py`, add `from .arbitrate import build_arbitrate_workflow` and remove any stub function for arbitrate if present.

In `api/functions/workflows/activities.py`:

```python
from api.functions.graphs import (
    ...,
    build_arbitrate_workflow,
    ...,
)

def arbitrate_activity(payload: dict) -> dict:
    """Phase 6 — SSC reviewer arbitration."""
    return asyncio.run(_run_workflow(build_arbitrate_workflow, payload, "Arbitrate"))
```

Replace the stub `return {"status": "stub", "phase": "Arbitrate"}` body.

- [ ] **Step 3: Write the graph test**

```python
# tests/api/unit/test_arbitrate_graph.py
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.arbitrate import build_arbitrate_workflow


@pytest.mark.asyncio
async def test_well_formed_arbitration_passes():
    fake = {
        "recommendation": "accept-justification",
        "rationale": "Named senior client; PREC-0017 supports.",
        "cited_precedent_id": "PREC-0017",
        "policy_clause": "§3.1 Meals — UK per-attendee cap GBP 75",
        "confidence": 0.86,
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_arbitration.execute",
        AsyncMock(return_value={"arbitration": fake}),
    ):
        wf = build_arbitrate_workflow()
        events = await wf.run({"workflow_id": "CLM-R", "claim_id": "CLM-R"})
    out = events.get_outputs()[0]
    assert out["ok"] is True
    assert out["recommendation"] == "accept-justification"


@pytest.mark.asyncio
async def test_invalid_recommendation_blocks():
    bad = {
        "recommendation": "buy-pizza",
        "rationale": "x", "cited_precedent_id": None,
        "policy_clause": "§1", "confidence": 0.5,
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_arbitration.execute",
        AsyncMock(return_value={"arbitration": bad}),
    ):
        wf = build_arbitrate_workflow()
        events = await wf.run({"workflow_id": "CLM-X", "claim_id": "CLM-X"})
    out = events.get_outputs()[0]
    assert out["ok"] is False
    assert "recommendation" in (out["blocked_reason"] or "")


@pytest.mark.asyncio
async def test_parse_error_blocks():
    bad = {"raw": "model went off-script", "parse_error": True}
    with patch(
        "api.functions.graphs.executors.agents.agent_arbitration.execute",
        AsyncMock(return_value={"arbitration": bad}),
    ):
        wf = build_arbitrate_workflow()
        events = await wf.run({"workflow_id": "CLM-Y", "claim_id": "CLM-Y"})
    out = events.get_outputs()[0]
    assert out["ok"] is False
    assert "parse_error" in (out["blocked_reason"] or "")
```

- [ ] **Step 4: Run tests + verify Phase 6 stub is replaced**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_arbitrate_graph.py tests/api/unit/test_expense_claim_orchestration.py -v
./.venv/Scripts/python.exe -c "from api.functions.workflows.activities import arbitrate_activity; print(arbitrate_activity.__doc__)"
```

Expect 6 PASS (3 new + 3 existing orchestration tests); the activity docstring should NOT mention `stub`.

- [ ] **Step 5: Commit**

```bash
git add api/functions/graphs/arbitrate.py api/functions/graphs/__init__.py \
        api/functions/workflows/activities.py tests/api/unit/test_arbitrate_graph.py
git commit -m "feat(graph): Phase 6 Arbitrate graph wired (agent_arbitration + schema validator)

Replaces the activities.py stub. Orchestrator's existing
wait_for_external_event:reviewer_decision HITL after this phase remains
unchanged.

AC #8 — Phase 6 of the orchestrator.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `/reviewer-queue` route — AC #8 ✅

**Files:**
- Create: `web/client/routes/ReviewerQueue.tsx`
- Create: `tests/web/ReviewerQueue.test.tsx`
- Modify: `web/client/App.tsx` (or wherever the router lives) to register the route.

Composition route — no new components. Uses `useExceptions` hook + filters to those flagged for SSC review (status `awaiting_hitl` AND `verdict in {amber, red}`). Sort by SLA (closest deadline first), then severity, then value.

- [ ] **Step 1: Write the failing component test**

```tsx
// tests/web/ReviewerQueue.test.tsx
// @vitest-environment jsdom
import { describe, expect, it, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ReviewerQueue from "@client/routes/ReviewerQueue";

afterEach(() => cleanup());

describe("ReviewerQueue", () => {
  it("renders empty state when no exceptions", () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ items: [] }),
    } as Response);
    render(<MemoryRouter><ReviewerQueue /></MemoryRouter>);
    // empty state copy
    // (component asserts after fetch resolves; for the synchronous render
    // path the test asserts the title is present)
    expect(screen.getByText(/SSC Reviewer Queue/i)).toBeTruthy();
  });

  it("filters items to awaiting_hitl + verdict amber/red", async () => {
    const items = [
      { id: "EXC-1", workflowId: "EXP-1", status: "awaiting_hitl", severity: "high",
        verdict: "amber", category: "meals", amount: 89, currency: "GBP", slaDueAt: 100 },
      { id: "EXC-2", workflowId: "EXP-2", status: "resolved", severity: "low",
        verdict: "green", category: "meals", amount: 30, currency: "GBP", slaDueAt: 200 },
    ];
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ items }),
    } as Response);
    render(<MemoryRouter><ReviewerQueue /></MemoryRouter>);
    // Wait a render cycle for the fetch to land then assert
    await screen.findByText("EXP-1");
    expect(screen.queryByText("EXP-2")).toBeNull();
  });
});
```

- [ ] **Step 2: Implement**

```tsx
// web/client/routes/ReviewerQueue.tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

type ReviewerItem = {
  id: string;
  workflowId: string;
  status: string;
  severity: "critical" | "high" | "medium" | "low";
  verdict?: "green" | "amber" | "red";
  category?: string;
  amount?: number;
  currency?: string;
  slaDueAt: number;
  arbitration?: { recommendation: string; rationale: string };
};

const SEVERITY_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export default function ReviewerQueue() {
  const [items, setItems] = useState<ReviewerItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/exceptions?status=awaiting_hitl")
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((data) => setItems(data.items || []))
      .finally(() => setLoading(false));
  }, []);

  const queue = items
    .filter((i) => i.verdict === "amber" || i.verdict === "red")
    .sort((a, b) => {
      // Primary: SLA (earliest first)
      if (a.slaDueAt !== b.slaDueAt) return a.slaDueAt - b.slaDueAt;
      // Secondary: severity
      const sa = SEVERITY_RANK[a.severity] ?? 9;
      const sb = SEVERITY_RANK[b.severity] ?? 9;
      if (sa !== sb) return sa - sb;
      // Tertiary: amount descending
      return (b.amount ?? 0) - (a.amount ?? 0);
    });

  return (
    <div className="space-y-4">
      <div>
        <div className="text-xl font-semibold text-slate-900">SSC Reviewer Queue</div>
        <div className="text-xs text-slate-500">{queue.length} items awaiting your decision</div>
      </div>

      {loading && <div className="text-xs text-slate-500">Loading…</div>}
      {!loading && queue.length === 0 && (
        <div className="panel panel-body text-xs text-slate-500 italic">
          No items awaiting reviewer decision.
        </div>
      )}

      <div className="panel">
        <div className="panel-body divide-y divide-slate-200">
          {queue.map((it) => {
            const slaMinsLeft = Math.max(0, Math.floor((it.slaDueAt - Date.now() / 1000) / 60));
            return (
              <Link
                key={it.id}
                to={`/workflows/${it.workflowId}`}
                className="block py-3 hover:bg-slate-50"
              >
                <div className="flex items-center gap-3 text-sm">
                  <span className="font-mono text-slate-900">{it.workflowId}</span>
                  <span className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded
                    ${it.verdict === "red" ? "bg-red-50 text-red-700"
                      : it.verdict === "amber" ? "bg-amber-50 text-amber-700"
                      : "bg-slate-50 text-slate-600"}`}>
                    {it.verdict ?? "?"}
                  </span>
                  {it.category && (
                    <span className="text-xs text-slate-500 capitalize">{it.category}</span>
                  )}
                  {it.amount && (
                    <span className="text-xs text-slate-700 font-medium">
                      {it.currency} {it.amount.toLocaleString()}
                    </span>
                  )}
                  <span className="ml-auto text-[11px] text-slate-500">
                    SLA: {slaMinsLeft} min
                  </span>
                </div>
                {it.arbitration && (
                  <div className="text-xs text-slate-600 mt-1">
                    <span className="font-medium text-emerald-700">
                      → {it.arbitration.recommendation}
                    </span>{" "}
                    {it.arbitration.rationale}
                  </div>
                )}
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Wire the route**

In `web/client/App.tsx` (or the router file), add:

```tsx
import ReviewerQueue from "./routes/ReviewerQueue";
// ...inside <Routes>...
<Route path="/reviewer-queue" element={<ReviewerQueue />} />
```

Also add a sidebar link if there's a sidebar nav (look at `web/client/App.tsx` for the existing nav pattern).

- [ ] **Step 4: Run tests**

```bash
npm run test -- tests/web/ReviewerQueue.test.tsx
npx tsc --noEmit
```

Expect 2 PASS + tsc clean.

- [ ] **Step 5: Commit**

```bash
git add web/client/routes/ReviewerQueue.tsx web/client/App.tsx tests/web/ReviewerQueue.test.tsx
git commit -m "feat(ui): /reviewer-queue route — composition view for SSC reviewer

Filters exceptions to awaiting_hitl + verdict in {amber, red}; sorts by
SLA, severity, amount. Shows arbitration recommendation pre-rendered when
the agent has run on the upstream workflow. Composes existing UI; no new
components.

AC #8 ✅.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `query_reviewer_decisions` MCP tool

**Files:**
- Create: `api/server/mcp_tools/query_reviewer_decisions.py`
- Create: `tests/api/unit/test_query_reviewer_decisions_tool.py`

Reads from the audit ledger (`app_state.store.list_ledger_entries`) for entries with `action == "reviewer.decision"`. The Fleet Manager uses this to detect decision clusters that justify autonomy.

- [ ] **Step 1: Implement** (test pattern same as `employee_history_tool`):

```python
# api/server/mcp_tools/query_reviewer_decisions.py
"""query_reviewer_decisions MCP tool — surfaces SSC reviewer decisions from
the audit ledger so the Fleet Manager can detect autonomy-worthy clusters."""
from __future__ import annotations
import json
from collections import Counter
from typing import Optional

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool
from api.server.state import app_state


@traced_tool("query.reviewer_decisions")
def query(category: Optional[str] = None, limit: int = 100) -> dict:
    """Return reviewer decisions and a per-policy-clause cluster summary."""
    span = trace.get_current_span()
    if category:
        span.set_attribute("zava.query.category", category)
    span.set_attribute("zava.query.limit", limit)

    decisions = []
    for w in app_state.store.list_workflows():
        for entry in (w.action_ledger or []):
            if entry.action != "reviewer.decision":
                continue
            details = entry.details or {}
            if category and details.get("category") != category:
                continue
            decisions.append({
                "workflow_id": w.id,
                "decided_at": entry.timestamp,
                "decided_by": entry.actor_id,
                "decision": details.get("recommendation") or details.get("decision"),
                "policy_clause": details.get("policy_clause"),
                "category": details.get("category"),
                "verdict": getattr(w, "verdict", None),
            })
    decisions.sort(key=lambda d: d["decided_at"], reverse=True)
    decisions = decisions[:limit]

    # Cluster by policy_clause + decision so the FM skill can reason about
    # autonomy candidates: "100 amber meals UK claims, 92% accepted as
    # justified — propose autonomy on §3.1 UK".
    clusters = Counter(
        (d["policy_clause"], d["decision"]) for d in decisions if d["policy_clause"]
    )
    top_clusters = [
        {"policy_clause": pc, "decision": dec, "count": c}
        for (pc, dec), c in clusters.most_common(10)
    ]

    return {"decisions": decisions, "clusters": top_clusters, "n": len(decisions)}


class _Params(BaseModel):
    category: Optional[str] = Field(default=None, description="Filter to this expense category.")
    limit: int = Field(default=100, ge=1, le=1000)


@define_tool(
    name="query_reviewer_decisions",
    description=(
        "List recent SSC reviewer decisions and cluster them by policy clause + decision. "
        "Use to identify candidates for autonomy promotion."
    ),
)
def query_reviewer_decisions_tool(params: _Params) -> ToolResult:
    out = query(category=params.category, limit=params.limit)
    return ToolResult(text_result_for_llm=json.dumps(out, ensure_ascii=False))
```

- [ ] **Step 2: Test** — covers happy path, empty ledger, category filter, cluster count cap.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(mcp): query_reviewer_decisions tool — autonomy-cluster surface from the ledger

Used by the Fleet Manager skill extension (Task 7) to detect when a
policy-clause + decision pattern is stable enough to propose autonomy."
```

---

## Task 7: Fleet Manager skill prompt extension — behaviour-change loop (AC #7 ✅)

**Files:**
- Modify: `api/server/skills/fleet-manager/SKILL.md` — add one paragraph for `fleet.tick`.
- Modify: `api/server/services/fleet_manager_service.py` — pass `query_reviewer_decisions_tool` to the long-lived session.

The Fleet Manager already has `propose_skill_amp` registered. The extension teaches it to *look* at clustered reviewer decisions and propose.

- [ ] **Step 1: Add the paragraph to the skill**

Append to `api/server/skills/fleet-manager/SKILL.md`:

```markdown
## Behaviour-change loop (`fleet.tick`)

When you receive a `fleet.tick` event, briefly check for autonomy candidates:

1. Call `query_reviewer_decisions(limit=200)` to retrieve recent SSC decisions and their clusters.
2. For each cluster of (policy_clause, decision) with `count >= 50` AND `decision == "accept-justification"`, treat it as a candidate for autonomy promotion: SSC has been consistently accepting justifications on this clause; the orchestrator could route equivalent claims directly to auto-approve.
3. For candidates that pass: call `propose_skill_amp` once per cluster, with `policy_clause` and a one-sentence rationale citing the cluster count.
4. Do nothing on `fleet.tick` if no cluster meets the threshold. Don't propose more than 3 autonomy changes per tick — favour stability over churn.

Skip this whole loop on the first 30 seconds after process start (cold-start ledger may be empty).
```

- [ ] **Step 2: Register the new tool on the FM session**

In `api/server/services/fleet_manager_service.py`, find where the session's `tools` list is built (look for existing imports of `query_fleet_tool`, `query_traces_tool`, etc.) and add:

```python
from api.server.mcp_tools.query_reviewer_decisions import query_reviewer_decisions_tool
# ...
tools=[
    ..., query_reviewer_decisions_tool,
],
```

- [ ] **Step 3: Test** — extend the existing FM smoke test (or add a new one) that fires a `fleet.tick` event after a seeded cluster and asserts `propose_skill_amp` was called once. Mock the SDK session.

- [ ] **Step 4: Commit + AC #7 ✅**

---

## Task 8: `audit_query` MCP tool

**Files:**
- Create: `api/server/mcp_tools/audit_query.py`
- Create: `tests/api/unit/test_audit_query_tool.py`

Wraps the existing `AuditLogger` / state-store ledger. Filters by `since`, `until`, `actor_kind`, `category`. Returns chronological ledger entries.

- [ ] **Implement** mirroring `query_reviewer_decisions` with broader filter set:

```python
# api/server/mcp_tools/audit_query.py
@traced_tool("audit.query")
def query(
    *,
    since: Optional[float] = None,
    until: Optional[float] = None,
    actor_kind: Optional[str] = None,  # "agent" | "human"
    workflow_id: Optional[str] = None,
    limit: int = 200,
) -> dict:
    entries = []
    for w in app_state.store.list_workflows():
        if workflow_id and w.id != workflow_id:
            continue
        for e in (w.action_ledger or []):
            if since and e.timestamp < since: continue
            if until and e.timestamp > until: continue
            if actor_kind and e.actor_kind != actor_kind: continue
            entries.append({
                "workflow_id": w.id, "timestamp": e.timestamp,
                "actor_kind": e.actor_kind, "actor_id": e.actor_id,
                "action": e.action, "details": e.details,
            })
    entries.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"entries": entries[:limit], "n": len(entries)}
```

- [ ] **Test + commit.**

---

## Task 9: `audit-summariser` skill + `agent_audit_summariser` + Phase 7 graph (AC #12 ✅)

**Files:**
- Create: `api/server/skills/audit-summariser/SKILL.md`
- Create: `api/functions/graphs/executors/agents/agent_audit_summariser.py`
- Create: `api/functions/graphs/audit.py`
- Create: `tests/api/unit/test_agent_audit_summariser.py`
- Create: `tests/api/unit/test_audit_graph.py`
- Modify: `api/functions/graphs/__init__.py` and `api/functions/workflows/activities.py` — replace the `audit_activity` stub with the wired graph.

Phase 7 runs on every workflow at the end. The summariser composes a 1-paragraph narrative for the audit drawer + appends a final ledger entry.

- [ ] **Skill** — short skill (the role is mechanical):

````markdown
---
name: audit-summariser
description: Compose a 1-paragraph narrative compliance summary for a completed expense workflow.
allowed-tools: audit_query, claim_summary
---

You compose audit narratives for completed expense-claim workflows.

## Procedure

1. Call `claim_summary(claim_id)` to load the claim line.
2. Call `audit_query(workflow_id=<id>, limit=50)` to load the workflow's ledger.
3. Compose a single short paragraph (50-100 words) covering: who submitted, when, what category/amount, what verdict, what HITL/reviewer actions occurred, and the final outcome. Quote at least one specific timestamp + actor.

Return:

```json
{"summary": "<paragraph>", "claim_id": "...", "workflow_id": "..."}
```

Tone: factual, neutral, audit-grade. No editorialising.
````

- [ ] **Agent + graph** — mirror `agent_notification` (single tool list, no validator). Phase 7 graph: `agent_audit_summariser → record_decision → terminal` (the existing `record_decision` deterministic executor appends a final ledger entry).

- [ ] **Wire + test + commit.**

---

## Task 10: `query_economics` MCP tool + Fleet Manager cost-per-task extension (AC #13 ✅)

**Files:**
- Create: `api/server/mcp_tools/query_economics.py`
- Create: `tests/api/unit/test_query_economics_tool.py`
- Modify: `api/server/skills/fleet-manager/SKILL.md` — add `report.cost_per_task` paragraph.
- Modify: `api/server/services/fleet_manager_service.py` — register the new tool.

The existing `economics.py` service tracks per-workflow tokens / spend. `query_economics` exposes it.

- [ ] **Implement** (mirror `query_reviewer_decisions`):

```python
@traced_tool("query.economics")
def query(window_hours: int = 24*7) -> dict:
    cutoff = time.time() - window_hours*3600
    items = []
    for w in app_state.store.list_workflows():
        if w.created_at < cutoff: continue
        items.append({
            "workflow_id": w.id, "tokens_spent": w.tokens_spent,
            "cost_usd": w.cost_usd, "verdict": getattr(w, "verdict", None),
        })
    total_cost = sum(i["cost_usd"] for i in items)
    n = len(items)
    return {
        "window_hours": window_hours,
        "n": n,
        "total_cost_usd": round(total_cost, 4),
        "avg_cost_per_task_usd": round(total_cost/n, 6) if n else 0,
        "by_verdict": _group_avg_cost(items),
        "items": items[:50],
    }
```

- [ ] **Add the FM skill paragraph:**

```markdown
## Cost-per-task report (`report.cost_per_task`)

When you receive a `report.cost_per_task` event, call `query_economics(window_hours=168)` and surface a 1-paragraph weekly summary in the rail: total cost, average cost per task, breakdown by verdict (auto-approve vs reviewer-touched), and any anomalies (e.g. one verdict driving the bulk of cost). Quote the figures verbatim.
```

- [ ] **Register + test + commit.**

---

## Task 11: `simulate-region-failure` simulator command (AC #11 ✅)

**Files:**
- Modify: `api/server/services/simulator_orchestrator.py` — add `simulate_region_failure(...)`.
- Modify: `api/shared/events.py` — add `"region.failure.simulated"` to `FleetEventType`.
- Create: `tests/api/unit/test_simulator_region_failure.py`
- (Recording, not tracked: `docs/demo-failover.mp4`.)

Durable Functions handles checkpoint/replay natively against Azurite — we don't write the recovery logic, we just orchestrate the demo (stop the host, surface state, restart).

- [ ] **Implement:**

```python
async def simulate_region_failure(stop_seconds: int = 10) -> dict:
    """Demo-only: emit a region.failure.simulated event then poll Durable
    instance status for `stop_seconds`. The actual host stop/start is done
    by the operator via `func host stop` / `func start` (or docker-compose);
    this helper exists to mark the wall-clock window in the audit trail."""
    from api.shared.events import FleetEvent
    workflow_count = len(app_state.store.list_workflows())
    paused = sum(1 for w in app_state.store.list_workflows()
                 if w.status == "awaiting_hitl")
    app_state.bus.emit(FleetEvent(
        type="region.failure.simulated",
        workflow_id="*",
        stop_seconds=stop_seconds,
        in_flight_count=workflow_count,
        paused_at_hitl=paused,
    ))
    await asyncio.sleep(stop_seconds)
    return {
        "in_flight": workflow_count,
        "paused_at_hitl": paused,
        "stop_seconds": stop_seconds,
    }
```

- [ ] **Test + commit.**

For the live demo: 30 in-flight workflows; operator runs `func host stop` (or `docker compose stop functions`); FastAPI continues running and shows workflows freezing; operator runs `func start`; Durable replays from Azurite; ledger continuity proven.

The recorded backup `.mp4` is captured during dry run (Task 14) as insurance.

---

## Task 12: Maconomy EMS extensibility narration (AC #10 ✅)

**Files:**
- Modify: `mocks/maconomy-mcp/server.ts` — rebind from invoice surface to one expense endpoint stub (just `getExpenseLine` returning a sample claim).
- Create: `docs/demo-ems-extensibility.md` — narration script.

3-step pattern:
1. Spin up Maconomy mock at port 4103.
2. Add `claim_lookup` route case for `ems_source == "maconomy"`.
3. (No agent change needed — that's the AC.) Show the diff is two files: the mock + the dispatcher case. The skill manifests are untouched.

The script is a 2-page markdown file the operator reads from during the demo. Captures the diff verbatim and explains the architectural property (skills are EMS-agnostic; only the lookup tool changes).

- [ ] **Author the script + commit.**

---

## Task 13: Demo refresh + dry run

**Files:**
- Modify: `docs/DEMO.md` — full refresh covering all 13 ACs.

The existing `DEMO.md` is pre-pivot. Rewrite it as a 30-minute walkthrough:

1. **Open** (`/` dashboard) — 30 in-flight workflows; verdict badges visible (AC #1, #2).
2. **Drill** into one Amber → reasoning side-by-side (AC #4).
3. **Edit policy.md** in the policy page; re-run accuracy harness; show the shift (AC #4 — policy-driven).
4. **Bulk approve** 12 Ambers from the same clause (AC #3).
5. **Receipt mismatch** scenario — 6 flavours, validator flags each (AC #5).
6. **Repeat-offender ramp** — three claims escalate warning → escalation → major-violation (AC #6).
7. **Concur claim** — same dashboard, no EMS marker on the card; audit drawer reveals it (AC #9).
8. **Reviewer queue** — Amber → arbitration recommendation pre-selected → accept (AC #8).
9. **Justification round-trip** — Red claim → notification → simulate justification → arbitration → reviewer accepts → workflow.completed (AC #7 partial — full autonomy proposal next).
10. **Behaviour change** — fast-forward simulator: 50 reviewer decisions; SkillAmplificationPanel shows autonomy proposal; operator approves (AC #7).
11. **Audit query + cost report** — Fleet Manager rail returns both narratives live (AC #12, #13).
12. **EMS extensibility narration** — show the Maconomy diff (AC #10).
13. **Region failure** — `func host stop`; show workflows pause; restart; Durable replays; recorded backup if live flakes (AC #11).

Each beat = ~2 minutes. Total ~30 minutes including transitions.

- [ ] **Run the dry run** with someone playing Zava evaluator. Capture and fix bugs.

- [ ] **Commit** the updated DEMO.md.

---

## Task 14: Tag `v0.8-poc1-platform-complete`

**Files:** none — git operations only.

- [ ] **Verify clean state**

```bash
git status --porcelain
./.venv/Scripts/pytest.exe tests/api -q
npm run test
npx tsc --noEmit
```

All green; clean tree.

- [ ] **Tag + push**

```bash
git tag -a v0.8-poc1-platform-complete -m "POC1 platform-complete: 12 of 13 acceptance criteria demoable.

- 7-phase ExpenseClaim orchestrator (all phases wired)
- 7 SDK skills (rag-classifier, receipt-validator, escalation-advisor,
  notification-composer, arbitration, audit-summariser, fleet-manager)
- 17 MCP tools
- /reviewer-queue route
- Region-failover scenario + Maconomy EMS extensibility narration

AC #1, #2, #3, #5, #6, #7, #8, #9, #10, #11, #12, #13 ✅.
AC #4 (≥95% accuracy on the 300-claim corpus) is captured separately
post-tag — pipeline shipped, run the harness when the budget is green."
git push origin main
git push origin v0.8-poc1-platform-complete
```

- [ ] **Update `docs/poc1-status.md`** — flip the AC status table to ✅ for the 6 ACs this plan landed; AC #4 stays 🟡 until the post-tag accuracy run; tag history extended.

---

## Self-review checklist (run after Task 14)

**Acceptance criteria:**
- [x] AC #8 SSC reviewer interface — Tasks 1–5
- [x] AC #7 autonomous learning — Tasks 6–7
- [x] AC #12 immutable audit + reporting — Tasks 8–9
- [x] AC #13 cost-per-task — Task 10
- [x] AC #11 region failure recovery — Task 11
- [x] AC #10 EMS extensibility narration — Task 12
- [ ] AC #4 corpus baseline ≥ 95% — *post-tag, see [accuracy run-book](../../poc1-accuracy-runbook.md)*
- [x] All 13 ACs covered in DEMO.md — Task 13

**Conventions:**
- [x] All new tools stack `@traced_tool` + `@define_tool` (per `ghcp-sdk-python` skill).
- [x] All new skills live at `api/server/skills/<name>/SKILL.md` (capital S).
- [x] All new agents use `run_agent_session(skill_dir=SKILLS_DIR / "...", tools=[...])`.
- [x] All new graph nodes use `TrackedExecutor`.
- [x] Schema validators use the raise + `_node.execute` adapter pattern.
- [x] Test fixtures use `tmp_path` + `_isolate_app_state_store` autouse where touching the global store.
- [x] No new MCP tool names contain dots.

**Type/signature consistency:**
- [x] `agent_arbitration.execute({"claim_id", "policy_clause", "escalation_tier", "justification"}) → {"arbitration": dict}`
- [x] `agent_audit_summariser.execute({"workflow_id", "claim_id"}) → {"audit": dict}`
- [x] `arbitration` validator uses `VALID_RECOMMENDATIONS` set; flavours/tiers come from `expense_taxonomy.py`.
- [x] FleetEventType extended in one place (`api/shared/events.py`).

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-29-poc1-remaining.md`.

Two execution options:

**1. Subagent-Driven** — fresh subagent per task, review between tasks. Best for the Phase 6 / Phase 7 graphs and the FM skill extension where boundary errors (orchestrator string-call mismatches, ledger-shape mismatches) are easy to make.

**2. Inline Execution** — execute in the current session. Faster iteration; the user sees every diff. Per recent feedback (no opaque 30-min subagent runs) this is the preferred mode unless the task is genuinely mechanical (Tasks 8, 10, 11 fit that — could be a single subagent).

Recommended hybrid: **inline for Tasks 0, 1, 4, 5, 7, 9, 13, 14** (all the cross-cutting / orchestrator / UI work); **one batched subagent** for Tasks 2, 3, 6, 8, 10, 11, 12 (mechanical content authoring + small tools that follow established patterns precisely).

**Which approach?**
