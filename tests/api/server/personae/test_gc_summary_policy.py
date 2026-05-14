"""Phase B4 of autonomous-domain-insights v1.1: gc summary_policy."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from api.server.services import persona_responder as pr
from api.server.services.entity_graph import EntityGraph, EntityWrite


def _seed_workflow(
    g: EntityGraph,
    *,
    wf_id: str,
    workflow_type: str,
) -> None:
    g.upsert(EntityWrite(
        kind="Workflow",
        id=wf_id,
        attrs={
            "workflow_type": workflow_type,
            "status": "running",
        },
        source_workflows=(),
    ))


def _seed_org(g: EntityGraph, *, org_id: str, name: str) -> None:
    g.upsert(EntityWrite(
        kind="Organisation",
        id=org_id,
        attrs={"name": name, "kind": "process_lane"},
        source_workflows=(),
    ))


def _load_gc(monkeypatch, g: EntityGraph):
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS.get("gc")
    assert persona is not None
    assert persona.summarise is not None, "gc SKILL.md must declare summary_policy"
    return persona


def test_gc_calm_when_no_escalations(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    persona = _load_gc(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["headline"] == "Legal posture stable", out
    assert out["proposed_actions"] == []
    assert out["kpis"]["contract_workflows"] == 0
    assert out["kpis"]["recent_contract_escalations"] == 0
    assert out["kpis"]["active_policies_total"] == 0
    assert out["kpis"]["legal_freeze_active"] is False
    assert out["fingerprint"].startswith("gc:")


def test_gc_proposes_review_on_high_escalation_count(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(6):
        wf_id = f"WF-CON-{i}"
        _seed_workflow(g, wf_id=wf_id, workflow_type="contract-renewal")
        g.record_decision(
            workflow_id=wf_id,
            phase="review",
            persona_role="gc",
            verdict="escalate",
            reason="contract risk",
            decided_at=datetime.utcnow(),
            source_event="test.seed",
            attributes={},
            decided_on=(),
        )

    persona = _load_gc(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert len(out["proposed_actions"]) == 1, out
    action = out["proposed_actions"][0]
    assert action["id"] == "legal-review-contracts"
    assert action["verdict"] == "freeze"
    assert action["kind"] == "policy_set"
    assert action["decided_on"] == ["LEGAL:contract-fast-track"]
    assert action["attributes"]["expiry_days"] == 14
    assert action["attributes"]["scope"] == "contracts"
    assert out["headline"] == "Contract risk elevated — recommend mandatory review"
    assert out["kpis"]["recent_contract_escalations"] == 6
    assert out["kpis"]["contract_workflows"] == 6


def test_gc_proposes_review_on_active_policies_total(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    # Four unrelated active policy_set Decisions across personae.
    for i in range(4):
        g.record_decision(
            workflow_id=f"WF-POL-x-{i}",
            phase="policy_set",
            persona_role="cfo",
            verdict="freeze",
            reason="manual seed",
            decided_at=datetime.utcnow(),
            source_event="test.seed",
            attributes={"expiry_days": 14, "scope": "po"},
            decided_on=(),
        )

    persona = _load_gc(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert len(out["proposed_actions"]) == 1, out
    assert out["kpis"]["active_policies_total"] == 4
    assert out["kpis"]["recent_contract_escalations"] == 0


def test_gc_skips_when_legal_freeze_active(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(6):
        wf_id = f"WF-CON-{i}"
        _seed_workflow(g, wf_id=wf_id, workflow_type="contract-renewal")
        g.record_decision(
            workflow_id=wf_id,
            phase="review",
            persona_role="gc",
            verdict="escalate",
            reason="contract risk",
            decided_at=datetime.utcnow(),
            source_event="test.seed",
            attributes={},
            decided_on=(),
        )
    # Seed the synthetic Organisation so active_policies_for can match.
    _seed_org(g, org_id="LEGAL:contract-fast-track", name="Legal lane")
    g.record_decision(
        workflow_id="WF-POL-gc-1",
        phase="policy_set",
        persona_role="gc",
        verdict="freeze",
        reason="manual seed",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={"expiry_days": 14, "scope": "contracts"},
        decided_on=("LEGAL:contract-fast-track",),
    )

    persona = _load_gc(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["proposed_actions"] == [], out
    assert out["kpis"]["legal_freeze_active"] is True
    assert out["kpis"]["recent_contract_escalations"] == 6


def test_gc_fingerprint_deterministic(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(2):
        wf_id = f"WF-CON-{i}"
        _seed_workflow(g, wf_id=wf_id, workflow_type="contract-review")
        g.record_decision(
            workflow_id=wf_id,
            phase="review",
            persona_role="gc",
            verdict="escalate",
            reason="x",
            decided_at=datetime.utcnow(),
            source_event="test.seed",
            attributes={},
            decided_on=(),
        )

    persona = _load_gc(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] == out_b["fingerprint"]
    assert out_a["fingerprint"].startswith("gc:")
