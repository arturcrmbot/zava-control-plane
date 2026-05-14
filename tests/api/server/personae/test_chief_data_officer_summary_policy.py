"""Phase B5 of autonomous-domain-insights v1.1: chief_data_officer summary_policy."""
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
    persona = pr.PERSONA_DEFINITIONS.get("chief_data_officer")
    assert persona is not None
    assert persona.summarise is not None, (
        "chief_data_officer SKILL.md must declare summary_policy"
    )
    return persona


def test_cdo_calm_when_no_data_workflows(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    persona = _load_persona(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["headline"] == "Data fabric healthy", out
    assert out["proposed_actions"] == []
    assert out["kpis"]["data_workflows_recent"] == 0
    assert out["kpis"]["data_workflow_failures"] == 0
    assert out["kpis"]["active_data_freeze"] is False
    assert out["fingerprint"].startswith("chief_data_officer:")


def test_cdo_proposes_freeze_on_failures(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(4):
        wf_id = f"WF-DATA-{i}"
        _seed_workflow(g, wf_id=wf_id, workflow_type="data-clean-room-setup")
        g.record_decision(
            workflow_id=wf_id,
            phase="review",
            persona_role="chief_data_officer",
            verdict="escalate",
            reason="lineage gap",
            decided_at=datetime.utcnow(),
            source_event="test.seed",
            attributes={},
            decided_on=(),
        )

    persona = _load_persona(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert len(out["proposed_actions"]) == 1, out
    action = out["proposed_actions"][0]
    assert action["id"] == "data-quality-freeze"
    assert action["verdict"] == "freeze"
    assert action["kind"] == "policy_set"
    assert action["decided_on"] == ["DATA:clean-room-new"]
    assert action["attributes"]["expiry_days"] == 14
    assert action["attributes"]["scope"] == "data"
    assert out["headline"] == "Data quality flagged — recommend setup freeze"
    assert out["kpis"]["data_workflow_failures"] == 4


def test_cdo_skips_when_freeze_active(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(4):
        wf_id = f"WF-DATA-{i}"
        _seed_workflow(g, wf_id=wf_id, workflow_type="data-clean-room-setup")
        g.record_decision(
            workflow_id=wf_id,
            phase="review",
            persona_role="chief_data_officer",
            verdict="escalate",
            reason="lineage gap",
            decided_at=datetime.utcnow(),
            source_event="test.seed",
            attributes={},
            decided_on=(),
        )
    _seed_org(g, org_id="DATA:clean-room-new", name="Data lane")
    g.record_decision(
        workflow_id="WF-POL-cdo-1",
        phase="policy_set",
        persona_role="chief_data_officer",
        verdict="freeze",
        reason="manual seed",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={"expiry_days": 14, "scope": "data"},
        decided_on=("DATA:clean-room-new",),
    )

    persona = _load_persona(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["proposed_actions"] == [], out
    assert out["kpis"]["active_data_freeze"] is True
    assert out["kpis"]["data_workflow_failures"] == 4


def test_cdo_fingerprint_deterministic(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(2):
        _seed_workflow(g, wf_id=f"WF-DATA-{i}", workflow_type="privacy-dpia")

    persona = _load_persona(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] == out_b["fingerprint"]
    assert out_a["fingerprint"].startswith("chief_data_officer:")


def test_cdo_fingerprint_changes_when_failures_change(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_workflow(g, wf_id="WF-DATA-1", workflow_type="data-clean-room-setup")

    persona = _load_persona(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})

    g.record_decision(
        workflow_id="WF-DATA-1",
        phase="review",
        persona_role="chief_data_officer",
        verdict="escalate",
        reason="x",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={},
        decided_on=(),
    )
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] != out_b["fingerprint"], (
        out_a["fingerprint"], out_b["fingerprint"],
    )
