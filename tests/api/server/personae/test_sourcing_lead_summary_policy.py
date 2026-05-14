"""Phase B3 of autonomous-domain-insights v1.1: sourcing_lead summary_policy."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from api.server.services import persona_responder as pr
from api.server.services.entity_graph import EntityGraph, EntityWrite


def _seed_vendor(
    g: EntityGraph,
    *,
    vendor_id: str,
    name: str,
    risk_band: str = "green",
) -> None:
    g.upsert(EntityWrite(
        kind="Organisation",
        id=vendor_id,
        attrs={"name": name, "kind": "vendor", "risk_band": risk_band},
        source_workflows=(),
    ))


def _seed_money_pays_vendor(
    g: EntityGraph,
    *,
    money_id: str,
    amount: float,
    vendor_id: str,
) -> None:
    g.upsert(EntityWrite(
        kind="Money",
        id=money_id,
        attrs={
            "amount": float(amount),
            "currency": "GBP",
            "kind": "invoice",
            "period": "FY26",
        },
        source_workflows=(),
    ))
    g.link(money_id, "PAYS", vendor_id, posted_at=datetime.utcnow())


def _load_sourcing_lead(monkeypatch, g: EntityGraph):
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS.get("sourcing_lead")
    assert persona is not None
    assert persona.summarise is not None, (
        "sourcing_lead SKILL.md must declare summary_policy"
    )
    return persona


def test_sourcing_calm_when_no_concentration(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    # 10 vendors with equal £100k spend → 10% each, below the 12% threshold.
    for i in range(10):
        vid = f"ORG-vendor-equal-{i}"
        _seed_vendor(g, vendor_id=vid, name=f"Equal {i}")
        _seed_money_pays_vendor(
            g, money_id=f"MONEY-{i}", amount=100_000.0, vendor_id=vid,
        )

    persona = _load_sourcing_lead(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["headline"] == "Vendor portfolio diversified", out
    assert out["proposed_actions"] == []
    assert out["kpis"]["vendors_tracked"] == 10
    assert out["kpis"]["concentration_risks"] == 0
    assert out["kpis"]["active_pauses"] == 0
    assert out["kpis"]["total_vendor_spend_gbp"] == pytest.approx(1_000_000.0)


def test_sourcing_proposes_pause_when_concentration_high(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_vendor(g, vendor_id="ORG-vendor-alpha", name="Alpha Co")
    _seed_vendor(g, vendor_id="ORG-vendor-beta", name="Beta Co")
    _seed_money_pays_vendor(
        g, money_id="MONEY-A", amount=900_000.0, vendor_id="ORG-vendor-alpha",
    )
    _seed_money_pays_vendor(
        g, money_id="MONEY-B", amount=100_000.0, vendor_id="ORG-vendor-beta",
    )

    persona = _load_sourcing_lead(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert len(out["proposed_actions"]) == 1, out
    action = out["proposed_actions"][0]
    assert action["verdict"] == "freeze"
    assert action["kind"] == "policy_set"
    assert action["decided_on"] == ["ORG-vendor-alpha"]
    assert action["attributes"] == {"expiry_days": 14, "scope": "vendor_po"}
    assert action["id"] == "pause-vendor-alpha"
    assert "Alpha Co" in action["label"]
    assert "90%" in action["label"]
    assert out["kpis"]["concentration_risks"] == 1
    assert out["kpis"]["top_vendor_pct"] == pytest.approx(0.9)


def test_sourcing_proposes_pause_when_amber_risk_band_and_above_5pct(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    # Amber vendor at ~7% concentration; one big green dilutor takes the rest.
    _seed_vendor(
        g, vendor_id="ORG-vendor-amber", name="Amber Co", risk_band="amber",
    )
    _seed_vendor(
        g, vendor_id="ORG-vendor-bulk", name="Bulk Co", risk_band="green",
    )
    _seed_money_pays_vendor(
        g, money_id="MONEY-AMBER", amount=70_000.0,
        vendor_id="ORG-vendor-amber",
    )
    _seed_money_pays_vendor(
        g, money_id="MONEY-BULK", amount=930_000.0,
        vendor_id="ORG-vendor-bulk",
    )

    persona = _load_sourcing_lead(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    # The amber vendor (7%) trips the dual-trigger; the bulk vendor (93%)
    # also trips on the > 12% leg.
    proposed_ids = sorted(a["id"] for a in out["proposed_actions"])
    assert "pause-vendor-amber" in proposed_ids, out
    amber_action = next(
        a for a in out["proposed_actions"] if a["id"] == "pause-vendor-amber"
    )
    assert amber_action["decided_on"] == ["ORG-vendor-amber"]
    assert "amber" in amber_action["reason"]


def test_sourcing_skips_vendor_with_active_pause(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_vendor(g, vendor_id="ORG-vendor-alpha", name="Alpha Co")
    _seed_vendor(g, vendor_id="ORG-vendor-beta", name="Beta Co")
    _seed_money_pays_vendor(
        g, money_id="MONEY-A", amount=900_000.0, vendor_id="ORG-vendor-alpha",
    )
    _seed_money_pays_vendor(
        g, money_id="MONEY-B", amount=100_000.0, vendor_id="ORG-vendor-beta",
    )
    g.record_decision(
        workflow_id="WF-POL-test-1",
        phase="policy_set",
        persona_role="sourcing_lead",
        verdict="freeze",
        reason="manual seed",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={"expiry_days": 14, "scope": "vendor_po"},
        decided_on=("ORG-vendor-alpha",),
    )

    persona = _load_sourcing_lead(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["proposed_actions"] == [], out
    # The vendor is still counted as a concentration risk but already covered.
    assert out["kpis"]["concentration_risks"] == 1
    assert out["kpis"]["active_pauses"] == 1


def test_sourcing_fingerprint_deterministic(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_vendor(g, vendor_id="ORG-vendor-alpha", name="Alpha Co")
    _seed_vendor(g, vendor_id="ORG-vendor-beta", name="Beta Co")
    _seed_money_pays_vendor(
        g, money_id="MONEY-A", amount=900_000.0, vendor_id="ORG-vendor-alpha",
    )
    _seed_money_pays_vendor(
        g, money_id="MONEY-B", amount=100_000.0, vendor_id="ORG-vendor-beta",
    )

    persona = _load_sourcing_lead(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] == out_b["fingerprint"]
    assert out_a["fingerprint"].startswith("sourcing_lead:")


def test_sourcing_fingerprint_changes_when_concentration_changes(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_vendor(g, vendor_id="ORG-vendor-alpha", name="Alpha Co")
    _seed_vendor(g, vendor_id="ORG-vendor-beta", name="Beta Co")
    _seed_money_pays_vendor(
        g, money_id="MONEY-A", amount=500_000.0, vendor_id="ORG-vendor-alpha",
    )
    _seed_money_pays_vendor(
        g, money_id="MONEY-B", amount=500_000.0, vendor_id="ORG-vendor-beta",
    )

    persona = _load_sourcing_lead(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})

    _seed_money_pays_vendor(
        g, money_id="MONEY-A2", amount=500_000.0, vendor_id="ORG-vendor-alpha",
    )
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] != out_b["fingerprint"], (
        out_a["fingerprint"], out_b["fingerprint"],
    )
