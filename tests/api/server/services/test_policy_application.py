"""Tests for the persona-in-the-loop self-application gate.

Verify that:
1. An action authorised by the matrix gets applied (Decision recorded).
2. An action not authorised gets denied (audit entry, no Decision).
3. Unknown action kinds are rejected.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services import policy_application as pa


@pytest.fixture()
def fresh_app_state(tmp_path: Path, monkeypatch):
    """Provide a fresh in-process app_state with a real EntityGraph.

    Other tests in the suite (notably test_portal.py) pop
    ``api.server.state`` from ``sys.modules`` to rebuild a fresh
    AppState. Modules imported earlier (like policy_application) still
    hold a reference to the OLD app_state object. Patch every reachable
    one so all paths see the same graph + audit.
    """
    from api.server.state import app_state as _state_module_app
    from api.server.services.entity_graph import EntityGraph
    from api.server.services import policy_application as pa_module

    # The policy_application module captured app_state at import time.
    pa_app_state = pa_module.app_state

    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(_state_module_app, "entities", g)
    if pa_app_state is not _state_module_app:
        monkeypatch.setattr(pa_app_state, "entities", g)

    # Ensure both references see the same audit logger too — some
    # earlier tests swap audit on one of the references but not the
    # other.
    if pa_app_state is not _state_module_app:
        monkeypatch.setattr(pa_app_state, "audit", _state_module_app.audit)

    yield pa_app_state
    g.close()


def test_authorised_action_applies_and_records_decision(fresh_app_state):
    """CFO is authorised by POL-CFO-001 (action=policy_set, category=po,
    requester_role=cfo). The action should land as a Decision row."""
    actions = [{
        "id": "freeze-brand-aurora",
        "kind": "policy_set",
        "verdict": "freeze",
        "decided_on": ["BRAND-aurora"],
        "attributes": {"expiry_days": 14, "scope": "po"},
        "reason": "Aurora at 123% of FY budget",
        "label": "Freeze Aurora POs for 14 days",
    }]

    # Seed the brand node so the DECIDED_BRAND rel can land.
    from api.server.services.entity_graph import EntityWrite
    fresh_app_state.entities.upsert(EntityWrite(
        kind="Brand", id="BRAND-aurora",
        attrs={"name": "Aurora"},
        source_workflows=(),
    ))

    outcomes = pa.apply_proposed_actions("cfo", actions)

    assert len(outcomes) == 1
    o = outcomes[0]
    assert o["outcome"] == pa.PolicyApplicationOutcome.APPLIED
    assert o["workflow_id"] is not None
    assert o["governing_rule_id"] == "POL-CFO-001"

    # Confirm the Decision landed.
    rows = fresh_app_state.entities.query(
        "MATCH (d:Decision {phase: 'policy_set', persona_role: 'cfo'}) "
        "RETURN d.id AS id, d.verdict AS verdict",
        {},
    )
    assert len(rows) == 1
    assert rows[0]["verdict"] == "freeze"


def test_unauthorised_action_denies_and_audits(fresh_app_state):
    """An ap_clerk has NO matrix authority for action=policy_set, so the
    kernel must deny. No Decision row, but an audit entry must exist."""
    actions = [{
        "id": "rogue-freeze",
        "kind": "policy_set",
        "verdict": "freeze",
        "decided_on": ["BRAND-aurora"],
        "attributes": {"expiry_days": 14, "scope": "po"},
        "reason": "ap_clerk should not be able to do this",
    }]

    before = len(fresh_app_state.audit.list())
    outcomes = pa.apply_proposed_actions("ap_clerk", actions)

    assert len(outcomes) == 1
    o = outcomes[0]
    assert o["outcome"] == pa.PolicyApplicationOutcome.DENIED
    assert o["workflow_id"] is None

    rows = fresh_app_state.entities.query(
        "MATCH (d:Decision {phase: 'policy_set'}) RETURN d.id AS id",
        {},
    )
    assert rows == []

    audit = fresh_app_state.audit.list()
    assert any(e.get("action") == "policy_set.denied" for e in audit[before:])


def test_unknown_kind_is_rejected(fresh_app_state):
    actions = [{"id": "x", "kind": "wibble", "verdict": "freeze"}]
    outcomes = pa.apply_proposed_actions("cfo", actions)
    assert outcomes[0]["outcome"] == pa.PolicyApplicationOutcome.UNKNOWN_KIND
