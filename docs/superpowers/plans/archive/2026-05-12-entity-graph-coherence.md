# Entity-Graph Coherence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the entity graph an honest, query-able representation of a small but real agency: one writer convention, populated agency entities, money that traverses to accounts, and decisions that carry meaning beyond a binary stamp.

**Architecture:** Four sequenced phases that each leave the system in a strictly better state.
1. **Unify the writer.** DataPack and the live event-bus path stop disagreeing on verb tense, persona role semantics, and which fields are populated. Single normalisation layer.
2. **Accounts substrate.** Add `Account` / `CostCentre` node kinds plus four new rel tables (`PAYS`, `OWED_BY`, `BOOKED_AGAINST`, `COSTED_TO`) and backfill them from existing `Money.attributes` JSON. Build the `/accounts` page on top.
3. **Agency entities live.** Migrate `_write_brands` and `creative_campaign` to first-class `Brand` / `Campaign` / `MediaPlan`. Wire DataPack one-shot workflows through the projection bus so `Pitch`-emitting projections actually run. Surface the missing kinds in `EntitiesPage`.
4. **Decisions tell a story.** Expand verdict vocabulary, project Decision JSON attributes onto first-class columns, add `decided_at` to every rel table, surface `PRECEDENT_OF` in the EntityView drawer, and bind Decision/Workflow to Period.

**Tech Stack:** Python 3.11, FastAPI, Kuzu 0.6.1, pytest, React/TypeScript, Vite, Vitest.

**Audit reference:** `tmp/entity-audit/FINDINGS.md` (gitignored) — full evidence. Quote IDs there map to gap-list items §9.

**Sequencing is NOT optional.** Phase 1 must land first or every later edge gets corrupted on the next reseed. Phase 2 unlocks the finance-narrative half. Phase 3 unlocks the agency-narrative half. Phase 4 is polish that turns volume into meaning.

---

## Phase 0 — Audit baseline & branch hygiene

**Goal:** Lock in the current numbers as a regression baseline so every later phase can prove it improved them.

### Task 0.1: Snapshot current entity-graph metrics into a baseline test

**Files:**
- Create: `tests/api/server/services/test_entity_graph_baseline.py`

- [ ] **Step 1: Write the baseline assertions**

```python
"""Baseline metrics from the audit on 2026-05-12.

This is intentionally a *change-detector* — it pins the current numbers
so each phase of the entity-graph-coherence plan can show measurable
deltas. Update the constants below when a phase intentionally changes
the shape (verdict vocab in Phase 4, agency kinds populating in Phase 3,
etc.) and reference the plan task that justified the change.
"""
from __future__ import annotations

import os
from pathlib import Path

import kuzu
import pytest


GRAPH_PATH = Path(os.getenv("PORTAL_DATA_DIR", "data/portal")) / "entity_graph.kuzu"

# Empty kinds today — these MUST go non-zero by end of Phase 3.
EMPTY_KINDS_TODAY = {"Brand", "Campaign", "Pitch", "MediaPlan"}

# Empty rels today — Phase 2 fills accounts rels, Phase 3 fills agency rels.
EMPTY_RELS_TODAY = {
    "BRAND_OF", "CAMPAIGN_FOR", "EXECUTED_BY", "SUPPLIED_BY",
    "PITCH_FOR", "RESULTED_IN",
    "DECIDED_BRAND", "DECIDED_CAMPAIGN", "DECIDED_PITCH",
    "DECIDED_MEDIAPLAN", "DECIDED_SUBSIDIARY", "DECIDED_PLACE",
    "DECIDED_ON",  # legacy, intentionally empty
}


@pytest.fixture(scope="module")
def conn() -> kuzu.Connection:
    if not GRAPH_PATH.exists():
        pytest.skip(f"no entity graph at {GRAPH_PATH}")
    db = kuzu.Database(str(GRAPH_PATH), read_only=True)
    return kuzu.Connection(db)


def _count_nodes(conn: kuzu.Connection, kind: str) -> int:
    res = conn.execute(f"MATCH (n:{kind}) RETURN count(*) AS c")
    return int(res.get_next()[0])


def _count_rels(conn: kuzu.Connection, rel: str) -> int:
    res = conn.execute(f"MATCH ()-[r:{rel}]->() RETURN count(*) AS c")
    return int(res.get_next()[0])


def test_empty_kinds_baseline(conn):
    """Phase 3 will flip these from 0 to non-zero. Failing fixtures are
    expected then — update the EMPTY_KINDS_TODAY set."""
    for k in EMPTY_KINDS_TODAY:
        assert _count_nodes(conn, k) == 0, f"{k} should still be empty pre-Phase 3"


def test_empty_rels_baseline(conn):
    for r in EMPTY_RELS_TODAY:
        assert _count_rels(conn, r) == 0, f"{r} should still be empty pre-fill"


def test_decision_verdict_vocab_today(conn):
    """Two-flavour bug: 'approve' (live) + 'approved' (datapack). Phase 1
    collapses these to a single token; this test will need updating then."""
    res = conn.execute(
        "MATCH (d:Decision) WHERE d.verdict IS NOT NULL "
        "RETURN d.verdict AS v"
    )
    seen: set[str] = set()
    while res.has_next():
        seen.add(res.get_next()[0])
    assert "approve" in seen
    assert "approved" in seen
    assert "reject" in seen


def test_persona_role_carries_person_ids_today(conn):
    """DataPack writes random person ids into persona_role. Phase 1 fixes
    this; flip the assertion then."""
    res = conn.execute(
        "MATCH (d:Decision) WHERE d.persona_role STARTS WITH 'PERSON-' "
        "RETURN count(*) AS c"
    )
    assert int(res.get_next()[0]) > 0, (
        "persona_role-as-person-id leak should still exist pre-Phase 1"
    )


def test_money_has_no_org_edges_today(conn):
    """Money attributes carry vendor_id/client_id but no graph edges to
    Organisation. Phase 2 adds PAYS/OWED_BY rels; flip assertions then."""
    res = conn.execute("MATCH (m:Money)-[r]-(o:Organisation) RETURN count(*) AS c")
    assert int(res.get_next()[0]) == 0
```

- [ ] **Step 2: Run it to verify baseline matches reality**

```
pytest tests/api/server/services/test_entity_graph_baseline.py -v
```

Expected: all 5 tests PASS against the live DB.

- [ ] **Step 3: Commit**

```
git add tests/api/server/services/test_entity_graph_baseline.py
git commit -m "test: pin entity-graph baseline metrics from 2026-05-12 audit"
```

### Task 0.2: Delete the stale duplicate Kuzu DB

**Files:**
- Delete: `api/data/portal/entity_graph.kuzu/`

- [ ] **Step 1: Confirm the stale dir is not referenced from runtime code**

```
grep -rn "api/data/portal" api/ tests/ scripts/ web/
```

Expected: zero hits. (`docs/` is excluded from the grep — this plan file references the path repeatedly, which is fine; it's documenting the cleanup, not depending on it.)

Also check whether `api/data/portal/{email_outbox,kpis.sqlite,magic_links.sqlite}` are stale duplicates of the live versions in `data/portal/`:

```
ls -la api/data/portal/ data/portal/
```

If the `api/data/portal/` siblings have stale mtimes (older than the live ones), delete the whole directory tree in Step 2 below; otherwise scope the delete to just `entity_graph.kuzu`.

- [ ] **Step 2: Remove it**

```
# Scope based on Step 1 finding — at minimum:
rm -rf api/data/portal/entity_graph.kuzu
# OR (if every sibling under api/data/portal/ proved stale):
# rm -rf api/data/portal
git add -A api/data
git commit -m "chore: remove stale duplicate entity_graph.kuzu (live one is data/portal/)"
```

---

## Phase 1 — Unify the writers

**Goal:** One vocabulary for verdicts, persona_role, source_workflows, and Person attributes regardless of whether the data was written by the live event-bus path or by `DataPack`. Eliminate the 196 id-only Person ghosts and the `approve`/`approved` split.

### Task 1.1: Centralise verdict vocabulary

**Files:**
- Create: `api/server/services/decision_vocab.py`
- Test: `tests/api/server/services/test_decision_vocab.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the centralised decision vocabulary."""
from __future__ import annotations

import pytest

from api.server.services.decision_vocab import (
    VERDICTS,
    canonical_verdict,
    is_valid_verdict,
)


def test_known_verdicts_listed():
    assert "approve" in VERDICTS
    assert "reject" in VERDICTS
    assert "escalate" in VERDICTS
    assert "defer" in VERDICTS
    assert "request_changes" in VERDICTS


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("approve", "approve"),
        ("approved", "approve"),
        ("APPROVED", "approve"),
        (" approve ", "approve"),
        ("reject", "reject"),
        ("rejected", "reject"),
        ("escalate", "escalate"),
        ("escalated", "escalate"),
    ],
)
def test_canonical_verdict_normalises(raw, expected):
    assert canonical_verdict(raw) == expected


def test_canonical_verdict_unknown_passes_through():
    # We don't want unknown verdicts to silently become "approve".
    assert canonical_verdict("partial") == "partial"


def test_is_valid_verdict():
    assert is_valid_verdict("approve")
    assert is_valid_verdict("reject")
    assert not is_valid_verdict("approved")  # callers must canonicalise first
    assert not is_valid_verdict("")
```

- [ ] **Step 2: Verify it fails**

```
pytest tests/api/server/services/test_decision_vocab.py -v
```

Expected: FAIL with `ModuleNotFoundError: api.server.services.decision_vocab`.

- [ ] **Step 3: Implement the module**

```python
"""Canonical Decision verdict vocabulary.

The graph today carries both `approve` (live event-bus path) and
`approved` (DataPack seed) as distinct verdict values. This module is
the single source of truth — every projection, the seed pack, and the
HTTP read layer call ``canonical_verdict`` so the column has one shape.
"""
from __future__ import annotations

VERDICTS: frozenset[str] = frozenset({
    "approve",
    "reject",
    "escalate",
    "defer",
    "request_changes",
    "partial",
    "void",
})

_ALIASES: dict[str, str] = {
    "approved": "approve",
    "ok": "approve",
    "rejected": "reject",
    "deny": "reject",
    "denied": "reject",
    "escalated": "escalate",
    "deferred": "defer",
    "changes_requested": "request_changes",
    "voided": "void",
}


def canonical_verdict(raw: str | None) -> str:
    if raw is None:
        return ""
    s = raw.strip().lower()
    return _ALIASES.get(s, s)


def is_valid_verdict(s: str | None) -> bool:
    return s in VERDICTS
```

- [ ] **Step 4: Verify it passes**

```
pytest tests/api/server/services/test_decision_vocab.py -v
```

Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```
git add api/server/services/decision_vocab.py tests/api/server/services/test_decision_vocab.py
git commit -m "feat(entity-graph): central decision verdict vocabulary"
```

### Task 1.2: Apply canonical_verdict in build_decision and DataPack

**Files:**
- Modify: `api/server/services/entity_projections/__init__.py` (the `build_decision` function around line 90)
- Modify: `api/server/data_fabric/pack.py` (`_write_decisions` — find the verdict literal)
- Test: extend `tests/api/server/services/test_decision_vocab.py`

- [ ] **Step 1: Write the failing integration test**

Add to `tests/api/server/services/test_decision_vocab.py`:

```python
from api.server.services.entity_projections import build_decision
from tests.api.server.services.entity_projections._helpers import make_workflow


def test_build_decision_canonicalises_verdict():
    wf = make_workflow(
        "TST-0001", "ap-invoice", {},
        decisions=[{
            "phase": "ap_clerk_signoff", "verdict": "approved",
            "reason": "ok", "decided_at": "2026-05-12T10:00:00",
        }],
    )
    d = build_decision(
        wf, gate_phase="ap_clerk_signoff", persona_role="ap_clerk",
        source_event="workflow.hitl.requested", decided_on=("MONEY-X",),
    )
    assert d is not None
    assert d.verdict == "approve"  # not "approved"
```

- [ ] **Step 2: Verify it fails**

```
pytest tests/api/server/services/test_decision_vocab.py::test_build_decision_canonicalises_verdict -v
```

Expected: FAIL — `assert "approved" == "approve"`.

- [ ] **Step 3: Apply canonicalisation in build_decision**

In `api/server/services/entity_projections/__init__.py`, modify the `build_decision` return:

```python
from api.server.services.decision_vocab import canonical_verdict  # add at top

# ... inside build_decision, change verdict line to:
    return DecisionWrite(
        workflow_id=workflow.id,
        phase=gate_phase,
        persona_role=str(entry.get("persona_role") or persona_role),
        verdict=canonical_verdict(entry.get("verdict", "")),
        reason=str(entry.get("reason", "")),
        decided_at=str(entry.get("decided_at", "")),
        source_event=source_event,
        attributes=dict(attributes or {}),
        decided_on=decided_on,
    )
```

- [ ] **Step 4: Apply canonicalisation in DataPack `_write_decisions`**

In `api/server/data_fabric/pack.py`, find the verdict literal `"approved"` inside `_write_decisions` and replace with `canonical_verdict("approve")` (i.e. `"approve"`). Add `from api.server.services.decision_vocab import canonical_verdict` to the imports at the top of `pack.py`.

- [ ] **Step 5: Run focused tests**

```
pytest tests/api/server/services/test_decision_vocab.py tests/api/server/services/entity_projections/ -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```
git add api/server/services/entity_projections/__init__.py api/server/data_fabric/pack.py tests/api/server/services/test_decision_vocab.py
git commit -m "fix(entity-graph): canonicalise verdict everywhere; remove approve/approved split"
```

### Task 1.3: Stop writing person ids into Decision.persona_role from DataPack

**Files:**
- Modify: `api/server/data_fabric/pack.py` (`_write_decisions`)
- Modify: `api/server/data_fabric/employee_gen.py` (expose `persona_role` if not already on the dataclass — it is, see line ~115 of pack.py: `role=emp.persona_role`)

- [ ] **Step 1: Write the failing test**

Add to `tests/api/server/data_fabric/test_pack.py` (create if missing):

```python
"""DataPack regression tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.server.data_fabric.pack import DataPack


@pytest.fixture
def materialised(tmp_path: Path):
    pack = DataPack(name="test", seed=42, fiscal_year=2026)
    out = tmp_path / "graph.kuzu"
    summary = pack.materialise(out)
    return out, summary


def test_no_person_id_leaks_into_decision_persona_role(materialised):
    import kuzu
    db_path, _ = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    res = conn.execute(
        "MATCH (d:Decision) WHERE d.persona_role STARTS WITH 'PERSON-' "
        "RETURN count(*) AS c"
    )
    assert int(res.get_next()[0]) == 0, (
        "DataPack must write role strings, not person ids, into persona_role"
    )
```

- [ ] **Step 2: Verify it fails**

```
pytest tests/api/server/data_fabric/test_pack.py::test_no_person_id_leaks_into_decision_persona_role -v
```

Expected: FAIL.

- [ ] **Step 3: Fix DataPack `_write_decisions`**

Open `api/server/data_fabric/pack.py`. The current code (around L562) builds `person_ids = [e.id for e in employees]` once and then picks `persona = person_ids[rng.randint(...)]` — which puts a `PERSON-EMP-XXXX` id into the `persona_role` column.

Replace:

```python
        person_ids = [e.id for e in employees]
        for entry in timeline:
            wf = entry.workflow
            for phase, verdict in (("intake", "approved"), ("approve", "approved")):
                persona = (
                    person_ids[rng.randint(0, len(person_ids) - 1)]
                    if person_ids else f"PERSONA-{wf.type}"
                )
```

with:

```python
        # Plan task 1.3: persona_role is a ROLE STRING ("ap_clerk"), not a
        # Person id. The actual decider's id moves to attributes.decider_id
        # so TOUCHED edges and provenance are preserved without polluting
        # the role column.
        persona_pool = [(e.id, e.persona_role) for e in employees]
        person_ids = [pid for pid, _ in persona_pool]  # kept for decided_on picking below
        for entry in timeline:
            wf = entry.workflow
            # Plan task 1.2: canonical verdict — "approve", not "approved".
            for phase, verdict in (("intake", canonical_verdict("approve")),
                                   ("approve", canonical_verdict("approve"))):
                if persona_pool:
                    decider_id, persona = persona_pool[rng.randint(0, len(persona_pool) - 1)]
                else:
                    decider_id, persona = f"PERSON-stub-{wf.type}", f"PERSONA-{wf.type}"
```

Then update the `record_decision` call further down the same function to thread the decider id into the attributes blob:

```python
                decision_id = graph.record_decision(
                    workflow_id=wf.id,
                    phase=phase,
                    persona_role=persona,
                    verdict=verdict,
                    reason=f"{wf.type} {phase} via DataPack seed",
                    decided_at=decided_at,
                    source_event=f"datapack.{wf.type}.{phase}",
                    attributes={"workflow_type": wf.type, "decider_id": decider_id},
                    decided_on=tuple(decided_on),
                )
```

Add `from api.server.services.decision_vocab import canonical_verdict` to the imports at the top of `pack.py` (Phase 1 Task 1.2 added this; if it's already there from that task, this step is a no-op).

- [ ] **Step 4: Verify it passes**

```
pytest tests/api/server/data_fabric/test_pack.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add api/server/data_fabric/pack.py tests/api/server/data_fabric/test_pack.py
git commit -m "fix(datapack): write role string to persona_role; person id moves to attributes.decider_id"
```

### Task 1.4: Backfill named Persons so id-only ghosts disappear

**Files:**
- Modify: `api/server/services/entity_graph.py` (`upsert` for `Person` — add a "don't blank existing fields" guard)
- Modify: `api/server/services/entity_projections/__init__.py` (add helper `ghost_person`)
- Test: `tests/api/server/services/test_entity_graph_person_merge.py`

- [ ] **Step 1: Write the failing test**

```python
"""Person upsert merge semantics — Phase 1 ghost-person fix.

When a projection later reflects a fully-attributed Person, the upsert
must NOT blank out fields that were populated by an earlier seed write.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    return EntityGraph(tmp_path / "g.kuzu")


def test_seed_then_projection_does_not_blank_name(graph: EntityGraph):
    # Phase 1: full named seed from DataPack
    graph.upsert(EntityWrite(
        kind="Person", id="PERSON-EMP-0042",
        attrs={"name": "Aisha Khan", "email": "aisha@zava", "role": "ap_clerk"},
    ))
    # Phase 2: a workflow projection later references the same id with no attrs
    graph.upsert(EntityWrite(
        kind="Person", id="PERSON-EMP-0042",
        attrs={},
        source_workflows=("API-0001",),
    ))
    rows = graph.query(
        "MATCH (p:Person {id: 'PERSON-EMP-0042'}) RETURN p.name, p.role"
    )
    assert rows[0]["p.name"] == "Aisha Khan"
    assert rows[0]["p.role"] == "ap_clerk"
```

- [ ] **Step 2: Verify it fails**

```
pytest tests/api/server/services/test_entity_graph_person_merge.py -v
```

Expected: FAIL — second upsert blanks the name.

- [ ] **Step 3: Add merge guard to `_build_set_clauses`**

The SET-clause assembly is shared between `upsert` and `link` via [`_build_set_clauses`](../../api/server/services/entity_graph.py#L519). Edit that helper, NOT `upsert` directly. Add an opt-in `skip_empty` parameter so `upsert` (merge semantics) can drop empty values while `link` (rel attrs are usually intentional) keeps current behaviour.

Replace the helper signature + body in `api/server/services/entity_graph.py` (around L519–L565):

```python
def _build_set_clauses(
    attrs: Mapping[str, Any],
    *,
    prefix: str,
    kind: str | None = None,
    skip_empty: bool = False,
) -> tuple[list[str], dict[str, Any]]:
    """Build per-attr SET-clause fragments and parameter dict for Cypher.

    See module docstring. ``skip_empty=True`` (set by :meth:`EntityGraph.upsert`)
    drops keys whose value is None / "" / [] so a later projection-time upsert
    can NOT blank a field that an earlier seed-time upsert populated. ``link``
    callers leave it False because rel attrs are usually written intentionally
    and the empty-string case is rare there.
    """
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for i, (key, value) in enumerate(attrs.items()):
        if kind != "Decision" and key in _ATTR_METADATA_KEYS:
            continue
        if skip_empty and (value is None or value == "" or value == []):
            continue
        if not _VALID_ATTR_KEY.match(key):
            raise ValueError(
                f"invalid attr key: {key!r} "
                f"(must match {_VALID_ATTR_KEY.pattern})"
            )
        placeholder = f"attr_{i}"
        clauses.append(f"{prefix}.`{key}` = ${placeholder}")
        params[placeholder] = value
    return clauses, params
```

Then update the single call site inside `upsert` (around L780) to pass `skip_empty=True`:

```python
            attr_clauses, attr_params = _build_set_clauses(
                entity.attrs, prefix="n", kind=entity.kind, skip_empty=True,
            )
```

Do NOT change the call sites inside `link()` or `record_decision()` — they keep the default `skip_empty=False` so explicit empty rel attrs still get written through if a caller passes them.

- [ ] **Step 4: Verify the test passes**

```
pytest tests/api/server/services/test_entity_graph_person_merge.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the projection test suite to catch regressions**

```
pytest tests/api/server/services/entity_projections/ -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```
git add api/server/services/entity_graph.py tests/api/server/services/test_entity_graph_person_merge.py
git commit -m "fix(entity-graph): never blank populated fields with empty upsert values"
```

### Task 1.5: Reseed and verify the baseline tests start failing in the right way

**Files:** none

- [ ] **Step 1: Wipe and reseed the live graph**

```
# API must be stopped first — Kuzu locks the directory while open.
rm -rf data/portal/entity_graph.kuzu data/portal/entity_graph.kuzu.bak
uv run python -c "from api.server.data_fabric.pack import build_zava_pack; r = build_zava_pack().materialise('data/portal/entity_graph.kuzu'); print(r)"
```

(`scripts/boot-demo.sh` uses this same one-liner under `BOOT_DEMO_SNAPSHOT=zava-baseline`. There is no `--rebuild` flag on `scripts/zava-snapshot.py`; that script only `save | restore | list | info`.)

- [ ] **Step 2: Re-run the audit dump and confirm**

```
python tmp/entity-audit/dump.py
python tmp/entity-audit/dump_rels.py
jq '.decision_verdict' tmp/entity-audit/summary.json
```

Expected output for verdict histogram: only `{"approve": ..., "reject": ...}` — no `"approved"` key.

- [ ] **Step 3: Re-run baseline test**

```
pytest tests/api/server/services/test_entity_graph_baseline.py -v
```

Expected: `test_decision_verdict_vocab_today` and `test_persona_role_carries_person_ids_today` now FAIL — that's correct. Update the baseline file to invert those assertions (delete the `assert "approved" in seen` line; flip the persona-role test to `assert int(...) == 0`).

- [ ] **Step 4: Commit baseline update**

```
git add tests/api/server/services/test_entity_graph_baseline.py
git commit -m "test: update baseline — Phase 1 has unified writer vocab"
```

---

## Phase 2 — Accounts substrate

**Goal:** Money becomes traversable to who owes it, who's paid, what GL account it hits, and which brand or campaign it costs to. Build an `/accounts` page that a finance persona could plausibly use.

### Task 2.1: Add `Account` and `CostCentre` node tables to the Kuzu schema

**Files:**
- Modify: `api/server/services/entity_graph.py` — extend `_NODE_TABLES`
- Test: `tests/api/server/services/test_entity_graph_accounts_schema.py`

- [ ] **Step 1: Write the failing test**

```python
"""Phase 2 — Account / CostCentre node tables."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    return EntityGraph(tmp_path / "g.kuzu")


def test_account_node_writeable(graph: EntityGraph):
    graph.upsert(EntityWrite(
        kind="Account", id="ACC-6010",
        attrs={
            "code": "6010",
            "name": "Production cost — external",
            "type": "expense",
            "currency": "GBP",
        },
    ))
    rows = graph.query("MATCH (a:Account {id: 'ACC-6010'}) RETURN a.name AS n")
    assert rows[0]["n"] == "Production cost — external"


def test_costcentre_node_writeable(graph: EntityGraph):
    graph.upsert(EntityWrite(
        kind="CostCentre", id="CC-zava-creative",
        attrs={
            "name": "Zava Creative",
            "subsidiary_id": "ORG-zava-creative",
            "owner_role": "regional_account_lead",
        },
    ))
    rows = graph.query(
        "MATCH (c:CostCentre {id: 'CC-zava-creative'}) RETURN c.name AS n"
    )
    assert rows[0]["n"] == "Zava Creative"
```

- [ ] **Step 2: Verify it fails**

```
pytest tests/api/server/services/test_entity_graph_accounts_schema.py -v
```

Expected: FAIL with Kuzu binder error (table doesn't exist).

- [ ] **Step 3: Add to `_NODE_TABLES`**

In `api/server/services/entity_graph.py`, append to `_NODE_TABLES`:

```python
    (
        "Account",
        """
        CREATE NODE TABLE IF NOT EXISTS Account (
            id STRING,
            code STRING, name STRING, type STRING, currency STRING,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
    (
        "CostCentre",
        """
        CREATE NODE TABLE IF NOT EXISTS CostCentre (
            id STRING,
            name STRING, subsidiary_id STRING, owner_role STRING,
            source_workflows STRING[],
            attributes STRING,
            PRIMARY KEY (id)
        )
        """,
    ),
```

Also extend the route-layer `_KINDS` and `_PROJECT_FIELDS_BY_KIND` in `api/server/routes/entities.py` so the new kinds are accepted by `/api/entities?kind=...`. The graph-side `_VALID_KINDS` is auto-derived from `_NODE_TABLES` (see `entity_graph.py:460`) so it updates for free — nothing extra to edit there.

- [ ] **Step 4: Verify the test passes**

```
pytest tests/api/server/services/test_entity_graph_accounts_schema.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add api/server/services/entity_graph.py api/server/routes/entities.py tests/api/server/services/test_entity_graph_accounts_schema.py
git commit -m "feat(entity-graph): add Account and CostCentre node kinds"
```

### Task 2.2: Add four new rel tables: PAYS, OWED_BY, BOOKED_AGAINST, COSTED_TO

**Files:**
- Modify: `api/server/services/entity_graph.py` — extend `_REL_TABLES`
- Test: `tests/api/server/services/test_entity_graph_accounts_rels.py`

- [ ] **Step 1: Write the failing test**

```python
"""Phase 2 — Money↔Account / Money↔Org / Money↔Brand rel tables."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite, RelWrite


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    g = EntityGraph(tmp_path / "g.kuzu")
    g.upsert(EntityWrite(
        kind="Money", id="MONEY-INV-1",
        attrs={"kind": "invoice", "amount": 1000.0, "currency": "GBP"},
    ))
    g.upsert(EntityWrite(
        kind="Organisation", id="ORG-vendor-globex",
        attrs={"name": "Globex", "kind": "vendor"},
    ))
    g.upsert(EntityWrite(
        kind="Account", id="ACC-6010",
        attrs={"code": "6010", "name": "External production", "type": "expense"},
    ))
    g.upsert(EntityWrite(
        kind="CostCentre", id="CC-zava-creative",
        attrs={"name": "Zava Creative", "subsidiary_id": "ORG-zava-creative"},
    ))
    return g


def test_pays_money_to_org(graph: EntityGraph):
    graph.link("MONEY-INV-1", "PAYS", "ORG-vendor-globex")
    rows = graph.query(
        "MATCH (m:Money)-[:PAYS]->(o:Organisation) "
        "RETURN m.id AS m, o.id AS o"
    )
    assert rows == [{"m": "MONEY-INV-1", "o": "ORG-vendor-globex"}]


def test_booked_against_account(graph: EntityGraph):
    graph.link("MONEY-INV-1", "BOOKED_AGAINST", "ACC-6010")
    assert graph.query(
        "MATCH (m:Money)-[:BOOKED_AGAINST]->(a:Account) RETURN count(*) AS c"
    )[0]["c"] == 1


def test_costed_to_costcentre(graph: EntityGraph):
    graph.link("MONEY-INV-1", "COSTED_TO", "CC-zava-creative")
    assert graph.query(
        "MATCH (m:Money)-[:COSTED_TO]->(c:CostCentre) RETURN count(*) AS c"
    )[0]["c"] == 1
```

- [ ] **Step 2: Verify it fails**

```
pytest tests/api/server/services/test_entity_graph_accounts_rels.py -v
```

Expected: FAIL with Kuzu binder error.

- [ ] **Step 3: Add to `_REL_TABLES`**

In `api/server/services/entity_graph.py`, append to `_REL_TABLES`:

```python
    ("PAYS", "CREATE REL TABLE IF NOT EXISTS PAYS (FROM Money TO Organisation, posted_at TIMESTAMP)"),
    ("OWED_BY", "CREATE REL TABLE IF NOT EXISTS OWED_BY (FROM Money TO Organisation, posted_at TIMESTAMP)"),
    ("BOOKED_AGAINST", "CREATE REL TABLE IF NOT EXISTS BOOKED_AGAINST (FROM Money TO Account, posted_at TIMESTAMP)"),
    ("BOOKED_AGAINST_CC", "CREATE REL TABLE IF NOT EXISTS BOOKED_AGAINST_CC (FROM Money TO CostCentre, posted_at TIMESTAMP)"),
    ("COSTED_TO", "CREATE REL TABLE IF NOT EXISTS COSTED_TO (FROM Money TO CostCentre, posted_at TIMESTAMP)"),
    # Note: COSTED_TO targets CostCentre. A separate Money→Brand cost rel
    # is added in Phase 3 (Task 3.5) once Brand nodes exist.
```

(`BOOKED_AGAINST_CC` lets a row be booked simultaneously to a GL account and a cost centre. If you'd rather have a single typed `BOOKED_AGAINST` that accepts both, you'd need a polymorphic encoding — keep them separate for Phase 2.)

- [ ] **Step 4: Verify the test passes**

```
pytest tests/api/server/services/test_entity_graph_accounts_rels.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add api/server/services/entity_graph.py tests/api/server/services/test_entity_graph_accounts_rels.py
git commit -m "feat(entity-graph): add PAYS / OWED_BY / BOOKED_AGAINST / COSTED_TO rel tables"
```

### Task 2.3: Backfill PAYS / OWED_BY edges from existing Money.attributes JSON

**Files:**
- Create: `scripts/backfill_money_org_edges.py`
- Test: `tests/scripts/test_backfill_money_org_edges.py`

- [ ] **Step 1: Write the failing test**

```python
"""Backfill: every Money row whose attributes JSON contains vendor_id or
client_id should get a PAYS / OWED_BY edge to that Organisation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite
from scripts.backfill_money_org_edges import backfill


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    g = EntityGraph(tmp_path / "g.kuzu")
    g.upsert(EntityWrite(
        kind="Organisation", id="ORG-vendor-globex",
        attrs={"name": "Globex", "kind": "vendor"},
    ))
    g.upsert(EntityWrite(
        kind="Organisation", id="ORG-client-acme",
        attrs={"name": "Acme", "kind": "client"},
    ))
    g.upsert(EntityWrite(
        kind="Money", id="MONEY-INV-1",
        attrs={
            "kind": "invoice", "amount": 1000.0, "currency": "GBP",
            "attributes": json.dumps({"vendor_id": "ORG-vendor-globex"}),
        },
    ))
    g.upsert(EntityWrite(
        kind="Money", id="MONEY-RECHARGE-1",
        attrs={
            "kind": "recharge", "amount": 500.0, "currency": "GBP",
            "attributes": json.dumps({"client_id": "ORG-client-acme"}),
        },
    ))
    return g


def test_backfill_creates_pays_for_invoices(graph: EntityGraph):
    backfill(graph)
    rows = graph.query(
        "MATCH (m:Money)-[:PAYS]->(o:Organisation) "
        "RETURN m.id AS m, o.id AS o"
    )
    assert {"m": "MONEY-INV-1", "o": "ORG-vendor-globex"} in rows


def test_backfill_creates_owed_by_for_recharges(graph: EntityGraph):
    backfill(graph)
    rows = graph.query(
        "MATCH (m:Money)-[:OWED_BY]->(o:Organisation) "
        "RETURN m.id AS m, o.id AS o"
    )
    assert {"m": "MONEY-RECHARGE-1", "o": "ORG-client-acme"} in rows


def test_backfill_idempotent(graph: EntityGraph):
    backfill(graph)
    backfill(graph)
    n = graph.query("MATCH ()-[r:PAYS]->() RETURN count(*) AS c")[0]["c"]
    assert n == 1
```

- [ ] **Step 2: Verify it fails**

```
pytest tests/scripts/test_backfill_money_org_edges.py -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the backfill script**

```python
"""scripts/backfill_money_org_edges.py — one-shot backfill.

Reads Money.attributes JSON and writes:
  - PAYS    (Money→Organisation) when attributes.vendor_id is set
  - OWED_BY (Money→Organisation) when attributes.client_id is set

Both writes use Kuzu's MERGE semantics so re-running is a no-op. Designed
to be run after `EntityGraph` schema has been extended with the rel
tables (Plan task 2.2).

Usage:
    python -m scripts.backfill_money_org_edges \\
        --kuzu data/portal/entity_graph.kuzu
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from api.server.services.entity_graph import EntityGraph

log = logging.getLogger(__name__)


def backfill(graph: EntityGraph) -> dict[str, int]:
    rows = graph.query(
        "MATCH (m:Money) WHERE m.attributes IS NOT NULL "
        "RETURN m.id AS id, m.attributes AS a"
    )
    pays = 0
    owed = 0
    for r in rows:
        try:
            a = json.loads(r["a"])
        except Exception:
            continue
        if not isinstance(a, dict):
            continue
        vendor_id = a.get("vendor_id")
        client_id = a.get("client_id")
        if vendor_id:
            graph.conn.execute(
                "MATCH (m:Money), (o:Organisation) "
                "WHERE m.id = $m AND o.id = $o "
                "MERGE (m)-[:PAYS]->(o)",
                {"m": r["id"], "o": vendor_id},
            )
            pays += 1
        if client_id:
            graph.conn.execute(
                "MATCH (m:Money), (o:Organisation) "
                "WHERE m.id = $m AND o.id = $o "
                "MERGE (m)-[:OWED_BY]->(o)",
                {"m": r["id"], "o": client_id},
            )
            owed += 1
    log.info("backfill: pays=%d owed_by=%d", pays, owed)
    return {"pays": pays, "owed_by": owed}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--kuzu", default=os.getenv("PORTAL_DATA_DIR", "data/portal") + "/entity_graph.kuzu")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO)
    g = EntityGraph(Path(args.kuzu))
    summary = backfill(g)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Verify it passes**

```
pytest tests/scripts/test_backfill_money_org_edges.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 5: Wire backfill into DataPack so reseeds get it for free**

In `api/server/data_fabric/pack.py`, at the end of `materialise()` (after `_write_decisions`), add:

```python
            from scripts.backfill_money_org_edges import backfill
            money_edges = backfill(graph)
            summary["pays_links"] = money_edges["pays"]
            summary["owed_by_links"] = money_edges["owed_by"]
```

**Sequencing note (Phase 3 dependency):** Phase 3 Task 3.5 will extend the same backfill to write `COSTED_TO_BRAND` edges. While Phase 2 is on its own, that future extension will silently no-op because Brand nodes don't exist yet (`_write_brands` is still emitting `Organisation(kind='brand')`). That's expected and documented in Task 3.5's first step — don't add a Brand-related assertion to the Phase 2 backfill test.

- [ ] **Step 6: Commit**

```
git add scripts/backfill_money_org_edges.py tests/scripts/test_backfill_money_org_edges.py api/server/data_fabric/pack.py
git commit -m "feat(accounts): backfill PAYS/OWED_BY from Money.attributes JSON; wire into DataPack"
```

### Task 2.4: Seed a baseline chart of accounts and cost centres in DataPack

**Files:**
- Modify: `api/server/data_fabric/pack.py` (add `_write_accounts` and `_write_cost_centres`)
- Modify: `api/server/data_fabric/money_gen.py` (add `account_id` and `cost_centre_id` to `GeneratedMoney` and pick them per row)
- Test: extend `tests/api/server/data_fabric/test_pack.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/api/server/data_fabric/test_pack.py`:

```python
def test_chart_of_accounts_seeded(materialised):
    import kuzu
    db_path, summary = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    n = int(conn.execute("MATCH (a:Account) RETURN count(*) AS c").get_next()[0])
    assert n >= 8, f"expected at least 8 GL accounts, got {n}"


def test_cost_centres_one_per_subsidiary(materialised):
    import kuzu
    db_path, _ = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    n = int(conn.execute("MATCH (c:CostCentre) RETURN count(*) AS c").get_next()[0])
    # 5 subsidiaries in _SUBSIDIARY_META but the holding (ORG-zava-group)
    # doesn't get a CC — holdings don't take cost. So 4.
    assert n == 4, f"expected 4 cost centres (one per non-holding subsidiary), got {n}"


def test_every_money_row_booked(materialised):
    import kuzu
    db_path, _ = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    total = int(conn.execute("MATCH (m:Money) RETURN count(*) AS c").get_next()[0])
    booked = int(conn.execute(
        "MATCH (m:Money)-[:BOOKED_AGAINST]->(:Account) RETURN count(DISTINCT m) AS c"
    ).get_next()[0])
    assert booked == total, (
        f"every Money row must be booked to a GL account; {booked}/{total}"
    )
```

- [ ] **Step 2: Verify it fails**

```
pytest tests/api/server/data_fabric/test_pack.py -v -k "chart_of_accounts or cost_centres or money_row_booked"
```

Expected: all three FAIL.

- [ ] **Step 3: Add chart-of-accounts constant + seed function in pack.py**

```python
# Near the top of api/server/data_fabric/pack.py with the other constants:
_GL_ACCOUNTS: tuple[tuple[str, str, str, str], ...] = (
    # (id, code, name, type)
    ("ACC-4000", "4000", "Revenue — fee income",         "revenue"),
    ("ACC-4100", "4100", "Revenue — media commission",   "revenue"),
    ("ACC-6010", "6010", "Production cost — external",   "expense"),
    ("ACC-6020", "6020", "Freelance talent",             "expense"),
    ("ACC-6100", "6100", "Media buys (pass-through)",    "expense"),
    ("ACC-7000", "7000", "Salaries & benefits",          "expense"),
    ("ACC-7200", "7200", "Travel & entertainment",       "expense"),
    ("ACC-7300", "7300", "Software & subscriptions",     "expense"),
    ("ACC-8500", "8500", "FX gains/losses",              "other"),
    ("ACC-9000", "9000", "Intercompany recharge",        "intercompany"),
)

# Money kind → GL account id mapping
_KIND_TO_ACCOUNT: dict[str, str] = {
    "invoice":     "ACC-6010",
    "po":          "ACC-6010",  # PO commitment hits same expense bucket
    "contract":    "ACC-6010",
    "commission":  "ACC-4100",
    "fx":          "ACC-8500",
    "fx-adj":      "ACC-8500",
    "recharge":    "ACC-9000",
    "budget-line": "ACC-6010",
}


def _write_accounts(self, graph: EntityGraph) -> int:
    for acc_id, code, name, type_ in _GL_ACCOUNTS:
        graph.upsert(EntityWrite(
            kind="Account", id=acc_id,
            attrs={"code": code, "name": name, "type": type_, "currency": "GBP"},
        ))
    return len(_GL_ACCOUNTS)


def _write_cost_centres(self, graph: EntityGraph) -> int:
    # Skip the holding (ORG-zava-group) — holdings don't take cost.
    n = 0
    for sub_id, name, country, _ in _SUBSIDIARY_META:
        if sub_id == _HOLDING_ID:
            continue
        cc_id = sub_id.replace("ORG-", "CC-")
        graph.upsert(EntityWrite(
            kind="CostCentre", id=cc_id,
            attrs={"name": name, "subsidiary_id": sub_id, "owner_role": "regional_account_lead"},
        ))
        n += 1
    return n
```

Call them from `materialise()` after `_write_subsidiaries`:

```python
            summary["accounts"] = self._write_accounts(graph)
            summary["cost_centres"] = self._write_cost_centres(graph)
```

In `_write_money` (after the existing `graph.upsert(...)` for each Money row), add:

```python
            account_id = _KIND_TO_ACCOUNT.get(row.kind, "ACC-6010")
            graph.conn.execute(
                "MATCH (m:Money), (a:Account) WHERE m.id = $m AND a.id = $a "
                "MERGE (m)-[:BOOKED_AGAINST]->(a)",
                {"m": row.id, "a": account_id},
            )
            # GeneratedMoney.subsidiary_id (NOT .subsidiary). Holding
            # money rows fall back to ORG-zava-group's CC equivalent
            # only if a CC was created for it; per Task 2.4 _write_cost_centres
            # skips the holding, so holding-routed rows won't get a COSTED_TO.
            sub_id = getattr(row, "subsidiary_id", None)
            if sub_id and sub_id != _HOLDING_ID:
                cc_id = sub_id.replace("ORG-", "CC-")
                graph.conn.execute(
                    "MATCH (m:Money), (c:CostCentre) WHERE m.id = $m AND c.id = $c "
                    "MERGE (m)-[:COSTED_TO]->(c)",
                    {"m": row.id, "c": cc_id},
                )
```

- [ ] **Step 4: Verify the new tests pass**

```
pytest tests/api/server/data_fabric/test_pack.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add api/server/data_fabric/pack.py tests/api/server/data_fabric/test_pack.py
git commit -m "feat(accounts): seed chart of accounts + cost centres; book every Money row"
```

### Task 2.5: HTTP route — `/api/accounts/summary`

**Files:**
- Create: `api/server/routes/accounts.py`
- Modify: `api/server/main.py` — add `accounts_router` to the existing `for r in (...)` tuple (around L379)
- Test: `tests/api/server/routes/test_accounts.py`

- [ ] **Step 1: Write the failing test**

```python
"""Phase 2 — /api/accounts/summary route."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.server.main import app
from api.server.state import app_state
from tests.api.server.fixtures.entity_graph_seed import seed_account_demo


def test_accounts_summary_returns_per_account_totals(client_with_seed):
    r = client_with_seed.get("/api/accounts/summary")
    assert r.status_code == 200
    data = r.json()
    assert "accounts" in data
    rows = {a["id"]: a for a in data["accounts"]}
    assert "ACC-6010" in rows
    assert rows["ACC-6010"]["total_gbp"] > 0
    assert rows["ACC-6010"]["row_count"] >= 1


def test_accounts_summary_groups_by_period(client_with_seed):
    r = client_with_seed.get("/api/accounts/summary?group_by=period")
    assert r.status_code == 200
    assert "by_period" in r.json()


def test_accounts_summary_filters_by_subsidiary(client_with_seed):
    r = client_with_seed.get(
        "/api/accounts/summary?cost_centre=CC-zava-creative"
    )
    assert r.status_code == 200
    # Every returned account row must trace to CC-zava-creative
    for a in r.json()["accounts"]:
        assert "CC-zava-creative" in a.get("cost_centres", [])
```

For the fixture `client_with_seed`, create `tests/api/server/fixtures/entity_graph_seed.py` with a helper that seeds a tiny set of accounts/money + builds a `TestClient`.

- [ ] **Step 2: Verify it fails**

```
pytest tests/api/server/routes/test_accounts.py -v
```

Expected: FAIL — route does not exist.

- [ ] **Step 3: Implement the route**

```python
"""Read-only HTTP surface for the accounts substrate (Phase 2)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from api.server.state import app_state
from api.server.services.read_route_auth import (
    Actor, project_for_role, require_actor,
)

router = APIRouter(prefix="/api/accounts")


@router.get("/summary")
async def summary(
    group_by: str | None = Query(None, regex="^(period|cost_centre|none)?$"),
    cost_centre: str | None = None,
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    g = app_state.entities

    # Kuzu 0.6.1 has no pattern-comprehension subqueries; express the
    # cost-centre filter as an extra MATCH leg instead.
    base_match = (
        "MATCH (m:Money)-[:BOOKED_AGAINST]->(a:Account)"
    )
    cc_clause = ""
    params: dict[str, Any] = {}
    if cost_centre:
        base_match += ", (m)-[:COSTED_TO]->(:CostCentre {id: $cc})"
        params["cc"] = cost_centre

    rows = g.query(
        f"""
        {base_match}
        OPTIONAL MATCH (m)-[:COSTED_TO]->(c:CostCentre)
        RETURN a.id AS account_id, a.code AS code, a.name AS name,
               a.type AS type, sum(m.amount) AS total_gbp,
               count(DISTINCT m) AS row_count,
               collect(DISTINCT c.id) AS cost_centres
        """,
        params,
    )
    out = {
        "accounts": [
            {
                "id": r["account_id"],
                "code": r["code"],
                "name": r["name"],
                "type": r["type"],
                "total_gbp": float(r["total_gbp"] or 0),
                "row_count": int(r["row_count"]),
                "cost_centres": [c for c in (r["cost_centres"] or []) if c],
            }
            for r in rows
        ],
    }
    if group_by == "period":
        period_rows = g.query(
            """
            MATCH (m:Money)-[:BOOKED_AGAINST]->(a:Account)
            OPTIONAL MATCH (m)-[:BELONGS_TO]->(p:Period)
            RETURN p.id AS period_id, p.label AS label,
                   a.id AS account_id, sum(m.amount) AS total
            """
        )
        out["by_period"] = [
            {"period_id": r["period_id"], "label": r["label"],
             "account_id": r["account_id"], "total_gbp": float(r["total"] or 0)}
            for r in period_rows
        ]
    return project_for_role(out, actor.role)
```

In `api/server/main.py`, the routers are mounted via a single tuple loop (around L379). Add the import next to the other route imports near the top of the file:

```python
# Phase 2 — accounts substrate.
from api.server.routes.accounts import router as accounts_router
```

Then append `accounts_router` to the existing `for r in (...)` tuple (alongside `entities_router`, `kpis_router`, etc.). Do NOT add a free-standing `app.include_router(accounts.router)` after the loop — the file convention is the tuple.

- [ ] **Step 4: Verify the tests pass**

```
pytest tests/api/server/routes/test_accounts.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add api/server/routes/accounts.py api/server/main.py tests/api/server/routes/test_accounts.py tests/api/server/fixtures/entity_graph_seed.py
git commit -m "feat(accounts): /api/accounts/summary endpoint"
```

### Task 2.6: `/accounts` page in the blueprint UI

**Files:**
- Create: `web/blueprint/src/pages/AccountsPage.tsx`
- Modify: `web/blueprint/src/App.tsx` (or wherever routes are registered) — add the route
- Test: `web/blueprint/src/pages/__tests__/AccountsPage.test.tsx`

- [ ] **Step 1: Write the failing component test**

```typescript
// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AccountsPage } from "../AccountsPage";

const SUMMARY = {
  accounts: [
    { id: "ACC-6010", code: "6010", name: "Production cost — external",
      type: "expense", total_gbp: 154300, row_count: 47, cost_centres: ["CC-zava-creative"] },
    { id: "ACC-4100", code: "4100", name: "Revenue — media commission",
      type: "revenue", total_gbp: 88200, row_count: 23, cost_centres: [] },
  ],
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(SUMMARY), {
    status: 200, headers: { "Content-Type": "application/json" },
  })));
});
afterEach(() => { vi.unstubAllGlobals(); });

describe("AccountsPage", () => {
  it("lists accounts with totals", async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Production cost/)).toBeTruthy();
      expect(screen.getByText(/154,300/)).toBeTruthy();
    });
  });

  it("groups expense vs revenue", async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Expenses/i)).toBeTruthy();
      expect(screen.getByText(/Revenue/i)).toBeTruthy();
    });
  });
});
```

- [ ] **Step 2: Verify it fails**

```
cd web/blueprint && npx vitest run src/pages/__tests__/AccountsPage.test.tsx
```

Expected: FAIL — component doesn't exist.

- [ ] **Step 3: Implement `AccountsPage.tsx`**

```typescript
import { useEffect, useState } from "react";

interface AccountRow {
  id: string;
  code: string;
  name: string;
  type: string;
  total_gbp: number;
  row_count: number;
  cost_centres: string[];
}

interface SummaryResponse {
  accounts: AccountRow[];
}

const fmtGBP = (n: number) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 }).format(n);

export function AccountsPage() {
  const [data, setData] = useState<SummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/accounts/summary")
      .then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
      .then(d => { if (!cancelled) setData(d); })
      .catch(e => { if (!cancelled) setError(String(e)); });
    return () => { cancelled = true; };
  }, []);

  if (error) return <div className="accounts-page__error">accounts unavailable: {error}</div>;
  if (!data) return <div className="accounts-page__loading">loading…</div>;

  const grouped: Record<string, AccountRow[]> = {};
  for (const a of data.accounts) {
    (grouped[a.type] ??= []).push(a);
  }

  return (
    <div className="accounts-page">
      <header className="accounts-page__header">
        <div className="accounts-page__eyebrow">live ledger</div>
        <h1>Accounts</h1>
      </header>
      {(["revenue", "expense", "intercompany", "other"] as const).map(t => (
        grouped[t]?.length ? (
          <section key={t} className="accounts-page__group">
            <h2 className="accounts-page__group-title">
              {t === "revenue" ? "Revenue" : t === "expense" ? "Expenses" : t}
            </h2>
            <table className="accounts-page__table">
              <thead>
                <tr><th>Code</th><th>Account</th><th className="num">Rows</th><th className="num">Total</th></tr>
              </thead>
              <tbody>
                {grouped[t].map(a => (
                  <tr key={a.id}>
                    <td className="mono">{a.code}</td>
                    <td>{a.name}</td>
                    <td className="num">{a.row_count}</td>
                    <td className="num">{fmtGBP(a.total_gbp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : null
      ))}
    </div>
  );
}
```

Add styles to `styles.css` matching the existing `entities-page__*` BEM. Wire the route in `App.tsx`:

```typescript
import { AccountsPage } from "./pages/AccountsPage";
// in route table:
{ path: "/accounts", element: <AccountsPage /> }
```

- [ ] **Step 4: Verify it passes**

```
cd web/blueprint && npx vitest run src/pages/__tests__/AccountsPage.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add web/blueprint/src/pages/AccountsPage.tsx web/blueprint/src/pages/__tests__/AccountsPage.test.tsx web/blueprint/src/App.tsx web/blueprint/src/styles.css
git commit -m "feat(accounts): /accounts page with revenue + expense groupings"
```

### Task 2.7: Reseed and update Phase 0 baseline

- [ ] **Step 1:** Stop the API, then reseed:

```
rm -rf data/portal/entity_graph.kuzu data/portal/entity_graph.kuzu.bak
uv run python -c "from api.server.data_fabric.pack import build_zava_pack; r = build_zava_pack().materialise('data/portal/entity_graph.kuzu'); print(r)"
```

- [ ] **Step 2:** Re-run the audit dump scripts; confirm `money_neighbours` now includes `PAYS`/`OWED_BY`/`BOOKED_AGAINST`/`COSTED_TO`.
- [ ] **Step 3:** Update `tests/api/server/services/test_entity_graph_baseline.py` to remove `test_money_has_no_org_edges_today` (it's now wrong) and replace with a positive `test_money_has_pays_edges`.
- [ ] **Step 4:** Commit.

```
git add tests/api/server/services/test_entity_graph_baseline.py
git commit -m "test: update baseline — Phase 2 has accounts substrate"
```

---

## Phase 3 — Agency entities live

**Goal:** Brand / Campaign / Pitch / MediaPlan stop being dead schema. The agency half of the company is queryable and visible in the UI.

### Task 3.1: Migrate `_write_brands` to first-class Brand nodes

**Files:**
- Modify: `api/server/data_fabric/pack.py` (`_write_brands` and add `_write_brand_org_edges`)
- Test: extend `tests/api/server/data_fabric/test_pack.py`

- [ ] **Step 1: Write the failing test**

```python
def test_brands_seeded_as_first_class(materialised):
    import kuzu
    db_path, _ = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    n = int(conn.execute("MATCH (b:Brand) RETURN count(*) AS c").get_next()[0])
    assert n >= 8, f"expected at least 8 Brand nodes, got {n}"


def test_brand_of_edge_to_client_org(materialised):
    import kuzu
    db_path, _ = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    n = int(conn.execute(
        "MATCH (b:Brand)-[:BRAND_OF]->(o:Organisation {kind: 'client'}) "
        "RETURN count(*) AS c"
    ).get_next()[0])
    assert n >= 8
```

- [ ] **Step 2: Verify both fail.**

- [ ] **Step 3: Rewrite `_write_brands`**

```python
def _write_brands(self, graph: EntityGraph, brands: list) -> int:
    for b in brands:
        graph.upsert(EntityWrite(
            kind="Brand", id=b.id,
            attrs={
                "name": b.name,
                "market_segment": b.market_segment,
                "annual_budget_gbp": float(b.annual_budget_gbp),
                "budget_remaining_gbp": float(b.annual_budget_gbp),
            },
        ))
        graph.conn.execute(
            "MATCH (b:Brand), (o:Organisation) "
            "WHERE b.id = $b AND o.id = $o "
            "MERGE (b)-[:BRAND_OF]->(o)",
            {"b": b.id, "o": b.client_id},
        )
    return len(brands)
```

Remove the old `# TODO(e1)` comment.

- [ ] **Step 4: Verify it passes.**
- [ ] **Step 5: Commit.**

```
git commit -m "feat(agency): brands materialise as first-class Brand + BRAND_OF edges"
```

### Task 3.2: Migrate `creative_campaign` projection to first-class Campaign

**Files:**
- Modify: `api/server/services/entity_projections/creative_campaign.py`
- Test: `tests/api/server/services/entity_projections/test_creative_campaign_projection.py` (extend existing)

- [ ] **Step 1: Write/extend the failing test**

```python
def test_creative_campaign_emits_first_class_campaign(make_workflow):
    wf = make_workflow(
        "CMP-0001", "creative-campaign",
        {"client_brand": "Aurora", "agency": "Zava-Creative", "category": "fmcg",
         "channels": ["tv", "social"], "jurisdictions": ["UK", "US"]},
        nest_under="brief",
    )
    ops = creative_campaign.project(wf)
    kinds = [op.kind for op in ops if isinstance(op, EntityWrite)]
    assert "Campaign" in kinds
    assert "MediaPlan" in kinds
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Modify the projection** so it emits `EntityWrite(kind="Campaign", ...)` and `EntityWrite(kind="MediaPlan", ...)` plus `RelWrite(src=campaign_id, rel="CAMPAIGN_FOR", dst=brand_id)` and `RelWrite(src=campaign_id, rel="EXECUTED_BY", dst="ORG-zava-creative")`. Keep the existing Asset write only if you also want a deck artefact — or drop it.

- [ ] **Step 4: Verify it passes; run all projection tests.**

```
pytest tests/api/server/services/entity_projections/ -v
```

- [ ] **Step 5: Commit.**

### Task 3.3: Run DataPack one-shot workflows through the projection bus

**Files:**
- Modify: `api/server/data_fabric/pack.py` (`_write_workflows` — currently writes Workflow nodes directly; should emit a synthetic `workflow.completed` FleetEvent for each so the EntityReflector dispatches the projection)
- Test: extend `tests/api/server/data_fabric/test_pack.py`

- [ ] **Step 1: Write the failing test**

```python
def test_pitch_emitting_workflows_actually_create_pitches(materialised):
    """client-renewal etc. emit Pitch nodes via their projection. After
    DataPack runs them through the bus, the Pitch table must be non-empty."""
    import kuzu
    db_path, _ = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    n = int(conn.execute("MATCH (p:Pitch) RETURN count(*) AS c").get_next()[0])
    assert n >= 5, f"expected ≥5 Pitch nodes from one-shot agency workflows, got {n}"


def test_creative_campaign_workflows_create_campaigns(materialised):
    import kuzu
    db_path, _ = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    n = int(conn.execute("MATCH (c:Campaign) RETURN count(*) AS c").get_next()[0])
    assert n >= 14
```

- [ ] **Step 2: Verify both fail.**

- [ ] **Step 3: Run projections directly inside `_write_workflows`**

`workflow_timeline.TimelineEntry.workflow` is already a fully-formed `Workflow` object (see `workflow_timeline.py:25-27`); no helper needed. Bus-path dispatch is NOT viable here because `EntityReflector._on_event` short-circuits on `store.get_workflow(workflow_id) is None` (`entity_reflector.py:128`) and `_write_workflows` doesn't populate the StateStore.

Inside `_write_workflows`, after the existing `graph.upsert(EntityWrite(kind="Workflow", ...))` for each timeline entry, add a direct projection call:

```python
            projection = PROJECTIONS.get(wf.type)
            if projection is not None:
                for op in projection(entry.workflow):
                    if isinstance(op, EntityWrite):
                        graph.upsert(op)
                    elif isinstance(op, RelWrite):
                        try:
                            graph.link(op.src_id, op.rel, op.dst_id, **op.attrs)
                        except Exception as exc:
                            log.warning(
                                "pack: rel %s %s->%s failed: %s",
                                op.rel, op.src_id, op.dst_id, exc,
                            )
                    elif isinstance(op, DecisionWrite):
                        decided_at = op.decided_at
                        if isinstance(decided_at, str):
                            from datetime import datetime as _dt
                            decided_at = _dt.fromisoformat(decided_at) if decided_at else _dt.utcnow()
                        graph.record_decision(
                            workflow_id=op.workflow_id,
                            phase=op.phase,
                            persona_role=op.persona_role,
                            verdict=op.verdict,
                            reason=op.reason,
                            decided_at=decided_at,
                            source_event=op.source_event,
                            attributes=op.attributes,
                            decided_on=op.decided_on,
                        )
```

Add these imports near the top of `pack.py` if not already present:

```python
from api.server.services.entity_projections import PROJECTIONS
from api.server.services.entity_graph import DecisionWrite, RelWrite
```

**Performance note:** `ap-invoice` projections fire once per timeline entry; for a ~3000-row historical timeline this multiplies the writes. If reseed time becomes a problem, add `if wf.type in {"ap-invoice", "it-access-request", "purchase-order"}: continue` to gate the high-volume types out of the per-row loop — their seed-time decisions are still written by `_write_decisions` further down.

**Payload coverage:** the test floor (`Pitch >= 5`, `Campaign >= 14`) assumes the per-domain fixtures at `data/synthetic/<workflow-type>/*.json` carry the keys each projection reads. Before relying on the floor, run:

```
uv run python -c "
from api.server.services.entity_projections import PROJECTIONS
from api.server.data_fabric.workflow_timeline import generate_timeline
for e in generate_timeline(seed=42, in_flight_count=5, historical_count=20):
    p = PROJECTIONS.get(e.workflow.type)
    if p is None:
        continue
    ops = p(e.workflow)
    print(e.workflow.type, len(ops), [type(o).__name__ for o in ops])
"
```

If any agency projection returns 0 ops, fix its fixture or its payload-key reads before continuing.

- [ ] **Step 4: Verify both tests pass.**
- [ ] **Step 5: Commit.**

### Task 3.4: Surface the missing kinds in `/entities` page

**Files:**
- Modify: `web/blueprint/src/pages/EntitiesPage.tsx` (extend `KINDS`)
- Modify: `api/server/routes/entities.py` (extend `_KINDS` if not already, and `_PROJECT_FIELDS_BY_KIND`)
- Test: `web/blueprint/src/pages/__tests__/EntitiesPage.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
import { render, screen } from "@testing-library/react";
import { EntitiesPage } from "../EntitiesPage";

it("lists all 13 kinds in the dropdown", () => {
  // mock fetch to return a stats with all kinds
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
    counts: { Person: 100, Brand: 8, Campaign: 14, Pitch: 5, MediaPlan: 3, Subsidiary: 5, Workflow: 200 },
    hot: [], recentLinks: [],
  }), { status: 200 })));
  render(<EntitiesPage />);
  for (const k of ["Brand", "Campaign", "Pitch", "MediaPlan", "Subsidiary", "Workflow"]) {
    expect(screen.getByRole("option", { name: k })).toBeTruthy();
  }
});
```

- [ ] **Step 2: Verify it fails.**

- [ ] **Step 3: Extend `KINDS` in `EntitiesPage.tsx`**

```typescript
const KINDS = [
  "Person","Organisation","Asset","Money","Decision","Place","Period",
  "Workflow","Brand","Campaign","Pitch","MediaPlan","Subsidiary",
  "Account","CostCentre",
] as const;
```

(The 15-kind list is intentional — keep `Account` and `CostCentre` from Phase 2 visible too.)

- [ ] **Step 4: Verify it passes.**
- [ ] **Step 5: Commit.**

### Task 3.5: Add `Money→Brand` cost rel for campaign attribution

**Files:**
- Modify: `api/server/services/entity_graph.py` (add `COSTED_TO_BRAND` rel table)
- Modify: `scripts/backfill_money_org_edges.py` (also write `COSTED_TO_BRAND` from `attributes.brand_id`)
- Test: extend `tests/scripts/test_backfill_money_org_edges.py`

- [ ] **Step 1-5:** Standard test-write / red / fix / green / commit cycle. Schema:

```python
("COSTED_TO_BRAND", "CREATE REL TABLE IF NOT EXISTS COSTED_TO_BRAND (FROM Money TO Brand, posted_at TIMESTAMP)"),
```

Backfill block:

```python
brand_id = a.get("brand_id")
if brand_id:
    graph.conn.execute(
        "MATCH (m:Money), (b:Brand) WHERE m.id = $m AND b.id = $b "
        "MERGE (m)-[:COSTED_TO_BRAND]->(b)",
        {"m": r["id"], "b": brand_id},
    )
```

### Task 3.6: Brand-spend tile on `/accounts`

**Files:**
- Modify: `api/server/routes/accounts.py` (add `/api/accounts/by-brand`)
- Modify: `web/blueprint/src/pages/AccountsPage.tsx` (add a "Spend by brand" panel)
- Test: extend both test files.

- [ ] Standard cycle. Cypher:

```python
g.query("""
    MATCH (m:Money)-[:COSTED_TO_BRAND]->(b:Brand)
    OPTIONAL MATCH (b)-[:BRAND_OF]->(c:Organisation)
    RETURN b.id AS brand_id, b.name AS brand_name,
           c.name AS client_name, sum(m.amount) AS total_gbp,
           count(DISTINCT m) AS row_count
    ORDER BY total_gbp DESC
""")
```

### Task 3.7: Reseed and update Phase 0 baseline

- [ ] Stop the API, then reseed:

```
rm -rf data/portal/entity_graph.kuzu data/portal/entity_graph.kuzu.bak
uv run python -c "from api.server.data_fabric.pack import build_zava_pack; r = build_zava_pack().materialise('data/portal/entity_graph.kuzu'); print(r)"
```

- [ ] Confirm `Brand`/`Campaign`/`Pitch`/`MediaPlan` counts > 0 and `BRAND_OF`/`CAMPAIGN_FOR`/`COSTED_TO_BRAND` > 0.
- [ ] Remove the `EMPTY_KINDS_TODAY` and matching agency-rel asserts from the baseline test.
- [ ] Commit.

---

## Phase 4 — Decisions tell a story

**Goal:** Decisions stop being binary rubber-stamps. Verdict vocabulary widened, attributes promoted to columns, precedent chains visible, time wired into edges.

### Task 4.1: Use the wider verdict vocabulary in projections

**Files:**
- Modify: `api/server/services/entity_projections/ap_invoice.py` — escalate decisions where amount > clerk delegation cap. Add a small policy table.
- Modify: `api/server/services/entity_projections/it_access_request.py` — `defer` when manager OOO.
- Test: per-projection test extensions.

- [ ] Standard cycle per projection. Concrete rule for AP:

```python
DELEGATION_CAP_GBP = 5000.0
verdict = "approve" if amount <= DELEGATION_CAP_GBP else "escalate"
```

This is illustrative — wire the delegation matrix from `api/shared/personas.py` if it has one.

### Task 4.2: Add `decided_at` column to every rel table; backfill from Decision/Money first_seen_at

**Files:**
- Modify: `api/server/services/entity_graph.py` (`_REL_TABLES` — add `decided_at TIMESTAMP` to each rel except where already present)
- Create: `scripts/backfill_rel_timestamps.py`
- Test: per-rel migration tests

- [ ] **Step 1: Commit upfront to drop+recreate, NOT ALTER.**

Kuzu 0.6.1 has no precedent in this codebase for `ALTER TABLE ADD` on rel tables (the existing `_TIMESTAMP_KINDS` ALTER loop in `entity_graph.py` only touches NODE tables; `_KUZU_ALREADY_EXISTS_MARKERS` covers only `"already exists in catalog"` and `"already has property"`). Rather than gamble on whether the version supports rel-table ALTER, this task adopts a **drop + recreate + full reseed** strategy:

1. Bump the schema literals in `_REL_TABLES` to add `decided_at TIMESTAMP` to every rel.
2. Add a top-of-bootstrap `_REL_SCHEMA_VERSION` constant (e.g. `"v2-decided-at"`).
3. On `EntityGraph.__init__`, write the version to a `Meta` node (or a sentinel `META` row in any existing table). If the read version differs from the constant, drop every rel table (`DROP TABLE <rel>`) and re-CREATE from `_REL_TABLES`.
4. Document in the `EntityGraph` docstring that rel-schema bumps require a full reseed.

This means the FIRST run after Task 4.2 lands MUST be preceded by `rm -rf data/portal/entity_graph.kuzu*` and a fresh `materialise()`. There is no in-place migration. Phase 4 Task 4.6 reseed is mandatory, not optional.

- [ ] **Step 2:** Standard test-write / migration / backfill cycle. Backfill rule: pull `Decision.decided_at` for `DECIDED_*` rels; pull `Money.first_seen_at` for `PAYS`/`OWED_BY`/`BOOKED_AGAINST`/`COSTED_TO`/`COSTED_TO_BRAND`/`BELONGS_TO`/`TRANSACTS`.

- [ ] **Step 3:** Update `/api/entities/_stats` `recentLinks` query to `ORDER BY decided_at DESC LIMIT 20` so "recent" actually means recent.

### Task 4.3: Promote Decision JSON attributes to first-class columns

**Files:**
- Modify: `api/server/services/entity_graph.py` (`Decision` node table — add `amount_gbp DOUBLE`, `currency_pair STRING`, `notional_gbp DOUBLE`, `vendor_id STRING`, `client_brand STRING`)
- Modify: `entity_projections/__init__.py` (`build_decision` — splat known keys from `attributes` dict onto the new columns)
- Test: extend `tests/api/server/services/entity_projections/`

- [ ] Standard cycle. After this, Cypher queries can do `WHERE d.amount_gbp > 10000` instead of JSON-parsing `d.attributes` in Python.

### Task 4.4: Surface PRECEDENT_OF in the EntityView drawer

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx` (`EntityView` — when `entity.kind === "Decision"`, fetch and render the precedent chain)
- Modify: `api/server/routes/entities.py` — add `/api/entities/{id}/precedents` endpoint
- Test: extend `tests/api/server/routes/test_entities.py` and the `EntityView.test.tsx`

- [ ] Standard cycle. Cypher:

```cypher
MATCH (d:Decision {id: $id})-[:PRECEDENT_OF*1..3]->(p:Decision)
RETURN p.id, p.workflow_id, p.phase, p.verdict, p.reason, p.decided_at
ORDER BY p.decided_at DESC LIMIT 10
```

### Task 4.5: Bind Workflow and Decision to Period

**Files:**
- Modify: `api/server/services/entity_graph.py` — add rel tables `WORKFLOW_IN_PERIOD` (Workflow→Period) and `DECISION_IN_PERIOD` (Decision→Period) — only if `DECIDED_PERIOD` semantics differ from this; otherwise reuse.
- Modify: every projection that already knows the period (treasury_fx, perf_review, ap_invoice via the BELONGS_TO chain) to also write the Workflow→Period edge.
- Create: `scripts/backfill_workflow_periods.py` — derive period from `Workflow.started_at` lookup against the `Period` `starts`/`ends` ranges.

- [ ] Standard cycle.

### Task 4.6: Reseed, update baseline, archive plan

- [ ] **Step 1:** Stop the API, then **fully reseed** (Phase 4 Task 4.2 may have dropped + recreated rel tables):

```
rm -rf data/portal/entity_graph.kuzu data/portal/entity_graph.kuzu.bak
uv run python -c "from api.server.data_fabric.pack import build_zava_pack; r = build_zava_pack().materialise('data/portal/entity_graph.kuzu'); print(r)"
```

- [ ] **Step 2:** Re-run audit dump — verify decision verdict histogram now contains `escalate` and `defer`; precedent edges have timestamps; `Decision.amount_gbp` column populated for ≥3000 rows; Workflow→Period edges populated.
- [ ] **Step 3:** Update `tests/api/server/services/test_entity_graph_baseline.py` to assert the post-Phase-4 shape.
- [ ] **Step 4:** Move this plan to `docs/plans/archive/` and mark `Status: Shipped`.

```
git mv docs/plans/2026-05-12-entity-graph-coherence.md docs/plans/archive/
git commit -m "docs: archive entity-graph-coherence plan (shipped)"
```

---

## Files

**Created:**
- `api/server/services/decision_vocab.py`
- `api/server/routes/accounts.py`
- `scripts/backfill_money_org_edges.py`
- `scripts/backfill_rel_timestamps.py`
- `scripts/backfill_workflow_periods.py`
- `web/blueprint/src/pages/AccountsPage.tsx`
- `tests/api/server/services/test_entity_graph_baseline.py`
- `tests/api/server/services/test_decision_vocab.py`
- `tests/api/server/services/test_entity_graph_person_merge.py`
- `tests/api/server/services/test_entity_graph_accounts_schema.py`
- `tests/api/server/services/test_entity_graph_accounts_rels.py`
- `tests/api/server/data_fabric/test_pack.py`
- `tests/api/server/routes/test_accounts.py`
- `tests/api/server/fixtures/entity_graph_seed.py`
- `tests/scripts/test_backfill_money_org_edges.py`
- `web/blueprint/src/pages/__tests__/AccountsPage.test.tsx`
- `web/blueprint/src/pages/__tests__/EntitiesPage.test.tsx`

**Modified:**
- `api/server/services/entity_graph.py` — Account/CostCentre kinds, PAYS/OWED_BY/BOOKED_AGAINST/COSTED_TO/COSTED_TO_BRAND rel tables, decided_at on rels, first-class Decision columns, upsert merge guard
- `api/server/services/entity_projections/__init__.py` — `build_decision` canonicalisation + attribute splat
- `api/server/services/entity_projections/creative_campaign.py` — Brand/Campaign/MediaPlan emission
- `api/server/services/entity_projections/ap_invoice.py` — escalate verdict
- `api/server/services/entity_projections/it_access_request.py` — defer verdict
- `api/server/data_fabric/pack.py` — `_write_accounts`, `_write_cost_centres`, fix `_write_decisions`, run projections through bus, first-class Brand
- `api/server/routes/entities.py` — extend `_KINDS` and `_PROJECT_FIELDS_BY_KIND`; rewrite `_stats` recentLinks ORDER BY
- `api/server/main.py` — mount accounts router
- `web/blueprint/src/pages/EntitiesPage.tsx` — extend KINDS list
- `web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx` — EntityView precedent panel
- `web/blueprint/src/App.tsx` — route registration

**Deleted:**
- `api/data/portal/entity_graph.kuzu/` — stale duplicate

---

## Testing strategy

- **Unit:** every helper module gets a focused test (`decision_vocab`, `backfill_*`).
- **Schema:** every new node/rel table has a write-then-read test that exercises the actual Kuzu DDL.
- **Integration:** `test_pack.py` materialises a fresh DB end-to-end and asserts the post-seed shape.
- **HTTP:** `test_accounts.py` uses `TestClient` against a seeded fixture graph.
- **UI:** Vitest+JSDOM for `AccountsPage` and the extended `EntitiesPage`.
- **Regression:** the Phase 0 baseline test pins current shape; each phase's final task updates the baseline so the file always reflects what the system actually is.

---

## Risks & assumptions

- **RISK-1:** Kuzu 0.6.1 has no precedent for `ALTER TABLE ADD` on rel tables in this codebase. Phase 4 Task 4.2 commits upfront to drop + recreate + full reseed for that reason — documented in the task's Step 1.
- **RISK-2:** Running every DataPack workflow through the projection bus (Phase 3 Task 3.3) may slow seed time noticeably. Mitigation: keep direct `graph.upsert` for the common AP-invoice projection; only bus-dispatch the agency-narrative one-shot types. (Bus-path itself is ruled out per Task 3.3 Step 3 — we use direct projection calls.)
- **RISK-3:** `_KIND_TO_ACCOUNT` mapping (Phase 2 Task 2.4) is judgement-call. Mitigation: keep it in one constant in `pack.py`; document the rule near it.
- **RISK-4:** Sequencing inside `pack.materialise()`: the Phase 2 backfill (`backfill_money_org_edges`) runs once at the end and assumes Brand nodes exist for the Phase 3 extension. Until Phase 3 lands, `COSTED_TO_BRAND` will be empty. Phase 2 Task 2.3 Step 5 documents this; Phase 3 Task 3.5 fixes it.
- **ASSUMPTION-1:** No external system reads `Decision.verdict == "approved"` directly. Searched for it; only the graph itself has that variant. If a downstream consumer surfaces, add a compatibility shim in the read route.
- **ASSUMPTION-2:** The 22 one-shot workflow types (`media-pitch-to-win` etc.) have payload shapes that match what their projections expect when DataPack constructs the `Workflow` object. Phase 3 Task 3.3 Step 3 includes a one-shot smoke script to verify before relying on the test floor.

---

## Related

- `tmp/entity-audit/FINDINGS.md` (gitignored) — the audit that drove this plan.
- `tmp/entity-audit/{nodes,rels}/*.jsonl` — raw per-node and per-edge dumps from 2026-05-12.
- `plan/feature-enterprise-pitch-readiness-1.md` — the parent "living simulator" plan; this one delivers parts of Tracks B/E/H from it.
- `api/server/services/entity_graph.py` — the substrate this plan reshapes.
- `api/server/data_fabric/pack.py` — the seeder this plan repairs.
