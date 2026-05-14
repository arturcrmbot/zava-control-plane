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
    workflow_id: str = "WF-pol",
) -> None:
    g.upsert(EntityWrite(
        kind="Brand", id="BRAND-acme", attrs={"name": "Acme"}, source_workflows=()))
    # NOTE: EntityGraph.record_decision auto-mints the Decision ULID via
    # the (workflow_id, phase, persona_role) dedupe key — there is no
    # `decision_id` kwarg. To get distinct Decisions for distinct verdicts
    # in the same test we vary `workflow_id` instead.
    g.record_decision(
        workflow_id=workflow_id,
        phase="policy_set",
        persona_role="cfo",
        verdict=verdict,
        reason="test policy",
        decided_at=decided_at,
        source_event="persona.action.approved",
        attributes={} if expiry_days is None else {"expiry_days": expiry_days},
        decided_on=("BRAND-acme",),
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
        verdict="cap", workflow_id="WF-pol-cap",
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
