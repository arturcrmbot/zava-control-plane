"""Phase B4 of autonomous-domain-insights v1.1: dpo summary_policy."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from api.server.services import persona_responder as pr
from api.server.services.entity_graph import EntityGraph, EntityWrite


def _seed_org(
    g: EntityGraph,
    *,
    org_id: str,
    name: str,
    risk_band: str | None = None,
    kind: str = "vendor",
) -> None:
    attrs: dict = {"name": name, "kind": kind}
    if risk_band is not None:
        attrs["risk_band"] = risk_band
    g.upsert(EntityWrite(
        kind="Organisation",
        id=org_id,
        attrs=attrs,
        source_workflows=(),
    ))


def _load_dpo(monkeypatch, g: EntityGraph):
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS.get("dpo")
    assert persona is not None
    assert persona.summarise is not None, "dpo SKILL.md must declare summary_policy"
    return persona


def test_dpo_calm_when_no_red_vendors(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    persona = _load_dpo(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["headline"] == "Privacy posture stable", out
    assert out["proposed_actions"] == []
    assert out["kpis"]["red_band_vendors"] == 0
    assert out["kpis"]["recent_privacy_escalations"] == 0
    assert out["kpis"]["active_data_restrictions"] == 0
    assert out["fingerprint"].startswith("dpo:")


def test_dpo_proposes_restriction_on_red_band_vendors(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(3):
        _seed_org(
            g,
            org_id=f"ORG-red-{i}",
            name=f"Red Vendor {i}",
            risk_band="red",
        )
    # A green vendor that should NOT count
    _seed_org(g, org_id="ORG-green-1", name="Green Vendor", risk_band="green")

    persona = _load_dpo(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert len(out["proposed_actions"]) == 1, out
    action = out["proposed_actions"][0]
    assert action["id"] == "data-restrict-vendors"
    assert action["verdict"] == "freeze"
    assert action["kind"] == "policy_set"
    assert action["decided_on"] == ["DATA:vendor-sharing"]
    assert action["attributes"]["expiry_days"] == 30
    assert action["attributes"]["scope"] == "data"
    assert "red-band vendor" in out["headline"]
    assert out["kpis"]["red_band_vendors"] == 3


def test_dpo_skips_when_active_data_restriction(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(3):
        _seed_org(
            g,
            org_id=f"ORG-red-{i}",
            name=f"Red Vendor {i}",
            risk_band="red",
        )
    # Seed the synthetic Organisation so active_policies_for can match
    # the policy_set Decision via the DECIDED_ORG rel.
    _seed_org(
        g,
        org_id="DATA:vendor-sharing",
        name="DATA scope",
        kind="data_scope",
    )
    g.record_decision(
        workflow_id="WF-POL-dpo-1",
        phase="policy_set",
        persona_role="dpo",
        verdict="freeze",
        reason="manual seed",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={"expiry_days": 30, "scope": "data"},
        decided_on=("DATA:vendor-sharing",),
    )

    persona = _load_dpo(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["proposed_actions"] == [], out
    assert out["kpis"]["active_data_restrictions"] == 1
    assert out["kpis"]["red_band_vendors"] == 3


def test_dpo_fingerprint_deterministic(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(2):
        _seed_org(
            g, org_id=f"ORG-red-{i}", name=f"R{i}", risk_band="red",
        )

    persona = _load_dpo(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] == out_b["fingerprint"]
    assert out_a["fingerprint"].startswith("dpo:")


def test_dpo_fingerprint_changes_when_red_count_changes(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_org(g, org_id="ORG-red-1", name="R1", risk_band="red")

    persona = _load_dpo(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})

    for i in range(3):
        _seed_org(
            g, org_id=f"ORG-red-add-{i}", name=f"RA{i}", risk_band="red",
        )
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] != out_b["fingerprint"], (
        out_a["fingerprint"], out_b["fingerprint"],
    )
