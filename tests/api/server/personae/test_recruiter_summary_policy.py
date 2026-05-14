"""Phase B5 of autonomous-domain-insights v1.1: recruiter summary_policy."""
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
    workflow_type: str = "hiring",
) -> None:
    g.upsert(EntityWrite(
        kind="Workflow",
        id=wf_id,
        attrs={
            "workflow_type": workflow_type,
            "status": "running",
            "started_at": datetime.utcnow(),
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


def _load_persona(monkeypatch, g: EntityGraph):
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS.get("recruiter")
    assert persona is not None
    assert persona.summarise is not None, (
        "recruiter SKILL.md must declare summary_policy"
    )
    return persona


def test_recruiter_calm_when_no_workflows(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    persona = _load_persona(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["headline"] == "Hiring on track", out
    assert out["proposed_actions"] == []
    assert out["kpis"]["recent_hiring_workflows"] == 0
    assert out["kpis"]["hires"] == 0
    assert out["kpis"]["closure_rate_pct"] == 0
    assert out["kpis"]["active_freeze"] is False
    assert out["fingerprint"].startswith("recruiter:")


def test_recruiter_proposes_freeze_on_low_closure_rate(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    # 5 hiring workflows, 1 hire -> 20% closure rate
    for i in range(5):
        _seed_workflow(g, wf_id=f"WF-HIRE-{i}")
    g.record_decision(
        workflow_id="WF-HIRE-0",
        phase="offer_approval",
        persona_role="recruiter",
        verdict="approve",
        reason="hire",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={},
        decided_on=(),
    )

    persona = _load_persona(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert len(out["proposed_actions"]) == 1, out
    action = out["proposed_actions"][0]
    assert action["id"] == "recruit-prioritise-replacements"
    assert action["verdict"] == "freeze"
    assert action["kind"] == "policy_set"
    assert action["decided_on"] == ["HIRING:net-new-reqs"]
    assert action["attributes"]["expiry_days"] == 14
    assert action["attributes"]["scope"] == "hiring"
    assert out["headline"] == (
        "Hiring velocity below target — focus on replacements"
    )
    assert out["kpis"]["recent_hiring_workflows"] == 5
    assert out["kpis"]["hires"] == 1
    assert out["kpis"]["closure_rate_pct"] == 20


def test_recruiter_skips_when_freeze_active(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(5):
        _seed_workflow(g, wf_id=f"WF-HIRE-{i}")
    g.record_decision(
        workflow_id="WF-HIRE-0",
        phase="offer_approval",
        persona_role="recruiter",
        verdict="approve",
        reason="hire",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={},
        decided_on=(),
    )
    _seed_org(g, org_id="HIRING:net-new-reqs", name="Hiring lane")
    g.record_decision(
        workflow_id="WF-POL-rec-1",
        phase="policy_set",
        persona_role="recruiter",
        verdict="freeze",
        reason="manual seed",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={"expiry_days": 14, "scope": "hiring"},
        decided_on=("HIRING:net-new-reqs",),
    )

    persona = _load_persona(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["proposed_actions"] == [], out
    assert out["kpis"]["active_freeze"] is True
    assert out["kpis"]["recent_hiring_workflows"] == 5


def test_recruiter_fingerprint_deterministic(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(3):
        _seed_workflow(g, wf_id=f"WF-HIRE-{i}")

    persona = _load_persona(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] == out_b["fingerprint"]
    assert out_a["fingerprint"].startswith("recruiter:")


def test_recruiter_fingerprint_changes_when_workflow_count_changes(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_workflow(g, wf_id="WF-HIRE-1")

    persona = _load_persona(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})

    for i in range(3):
        _seed_workflow(g, wf_id=f"WF-HIRE-add-{i}")
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] != out_b["fingerprint"], (
        out_a["fingerprint"], out_b["fingerprint"],
    )
