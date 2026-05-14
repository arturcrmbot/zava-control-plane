"""Phase A1 of autonomous-domain-insights v1.1: CFO summary_policy."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from api.server.services import persona_responder as pr
from api.server.services.entity_graph import EntityGraph, EntityWrite


def _seed_brand(
    g: EntityGraph,
    *,
    brand_id: str,
    name: str,
    budget: float,
) -> None:
    g.upsert(EntityWrite(
        kind="Brand",
        id=brand_id,
        attrs={
            "name": name,
            "annual_budget_gbp": float(budget),
            "budget_remaining_gbp": float(budget),
        },
        source_workflows=(),
    ))


def _seed_money_against_brand(
    g: EntityGraph,
    *,
    money_id: str,
    amount: float,
    brand_id: str,
) -> None:
    g.upsert(EntityWrite(
        kind="Money",
        id=money_id,
        attrs={
            "amount": float(amount),
            "currency": "GBP",
            "kind": "spend",
            "period": "FY26",
        },
        source_workflows=(),
    ))
    g.link(money_id, "COSTED_TO_BRAND", brand_id, posted_at=datetime.utcnow())


def _load_cfo(monkeypatch, g: EntityGraph):
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS.get("cfo")
    assert persona is not None
    assert persona.summarise is not None, "cfo SKILL.md must declare summary_policy"
    return persona


def test_cfo_calm_when_no_brands_over_budget(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_brand(g, brand_id="BRAND-aurora", name="Aurora", budget=100_000.0)
    _seed_brand(g, brand_id="BRAND-solace", name="Solace", budget=50_000.0)
    _seed_money_against_brand(
        g, money_id="MONEY-1", amount=5_000.0, brand_id="BRAND-aurora",
    )
    _seed_money_against_brand(
        g, money_id="MONEY-2", amount=2_000.0, brand_id="BRAND-solace",
    )

    persona = _load_cfo(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["headline"].startswith("All brands within budget"), out
    assert out["proposed_actions"] == []
    assert out["kpis"]["brands_tracked"] == 2
    assert out["kpis"]["brands_over_85pct"] == 0


def test_cfo_proposes_freeze_when_brand_over_85pct(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_brand(g, brand_id="BRAND-aurora", name="Aurora", budget=100_000.0)
    _seed_money_against_brand(
        g, money_id="MONEY-1", amount=90_000.0, brand_id="BRAND-aurora",
    )

    persona = _load_cfo(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert len(out["proposed_actions"]) == 1, out
    action = out["proposed_actions"][0]
    assert action["verdict"] == "freeze"
    assert action["kind"] == "policy_set"
    assert "BRAND-aurora" in action["decided_on"]
    assert action["attributes"]["expiry_days"] == 14
    assert action["id"] == "freeze-brand-aurora"
    assert "Aurora" in action["label"]
    assert out["kpis"]["brands_over_85pct"] == 1
    assert out["kpis"]["active_freezes"] == 0


def test_cfo_skips_brands_with_active_freeze(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_brand(g, brand_id="BRAND-aurora", name="Aurora", budget=100_000.0)
    _seed_money_against_brand(
        g, money_id="MONEY-1", amount=90_000.0, brand_id="BRAND-aurora",
    )
    # Plant an active freeze policy via record_decision.
    g.record_decision(
        workflow_id="WF-POL-test-1",
        phase="policy_set",
        persona_role="cfo",
        verdict="freeze",
        reason="manual seed",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={"expiry_days": 14, "scope": "po"},
        decided_on=("BRAND-aurora",),
    )

    persona = _load_cfo(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["proposed_actions"] == [], out
    # The brand is still counted as over budget but already covered.
    assert out["kpis"]["brands_over_85pct"] == 1
    assert out["kpis"]["active_freezes"] == 1


def test_cfo_fingerprint_is_deterministic(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_brand(g, brand_id="BRAND-aurora", name="Aurora", budget=100_000.0)
    _seed_brand(g, brand_id="BRAND-solace", name="Solace", budget=50_000.0)
    _seed_money_against_brand(
        g, money_id="MONEY-1", amount=90_000.0, brand_id="BRAND-aurora",
    )
    _seed_money_against_brand(
        g, money_id="MONEY-2", amount=10_000.0, brand_id="BRAND-solace",
    )

    persona = _load_cfo(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] == out_b["fingerprint"]
    assert out_a["fingerprint"].startswith("cfo:")


def test_cfo_fingerprint_changes_when_brand_pct_changes(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_brand(g, brand_id="BRAND-aurora", name="Aurora", budget=100_000.0)
    _seed_money_against_brand(
        g, money_id="MONEY-1", amount=10_000.0, brand_id="BRAND-aurora",
    )

    persona = _load_cfo(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})

    _seed_money_against_brand(
        g, money_id="MONEY-2", amount=80_000.0, brand_id="BRAND-aurora",
    )
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] != out_b["fingerprint"], (
        out_a["fingerprint"], out_b["fingerprint"],
    )
