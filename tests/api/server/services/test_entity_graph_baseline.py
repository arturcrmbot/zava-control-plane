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

# Empty kinds today — Phase 3.7 reseed populated all four ex-empty agency
# kinds (Brand=9, Campaign=2, Pitch=5, MediaPlan=1). Kept as an empty guard
# so a future regression that empties any kind reappears here trivially.
EMPTY_KINDS_TODAY: frozenset[str] = frozenset()

# Empty rels today — Phase 3.7 reseed populated BRAND_OF, EXECUTED_BY, and
# COSTED_TO_BRAND. The rels below are still empty because:
#   * CAMPAIGN_FOR / SUPPLIED_BY / PITCH_FOR / RESULTED_IN — no projection
#     writes them today.
#   * DECIDED_<kind> shards — empty until Phase 4 promotes the agency
#     decision projections.
#   * DECIDED_ON — legacy, intentionally empty.
EMPTY_RELS_TODAY = {
    "CAMPAIGN_FOR", "SUPPLIED_BY", "PITCH_FOR", "RESULTED_IN",
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
    """Phase 3.7 reseed populated Brand/Campaign/Pitch/MediaPlan; the set is
    now empty. Kept as a guard so a future regression that empties any kind
    reappears here trivially."""
    for k in EMPTY_KINDS_TODAY:
        assert _count_nodes(conn, k) == 0, f"{k} should still be empty pre-Phase 3"


def test_empty_rels_baseline(conn):
    for r in EMPTY_RELS_TODAY:
        assert _count_rels(conn, r) == 0, f"{r} should still be empty pre-fill"


def test_decision_verdict_vocab_today(conn):
    """Phase 4.6 known gap: the seed's bulk _write_decisions path
    (pack.py:696) hardcodes 'approve' for every workflow, AND the
    projection-bus dispatch at pack.py:609 skips ap-invoice/
    it-access-request/purchase-order for performance. So Phase 4.1's
    escalate (ap-invoice over delegation cap) and defer (it-access OOO)
    work in their unit tests (`test_ap_invoice_projection.py`,
    `test_it_access_request_projection.py`) but never appear in the
    seeded graph.

    The fix is a follow-up: either drop the perf-skip at line 609 and
    have `_write_decisions` skip workflow types whose projection already
    wrote decisions, OR teach `_write_decisions` to consult each
    projection's verdict-policy (DELEGATION_CAP_GBP, _line_manager_oo)
    for those three types.

    Until that lands, this test asserts only what the seed actually
    produces.
    """
    res = conn.execute(
        "MATCH (d:Decision) WHERE d.verdict IS NOT NULL "
        "RETURN d.verdict AS v"
    )
    seen: set[str] = set()
    while res.has_next():
        seen.add(res.get_next()[0])
    assert seen == {"approve"}, (
        f"Until the seed's _write_decisions consults projection policy, the "
        f"verdict column carries only 'approve'; got {seen}. If escalate/"
        f"defer have appeared, the follow-up landed — broaden this assertion."
    )


def test_owns_rels_have_decided_at(conn):
    """Phase 4.2: link()'s default-stamp populates decided_at on every
    new edge written through link(). Spot-checked OWNS (Person→Asset)
    because every Asset is OWNS-linked at seed time.
    """
    res = conn.execute(
        "MATCH ()-[r:OWNS]->() WHERE r.decided_at IS NOT NULL RETURN count(*) AS c"
    )
    n = int(res.get_next()[0])
    assert n > 0, f"OWNS edges should have decided_at after Phase 4.2 reseed; got {n}"


def test_decision_table_has_typed_amount_column(conn):
    """Phase 4.3: the Decision DDL declares amount_gbp DOUBLE etc. as
    first-class columns. The column EXISTS even though the seed's bulk
    _write_decisions doesn't currently splat amount_gbp (see the
    test_decision_verdict_vocab_today known-gap docstring). The
    test_record_decision_promotes_known_keys_to_columns unit test in
    test_entity_graph_decided_at.py proves the splat works when called
    directly with attributes={'amount_gbp': ...}.
    """
    rows = conn.execute("MATCH (d:Decision) RETURN d.amount_gbp AS amt LIMIT 1")
    assert rows.has_next(), "Decision table should be populated"
    _ = rows.get_next()[0]


def test_workflows_have_period_edges(conn):
    """Phase 4.5: WORKFLOW_IN_PERIOD rel + backfill (commit 6c51e1fe)."""
    res = conn.execute("MATCH ()-[r:WORKFLOW_IN_PERIOD]->() RETURN count(*) AS c")
    n = int(res.get_next()[0])
    assert n > 0, f"every Workflow with started_at should link to its Period; got {n}"


def test_persona_role_no_longer_carries_person_ids(conn):
    """DataPack writes role strings (not person ids) into persona_role.

    Phase 0.1 originally pinned this as `> 0` because the unfixed seeder
    used person ids (PERSON-EMP-XXXX) where role strings belonged. Phase 1
    Task 1.3 (commit e708eba3) split the two: persona_role now carries the
    role string ('ap_clerk' etc.) and the decider's person id moves to
    attributes.decider_id. Phase 1 Task 1.5 (this commit) reseeded the
    live graph through the fixed DataPack.
    """
    res = conn.execute(
        "MATCH (d:Decision) WHERE d.persona_role STARTS WITH 'PERSON-' "
        "RETURN count(*) AS c"
    )
    assert int(res.get_next()[0]) == 0, (
        "DataPack must write role strings, not person ids, into persona_role. "
        "If a non-zero count returns, a regression has been introduced — see "
        "Phase 1 Task 1.3 (commit e708eba3) for the canonical fix."
    )


def test_money_has_org_edges(conn):
    """Phase 2 (Task 2.3) backfilled PAYS / OWED_BY edges from each Money row's
    attributes JSON. Phase 2.4 then booked every Money row to a GL Account
    via BOOKED_AGAINST. Phase 0.1 originally pinned this as zero org-edges
    today — Phase 2.7 (this commit) flipped it to a positive lower bound.
    """
    res = conn.execute(
        "MATCH (m:Money)-[:PAYS|:OWED_BY]->(:Organisation) "
        "RETURN count(DISTINCT m) AS c"
    )
    n = int(res.get_next()[0])
    assert n >= 100, (
        f"Post-Phase-2 every Money row with a vendor_id/client_id attribute "
        f"should have a PAYS or OWED_BY edge; got {n} (expected >= 100). "
        "If much lower, Task 2.3's backfill (commit 7415ae1c) regressed — "
        "verify pack.materialise() still calls "
        "scripts.backfill_money_org_edges.backfill, and that the "
        "`m.attributes IS NOT NULL` filter in backfill() still matches "
        "the seed-side Money attributes shape."
    )
