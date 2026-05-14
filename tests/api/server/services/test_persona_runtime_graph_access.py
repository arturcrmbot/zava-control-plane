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
