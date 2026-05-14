"""Phase A2 of autonomous-domain-insights v1.1: ap_clerk decision_policy
honours active brand policy_set freezes set by other personae (e.g. CFO).

Pattern mirrors tests/api/server/personae/test_ceo_summary_policy.py — a
tmp-dir EntityGraph monkeypatched in for `_lazy_app_graph`, then
`_load_personae()` rebuilds PERSONA_DEFINITIONS so the compiled
decision_policy closes over the test graph.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from api.server.services import persona_responder as pr
from api.server.services.entity_graph import EntityGraph, EntityWrite


def _seed_brand_freeze(
    g: EntityGraph,
    *,
    brand_id: str = "BRAND-test",
    persona_role: str = "cfo",
    reason: str = "Q4 spend pause — pending board review",
    expiry_days: int = 14,
) -> None:
    g.upsert(EntityWrite(
        kind="Brand", id=brand_id, attrs={"name": brand_id},
        source_workflows=(),
    ))
    g.record_decision(
        workflow_id=f"WF-pol-{brand_id}",
        phase="policy_set",
        persona_role=persona_role,
        verdict="freeze",
        reason=reason,
        decided_at=datetime.utcnow(),
        source_event="persona.action.approved",
        attributes={"expiry_days": expiry_days},
        decided_on=(brand_id,),
    )


def _build_ap_clerk(tmp_path: Path, monkeypatch) -> object:
    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS.get("ap_clerk")
    assert persona is not None
    return g, persona


def test_ap_clerk_escalates_on_active_brand_freeze(
    tmp_path: Path, monkeypatch,
) -> None:
    g, persona = _build_ap_clerk(tmp_path, monkeypatch)
    _seed_brand_freeze(g, brand_id="BRAND-test", persona_role="cfo")

    out = persona.decide({
        "invoice": {
            "brand_id": "BRAND-test",
            "amount_gbp": 5000,
            "category": "standard",
        },
        # Even a clean three-way match must not override the freeze.
        "three_way_match": {"matched": True},
    })
    assert out["decision"] == "escalate", out
    assert "cfo" in (out.get("reason") or "").lower(), out


def test_ap_clerk_falls_through_when_no_freeze(
    tmp_path: Path, monkeypatch,
) -> None:
    _g, persona = _build_ap_clerk(tmp_path, monkeypatch)
    out = persona.decide({
        "invoice": {
            "brand_id": "BRAND-test",
            "amount_gbp": 1000,
            "category": "standard",
        },
        "three_way_match": {"matched": True},
    })
    # No freeze recorded → existing logic runs. Whatever it produces, it
    # must be a valid verdict (not None).
    assert out["decision"] in {"approve", "reject", "escalate"}, out
    # And specifically not the freeze-override message.
    assert "frozen by" not in (out.get("reason") or "").lower(), out


def test_ap_clerk_falls_through_when_brand_not_in_context(
    tmp_path: Path, monkeypatch,
) -> None:
    g, persona = _build_ap_clerk(tmp_path, monkeypatch)
    # A freeze exists, but the invoice doesn't reference any brand at
    # all — the new block must skip silently and the existing logic runs.
    _seed_brand_freeze(g, brand_id="BRAND-other")
    out = persona.decide({
        "invoice": {"amount_gbp": 1000, "category": "standard"},
        "three_way_match": {"matched": True},
    })
    assert out["decision"] in {"approve", "reject", "escalate"}, out
    assert "frozen by" not in (out.get("reason") or "").lower(), out
