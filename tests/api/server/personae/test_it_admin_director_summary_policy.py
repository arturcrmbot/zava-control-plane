"""Phase B5 of autonomous-domain-insights v1.1: it_admin_director summary_policy."""
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
    workflow_type: str = "it-access-request",
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
    persona = pr.PERSONA_DEFINITIONS.get("it_admin_director")
    assert persona is not None
    assert persona.summarise is not None, (
        "it_admin_director SKILL.md must declare summary_policy"
    )
    return persona


def test_it_admin_director_calm_when_no_anomalies(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    persona = _load_persona(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["headline"] == "Access posture stable", out
    assert out["proposed_actions"] == []
    assert out["kpis"]["recent_access_requests"] == 0
    assert out["kpis"]["anomalies"] == 0
    assert out["kpis"]["anomaly_rate_pct"] == 0
    assert out["kpis"]["active_freeze"] is False
    assert out["fingerprint"].startswith("it_admin_director:")


def test_it_admin_director_proposes_freeze_on_high_anomaly_rate(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    # 5 access workflows, 2 escalations -> 40% anomaly rate
    for i in range(5):
        wf_id = f"WF-IT-{i}"
        _seed_workflow(g, wf_id=wf_id)
    for i in range(2):
        g.record_decision(
            workflow_id=f"WF-IT-{i}",
            phase="it_admin_approval",
            persona_role="it_admin_director",
            verdict="escalate",
            reason="suspicious access",
            decided_at=datetime.utcnow(),
            source_event="test.seed",
            attributes={},
            decided_on=(),
        )

    persona = _load_persona(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert len(out["proposed_actions"]) == 1, out
    action = out["proposed_actions"][0]
    assert action["id"] == "freeze-access-broad"
    assert action["verdict"] == "freeze"
    assert action["kind"] == "policy_set"
    assert action["decided_on"] == ["IT:access-fast-track"]
    assert action["attributes"]["expiry_days"] == 7
    assert action["attributes"]["scope"] == "access"
    assert out["headline"] == (
        "Access anomaly rate elevated — recommend tighter approvals"
    )
    assert out["kpis"]["recent_access_requests"] == 5
    assert out["kpis"]["anomalies"] == 2
    assert out["kpis"]["anomaly_rate_pct"] == 40


def test_it_admin_director_skips_when_freeze_active(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(5):
        wf_id = f"WF-IT-{i}"
        _seed_workflow(g, wf_id=wf_id)
    for i in range(2):
        g.record_decision(
            workflow_id=f"WF-IT-{i}",
            phase="it_admin_approval",
            persona_role="it_admin_director",
            verdict="escalate",
            reason="suspicious access",
            decided_at=datetime.utcnow(),
            source_event="test.seed",
            attributes={},
            decided_on=(),
        )
    _seed_org(g, org_id="IT:access-fast-track", name="IT lane")
    g.record_decision(
        workflow_id="WF-POL-it-1",
        phase="policy_set",
        persona_role="it_admin_director",
        verdict="freeze",
        reason="manual seed",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={"expiry_days": 7, "scope": "access"},
        decided_on=("IT:access-fast-track",),
    )

    persona = _load_persona(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["proposed_actions"] == [], out
    assert out["kpis"]["active_freeze"] is True
    assert out["kpis"]["anomalies"] == 2


def test_it_admin_director_fingerprint_deterministic(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(3):
        _seed_workflow(g, wf_id=f"WF-IT-{i}")

    persona = _load_persona(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] == out_b["fingerprint"]
    assert out_a["fingerprint"].startswith("it_admin_director:")


def test_it_admin_director_fingerprint_changes_when_anomalies_change(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(5):
        _seed_workflow(g, wf_id=f"WF-IT-{i}")

    persona = _load_persona(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})

    g.record_decision(
        workflow_id="WF-IT-0",
        phase="it_admin_approval",
        persona_role="it_admin_director",
        verdict="escalate",
        reason="suspicious",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={},
        decided_on=(),
    )
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] != out_b["fingerprint"], (
        out_a["fingerprint"], out_b["fingerprint"],
    )
