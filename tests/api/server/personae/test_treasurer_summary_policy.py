"""Phase B2 of autonomous-domain-insights v1.1: treasurer summary_policy."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from api.server.services import persona_responder as pr
from api.server.services.entity_graph import EntityGraph, EntityWrite


def _seed_fx_money_node(g: EntityGraph, *, pair: str) -> None:
    """Seed a synthetic Money node so DECIDED_MONEY rels survive.

    The treasurer summary_policy uses ``scope_id = "FX:<pair>"`` to look
    up active cap policies via :func:`active_policies_for`, which walks
    the ``DECIDED_MONEY`` rel from a ``policy_set`` Decision to a
    ``Money`` node with that id. ``EntityGraph.link`` silently no-ops on
    missing endpoints, so the cap-bearing test seeds the synthetic
    node first.
    """
    g.upsert(EntityWrite(
        kind="Money",
        id="FX:" + pair,
        attrs={"kind": "fx_pair_marker", "currency": pair},
        source_workflows=(),
    ))


def _record_fx_decision(
    g: EntityGraph,
    *,
    workflow_id: str,
    pair: str,
    notional_gbp: float,
) -> None:
    g.record_decision(
        workflow_id=workflow_id,
        phase="treasury_signoff",
        persona_role="treasurer",
        verdict="approve",
        reason="seed",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={
            "currency_pair": pair,
            "notional_gbp": float(notional_gbp),
        },
        decided_on=(),
    )


def _load_treasurer(monkeypatch, g: EntityGraph):
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS.get("treasurer")
    assert persona is not None
    assert persona.summarise is not None, (
        "treasurer SKILL.md must declare summary_policy"
    )
    return persona


def test_treasurer_calm_when_no_fx_decisions(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")

    persona = _load_treasurer(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["headline"] == "FX exposure within tolerance", out
    assert out["proposed_actions"] == []
    assert out["kpis"]["pairs_tracked"] == 0
    assert out["kpis"]["high_exposure_pairs"] == 0
    assert out["kpis"]["active_caps"] == 0
    assert out["kpis"]["total_notional_gbp"] == 0.0
    assert out["fingerprint"].startswith("treasurer:")


def test_treasurer_proposes_cap_when_pair_over_threshold(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _record_fx_decision(
        g, workflow_id="WF-FX-1", pair="EUR/GBP", notional_gbp=8_000_000.0,
    )

    persona = _load_treasurer(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert len(out["proposed_actions"]) == 1, out
    action = out["proposed_actions"][0]
    assert action["verdict"] == "cap"
    assert action["kind"] == "policy_set"
    assert action["decided_on"] == ["FX:EUR/GBP"]
    assert action["attributes"]["expiry_days"] == 30
    assert action["attributes"]["scope"] == "fx"
    assert action["attributes"]["current_notional_gbp"] == 8_000_000.0
    assert action["id"] == "cap-fx-eur/gbp"
    assert "EUR/GBP" in action["label"]
    assert out["kpis"]["pairs_tracked"] == 1
    assert out["kpis"]["high_exposure_pairs"] == 1
    assert out["kpis"]["active_caps"] == 0
    assert out["kpis"]["total_notional_gbp"] == 8_000_000.0
    assert "1 currency pair(s) above £5m" in out["headline"]


def test_treasurer_skips_pair_with_active_cap(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _record_fx_decision(
        g, workflow_id="WF-FX-1", pair="EUR/GBP", notional_gbp=8_000_000.0,
    )
    _seed_fx_money_node(g, pair="EUR/GBP")
    g.record_decision(
        workflow_id="WF-POL-fx-1",
        phase="policy_set",
        persona_role="treasurer",
        verdict="cap",
        reason="manual seed",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={"expiry_days": 30, "scope": "fx"},
        decided_on=("FX:EUR/GBP",),
    )

    persona = _load_treasurer(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["proposed_actions"] == [], out
    assert out["kpis"]["high_exposure_pairs"] == 1
    assert out["kpis"]["active_caps"] == 1


def test_treasurer_fingerprint_deterministic(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _record_fx_decision(
        g, workflow_id="WF-FX-1", pair="EUR/GBP", notional_gbp=8_000_000.0,
    )
    _record_fx_decision(
        g, workflow_id="WF-FX-2", pair="USD/GBP", notional_gbp=2_000_000.0,
    )

    persona = _load_treasurer(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] == out_b["fingerprint"]
    assert out_a["fingerprint"].startswith("treasurer:")


def test_treasurer_fingerprint_changes_when_notional_changes(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _record_fx_decision(
        g, workflow_id="WF-FX-1", pair="EUR/GBP", notional_gbp=1_000_000.0,
    )

    persona = _load_treasurer(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})

    _record_fx_decision(
        g, workflow_id="WF-FX-2", pair="EUR/GBP", notional_gbp=7_000_000.0,
    )
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] != out_b["fingerprint"], (
        out_a["fingerprint"], out_b["fingerprint"],
    )
