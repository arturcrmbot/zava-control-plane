# Autonomous Domain Insights v1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the closed-loop persona governance system end-to-end (schema + runtime + HTTP + projection + cadence) without baking in any domain-specific persona behaviour.

**Architecture:** Compose existing pieces (entity graph, persona registry, persona_responder, AGT kernel, Decision-as-Policy, one-shot workflow spawn). Add exactly one new node kind (`Insight`), one new generic workflow type (`policy_set`), one helper (`active_policies_for`), three HTTP routes, one cadence loop in `persona_responder.attach()`, and a `summary_policy` block on persona SKILL.md. CEO is the only new persona shipped in v1; other personae stay unchanged. Per-domain `summary_policy` blocks (CFO, HR-head, etc.) and the Aurora demo scenario land later as v1.1+.

**Tech Stack:** Python 3.11, FastAPI, Kuzu 0.6.1, pytest, asyncio, React/Vite (blueprint UI).

**Spec:** `docs/superpowers/specs/2026-05-12-autonomous-domain-insights-design.md` (sections §1-§7, §10-§13 in scope; §8 Aurora scenario explicitly out for v1).

**Critical patterns to know before starting:**

- Persona SKILL.md files live at `api/server/personae/<role>/SKILL.md`. They are discovered by `_load_personae()` in `api/server/services/persona_responder.py:522`. The YAML frontmatter exposes `decision_policy: |` as a Python source block; `_compile_decision_policy()` (line 452) compiles it inside a sandbox with builtins from `_DECISION_BUILTINS` (line 411).
- The persona responder `attach(bus)` at `api/server/services/persona_responder.py:1190` is where the bus subscription + the existing `_sweep_loop` live. The new insight cadence loop belongs here too — same patterns, no new module-level state.
- Workflow projections live in `api/server/services/entity_projections/<workflow_type>.py`, each exposing `WORKFLOW_TYPE` and `project(workflow)`. They self-register in `entity_projections/__init__.py` via the `_DOMAIN_MODULES` tuple at line 165.
- Routes follow the pattern in `api/server/routes/accounts.py` — `router = APIRouter(prefix="/api/...")`, `actor: Actor = Depends(require_actor)`, `app_state.entities` for the graph.
- New routers are mounted via the tuple loop in `api/server/main.py:357`.
- Kuzu 0.6.1 quirks: see stored memories — no `SET n += $map` (use per-key clauses), `id STRING PRIMARY KEY` rejected inline (use trailing `PRIMARY KEY (id)`), reserved words (`starts`, `ends`) need backticks, LIMIT cannot be parameterised.

**Out of scope for v1 (deferred):** the entire spec §8 Aurora demo, CFO `summary_policy` block, ap_clerk/controller policy honouring, demo trigger route, persona voice/animation/ticker polish (spec §9). When v1 lands, the system is fully end-to-end runnable: CEO emits a calm meta-Insight every tick; the WorkflowDrawer fetches and renders it; the Approve button is wired to `policy_set` workflow spawn.

---

## Phase 0 — Worktree + baseline

### Task 0.1: Create isolated worktree

**Files:** none (git plumbing)

- [ ] **Step 1: Verify main is clean**

```bash
cd /Users/arturzielinski/dev/github-repos/zava-control-plane-poc1
git status
git log --oneline -3
```

Expected: clean tree, top commit `a01f68ff` (spec amendment).

- [ ] **Step 2: Create the worktree**

```bash
git worktree add -b feat/autonomous-insights-v1 .worktrees/autonomous-insights-v1 main
cd .worktrees/autonomous-insights-v1
```

Expected: new worktree at `.worktrees/autonomous-insights-v1` on branch `feat/autonomous-insights-v1`.

- [ ] **Step 3: Sync deps inside worktree**

```bash
uv sync
```

Expected: `Resolved … packages` then `Audited` lines, no failures.

- [ ] **Step 4: Capture baseline test count**

```bash
uv run pytest tests/api/server/services tests/api/server/routes -x --no-header -q 2>&1 | tail -5
```

Expected: write the pass/fail counts to a scratchpad. Every later regression run compares against this baseline (1522 pass / 17 known mock-server failures from main).

---

## Phase 1 — Schema additions (TDD)

Adds the `Insight` node kind to the graph and widens the verdict vocabulary to accept `freeze` / `unfreeze` / `cap`. No data writes yet; this phase only proves the schema bootstraps cleanly.

### Task 1.1: Add `freeze` / `unfreeze` / `cap` verdicts

**Files:**
- Modify: `api/server/services/decision_vocab.py`
- Test: `tests/api/server/services/test_decision_vocab.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/api/server/services/test_decision_vocab.py`:

```python
def test_freeze_unfreeze_cap_are_canonical():
    from api.server.services.decision_vocab import canonical_verdict, is_valid_verdict
    for v in ("freeze", "unfreeze", "cap"):
        assert is_valid_verdict(v), f"{v} should be a valid verdict"
        assert canonical_verdict(v) == v
        assert canonical_verdict(v.upper()) == v
        assert canonical_verdict(f"  {v}  ") == v


def test_policy_verdict_aliases():
    from api.server.services.decision_vocab import canonical_verdict
    assert canonical_verdict("frozen") == "freeze"
    assert canonical_verdict("unfrozen") == "unfreeze"
    assert canonical_verdict("capped") == "cap"
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/api/server/services/test_decision_vocab.py::test_freeze_unfreeze_cap_are_canonical -v
```

Expected: FAIL — `is_valid_verdict("freeze")` returns False today.

- [ ] **Step 3: Extend the vocabulary**

Edit `api/server/services/decision_vocab.py` — add `"freeze"`, `"unfreeze"`, `"cap"` to `VERDICTS` and add the three alias entries (`"frozen"` / `"unfrozen"` / `"capped"`) to `_ALIASES`. Annotate the additions with a short comment explaining they are policy verdicts written by `policy_set` workflows.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/api/server/services/test_decision_vocab.py -v
```

Expected: PASS — all decision_vocab tests, including the two new ones.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/decision_vocab.py tests/api/server/services/test_decision_vocab.py
git commit -m "feat(decision_vocab): add freeze/unfreeze/cap policy verdicts

Persona summary_policy blocks propose freeze/unfreeze/cap actions; on
approval a policy_set workflow records a Decision with the matching
verdict. Other personae query active policies via active_policies_for().

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```


---

### Task 1.2: Add `Insight` node table

**Files:**
- Modify: `api/server/services/entity_graph.py` (`_NODE_TABLES`, `_TIMESTAMP_KINDS`)
- Test: `tests/api/server/services/test_entity_graph_schema.py`

- [ ] **Step 1: Update the schema-test fixture**

Edit `tests/api/server/services/test_entity_graph_schema.py`. Locate `EXPECTED_NODE_TABLES = { ... }` (around line 13) and add `"Insight"` to the set.

- [ ] **Step 2: Run schema test — should fail**

```bash
uv run pytest tests/api/server/services/test_entity_graph_schema.py::test_show_tables_lists_exact_expected_tables -v
```

Expected: FAIL — `missing={'Insight'}`.

- [ ] **Step 3: Add `Insight` to `_NODE_TABLES`**

Edit `api/server/services/entity_graph.py`. After the last entry in `_NODE_TABLES` (around line 488 — the `CostCentre` table), append a new tuple. The DDL MUST use the trailing-`PRIMARY KEY (id)` form (Kuzu 0.6.1 rejects inline `id STRING PRIMARY KEY`):

```python
    (
        "Insight",
        """
        CREATE NODE TABLE IF NOT EXISTS Insight (
            id STRING,
            role STRING,
            scope STRING,
            decided_at TIMESTAMP,
            headline STRING,
            body STRING,
            kpis STRING,
            proposed_actions STRING,
            fingerprint STRING,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
```

Also extend `_TIMESTAMP_KINDS` (around line 506) by appending `"Insight"` so the `first_seen_at` / `last_seen_at` ALTER migration covers it.

- [ ] **Step 4: Run the schema test — should pass**

```bash
uv run pytest tests/api/server/services/test_entity_graph_schema.py -v
```

Expected: PASS — all schema tests.

- [ ] **Step 5: Add an upsert round-trip test**

Append to `tests/api/server/services/test_entity_graph_schema.py`. Add `from datetime import datetime` and `from api.server.services.entity_graph import EntityGraph, EntityWrite` at the top if not already imported, then:

```python
def test_insight_upsert_roundtrip(tmp_path: Path) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    g.upsert(EntityWrite(
        kind="Insight",
        id="INSIGHT-test-1",
        attrs={
            "role": "test",
            "scope": "test_scope",
            "decided_at": datetime.utcnow(),
            "headline": "hello",
            "body": "world",
            "kpis": "{}",
            "proposed_actions": "[]",
            "fingerprint": "abc123",
            "attributes": "{}",
        },
        source_workflows=(),
    ))
    rows = g.query("MATCH (i:Insight) RETURN i.id AS id, i.headline AS h")
    assert rows == [{"id": "INSIGHT-test-1", "h": "hello"}]
```

- [ ] **Step 6: Run new test**

```bash
uv run pytest tests/api/server/services/test_entity_graph_schema.py::test_insight_upsert_roundtrip -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add api/server/services/entity_graph.py tests/api/server/services/test_entity_graph_schema.py
git commit -m "feat(entity_graph): add Insight node kind

Insight is the only new node kind in autonomous-domain-insights v1.
Persona summary_policy blocks write one Insight per (role, fingerprint)
change; HTTP routes serve the latest per role.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 1.3: Surface `Insight` on the entities HTTP route

**Files:**
- Modify: `api/server/routes/entities.py` (`_KINDS`, `_PROJECT_FIELDS_BY_KIND`)
- Test: `tests/api/server/routes/` (whichever existing test asserts the kinds list)

- [ ] **Step 1: Find the kinds-list test**

```bash
grep -nR "Insight\|_KINDS\|expected_kinds" tests/api/server/routes/ | head
```

Locate the test that asserts the entities kinds list. Add `"Insight"` to the expected set.

- [ ] **Step 2: Run — should fail**

```bash
uv run pytest tests/api/server/routes/ -k "kinds or stats" -v
```

Expected: FAIL on the kinds assertion.

- [ ] **Step 3: Update `entities.py`**

Edit `api/server/routes/entities.py`. Append `"Insight"` to the `_KINDS` tuple (around line 30) and add an entry to `_PROJECT_FIELDS_BY_KIND` (around line 56):

```python
    "Insight": frozenset({
        "role", "scope", "decided_at", "headline", "body",
        "kpis", "proposed_actions", "fingerprint",
    }),
```

- [ ] **Step 4: Run — should pass**

```bash
uv run pytest tests/api/server/routes/ -k "kinds or stats" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/server/routes/entities.py tests/api/server/routes/
git commit -m "feat(routes/entities): expose Insight kind on /api/entities

Insight is now in _KINDS and gets a per-kind field projection so the
generic entities route returns it cleanly (no NULL union noise from
the other kinds' columns).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```


---

## Phase 2 — Closed-loop primitive: `active_policies_for`

The single helper that lets any persona's `decision_policy` block check whether an active policy from another persona constrains the current decision. Pure function, no side-effects, fully unit-testable against a tmp graph.

### Task 2.1: Implement `policy_lookup.active_policies_for`

**Files:**
- Create: `api/server/services/policy_lookup.py`
- Test: `tests/api/server/services/test_policy_lookup.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/server/services/test_policy_lookup.py`:

```python
"""Phase 2 of autonomous-domain-insights v1: active_policies_for helper."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite
from api.server.services.policy_lookup import active_policies_for


def _seed_brand_and_policy(
    g: EntityGraph,
    *,
    decided_at: datetime,
    expiry_days: int | None,
    verdict: str = "freeze",
    decision_id: str = "DEC-pol-1",
) -> None:
    g.upsert(EntityWrite(
        kind="Brand", id="BRAND-acme", attrs={"name": "Acme"}, source_workflows=()))
    g.record_decision(
        workflow_id="WF-pol",
        phase="policy_set",
        persona_role="cfo",
        verdict=verdict,
        reason="test policy",
        decided_at=decided_at,
        source_event="persona.action.approved",
        attributes={} if expiry_days is None else {"expiry_days": expiry_days},
        decided_on=("BRAND-acme",),
        decision_id=decision_id,
    )


def test_returns_active_policy(tmp_path: Path) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_brand_and_policy(g, decided_at=datetime.utcnow(), expiry_days=14)
    rows = active_policies_for(
        g, scope_kind="Brand", scope_id="BRAND-acme", verdict="freeze",
    )
    assert len(rows) == 1
    assert rows[0]["verdict"] == "freeze"
    assert rows[0]["persona_role"] == "cfo"
    assert rows[0]["attributes"]["expiry_days"] == 14


def test_skips_expired_policy(tmp_path: Path) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    long_ago = datetime.utcnow() - timedelta(days=30)
    _seed_brand_and_policy(g, decided_at=long_ago, expiry_days=14)
    rows = active_policies_for(
        g, scope_kind="Brand", scope_id="BRAND-acme", verdict="freeze",
    )
    assert rows == []


def test_returns_policies_with_no_expiry(tmp_path: Path) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    long_ago = datetime.utcnow() - timedelta(days=365)
    _seed_brand_and_policy(g, decided_at=long_ago, expiry_days=None)
    rows = active_policies_for(
        g, scope_kind="Brand", scope_id="BRAND-acme", verdict="freeze",
    )
    assert len(rows) == 1


def test_filters_by_verdict(tmp_path: Path) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_brand_and_policy(
        g, decided_at=datetime.utcnow(), expiry_days=14,
        verdict="cap", decision_id="DEC-pol-cap",
    )
    assert active_policies_for(
        g, scope_kind="Brand", scope_id="BRAND-acme", verdict="freeze") == []
    rows = active_policies_for(
        g, scope_kind="Brand", scope_id="BRAND-acme", verdict="cap")
    assert len(rows) == 1


def test_unknown_scope_kind_returns_empty(tmp_path: Path) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    assert active_policies_for(
        g, scope_kind="Unobtainium", scope_id="X", verdict="freeze") == []


def test_no_policy_returns_empty(tmp_path: Path) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    g.upsert(EntityWrite(
        kind="Brand", id="BRAND-acme", attrs={"name": "Acme"}, source_workflows=()))
    assert active_policies_for(
        g, scope_kind="Brand", scope_id="BRAND-acme", verdict="freeze") == []
```

(If `record_decision`'s call signature differs from the above — `decision_id` kwarg name in particular — adjust the seeding helper to match the in-code signature; the test intent is unchanged.)

- [ ] **Step 2: Run — should fail with ImportError**

```bash
uv run pytest tests/api/server/services/test_policy_lookup.py -v
```

Expected: FAIL — `ModuleNotFoundError: api.server.services.policy_lookup`.

- [ ] **Step 3: Implement `policy_lookup.py`**

Create `api/server/services/policy_lookup.py`:

```python
"""Active-policy lookup for persona decision_policy blocks.

A 'policy' here is a Decision with phase='policy_set' that has not yet
expired (decided_at + attributes.expiry_days >= now). Personas call this
helper at gate-time to discover policies that should constrain the
current decision.

Phase 2 of autonomous-domain-insights v1.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from api.server.services.entity_graph import EntityGraph

# Mirror of api/server/services/entity_graph.py:_DECIDED_REL_BY_KIND.
# Kept inline (rather than imported) to keep this module decoupled from
# the graph module's private constants — a regression here is caught by
# test_unknown_scope_kind_returns_empty.
_DECIDED_REL_BY_KIND: dict[str, str] = {
    "Person": "DECIDED_PERSON",
    "Money": "DECIDED_MONEY",
    "Asset": "DECIDED_ASSET",
    "Organisation": "DECIDED_ORG",
    "Period": "DECIDED_PERIOD",
    "Place": "DECIDED_PLACE",
    "Brand": "DECIDED_BRAND",
    "Campaign": "DECIDED_CAMPAIGN",
    "Pitch": "DECIDED_PITCH",
    "MediaPlan": "DECIDED_MEDIAPLAN",
    "Subsidiary": "DECIDED_SUBSIDIARY",
}


def active_policies_for(
    graph: EntityGraph,
    *,
    scope_kind: str,
    scope_id: str,
    verdict: str | None = None,
) -> list[dict[str, Any]]:
    """Return active policy_set Decisions whose decided_on includes scope_id.

    Args:
        graph: live EntityGraph (typically app_state.entities).
        scope_kind: target node kind (Brand, Money, ...). Unknown kinds
            return ``[]`` rather than raising — keeps persona policies
            future-proof against new kinds.
        scope_id: target node id (e.g. "BRAND-aurora").
        verdict: optional filter (e.g. "freeze"). When None, returns all
            verdicts including non-policy ones — callers SHOULD pass a
            specific verdict to avoid false positives from approve/reject
            Decisions that happen to share the policy_set phase.

    Returns:
        list of dicts with keys: id, verdict, decided_at, persona_role,
        reason, attributes (parsed dict). Sorted by decided_at descending
        (newest first) so latest-wins semantics are explicit at the
        callsite.
    """
    decided_rel = _DECIDED_REL_BY_KIND.get(scope_kind)
    if decided_rel is None:
        return []

    cypher = f"""
    MATCH (d:Decision {{phase: 'policy_set'}})-[:{decided_rel}]->(t:{scope_kind} {{id: $id}})
    RETURN d.id AS id, d.verdict AS verdict, d.decided_at AS decided_at,
           d.persona_role AS persona_role, d.reason AS reason,
           d.attributes AS attributes
    """
    rows = graph.query(cypher, {"id": scope_id})
    now = datetime.utcnow()
    out: list[dict[str, Any]] = []
    for r in rows:
        if verdict is not None and r["verdict"] != verdict:
            continue
        attrs: dict[str, Any] = {}
        raw_attrs = r.get("attributes")
        if raw_attrs:
            try:
                parsed = json.loads(raw_attrs)
                if isinstance(parsed, dict):
                    attrs = parsed
            except (TypeError, ValueError):
                pass
        expiry_days = attrs.get("expiry_days")
        decided_at = r["decided_at"]
        if expiry_days is not None and isinstance(decided_at, datetime):
            try:
                if decided_at + timedelta(days=int(expiry_days)) < now:
                    continue
            except (TypeError, ValueError):
                pass
        out.append({
            "id": r["id"],
            "verdict": r["verdict"],
            "decided_at": decided_at,
            "persona_role": r["persona_role"],
            "reason": r["reason"],
            "attributes": attrs,
        })
    out.sort(key=lambda d: d["decided_at"] or datetime.min, reverse=True)
    return out
```

- [ ] **Step 4: Run — all tests should pass**

```bash
uv run pytest tests/api/server/services/test_policy_lookup.py -v
```

Expected: PASS — 6 tests.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/policy_lookup.py tests/api/server/services/test_policy_lookup.py
git commit -m "feat(policy_lookup): active_policies_for helper

Single primitive that lets persona decision_policy blocks check whether
an active policy_set Decision constrains them. Latest-decided_at wins;
expired policies (decided_at + attributes.expiry_days < now) are skipped.
Unknown scope_kinds return [] for forward-compat.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```


---

## Phase 3 — Persona runtime: graph injection + summary_policy

Three small wires on `api/server/services/persona_responder.py`. Zero new classes.

### Task 3.1: Inject `graph` and `active_policies_for` into the persona sandbox

**Files:**
- Modify: `api/server/services/persona_responder.py` (`_DECISION_BUILTINS`, `_compile_decision_policy`)
- Test: `tests/api/server/services/test_persona_runtime_graph_access.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/api/server/services/test_persona_runtime_graph_access.py`:

```python
"""Phase 3 of autonomous-domain-insights v1: persona sandbox graph access."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite
from api.server.services.persona_responder import _compile_decision_policy


def test_decision_policy_can_read_graph(tmp_path: Path, monkeypatch) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    g.upsert(EntityWrite(
        kind="Brand", id="BRAND-acme", attrs={"name": "Acme"}, source_workflows=()))

    # Stand in for app_state.entities — the sandbox grabs `graph` from
    # app_state at call-time via a lazy lookup.
    from api.server.services import persona_responder as pr
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)

    src = textwrap.dedent("""
    rows = graph.query("MATCH (b:Brand) RETURN b.id AS id")
    decision = "approve" if rows and rows[0]["id"] == "BRAND-acme" else "reject"
    reason = f"saw {len(rows)} brand(s)"
    """)
    decide = _compile_decision_policy("test-role", src)
    out = decide({"some": "context"})
    assert out["decision"] == "approve"
    assert "saw 1 brand" in out["reason"]


def test_decision_policy_can_call_active_policies_for(
    tmp_path: Path, monkeypatch,
) -> None:
    from api.server.services import persona_responder as pr

    g = EntityGraph(tmp_path / "ig.kuzu")
    g.upsert(EntityWrite(
        kind="Brand", id="BRAND-acme", attrs={"name": "Acme"}, source_workflows=()))
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)

    src = textwrap.dedent("""
    policies = active_policies_for(
        graph, scope_kind="Brand", scope_id="BRAND-acme", verdict="freeze")
    decision = "escalate" if policies else "approve"
    reason = "frozen" if policies else "no active policy"
    """)
    decide = _compile_decision_policy("test-role", src)
    out = decide({})
    assert out["decision"] == "approve"
    assert out["reason"] == "no active policy"
```

- [ ] **Step 2: Run — should fail**

```bash
uv run pytest tests/api/server/services/test_persona_runtime_graph_access.py -v
```

Expected: FAIL — `graph` not in sandbox namespace, or `_lazy_app_graph` attribute missing.

- [ ] **Step 3: Add `_lazy_app_graph` and extend the sandbox**

Edit `api/server/services/persona_responder.py`:

1. Above `_DECISION_BUILTINS` (around line 411), add:

```python
def _lazy_app_graph():
    """Resolve the live EntityGraph at call-time.

    Lazy because app_state imports persona_responder transitively at boot;
    importing app_state at module top would create a cycle. Tests can
    monkeypatch this function to point at a tmp_path EntityGraph.
    """
    from api.server.state import app_state
    return app_state.entities
```

2. Inside `_compile_decision_policy`'s `decide()` function (around line 482), extend the namespace dict to include `graph` and `active_policies_for`:

```python
        from api.server.services.policy_lookup import active_policies_for as _apf
        ns: dict[str, Any] = {
            "context": context,
            "decision": None,
            "reason": None,
            "personality": dict(persona_personality),
            "graph": _lazy_app_graph(),
            "active_policies_for": _apf,
        }
```

3. Also extend `_DECISION_BUILTINS` to expose `active_policies_for` for personae that prefer it as a builtin (kept consistent with `query_precedents` / `authority_check`):

```python
_DECISION_BUILTINS: dict[str, Any] = {
    "isinstance": isinstance, "len": len,
    "str": str, "int": int, "float": float, "bool": bool,
    "list": list, "dict": dict, "set": set, "tuple": tuple,
    "min": min, "max": max, "abs": abs, "round": round,
    "any": any, "all": all, "sum": sum,
    "True": True, "False": False, "None": None,
    "authority_check": _sandbox_authority_check,
    "query_precedents": _sandbox_query_precedents,
    "precedent_check": _sandbox_precedent_check,
}
```

(No change needed to `_DECISION_BUILTINS` if you prefer to keep `active_policies_for` namespace-only; the tests above only assert namespace access.)

- [ ] **Step 4: Run — should pass**

```bash
uv run pytest tests/api/server/services/test_persona_runtime_graph_access.py -v
```

Expected: PASS.

- [ ] **Step 5: Re-run full persona_responder test suite to catch regressions**

```bash
uv run pytest tests/api/server/services/ -k "persona_responder or persona_runtime" -v
```

Expected: PASS for all (no existing tests reference `graph` in the namespace).

- [ ] **Step 6: Commit**

```bash
git add api/server/services/persona_responder.py tests/api/server/services/test_persona_runtime_graph_access.py
git commit -m "feat(persona_responder): inject graph + active_policies_for into sandbox

decision_policy and (Task 3.2) summary_policy blocks can now read live
graph state and check for constraining policies. Lazy app_state import
preserves the existing module load order. No change to existing personae.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```


---

### Task 3.2: Parse optional `summary_policy` block in `_load_personae`

**Files:**
- Modify: `api/server/services/persona_responder.py` (`PersonaDefinition`, `_load_personae`, new `_compile_summary_policy`)
- Test: `tests/api/server/services/test_persona_summary_policy_load.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/api/server/services/test_persona_summary_policy_load.py`:

```python
"""Phase 3.2 of autonomous-domain-insights v1: summary_policy compile."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from api.server.services import persona_responder as pr


def _write_skill(path: Path, *, with_summary: bool) -> None:
    summary_block = ""
    if with_summary:
        summary_block = textwrap.dedent("""
            summary_policy: |
                summary = {
                    "headline": "calm",
                    "body": "all quiet",
                    "kpis": {},
                    "proposed_actions": [],
                    "fingerprint": "f0",
                }
        """).rstrip("\n")
    skill = textwrap.dedent(f"""
    ---
    name: test-fixture
    description: test
    allowed-tools:
    workflow_label: Test
    external_event: test_signoff_decision
    decision_policy: |
        decision = "approve"
        reason = "fixture"
    {summary_block}
    ---

    # test-fixture
    """).strip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(skill, encoding="utf-8")


def test_summary_policy_loaded_when_present(
    tmp_path: Path, monkeypatch,
) -> None:
    skill = tmp_path / "test-fixture" / "SKILL.md"
    _write_skill(skill, with_summary=True)
    monkeypatch.setattr(pr, "PERSONAE_DIR", tmp_path)
    loaded = pr._load_personae()
    persona = loaded.get("test-fixture")
    assert persona is not None
    assert persona.summarise is not None
    out = persona.summarise({"last_insight": None})
    assert out["fingerprint"] == "f0"
    assert out["headline"] == "calm"


def test_summarise_is_none_when_block_absent(
    tmp_path: Path, monkeypatch,
) -> None:
    skill = tmp_path / "test-fixture" / "SKILL.md"
    _write_skill(skill, with_summary=False)
    monkeypatch.setattr(pr, "PERSONAE_DIR", tmp_path)
    loaded = pr._load_personae()
    persona = loaded.get("test-fixture")
    assert persona is not None
    assert persona.summarise is None


def test_personae_with_summary_policy_filter(
    tmp_path: Path, monkeypatch,
) -> None:
    _write_skill(tmp_path / "with-sum" / "SKILL.md", with_summary=True)
    _write_skill(tmp_path / "no-sum" / "SKILL.md", with_summary=False)
    monkeypatch.setattr(pr, "PERSONAE_DIR", tmp_path)
    loaded = pr._load_personae()
    monkeypatch.setattr(pr, "PERSONA_DEFINITIONS", loaded)
    roles = sorted(p.role for p in pr.personae_with_summary_policy())
    assert roles == ["with-sum"]
```

- [ ] **Step 2: Run — should fail**

```bash
uv run pytest tests/api/server/services/test_persona_summary_policy_load.py -v
```

Expected: FAIL — `summarise` attribute missing from `PersonaDefinition`; `personae_with_summary_policy` not defined.

- [ ] **Step 3: Extend `PersonaDefinition`**

Edit `api/server/services/persona_responder.py`. In the `PersonaDefinition` dataclass (around line 71), add a new optional field:

```python
@dataclass
class PersonaDefinition:
    role: str
    description: str
    workflow_label: str
    external_event: str
    decide: PersonaHandler
    skill_path: Path
    personality: dict[str, str] = field(default_factory=dict)
    # Phase 3.2 of autonomous-domain-insights v1. Optional: when present,
    # the cadence loop fires `domain.summary.requested` events and the
    # responder calls this handler. None for personae without a
    # summary_policy block in their SKILL.md frontmatter (today: all of
    # them; v1 ships the runtime support, v1.1+ adds blocks).
    summarise: PersonaHandler | None = None
```

- [ ] **Step 4: Add `_compile_summary_policy` and a helper**

Append below `_compile_decision_policy` (around line 519):

```python
def _compile_summary_policy(role: str, source: str) -> PersonaHandler:
    """Compile a `summary_policy` source block into a callable.

    Same sandbox shape as decision_policy (graph + active_policies_for in
    namespace, _DECISION_BUILTINS as builtins). The source MUST assign
    `summary` (a dict with keys: headline, body, kpis, proposed_actions,
    fingerprint) OR set `summary = None` to indicate no change since last
    Insight (the responder skips writing in that case).

    The handler is invoked with `context = {"last_insight": <dict|None>}`
    so the source can compare its computed fingerprint against the prior
    one and short-circuit by returning None.
    """
    cleaned = textwrap.dedent(source)
    try:
        code = compile(cleaned, f"<persona:{role}:summary_policy>", "exec")
    except SyntaxError as ex:
        raise ValueError(f"persona '{role}' summary_policy fails to compile: {ex}") from ex

    def summarise(context: dict[str, Any]) -> dict[str, Any]:
        from api.server.services.policy_lookup import active_policies_for as _apf
        ns: dict[str, Any] = {
            "context": context,
            "summary": None,
            "graph": _lazy_app_graph(),
            "active_policies_for": _apf,
        }
        try:
            exec(code, {"__builtins__": _DECISION_BUILTINS}, ns)
        except Exception as ex:
            return {"error": f"persona '{role}' summary_policy error: {ex}"}
        out = ns.get("summary")
        if out is None:
            return {"skip": True}
        if not isinstance(out, dict):
            return {"error": f"persona '{role}' summary_policy returned {type(out).__name__}, want dict"}
        # Coerce required keys to safe defaults so downstream writers
        # never see KeyError; fingerprint is the only one we strictly
        # require for change-detection.
        out.setdefault("headline", "")
        out.setdefault("body", "")
        out.setdefault("kpis", {})
        out.setdefault("proposed_actions", [])
        if "fingerprint" not in out:
            return {"error": f"persona '{role}' summary_policy missing 'fingerprint'"}
        return out

    return summarise


def personae_with_summary_policy() -> list[PersonaDefinition]:
    """Return loaded personae whose SKILL.md declared a summary_policy block."""
    return [p for p in PERSONA_DEFINITIONS.values() if p.summarise is not None]
```

- [ ] **Step 5: Wire it into `_load_personae`**

Inside `_load_personae` (around line 535), after `decide = _compile_decision_policy(...)`:

```python
            summary_src = fm.get("summary_policy")
            summarise = None
            if isinstance(summary_src, str) and summary_src.strip():
                try:
                    summarise = _compile_summary_policy(str(role), summary_src)
                except ValueError as ex:
                    print(f"[persona_responder] {skill_path}: {ex}")
            out[str(role)] = PersonaDefinition(
                role=str(role),
                description=str(description),
                workflow_label=str(workflow_label),
                external_event=str(external_event),
                decide=decide,
                skill_path=skill_path,
                personality=personality,
                summarise=summarise,
            )
```

(Replace the existing `out[str(role)] = PersonaDefinition(...)` block; do not duplicate.)

- [ ] **Step 6: Run — should pass**

```bash
uv run pytest tests/api/server/services/test_persona_summary_policy_load.py -v
```

Expected: PASS — all 3 tests.

- [ ] **Step 7: Commit**

```bash
git add api/server/services/persona_responder.py tests/api/server/services/test_persona_summary_policy_load.py
git commit -m "feat(persona_responder): parse optional summary_policy block

Personae can now declare a summary_policy in SKILL.md frontmatter; it is
compiled the same way as decision_policy with graph + active_policies_for
in scope. Returns None or sets summary=None to signal no-change (the
cadence loop in Task 4.1 will skip writes accordingly).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```


---

### Task 3.3: Handle `domain.summary.requested` events

**Files:**
- Modify: `api/server/services/persona_responder.py` (event subscription in `attach()`, new `_handle_summary_request`, `_latest_insight_for_role`)
- Test: `tests/api/server/services/test_persona_summary_runtime.py` (new)

The event flow: cadence loop emits `FleetEvent(type="domain.summary.requested", payload={"role": "<role>"})`; the responder reads the persona's last Insight, runs `summarise({"last_insight": last})`, compares fingerprints, writes a new Insight node only when changed.

- [ ] **Step 1: Write the failing test**

Create `tests/api/server/services/test_persona_summary_runtime.py`:

```python
"""Phase 3.3 of autonomous-domain-insights v1: end-to-end summary handling."""
from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path

import pytest

from api.server.services import persona_responder as pr
from api.server.services.entity_graph import EntityGraph
from api.shared.events import FleetEvent


def _make_fixture_persona(
    tmp_path: Path, monkeypatch, *, fingerprint: str, headline: str = "calm",
) -> EntityGraph:
    """Wire a tmp graph + a single fixture persona with a summary_policy
    that returns the given fingerprint + headline. Returns the graph for
    caller assertions.
    """
    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)

    skill = tmp_path / "personae" / "test-fixture" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(textwrap.dedent(f"""
    ---
    name: test-fixture
    description: test
    allowed-tools:
    workflow_label: Test
    external_event: test_signoff_decision
    decision_policy: |
        decision = "approve"
        reason = "fixture"
    summary_policy: |
        summary = {{
            "headline": "{headline}",
            "body": "fixture body",
            "kpis": {{}},
            "proposed_actions": [],
            "fingerprint": "{fingerprint}",
        }}
    ---

    # test-fixture
    """).strip() + "\n", encoding="utf-8")

    monkeypatch.setattr(pr, "PERSONAE_DIR", tmp_path / "personae")
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    return g


@pytest.mark.asyncio
async def test_first_summary_writes_insight(tmp_path: Path, monkeypatch) -> None:
    g = _make_fixture_persona(tmp_path, monkeypatch, fingerprint="fp-1")
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "test-fixture"}))
    rows = g.query(
        "MATCH (i:Insight {role: 'test-fixture'}) RETURN i.headline AS h, i.fingerprint AS f")
    assert len(rows) == 1
    assert rows[0]["h"] == "calm"
    assert rows[0]["f"] == "fp-1"


@pytest.mark.asyncio
async def test_no_change_does_not_write(tmp_path: Path, monkeypatch) -> None:
    g = _make_fixture_persona(tmp_path, monkeypatch, fingerprint="fp-1")
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "test-fixture"}))
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "test-fixture"}))
    rows = g.query("MATCH (i:Insight) RETURN count(i) AS n")
    assert rows[0]["n"] == 1, "second tick with same fingerprint must not write"


@pytest.mark.asyncio
async def test_changed_fingerprint_writes_new_insight(
    tmp_path: Path, monkeypatch,
) -> None:
    g = _make_fixture_persona(tmp_path, monkeypatch, fingerprint="fp-1")
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "test-fixture"}))

    # Rewrite the SKILL.md with a different fingerprint and reload.
    _make_fixture_persona(
        tmp_path, monkeypatch, fingerprint="fp-2", headline="alarm")
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "test-fixture"}))

    rows = g.query(
        "MATCH (i:Insight) RETURN i.fingerprint AS f, i.headline AS h ORDER BY i.decided_at")
    assert [r["f"] for r in rows] == ["fp-1", "fp-2"]
    assert [r["h"] for r in rows] == ["calm", "alarm"]


@pytest.mark.asyncio
async def test_unknown_role_is_no_op(tmp_path: Path, monkeypatch) -> None:
    g = _make_fixture_persona(tmp_path, monkeypatch, fingerprint="fp-1")
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "nonexistent"}))
    rows = g.query("MATCH (i:Insight) RETURN count(i) AS n")
    assert rows[0]["n"] == 0
```

- [ ] **Step 2: Run — should fail**

```bash
uv run pytest tests/api/server/services/test_persona_summary_runtime.py -v
```

Expected: FAIL — `_handle_summary_request` and `_latest_insight_for_role` not defined.

- [ ] **Step 3: Implement the handlers**

In `api/server/services/persona_responder.py`, append (just above `attach`, around line 1185):

```python
async def _handle_summary_request(event: FleetEvent) -> None:
    """Handle a `domain.summary.requested` FleetEvent.

    Looks up the persona by role; reads its last Insight from the graph;
    runs its summary_policy; compares the returned fingerprint with the
    last Insight's; writes a new Insight only on change.

    Phase 3.3 of autonomous-domain-insights v1.
    """
    import json
    import uuid
    from datetime import datetime
    from api.server.services.entity_graph import EntityWrite

    role = (event.payload or {}).get("role")
    if not isinstance(role, str) or not role:
        return
    persona = PERSONA_DEFINITIONS.get(role)
    if persona is None or persona.summarise is None:
        return

    graph = _lazy_app_graph()
    last = _latest_insight_for_role(graph, role)
    try:
        out = persona.summarise({"last_insight": last})
    except Exception as ex:  # pragma: no cover — defensive
        print(f"[persona_responder] summary {role!r} raised: {ex}")
        return
    if not isinstance(out, dict):
        return
    if out.get("error"):
        print(f"[persona_responder] summary {role!r}: {out['error']}")
        return
    if out.get("skip"):
        return

    new_fp = out.get("fingerprint")
    if last is not None and new_fp == last.get("fingerprint"):
        return  # no change

    insight_id = f"INSIGHT-{role}-{uuid.uuid4().hex[:12]}"
    decided_at = datetime.utcnow()
    graph.upsert(EntityWrite(
        kind="Insight",
        id=insight_id,
        attrs={
            "role": role,
            "scope": persona.workflow_label or role,
            "decided_at": decided_at,
            "headline": str(out.get("headline", ""))[:512],
            "body": str(out.get("body", "")),
            "kpis": json.dumps(out.get("kpis") or {}, default=str),
            "proposed_actions": json.dumps(out.get("proposed_actions") or [], default=str),
            "fingerprint": str(new_fp or ""),
            "attributes": json.dumps(out.get("attributes") or {}, default=str),
        },
        source_workflows=(),
    ))


def _latest_insight_for_role(graph, role: str) -> dict | None:
    rows = graph.query(
        "MATCH (i:Insight {role: $role}) "
        "RETURN i.id AS id, i.fingerprint AS fingerprint, "
        "       i.headline AS headline, i.body AS body, "
        "       i.kpis AS kpis, i.proposed_actions AS proposed_actions, "
        "       i.decided_at AS decided_at "
        "ORDER BY i.decided_at DESC LIMIT 1",
        {"role": role},
    )
    return rows[0] if rows else None
```

- [ ] **Step 4: Subscribe in `attach()`**

In `api/server/services/persona_responder.py:attach`, extend the bus subscription (around line 1214):

```python
    def _on_event(event: FleetEvent) -> None:
        if event.type == "workflow.hitl.requested":
            try:
                loop.create_task(_handle_hitl(event))
            except RuntimeError:
                pass
            return
        if event.type == "domain.summary.requested":
            try:
                loop.create_task(_handle_summary_request(event))
            except RuntimeError:
                pass
            return
```

- [ ] **Step 5: Run — should pass**

```bash
uv run pytest tests/api/server/services/test_persona_summary_runtime.py -v
```

Expected: PASS — 4 tests.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/persona_responder.py tests/api/server/services/test_persona_summary_runtime.py
git commit -m "feat(persona_responder): handle domain.summary.requested events

Reads the persona's last Insight, runs summary_policy, compares
fingerprints, writes a new Insight only on change. Unknown roles
no-op; non-dict / error returns log and skip. Bus subscription
in attach() handles both workflow.hitl.requested and the new event.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```


---

## Phase 4 — Cadence loop

### Task 4.1: Add the insight cadence loop to `persona_responder.attach()`

**Files:**
- Modify: `api/server/services/persona_responder.py` (extend `attach()`)
- Test: `tests/api/server/services/test_persona_insight_loop.py` (new)

The loop fires `domain.summary.requested` for every persona that declared a `summary_policy` block. Default 300s; demo profile sets `INSIGHT_REFRESH_SECONDS=15`. Disabled when `INSIGHT_LOOP_ENABLED=0` (safe default for unit tests).

- [ ] **Step 1: Write the failing test**

Create `tests/api/server/services/test_persona_insight_loop.py`:

```python
"""Phase 4 of autonomous-domain-insights v1: cadence loop."""
from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path

import pytest

from api.server.services import persona_responder as pr


@pytest.mark.asyncio
async def test_loop_emits_one_event_per_summary_persona(
    tmp_path: Path, monkeypatch,
) -> None:
    skill_dir = tmp_path / "personae" / "test-fixture"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(textwrap.dedent("""
    ---
    name: test-fixture
    description: test
    allowed-tools:
    workflow_label: Test
    external_event: test_signoff_decision
    decision_policy: |
        decision = "approve"
        reason = "fixture"
    summary_policy: |
        summary = {
            "headline": "calm", "body": "", "kpis": {},
            "proposed_actions": [], "fingerprint": "fp-1",
        }
    ---

    # test-fixture
    """).strip() + "\n", encoding="utf-8")

    monkeypatch.setattr(pr, "PERSONAE_DIR", tmp_path / "personae")
    pr.PERSONA_DEFINITIONS = pr._load_personae()

    emitted = []

    class FakeBus:
        def emit(self, event):
            emitted.append(event)

    fake = FakeBus()
    # Run a single tick by setting interval to 0 and stopping after one
    # iteration; the loop helper accepts a `max_iterations` kwarg for tests.
    await pr._insight_loop_tick(fake)

    assert len(emitted) == 1
    assert emitted[0].type == "domain.summary.requested"
    assert emitted[0].payload == {"role": "test-fixture"}


@pytest.mark.asyncio
async def test_loop_skips_personas_without_summary_policy(
    tmp_path: Path, monkeypatch,
) -> None:
    # Two personae, only one with summary_policy
    for role, with_sum in (("with-sum", True), ("no-sum", False)):
        skill_dir = tmp_path / "personae" / role
        skill_dir.mkdir(parents=True)
        sp = ""
        if with_sum:
            sp = textwrap.dedent("""
                summary_policy: |
                    summary = {
                        "headline": "x", "body": "", "kpis": {},
                        "proposed_actions": [], "fingerprint": "fp-1",
                    }
            """).rstrip("\n")
        (skill_dir / "SKILL.md").write_text(textwrap.dedent(f"""
        ---
        name: {role}
        description: test
        allowed-tools:
        workflow_label: Test
        external_event: test_signoff_decision
        decision_policy: |
            decision = "approve"
            reason = "fixture"
        {sp}
        ---

        # {role}
        """).strip() + "\n", encoding="utf-8")

    monkeypatch.setattr(pr, "PERSONAE_DIR", tmp_path / "personae")
    pr.PERSONA_DEFINITIONS = pr._load_personae()

    emitted = []

    class FakeBus:
        def emit(self, event):
            emitted.append(event)

    await pr._insight_loop_tick(FakeBus())
    roles = sorted(e.payload["role"] for e in emitted)
    assert roles == ["with-sum"]
```

- [ ] **Step 2: Run — should fail**

```bash
uv run pytest tests/api/server/services/test_persona_insight_loop.py -v
```

Expected: FAIL — `_insight_loop_tick` not defined.

- [ ] **Step 3: Implement `_insight_loop_tick` and `_insight_loop`**

Append to `api/server/services/persona_responder.py` (above `attach`):

```python
async def _insight_loop_tick(bus) -> None:
    """One tick of the insight cadence loop — emit a `domain.summary.requested`
    event per persona with a summary_policy block. Tests call this directly
    to skip the asyncio.sleep gating in `_insight_loop`.
    """
    for persona in personae_with_summary_policy():
        try:
            bus.emit(FleetEvent(
                type="domain.summary.requested",
                payload={"role": persona.role},
            ))
        except Exception as ex:  # pragma: no cover — defensive
            print(f"[persona_responder] insight tick emit failed for {persona.role}: {ex}")


async def _insight_loop(bus) -> None:
    """Periodic loop: every INSIGHT_REFRESH_SECONDS, emit a summary
    request per persona with a summary_policy. Cancelled by attach()'s
    teardown closure. Disabled entirely when INSIGHT_LOOP_ENABLED=0.
    """
    interval = float(os.environ.get("INSIGHT_REFRESH_SECONDS", "300"))
    if interval <= 0:
        return
    while True:
        try:
            await asyncio.sleep(interval)
            await _insight_loop_tick(bus)
        except asyncio.CancelledError:
            raise
        except Exception as ex:  # pragma: no cover — defensive
            print(f"[persona_responder] insight loop error: {ex}")
            await asyncio.sleep(1.0)
```

- [ ] **Step 4: Wire it into `attach()`**

In `api/server/services/persona_responder.py:attach` (around line 1252, just before `def _unsubscribe_with_sweep`):

```python
    insight_enabled = os.environ.get("INSIGHT_LOOP_ENABLED", "1") not in ("0", "false", "False")
    insight_task: asyncio.Task | None = None
    if insight_enabled:
        try:
            insight_task = loop.create_task(_insight_loop(bus))
            interval = float(os.environ.get("INSIGHT_REFRESH_SECONDS", "300"))
            print(
                f"[persona_responder] insight cadence loop enabled "
                f"every {interval}s"
            )
        except RuntimeError:
            pass

    def _unsubscribe_with_sweep() -> None:
        unsubscribe()
        if sweep_task is not None and not sweep_task.done():
            sweep_task.cancel()
        if insight_task is not None and not insight_task.done():
            insight_task.cancel()
```

(Replace the existing single-line `_unsubscribe_with_sweep` definition; do not duplicate.)

- [ ] **Step 5: Run — should pass**

```bash
uv run pytest tests/api/server/services/test_persona_insight_loop.py -v
```

Expected: PASS — 2 tests.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/persona_responder.py tests/api/server/services/test_persona_insight_loop.py
git commit -m "feat(persona_responder): periodic insight cadence loop

Every INSIGHT_REFRESH_SECONDS (default 300, demo profile sets 15) the
loop emits domain.summary.requested per persona with a summary_policy
block. Disabled with INSIGHT_LOOP_ENABLED=0 (safe default for tests).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```


---

## Phase 5 — Generic `policy_set` workflow type + projection

The Decision-as-Policy mechanism. Approving a persona's `proposed_action` spawns a one-shot `policy_set` workflow whose projection records a `Decision` with `phase="policy_set"` and the proposed verdict (`freeze` / `unfreeze` / `cap`). Any persona's `decision_policy` block then sees the new policy via `active_policies_for(...)`.

### Task 5.1: Register the `policy_set` workflow type

**Files:**
- Modify: `api/shared/domains.py`
- Test: `tests/api/shared/test_domains.py` (whichever existing test asserts the workflow_type list — find it first)

- [ ] **Step 1: Find the domains-list test**

```bash
grep -nR "DOMAINS\|workflow_type\|policy_set" tests/api/shared/ | head
```

If no test asserts the exact workflow_type list, skip the failing-test step and go straight to step 3 — Task 5.2's projection registry test will exercise this.

- [ ] **Step 2: (optional) Add a test assertion for `policy_set`**

If the existing tests have an `EXPECTED_WORKFLOW_TYPES` set or similar, add `"policy_set"` to it.

- [ ] **Step 3: Add the domain entry**

Edit `api/shared/domains.py`. Find the `DOMAINS` dict (around line 172) and add a new entry. The `policy_set` workflow type is intentionally minimal — it has one phase that just records the proposed verdict on completion. Use the simplest existing entry (`travel-preapproval` or `expense-claim`) as a template, with this shape:

```python
    "policy_set": Domain(
        workflow_type="policy_set",
        display_name="Policy Set",
        workflow_id_prefix="POLICY",
        orchestrator_name="PolicySetOrchestrator",
        operator_surface="executive",
        # No HITL gates — the persona-action approval IS the human step;
        # the workflow just persists the resulting Decision via projection.
        phases=(
            Phase(name="record"),
        ),
        hitl_gates=(),
        skills=(),
        # `function` is back-filled at boot by api.shared.functions._wire_function_back_refs
        # (set to None here per existing Domain field default). `spawn_fn` left None
        # because policy_set is not driven by the workflow simulator — it is spawned
        # directly by the /api/personas/.../actions/{id}/approve route.
    ),
```

(Re-check `Phase`'s required fields — at minimum `name`. If the dataclass needs `durable` or other flags, mirror them from `expense-claim` Phase entries, around line 180 of `api/shared/domains.py`.)

**IMPORTANT:** `policy_set` will not run through the simulator (no `spawn_fn`). The orphan validator at boot (in `api.shared.functions`) may complain about a missing spawner. If it does:
- Either mark `stub=True` (which excludes it from runtime contexts) AND wire the route's `_spawn_policy_set` (Task 6.3) to call durable functions directly without going through `simulator_orchestrator.spawn_workflow`,
- Or add a minimal `spawn_fn` that the simulator never calls (pointing at a no-op coroutine).
Pick whichever path the orphan validator accepts; the e2e test in Task 9.1 monkeypatches the spawn helper and is unaffected either way.

- [ ] **Step 4: Run any domain tests**

```bash
uv run pytest tests/api/shared/ -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/shared/domains.py tests/
git commit -m "feat(domains): register policy_set workflow type

Generic one-shot workflow used by the autonomous-domain-insights v1
closed loop. Persona action approvals spawn a policy_set workflow whose
projection records a Decision with the proposed verdict. No HITL gates.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5.2: Add the `policy_set` projection

**Files:**
- Create: `api/server/services/entity_projections/policy_set.py`
- Modify: `api/server/services/entity_projections/__init__.py` (import + `_DOMAIN_MODULES`)
- Test: `tests/api/server/services/entity_projections/test_policy_set_projection.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/api/server/services/entity_projections/test_policy_set_projection.py`:

```python
"""Phase 5.2 of autonomous-domain-insights v1: policy_set projection."""
from __future__ import annotations

from api.server.services.entity_projections import PROJECTIONS
from api.shared.types import Workflow


def test_policy_set_in_registry():
    assert "policy_set" in PROJECTIONS


def test_projection_emits_decision_with_verdict_and_targets():
    project = PROJECTIONS["policy_set"]
    wf = Workflow(
        id="WF-POL-1",
        workflow_type="policy_set",
        status="completed",
        payload={
            "decisions": [
                {
                    "phase": "policy_set",
                    "verdict": "freeze",
                    "reason": "CFO action approved",
                    "decided_at": "2026-05-12T10:00:00Z",
                    "persona_role": "cfo",
                },
            ],
            "persona_role": "cfo",
            "decided_on": ["BRAND-acme"],
            "attributes": {"expiry_days": 14, "scope": "po"},
            "verdict": "freeze",
        },
    )
    out = project(wf)
    decisions = [w for w in out if w.__class__.__name__ == "DecisionWrite"]
    assert len(decisions) == 1
    d = decisions[0]
    assert d.phase == "policy_set"
    assert d.verdict == "freeze"
    assert d.persona_role == "cfo"
    assert d.decided_on == ("BRAND-acme",)
    assert d.attributes["expiry_days"] == 14


def test_projection_returns_empty_when_no_decisions_in_payload():
    project = PROJECTIONS["policy_set"]
    wf = Workflow(
        id="WF-POL-2",
        workflow_type="policy_set",
        status="started",
        payload={},
    )
    assert project(wf) == []


def test_projection_canonicalises_verdict_aliases():
    project = PROJECTIONS["policy_set"]
    wf = Workflow(
        id="WF-POL-3",
        workflow_type="policy_set",
        status="completed",
        payload={
            "decisions": [{
                "phase": "policy_set",
                "verdict": "frozen",
                "reason": "alias path",
                "decided_at": "2026-05-12T10:00:00Z",
                "persona_role": "cfo",
            }],
            "persona_role": "cfo",
            "decided_on": ["BRAND-acme"],
            "verdict": "frozen",
        },
    )
    out = project(wf)
    decisions = [w for w in out if w.__class__.__name__ == "DecisionWrite"]
    assert decisions[0].verdict == "freeze"
```

- [ ] **Step 2: Run — should fail**

```bash
uv run pytest tests/api/server/services/entity_projections/test_policy_set_projection.py -v
```

Expected: FAIL — `policy_set` not in `PROJECTIONS`.

- [ ] **Step 3: Implement the projection**

Create `api/server/services/entity_projections/policy_set.py`:

```python
"""Projection: policy_set (autonomous-domain-insights v1, Phase 5.2).

A one-shot workflow spawned when an operator approves a persona's
proposed action. The payload carries:

    decided_on:      list[str]  — node ids the policy targets
    persona_role:    str        — the persona that proposed the action
    verdict:         str        — freeze / unfreeze / cap (or alias)
    attributes:      dict       — expiry_days, scope, ...

The projection records ONE Decision with phase='policy_set' and links
it to every node in decided_on (record_decision shards by kind via
DECIDED_<KIND> rels — see entity_graph.py:_DECIDED_REL_BY_KIND).

Other personae's decision_policy blocks discover the resulting policy
via api.server.services.policy_lookup.active_policies_for(...).
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "policy_set"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    decided_on = tuple(str(x) for x in (p.get("decided_on") or ()))
    persona_role = str(p.get("persona_role") or "")
    attributes = dict(p.get("attributes") or {})
    verdict_override = p.get("verdict")
    decision = build_decision(
        workflow,
        gate_phase="policy_set",
        persona_role=persona_role,
        source_event="persona.action.approved",
        decided_on=decided_on,
        attributes=attributes,
        verdict_override=str(verdict_override) if verdict_override else None,
    )
    return [decision] if decision is not None else []
```

- [ ] **Step 4: Register the projection**

Edit `api/server/services/entity_projections/__init__.py`:

1. Add the import (alphabetical order, before `purchase_order`):

```python
from . import policy_set           # noqa: E402  autonomous-domain-insights v1
```

2. Add `policy_set` to the `_DOMAIN_MODULES` tuple at line 165 (alphabetical order, before `purchase_order`).

- [ ] **Step 5: Run — should pass**

```bash
uv run pytest tests/api/server/services/entity_projections/test_policy_set_projection.py -v
```

Expected: PASS — 4 tests.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/entity_projections/policy_set.py api/server/services/entity_projections/__init__.py tests/api/server/services/entity_projections/test_policy_set_projection.py
git commit -m "feat(projections): policy_set projection

Records a Decision with phase=policy_set + the proposed verdict (freeze
/ unfreeze / cap). Targets all node ids in payload.decided_on; persona_role
+ attributes.expiry_days come from the persona's proposed_action payload.
build_decision canonicalises the verdict via decision_vocab.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```


---

## Phase 6 — HTTP routes

Three routes on a new `/api/personas/insights*` surface, plus the action-approval endpoint that spawns the policy_set workflow.

### Task 6.1: `GET /api/personas/{role}/insights/latest`

**Files:**
- Create: `api/server/routes/insights.py`
- Test: `tests/api/server/routes/test_insights.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/api/server/routes/test_insights.py`:

```python
"""Phase 6 of autonomous-domain-insights v1: HTTP routes."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_insight(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    monkeypatch.setenv("INSIGHT_LOOP_ENABLED", "0")  # do not auto-tick in tests
    # The entity graph lives at PORTAL_DATA_DIR / entity_graph.kuzu (see
    # api/server/state.py:96), so setting PORTAL_DATA_DIR above already
    # isolates this test's graph.

    from api.server.main import app  # imports app_state with the env above
    from api.server.state import app_state
    from api.server.services.entity_graph import EntityWrite

    app_state.entities.upsert(EntityWrite(
        kind="Insight",
        id="INSIGHT-cfo-1",
        attrs={
            "role": "cfo",
            "scope": "Finance",
            "decided_at": datetime.utcnow(),
            "headline": "All brands within budget",
            "body": "calm",
            "kpis": json.dumps({"budget_used_pct": 0.62}),
            "proposed_actions": json.dumps([]),
            "fingerprint": "fp-cfo-1",
            "attributes": "{}",
        },
        source_workflows=(),
    ))
    return TestClient(app)


def test_latest_for_role_returns_insight(client_with_insight):
    r = client_with_insight.get(
        "/api/personas/cfo/insights/latest",
        headers={"x-actor-role": "executive"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "cfo"
    assert body["headline"] == "All brands within budget"
    assert body["kpis"] == {"budget_used_pct": 0.62}
    assert body["proposed_actions"] == []


def test_latest_for_role_returns_404_when_none(client_with_insight):
    r = client_with_insight.get(
        "/api/personas/nobody/insights/latest",
        headers={"x-actor-role": "executive"},
    )
    assert r.status_code == 404
```

(The `x-actor-role: executive` header pattern matches `read_route_auth.require_actor`. Verify by reading the existing tests in `tests/api/server/routes/test_accounts.py` if the header name differs.)

- [ ] **Step 2: Run — should fail**

```bash
uv run pytest tests/api/server/routes/test_insights.py -v
```

Expected: FAIL — 404 on every request (router not mounted).

- [ ] **Step 3: Implement `routes/insights.py`**

Create `api/server/routes/insights.py`:

```python
"""HTTP read + action surface for persona insights.

Phase 6 of autonomous-domain-insights v1. Three endpoints:

  GET  /api/personas/{role}/insights/latest          (Task 6.1)
  GET  /api/personas/insights/latest                  (Task 6.2; CEO synth)
  POST /api/personas/{role}/actions/{action_id}/approve  (Task 6.3)
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path

from api.server.state import app_state
from api.server.services.read_route_auth import Actor, require_actor

router = APIRouter(prefix="/api/personas")


def _row_to_insight(row: dict[str, Any]) -> dict[str, Any]:
    """Decode the JSON-encoded columns + ISO timestamps for the wire."""
    decided_at = row.get("decided_at")
    out = {
        "id": row.get("id"),
        "role": row.get("role"),
        "scope": row.get("scope"),
        "decided_at": decided_at.isoformat() if hasattr(decided_at, "isoformat") else decided_at,
        "headline": row.get("headline") or "",
        "body": row.get("body") or "",
        "fingerprint": row.get("fingerprint") or "",
    }
    for col in ("kpis", "proposed_actions"):
        raw = row.get(col)
        if raw:
            try:
                out[col] = json.loads(raw)
            except (TypeError, ValueError):
                out[col] = None
        else:
            out[col] = {} if col == "kpis" else []
    return out


@router.get("/{role}/insights/latest")
async def latest_for_role(
    role: str = Path(..., min_length=1, max_length=64),
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    rows = app_state.entities.query(
        "MATCH (i:Insight {role: $role}) "
        "RETURN i.id AS id, i.role AS role, i.scope AS scope, "
        "       i.decided_at AS decided_at, i.headline AS headline, "
        "       i.body AS body, i.kpis AS kpis, "
        "       i.proposed_actions AS proposed_actions, "
        "       i.fingerprint AS fingerprint "
        "ORDER BY i.decided_at DESC LIMIT 1",
        {"role": role},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"no insight for role {role!r}")
    return _row_to_insight(rows[0])
```

- [ ] **Step 4: Mount the router**

Edit `api/server/main.py`. Add the import (alphabetical, alongside the others around line 348):

```python
from api.server.routes.insights import router as insights_router
```

Add `insights_router` to the tuple at line 357.

- [ ] **Step 5: Run — should pass**

```bash
uv run pytest tests/api/server/routes/test_insights.py -v
```

Expected: PASS — 2 tests. (If the actor header differs, fix the test header per the actual `require_actor` contract.)

- [ ] **Step 6: Commit**

```bash
git add api/server/routes/insights.py api/server/main.py tests/api/server/routes/test_insights.py
git commit -m "feat(routes/insights): GET /api/personas/{role}/insights/latest

Returns the most recent Insight node for a given role, with kpis and
proposed_actions decoded from their JSON-encoded columns. 404 when
no Insight has been written for the role yet.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```


---

### Task 6.2: `GET /api/personas/insights/latest` (one per role)

The CEO synthesis surface — returns one Insight per role (the latest of each), in role-name order.

**Files:**
- Modify: `api/server/routes/insights.py` (add second handler)
- Modify: `tests/api/server/routes/test_insights.py` (add tests)

- [ ] **Step 1: Add the failing test**

Append to `tests/api/server/routes/test_insights.py`:

```python
def test_latest_per_role_returns_one_per_role(client_with_insight):
    # Insight already seeded for cfo. Add one for hr_director.
    from datetime import datetime
    from api.server.state import app_state
    from api.server.services.entity_graph import EntityWrite

    app_state.entities.upsert(EntityWrite(
        kind="Insight",
        id="INSIGHT-hr_director-1",
        attrs={
            "role": "hr_director",
            "scope": "HR",
            "decided_at": datetime.utcnow(),
            "headline": "Headcount steady",
            "body": "",
            "kpis": "{}",
            "proposed_actions": "[]",
            "fingerprint": "fp-hr-1",
            "attributes": "{}",
        },
        source_workflows=(),
    ))

    r = client_with_insight.get(
        "/api/personas/insights/latest",
        headers={"x-actor-role": "executive"},
    )
    assert r.status_code == 200
    body = r.json()
    roles = sorted(item["role"] for item in body["insights"])
    assert roles == ["cfo", "hr_director"]


def test_latest_per_role_returns_empty_when_no_insights(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    monkeypatch.setenv("INSIGHT_LOOP_ENABLED", "0")
    from api.server.main import app
    client = TestClient(app)
    r = client.get(
        "/api/personas/insights/latest",
        headers={"x-actor-role": "executive"},
    )
    assert r.status_code == 200
    assert r.json() == {"insights": []}
```

- [ ] **Step 2: Run — should fail**

```bash
uv run pytest tests/api/server/routes/test_insights.py -v
```

Expected: FAIL — `/api/personas/insights/latest` 404.

- [ ] **Step 3: Implement the handler**

Append to `api/server/routes/insights.py`:

```python
@router.get("/insights/latest")
async def latest_per_role(
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    """Return one Insight per role (the most recent for each role).

    Used by the CEO synthesis surface and by any client that wants a
    cross-domain snapshot. Two-step Kuzu pattern (no window functions
    in 0.6.1): first compute (role, latest_decided_at) pairs, then
    re-MATCH to fetch the full row for each.
    """
    pairs = app_state.entities.query(
        "MATCH (i:Insight) "
        "WITH i.role AS role_, max(i.decided_at) AS latest "
        "RETURN role_, latest"
    )
    insights = []
    for p in pairs:
        rows = app_state.entities.query(
            "MATCH (i:Insight {role: $role}) WHERE i.decided_at = $when "
            "RETURN i.id AS id, i.role AS role, i.scope AS scope, "
            "       i.decided_at AS decided_at, i.headline AS headline, "
            "       i.body AS body, i.kpis AS kpis, "
            "       i.proposed_actions AS proposed_actions, "
            "       i.fingerprint AS fingerprint LIMIT 1",
            {"role": p["role_"], "when": p["latest"]},
        )
        if rows:
            insights.append(_row_to_insight(rows[0]))
    insights.sort(key=lambda d: d["role"])
    return {"insights": insights}
```

**ROUTE-ORDER NOTE:** FastAPI matches routes in declaration order. Because `/{role}/insights/latest` would shadow `/insights/latest` if declared first, ensure `latest_per_role` is defined BEFORE `latest_for_role` in the file (or rename the prefix to disambiguate). The simplest fix is to swap the function order — Step 3 above appends, so move `latest_per_role` above `latest_for_role` after writing it.

- [ ] **Step 4: Run — should pass**

```bash
uv run pytest tests/api/server/routes/test_insights.py -v
```

Expected: PASS — 4 tests.

- [ ] **Step 5: Commit**

```bash
git add api/server/routes/insights.py tests/api/server/routes/test_insights.py
git commit -m "feat(routes/insights): GET /api/personas/insights/latest

Returns one Insight per role — the most recent for each. Powers the
CEO synthesis surface and any cross-domain dashboard. Empty list when
no insights exist yet.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6.3: `POST /api/personas/{role}/actions/{action_id}/approve`

Spawns a one-shot `policy_set` workflow with the proposed-action payload.

**Files:**
- Modify: `api/server/routes/insights.py` (add POST handler)
- Modify: `tests/api/server/routes/test_insights.py` (add tests)

- [ ] **Step 1: Add the failing test**

Append to `tests/api/server/routes/test_insights.py`:

```python
def test_approve_action_spawns_policy_set_workflow(
    client_with_insight, monkeypatch,
):
    # Patch the spawn helper so the test does not actually run the
    # workflow — we only assert that the route invoked it with the
    # right payload + workflow_type.
    spawned: list[dict] = []

    def fake_spawn(workflow_type: str, payload: dict):
        spawned.append({"workflow_type": workflow_type, "payload": payload})
        return "WF-POL-fake-1"

    from api.server.routes import insights as insights_route
    monkeypatch.setattr(insights_route, "_spawn_policy_set", fake_spawn)

    # Re-seed the cfo Insight with an action.
    import json
    from datetime import datetime
    from api.server.state import app_state
    from api.server.services.entity_graph import EntityWrite

    app_state.entities.upsert(EntityWrite(
        kind="Insight",
        id="INSIGHT-cfo-2",
        attrs={
            "role": "cfo",
            "scope": "Finance",
            "decided_at": datetime.utcnow(),
            "headline": "Recommend freeze",
            "body": "",
            "kpis": "{}",
            "proposed_actions": json.dumps([{
                "id": "act-1",
                "label": "Freeze Acme POs for 14d",
                "kind": "policy_set",
                "verdict": "freeze",
                "decided_on": ["BRAND-acme"],
                "attributes": {"expiry_days": 14, "scope": "po"},
                "reason": "test",
            }]),
            "fingerprint": "fp-cfo-2",
            "attributes": "{}",
        },
        source_workflows=(),
    ))

    r = client_with_insight.post(
        "/api/personas/cfo/actions/act-1/approve",
        headers={"x-actor-role": "executive"},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["workflow_id"] == "WF-POL-fake-1"
    assert len(spawned) == 1
    s = spawned[0]
    assert s["workflow_type"] == "policy_set"
    assert s["payload"]["persona_role"] == "cfo"
    assert s["payload"]["verdict"] == "freeze"
    assert s["payload"]["decided_on"] == ["BRAND-acme"]
    assert s["payload"]["attributes"] == {"expiry_days": 14, "scope": "po"}


def test_approve_unknown_action_returns_404(client_with_insight):
    r = client_with_insight.post(
        "/api/personas/cfo/actions/no-such-action/approve",
        headers={"x-actor-role": "executive"},
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Run — should fail**

```bash
uv run pytest tests/api/server/routes/test_insights.py -v
```

Expected: FAIL — POST route 404 / 405.

- [ ] **Step 3: Implement `_spawn_policy_set` and the route**

Append to `api/server/routes/insights.py`:

```python
def _spawn_policy_set(workflow_type: str, payload: dict[str, Any]) -> str:
    """Spawn a one-shot `policy_set` workflow. Lazy-imports the existing
    spawn helper from simulator_orchestrator (the same path used by the
    ambient dispatcher in app_state) so this route stays decoupled from
    the durable-functions wiring at module load time. Tests monkeypatch
    this function to assert call payloads without firing the workflow.
    """
    from api.server.services import simulator_orchestrator
    spawn = getattr(simulator_orchestrator, "spawn_workflow", None)
    if not callable(spawn):
        raise RuntimeError("spawn_workflow not available in this build")
    return spawn(workflow_type, payload=payload)


@router.post("/{role}/actions/{action_id}/approve", status_code=202)
async def approve_action(
    role: str = Path(..., min_length=1, max_length=64),
    action_id: str = Path(..., min_length=1, max_length=128),
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    rows = app_state.entities.query(
        "MATCH (i:Insight {role: $role}) "
        "RETURN i.proposed_actions AS pa "
        "ORDER BY i.decided_at DESC LIMIT 1",
        {"role": role},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"no insight for role {role!r}")
    actions: list[dict[str, Any]] = []
    raw = rows[0].get("pa")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                actions = [a for a in parsed if isinstance(a, dict)]
        except (TypeError, ValueError):
            pass
    match = next((a for a in actions if a.get("id") == action_id), None)
    if match is None:
        raise HTTPException(
            status_code=404,
            detail=f"action {action_id!r} not found in latest {role!r} insight",
        )
    payload = {
        "persona_role": role,
        "verdict": str(match.get("verdict", "")),
        "decided_on": list(match.get("decided_on") or []),
        "attributes": dict(match.get("attributes") or {}),
        "decisions": [{
            "phase": "policy_set",
            "verdict": str(match.get("verdict", "")),
            "reason": str(match.get("reason") or match.get("label") or ""),
            "decided_at": "",
            "persona_role": role,
        }],
    }
    workflow_id = _spawn_policy_set(str(match.get("kind", "policy_set")), payload)
    return {"workflow_id": workflow_id, "status": "spawned"}
```

(If `simulator_orchestrator.spawn_workflow` does not accept a `payload=` kwarg, find the actual durable-functions spawn helper used elsewhere in the codebase — `git grep "spawn_workflow"` — and use that. The test's `_spawn_policy_set` monkeypatch isolates this concern; only the integration step in Phase 8 will exercise the real path.)

- [ ] **Step 4: Run — should pass**

```bash
uv run pytest tests/api/server/routes/test_insights.py -v
```

Expected: PASS — 6 tests.

- [ ] **Step 5: Commit**

```bash
git add api/server/routes/insights.py tests/api/server/routes/test_insights.py
git commit -m "feat(routes/insights): POST .../actions/{action_id}/approve

Spawns a one-shot policy_set workflow with the proposed action's
payload (verdict, decided_on, attributes, persona_role). Returns 202
with the new workflow id. 404 when the role has no insight or the
action_id is not found in the latest insight.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```


---

## Phase 7 — CEO persona

The only persona shipped in v1. Reads other personae's latest Insights via the existing graph and synthesises a meta-Insight. When no other insights exist (the v1 baseline state, since no other persona has a `summary_policy` block yet), it emits a calm "system online — awaiting domain insights" headline. Once v1.1+ adds CFO / HR-head summary blocks, the CEO synthesis becomes meaningful with no further changes.

### Task 7.1: Register `ceo` in the persona registry

**Files:**
- Modify: `api/shared/personas.py` (add CEO entry)

- [ ] **Step 1: Open `api/shared/personas.py` and locate the `PERSONAS` dict**

```bash
grep -n "PERSONAS: dict" api/shared/personas.py
```

- [ ] **Step 2: Add the CEO entry**

Use an existing minimal Persona entry as a template (e.g. CFO around line 195 or any other top-band signing persona). Add:

```python
    "ceo": Persona(
        role="ceo",
        archetype="approver",
        scope_function="finance",  # CEO sits across all functions; pick one
                                   # in the existing ScopeFunction Literal so the
                                   # registry validates. (CEO is cross-functional;
                                   # the synthesis surface does not depend on this.)
        workflow_label="Executive — synthesis",
        external_event_default="ceo_synthesis_decision",
        default_authority_band="any",
        description=("Chief Executive Officer. Synthesises domain-persona Insights "
                     "into a single org-wide narrative. Does not gate workflows in v1."),
    ),
```

(Persona is a frozen dataclass; required fields are `role`, `archetype`, `scope_function`, `workflow_label`. The `archetype` and `scope_function` literals are constrained — if either fails type-check, pick the closest matching value from the `Archetype` / `ScopeFunction` Literals declared at the top of `api/shared/personas.py`.)

- [ ] **Step 3: Sanity-check loader**

```bash
uv run python -c "from api.shared.personas import PERSONAS; print('ceo' in PERSONAS)"
```

Expected: `True`.

- [ ] **Step 4: Commit**

```bash
git add api/shared/personas.py
git commit -m "feat(personas): register ceo

Registry entry only — the CEO persona is used by the autonomous-domain-
insights v1 cadence loop for its summary_policy (Task 7.2). It does not
gate any workflow today.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 7.2: Author `api/server/personae/ceo/SKILL.md`

**Files:**
- Create: `api/server/personae/ceo/SKILL.md`
- Test: `tests/api/server/personae/test_ceo_summary_policy.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/api/server/personae/test_ceo_summary_policy.py`:

```python
"""Phase 7.2 of autonomous-domain-insights v1: CEO summary_policy."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from api.server.services import persona_responder as pr
from api.server.services.entity_graph import EntityGraph, EntityWrite


def _seed_insight(
    g: EntityGraph, *, role: str, headline: str, fingerprint: str,
) -> None:
    g.upsert(EntityWrite(
        kind="Insight",
        id=f"INSIGHT-{role}-1",
        attrs={
            "role": role,
            "scope": role,
            "decided_at": datetime.utcnow(),
            "headline": headline,
            "body": "",
            "kpis": "{}",
            "proposed_actions": "[]",
            "fingerprint": fingerprint,
            "attributes": "{}",
        },
        source_workflows=(),
    ))


def test_ceo_summary_emits_calm_when_no_other_insights(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS.get("ceo")
    assert persona is not None
    assert persona.summarise is not None
    out = persona.summarise({"last_insight": None})
    assert "headline" in out
    assert "fingerprint" in out
    # Calm baseline: no domains have produced insights yet.
    assert "no domain insights" in out["headline"].lower() \
        or "system online" in out["headline"].lower() \
        or out["kpis"] == {}


def test_ceo_summary_synthesises_when_other_insights_exist(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    _seed_insight(g, role="cfo", headline="Finance steady", fingerprint="fp-cfo-1")
    _seed_insight(g, role="hr_director", headline="Headcount steady", fingerprint="fp-hr-1")

    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS["ceo"]
    out = persona.summarise({"last_insight": None})
    # The synthesis fingerprint must change vs. the calm baseline.
    assert out["fingerprint"] != ""
    # Body should reference at least one of the domain insights so the
    # synthesis is verifiably wired to the graph.
    body = (out.get("body") or "") + " " + (out.get("headline") or "")
    assert "cfo" in body.lower() or "finance" in body.lower() \
        or "hr" in body.lower()


def test_ceo_summary_fingerprint_is_deterministic(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    _seed_insight(g, role="cfo", headline="Finance steady", fingerprint="fp-cfo-1")
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS["ceo"]
    out_a = persona.summarise({"last_insight": None})
    out_b = persona.summarise({"last_insight": None})
    assert out_a["fingerprint"] == out_b["fingerprint"], \
        "CEO summary fingerprint must be deterministic over the same inputs"
```

- [ ] **Step 2: Run — should fail**

```bash
uv run pytest tests/api/server/personae/test_ceo_summary_policy.py -v
```

Expected: FAIL — `ceo` not in `PERSONA_DEFINITIONS` (no SKILL.md yet).

- [ ] **Step 3: Author the SKILL.md**

Create `api/server/personae/ceo/SKILL.md`:

```markdown
---
name: ceo
description: Chief Executive Officer. Synthesises domain-persona Insights into a single org-wide narrative. Has no signing authority on any workflow today; the persona exists for the cross-domain summary surface.
allowed-tools:
workflow_label: Executive — synthesis
external_event: ceo_synthesis_decision
decision_policy: |
    # CEO does not gate any workflow today. Reject anything that is
    # somehow routed here so a misconfigured wake doesn't silently
    # auto-approve.
    decision = "reject"
    reason = "ceo persona does not gate workflows in v1"
summary_policy: |
    # Read every other persona's most recent Insight; synthesise one
    # meta-headline + one body paragraph + a kpis dict + a fingerprint
    # that is deterministic over the inputs (so the cadence loop only
    # writes when something has actually changed).
    import hashlib

    rows = graph.query(
        "MATCH (i:Insight) "
        "WITH i.role AS role_, max(i.decided_at) AS latest "
        "MATCH (i2:Insight) "
        "WHERE i2.role = role_ AND i2.decided_at = latest "
        "RETURN i2.role AS role, i2.headline AS headline, "
        "       i2.fingerprint AS fingerprint, i2.scope AS scope "
        "ORDER BY i2.role"
    )
    # Filter out the CEO's own prior Insights so the synthesis is
    # strictly downstream of domain personae.
    rows = [r for r in rows if r["role"] != "ceo"]

    if not rows:
        summary = {
            "headline": "System online — awaiting domain insights",
            "body": (
                "No persona has published a summary yet. "
                "Domain personae publish Insights on every cadence tick "
                "when their graph state changes."
            ),
            "kpis": {"domains_reporting": 0},
            "proposed_actions": [],
            "fingerprint": "ceo:empty",
        }
    else:
        # Determinstic fingerprint = sha1 of (role, fingerprint) pairs in
        # role-sorted order.
        material = "|".join(f"{r['role']}={r['fingerprint']}" for r in rows)
        fp = "ceo:" + hashlib.sha1(material.encode("utf-8")).hexdigest()[:16]
        domains = ", ".join(r["role"] for r in rows)
        bullets = " | ".join(f"{r['role']}: {r['headline']}" for r in rows)
        summary = {
            "headline": f"Org snapshot — {len(rows)} domain(s) reporting",
            "body": bullets,
            "kpis": {
                "domains_reporting": len(rows),
                "domains": [r["role"] for r in rows],
            },
            "proposed_actions": [],
            "fingerprint": fp,
        }
personality:
  risk_appetite: balanced
  thoroughness: high
  escalation_style: deliberate
---

# ceo

You are the **Chief Executive Officer**. You do not gate any workflow today; your role is to synthesise the domain personae's Insights into a single org-wide narrative.

## Summary policy

On every insight cadence tick, fetch the latest Insight for each non-CEO persona (one row per role). When none exist, emit a calm "system online" headline. Otherwise compose a one-line headline naming the count of reporting domains and a body that quotes each domain's headline.

The fingerprint is a SHA-1 of the `(role, fingerprint)` pairs in role-sorted order so the cadence loop only writes a new CEO Insight when at least one downstream domain's fingerprint changed.

## When this fires

The autonomous-domain-insights v1 cadence loop in `persona_responder.attach()` fires `domain.summary.requested` for every persona with a `summary_policy` block, including this one, every `INSIGHT_REFRESH_SECONDS` (default 300s; demo profile sets 15s).
```

- [ ] **Step 4: Run — should pass**

```bash
uv run pytest tests/api/server/personae/test_ceo_summary_policy.py -v
```

Expected: PASS — 3 tests.

- [ ] **Step 5: Commit**

```bash
git add api/server/personae/ceo/SKILL.md tests/api/server/personae/test_ceo_summary_policy.py
git commit -m "feat(personae): ceo SKILL.md with summary_policy

The only new persona shipped in autonomous-domain-insights v1. Reads
other personae's latest Insights and synthesises an org-wide narrative.
Calm baseline when no other insights exist; deterministic fingerprint
over the (role, fingerprint) pairs so the cadence loop only writes
on change.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```


---

## Phase 8 — UI surface (blueprint)

Wires the WorkflowDrawer to fetch + render persona insights.

### Task 8.1: Add persona-insight panel to WorkflowDrawer

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx`
- Test: `web/blueprint/src/components/cosmicLens/HUD/__tests__/WorkflowDrawer.insight.test.tsx` (new)

The drawer already has an entity-aware switch (extended in Phase 4.4 of the entity-graph plan for `PRECEDENT_OF`). Add a new branch: when the open entity has `_label === "Person"` AND its `role` matches a persona role (i.e., the planet clicked is a persona), fetch `/api/personas/{role}/insights/latest` and render the headline / body / kpis / proposed_actions list with an Approve button per action.

- [ ] **Step 1: Read the current WorkflowDrawer surface**

```bash
sed -n '1,80p' web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx
```

Note the existing pattern for fetching from the API and rendering one of several panels. Mirror that pattern.

- [ ] **Step 2: Write the failing component test**

Create `web/blueprint/src/components/cosmicLens/HUD/__tests__/WorkflowDrawer.insight.test.tsx` (the `__tests__` dir + naming convention may differ — match the closest existing vitest file in the same surface):

```typescript
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { WorkflowDrawer } from "../WorkflowDrawer";

describe("WorkflowDrawer persona-insight panel", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("/insights/latest")) {
        return new Response(JSON.stringify({
          id: "INSIGHT-cfo-1",
          role: "cfo",
          scope: "Finance",
          decided_at: "2026-05-12T10:00:00Z",
          headline: "All brands within budget",
          body: "calm",
          kpis: { budget_used_pct: 0.62 },
          proposed_actions: [],
          fingerprint: "fp-1",
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response("{}", { status: 200 });
    }));
  });

  it("renders the latest insight when a persona entity is open", async () => {
    render(<WorkflowDrawer
      open={true}
      entity={{ _label: "Person", id: "PER-cfo", role: "cfo", name: "CFO" }}
      onClose={() => {}}
    />);
    await waitFor(() => {
      expect(screen.getByText(/All brands within budget/)).toBeInTheDocument();
    });
  });
});
```

(If the existing test convention uses `react-testing-library` differently, mirror those imports + the `WorkflowDrawer` prop shape from a sibling vitest file.)

- [ ] **Step 3: Run the test — should fail**

```bash
cd web/blueprint && npm test -- WorkflowDrawer.insight
```

Expected: FAIL — either the headline isn't rendered or the new branch isn't hit.

- [ ] **Step 4: Add the panel branch to `WorkflowDrawer.tsx`**

Inside the component, near the existing entity-switch, add:

```tsx
const [insight, setInsight] = useState<any | null>(null);

useEffect(() => {
  if (!entity || entity._label !== "Person" || !entity.role) {
    setInsight(null);
    return;
  }
  let cancelled = false;
  fetch(`/api/personas/${encodeURIComponent(entity.role)}/insights/latest`)
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      if (!cancelled) setInsight(data);
    })
    .catch(() => { if (!cancelled) setInsight(null); });
  return () => { cancelled = true; };
}, [entity?.role, entity?._label]);

const insightPanel = insight ? (
  <section className="insight-panel">
    <h3>{insight.headline}</h3>
    <p>{insight.body}</p>
    {insight.kpis && Object.keys(insight.kpis).length > 0 && (
      <dl className="insight-kpis">
        {Object.entries(insight.kpis).map(([k, v]) => (
          <Fragment key={k}>
            <dt>{k}</dt><dd>{String(v)}</dd>
          </Fragment>
        ))}
      </dl>
    )}
    {Array.isArray(insight.proposed_actions) && insight.proposed_actions.length > 0 && (
      <ul className="insight-actions">
        {insight.proposed_actions.map((a: any) => (
          <li key={a.id}>
            <span>{a.label}</span>
            <button
              onClick={async () => {
                await fetch(
                  `/api/personas/${insight.role}/actions/${encodeURIComponent(a.id)}/approve`,
                  { method: "POST" },
                );
              }}
            >Approve</button>
          </li>
        ))}
      </ul>
    )}
  </section>
) : null;
```

Render `{insightPanel}` inside the existing drawer body, above or below the precedents panel.

- [ ] **Step 5: Run — should pass**

```bash
cd web/blueprint && npm test -- WorkflowDrawer.insight
```

Expected: PASS.

- [ ] **Step 6: Build the bundle**

```bash
cd web/blueprint && npm run build
```

Expected: Vite build succeeds; bundle written to `web/blueprint/dist/`.

- [ ] **Step 7: Commit**

```bash
git add web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx web/blueprint/src/components/cosmicLens/HUD/__tests__/WorkflowDrawer.insight.test.tsx web/blueprint/dist/
git commit -m "feat(blueprint): persona-insight panel in WorkflowDrawer

When a Person entity with a 'role' attribute is open, fetch
/api/personas/{role}/insights/latest and render headline / body /
kpis / proposed_actions. Approve button POSTs to .../actions/{id}/approve.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```


---

## Phase 9 — Integration verification + final regression

### Task 9.1: End-to-end smoke

**Files:**
- Create: `tests/integration/test_autonomous_insights_e2e.py` (new)

A single integration test that exercises every layer: persona load → cadence emit → handler write → HTTP fetch → action approval → projection.

- [ ] **Step 1: Write the e2e test**

Create `tests/integration/test_autonomous_insights_e2e.py`:

```python
"""End-to-end smoke for autonomous-domain-insights v1.

Exercises: persona load with summary_policy → cadence tick emits event →
handler writes Insight → HTTP fetch returns it → action approval spawns
the policy_set workflow → projection records a Decision the
active_policies_for helper can read.
"""
from __future__ import annotations

import asyncio
import json
import textwrap
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_e2e_one_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_LOOP_ENABLED", "0")
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))

    # Stand up a fixture persona that always proposes a freeze on BRAND-acme.
    from api.server.services import persona_responder as pr

    pdir = tmp_path / "personae"
    fixture = pdir / "test-fixture"
    fixture.mkdir(parents=True)
    (fixture / "SKILL.md").write_text(textwrap.dedent("""
    ---
    name: test-fixture
    description: e2e fixture
    allowed-tools:
    workflow_label: Test
    external_event: test_signoff_decision
    decision_policy: |
        decision = "approve"
        reason = "fixture"
    summary_policy: |
        summary = {
            "headline": "Fixture proposes freeze",
            "body": "",
            "kpis": {"acme_pct": 0.9},
            "proposed_actions": [{
                "id": "act-freeze-acme",
                "label": "Freeze Acme POs for 14d",
                "kind": "policy_set",
                "verdict": "freeze",
                "decided_on": ["BRAND-acme"],
                "attributes": {"expiry_days": 14, "scope": "po"},
                "reason": "fixture",
            }],
            "fingerprint": "fp-fix-1",
        }
    ---

    # test-fixture
    """).strip() + "\n", encoding="utf-8")

    monkeypatch.setattr(pr, "PERSONAE_DIR", pdir)
    pr.PERSONA_DEFINITIONS = pr._load_personae()

    from api.server.main import app
    from api.server.state import app_state
    from api.server.services.entity_graph import EntityWrite
    from api.server.services.policy_lookup import active_policies_for
    from api.shared.events import FleetEvent

    # Seed the BRAND-acme node so active_policies_for has something to match.
    app_state.entities.upsert(EntityWrite(
        kind="Brand", id="BRAND-acme", attrs={"name": "Acme"}, source_workflows=()))

    # 1. Cadence tick → Insight written
    await pr._handle_summary_request(FleetEvent(
        type="domain.summary.requested", payload={"role": "test-fixture"}))

    client = TestClient(app)

    # 2. HTTP fetch returns it
    r = client.get(
        "/api/personas/test-fixture/insights/latest",
        headers={"x-actor-role": "executive"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["proposed_actions"][0]["id"] == "act-freeze-acme"

    # 3. Approve the action — patch the spawn so we can drive the projection
    #    deterministically.
    from api.server.routes import insights as insights_route
    from api.server.services.entity_projections import PROJECTIONS
    from api.shared.types import Workflow

    spawned_payloads: list[dict] = []

    def fake_spawn(workflow_type: str, payload: dict) -> str:
        spawned_payloads.append({"wt": workflow_type, "payload": payload})
        # Simulate the workflow completing + the projection running.
        wf = Workflow(
            id="WF-POL-e2e-1",
            workflow_type="policy_set",
            status="completed",
            payload={**payload, "decisions": payload.get("decisions") or []},
        )
        for write in PROJECTIONS["policy_set"](wf):
            if write.__class__.__name__ == "DecisionWrite":
                app_state.entities.record_decision(
                    workflow_id=wf.id,
                    phase=write.phase,
                    persona_role=write.persona_role,
                    verdict=write.verdict,
                    reason=write.reason,
                    decided_at=datetime.utcnow(),
                    source_event=write.source_event,
                    attributes=write.attributes,
                    decided_on=write.decided_on,
                )
        return wf.id

    monkeypatch.setattr(insights_route, "_spawn_policy_set", fake_spawn)

    r = client.post(
        "/api/personas/test-fixture/actions/act-freeze-acme/approve",
        headers={"x-actor-role": "executive"},
    )
    assert r.status_code == 202
    assert spawned_payloads[0]["wt"] in ("policy_set",)
    assert spawned_payloads[0]["payload"]["verdict"] == "freeze"

    # 4. active_policies_for now sees the policy
    policies = active_policies_for(
        app_state.entities,
        scope_kind="Brand", scope_id="BRAND-acme", verdict="freeze",
    )
    assert len(policies) == 1
    assert policies[0]["persona_role"] == "test-fixture"
    assert policies[0]["attributes"]["expiry_days"] == 14
```

- [ ] **Step 2: Run the e2e**

```bash
uv run pytest tests/integration/test_autonomous_insights_e2e.py -v
```

Expected: PASS.

- [ ] **Step 3: Run full regression**

```bash
uv run pytest tests/api/server/services tests/api/server/routes tests/integration -x --no-header -q 2>&1 | tail -10
```

Expected: pass count = baseline (Phase 0 Step 4) + (new tests added in Phases 1-9). Failure count = 17 (the same pre-existing mock-server failures from main).

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_autonomous_insights_e2e.py
git commit -m "test(integration): autonomous-insights v1 end-to-end smoke

Exercises: persona load → summary handler writes Insight → HTTP fetch
returns it → action approval spawns policy_set → projection records a
Decision → active_policies_for sees the policy. Single test, fully
isolated under tmp_path with INSIGHT_LOOP_ENABLED=0.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```


---

## Phase 10 — Live verification + merge

### Task 10.1: Boot the stack + drive the round-trip by hand

- [ ] **Step 1: Wipe the live graph + boot demo profile**

```bash
cd /Users/arturzielinski/dev/github-repos/zava-control-plane-poc1/.worktrees/autonomous-insights-v1
rm -rf data/portal/entity_graph.kuzu
INSIGHT_REFRESH_SECONDS=15 INSIGHT_LOOP_ENABLED=1 make up
```

Wait for `[persona_responder] insight cadence loop enabled every 15s` in the log.

- [ ] **Step 2: Wait one cadence tick + fetch the CEO insight**

```bash
sleep 20
curl -s -H 'x-actor-role: executive' http://localhost:3101/api/personas/ceo/insights/latest | jq
```

Expected: a JSON Insight with `headline` mentioning "system online" or "0 domain(s) reporting" (the calm baseline, since no other persona has a `summary_policy` block in v1).

- [ ] **Step 3: Verify the cross-domain endpoint**

```bash
curl -s -H 'x-actor-role: executive' http://localhost:3101/api/personas/insights/latest | jq
```

Expected: `{"insights": [{"role": "ceo", ...}]}`.

- [ ] **Step 4: Verify the Insight kind appears on /api/entities**

```bash
curl -s -H 'x-actor-role: executive' http://localhost:3101/api/entities/_stats | jq '.byKind.Insight'
```

Expected: `{"count": 1}` (or higher if multiple ticks have fired).

- [ ] **Step 5: (Optional) Click the CEO planet in the constellation**

```
open 'http://localhost:5275/?view=constellation'
```

Click the CEO planet. The WorkflowDrawer should render the calm "system online" headline. (If the entity-click → drawer wiring doesn't pass `role` on the entity prop, file that as a v1.1 follow-up — the route works regardless, and the curl evidence above is the v1 acceptance bar.)

- [ ] **Step 6: Stop the stack**

```bash
make down
```

- [ ] **Step 7: Commit any blueprint dist changes**

```bash
git status
git add web/blueprint/dist/  # if rebuilt
git commit -m "chore(blueprint): rebuild bundle for v1 verification" --allow-empty
```

---

### Task 10.2: Merge back to main

Use the `superpowers:finishing-a-development-branch` skill. Expected sequence:

1. Re-run full regression on the worktree (`uv run pytest`); confirm baseline + new tests pass.
2. `cd ../..` (back to main checkout).
3. `git fetch origin && git log main..feat/autonomous-insights-v1 --oneline` (review commits about to merge).
4. `git merge --no-ff feat/autonomous-insights-v1 -m "Merge feat/autonomous-insights-v1 into main"`.
5. Reseed the live graph (`rm -rf data/portal/entity_graph.kuzu && make up && sleep 5 && make down`) so any developer fetching main gets a fresh graph with the `Insight` table on it.
6. Delete the worktree + branch:

```bash
git worktree remove .worktrees/autonomous-insights-v1
git branch -d feat/autonomous-insights-v1
```

7. Push (operator decision — confirm with user before pushing to remote main).

---

## v1.1+ deferred work (NOT IN v1 SCOPE)

These were considered and explicitly deferred. Each lands as an independent follow-up plan once v1 proves the loop works end-to-end.

| Slice | Spec ref | Notes |
|---|---|---|
| **CFO summary_policy** (Aurora-aware) | spec §8.3 | Add a `summary_policy` block to `api/server/personae/cfo/SKILL.md` that reads Brand spend/budget and proposes a freeze when over threshold. Drops in cleanly on top of v1. |
| **ap_clerk policy honour** | spec §8.4 | Extend `api/server/personae/ap_clerk/SKILL.md`'s `decision_policy` block to call `active_policies_for(graph, scope_kind="Brand", scope_id=..., verdict="freeze")` and auto-escalate when frozen. |
| **controller policy honour** | spec §8.4 | Same extension on the controller persona so the escalation chain doesn't auto-approve at the next level. |
| **Aurora demo trigger** | spec §8.1 | `POST /api/demo/trigger/aurora-overrun` route + helper that inserts ~5 Money rows on BRAND-aurora to push spend above 85%. |
| **Persona voice templates** (spec §9 polish a) | spec §9 | First-person prose layer over the structured `summary` payload. Optional GHCP SDK call for free-form variant. |
| **Demo trigger panel** (polish b) | spec §9 | Hidden `/demo` page with multiple pre-baked scenarios. |
| **Live decision ticker** (polish c) | spec §9 | Bottom strip of the constellation; chronological feed of recent Decisions / Insights. |
| **Policy-ripple animation** (polish d) | spec §9 | Constellation animation when a policy_set Decision lands. |
| **Per-persona hue** (polish e) | spec §9 | Distinct colour per persona surfaced on workflow particle tints. |
| **Time warp for personas** (polish f) | spec §9 | Apply existing `DEMO_TIME_WARP_FACTOR` to `INSIGHT_REFRESH_SECONDS`. |
| **Plain-language UI strings** (polish g) | spec §9 | Audit pass to translate `phase=policy_set verdict=freeze` → "CFO Policy: Freeze Aurora POs (14 days)". |
| **Multi-persona quorum on actions** (polish h) | spec §9 | `required_approvers` field on proposed_actions. |
| **Policy-conflict detector** (polish i) | spec §9 | Fleet Manager wakes on conflicting policies. |
| **Insight-citation graph** (polish j) | spec §9 | New rel `Insight -[:CITES]-> Decision` for graph-native explainability. |
| **More frictional workflow types** (polish k) | spec §9 | vendor-risk-demotion, hiring quorum, brand-pull-request, FX-hedge-quorum. |

---

## Notes for the implementing engineer

- **Subagent-driven cadence preference.** Per the entity-graph plan retrospective, the user prefers implementer-only with one final code review at the end. Do NOT run a per-task two-stage review. After Task 10.1 passes, dispatch a single `superpowers:code-reviewer` agent over the full diff (`git diff main...HEAD`).
- **Always use `claude-opus-4.7-1m-internal` for any subagent dispatch** (stored repo memory).
- **Each task ends with a `git commit`** so progress is recoverable from `git log` alone if the session crashes mid-run.
- **Kuzu 0.6.1 quirks** (all in stored memories — re-read before any Cypher work):
  1. Empty-list parameter values fail at driver `prepare()` ("ANY type" error) — never bind an empty list.
  2. Single-letter node alias clashing with aggregate alias raises `AGGREGATE_FUNCTION` — rename the node alias.
  3. `ORDER BY x` where `x` matches a bound node variable name breaks — pick a different alias.
  4. `SET n += $map` not supported — emit per-key clauses.
  5. Inline `id STRING PRIMARY KEY` rejected — use trailing `PRIMARY KEY (id)`.
  6. Reserved words `starts`, `ends` need backticks even in MATCH/WHERE.
  7. `LIMIT $n` not supported — inline the int literal.
- **The stack already runs detached** (verified post-merge of the entity-graph plan). To stop a stale stack: `make down` from the repo root.
- **Test data path:** all tests use `tmp_path` for the entity graph; the live graph at `data/portal/entity_graph.kuzu` is only touched by Phase 10.1 (live verification) and the Phase 10.2 reseed.

