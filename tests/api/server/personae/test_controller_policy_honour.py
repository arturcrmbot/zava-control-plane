"""A3: controller honours active Brand freeze policies.

Mirrors the ap_clerk hook (A2): if a policy_set Decision with
verdict='freeze' is active on the invoice's Brand, the controller
escalates upward to the CFO instead of auto-approving — keeping the
escalation chain ap_clerk -> controller -> CFO honest.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from api.server.services import persona_responder as pr
from api.server.services.entity_graph import EntityGraph, EntityWrite


def _seed_brand_freeze(g: EntityGraph, brand_id: str, by: str = "cfo") -> None:
    g.upsert(EntityWrite(
        kind="Brand",
        id=brand_id,
        attrs={"name": brand_id.removeprefix("BRAND-")},
        source_workflows=(),
    ))
    g.record_decision(
        workflow_id=f"WF-POL-{brand_id}",
        phase="policy_set",
        persona_role=by,
        verdict="freeze",
        reason="aurora-style risk freeze",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={"expiry_days": 14},
        decided_on=(brand_id,),
    )


def _controller(monkeypatch, g: EntityGraph):
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS.get("controller")
    assert persona is not None, "controller persona must be registered"
    return persona


def test_controller_escalates_on_active_brand_freeze(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    try:
        _seed_brand_freeze(g, "BRAND-acme", by="cfo")
        persona = _controller(monkeypatch, g)

        # Invoice that would normally fall within the controller band
        # (£47k standard) — must escalate purely because of the freeze.
        out = persona.decide({
            "workflow_type": "ap-invoice",
            "invoice": {
                "amount_gbp": 47000,
                "category": "standard",
                "brand_id": "BRAND-acme",
            },
        })
        assert out["decision"] == "escalate", out
        assert "BRAND-acme" in out["reason"]
        assert "freeze" in out["reason"].lower()
    finally:
        g.close()


def test_controller_falls_through_when_no_freeze(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    try:
        # Brand exists but no active freeze policy.
        g.upsert(EntityWrite(
            kind="Brand", id="BRAND-acme",
            attrs={"name": "Acme"}, source_workflows=(),
        ))
        persona = _controller(monkeypatch, g)

        out = persona.decide({
            "workflow_type": "ap-invoice",
            "invoice": {
                "amount_gbp": 47000,
                "category": "standard",
                "brand_id": "BRAND-acme",
            },
        })
        # Controller's normal band per AP-003 covers up to £250k -> approve.
        assert out["decision"] == "approve", out
        assert "controller delegation" in out["reason"]
    finally:
        g.close()


def test_controller_falls_through_when_brand_not_in_context(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    try:
        # Even with a freeze on some brand, an invoice that doesn't carry
        # a brand_id must NOT spuriously escalate — the hook is opt-in via
        # the payload's brand reference.
        _seed_brand_freeze(g, "BRAND-acme", by="cfo")
        persona = _controller(monkeypatch, g)

        out = persona.decide({
            "workflow_type": "ap-invoice",
            "invoice": {
                "amount_gbp": 47000,
                "category": "standard",
            },
        })
        assert out["decision"] == "approve", out
        assert "BRAND-acme" not in out["reason"]
    finally:
        g.close()
