"""Phase B1 of autonomous-domain-insights v1.1: hr_director summary_policy."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from api.server.services import persona_responder as pr
from api.server.services.entity_graph import EntityGraph, EntityWrite


def _seed_person(
    g: EntityGraph,
    *,
    person_id: str,
    department: str,
    employed_to: date | None = None,
) -> None:
    attrs: dict = {
        "name": person_id,
        "department": department,
        "employed_from": date(2023, 1, 1),
        "role": "staff",
    }
    if employed_to is not None:
        attrs["employed_to"] = employed_to
    g.upsert(EntityWrite(
        kind="Person",
        id=person_id,
        attrs=attrs,
        source_workflows=(),
    ))


def _seed_org(g: EntityGraph, *, org_id: str, name: str) -> None:
    g.upsert(EntityWrite(
        kind="Organisation",
        id=org_id,
        attrs={"name": name},
        source_workflows=(),
    ))


def _load_hr(monkeypatch, g: EntityGraph):
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS.get("hr_director")
    assert persona is not None
    assert persona.summarise is not None, (
        "hr_director SKILL.md must declare summary_policy"
    )
    return persona


def test_hr_calm_when_attrition_low(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(5):
        _seed_person(
            g,
            person_id=f"PERSON-A-{i}",
            department="Dept A",
        )

    persona = _load_hr(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["headline"].startswith("Headcount steady"), out
    assert out["proposed_actions"] == []
    assert out["kpis"]["persons_total"] == 5
    assert out["kpis"]["stressed_departments"] == 0


def test_hr_proposes_freeze_when_attrition_high(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(5):
        _seed_person(
            g,
            person_id=f"PERSON-A-cur-{i}",
            department="Dept A",
        )
    for i in range(3):
        _seed_person(
            g,
            person_id=f"PERSON-A-lev-{i}",
            department="Dept A",
            employed_to=date(2025, 1, 1),
        )

    persona = _load_hr(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert len(out["proposed_actions"]) == 1, out
    action = out["proposed_actions"][0]
    assert action["verdict"] == "freeze"
    assert action["kind"] == "policy_set"
    assert action["decided_on"] == ["DEPT:Dept A"]
    assert action["attributes"]["expiry_days"] == 30
    assert action["attributes"]["scope"] == "hiring"
    assert action["id"] == "freeze-hiring-dept-a"
    assert "Dept A" in action["label"]
    assert out["kpis"]["stressed_departments"] == 1
    assert out["kpis"]["persons_total"] == 8


def test_hr_skips_dept_with_active_freeze(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(5):
        _seed_person(
            g,
            person_id=f"PERSON-A-cur-{i}",
            department="Dept A",
        )
    for i in range(3):
        _seed_person(
            g,
            person_id=f"PERSON-A-lev-{i}",
            department="Dept A",
            employed_to=date(2025, 1, 1),
        )
    # Seed the synthetic Organisation node so active_policies_for can
    # match the policy_set Decision via the DECIDED_ORG rel.
    _seed_org(g, org_id="DEPT:Dept A", name="Dept A")
    g.record_decision(
        workflow_id="WF-POL-hr-1",
        phase="policy_set",
        persona_role="hr_director",
        verdict="freeze",
        reason="manual seed",
        decided_at=datetime.utcnow(),
        source_event="test.seed",
        attributes={"expiry_days": 30, "scope": "hiring"},
        decided_on=("DEPT:Dept A",),
    )

    persona = _load_hr(monkeypatch, g)
    out = persona.summarise({"last_insight": None})

    assert out["proposed_actions"] == [], out
    assert out["kpis"]["stressed_departments"] == 1


def test_hr_fingerprint_deterministic(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(5):
        _seed_person(g, person_id=f"PERSON-A-{i}", department="Dept A")
    for i in range(2):
        _seed_person(
            g, person_id=f"PERSON-A-lev-{i}",
            department="Dept A", employed_to=date(2025, 1, 1),
        )
    for i in range(4):
        _seed_person(g, person_id=f"PERSON-B-{i}", department="Dept B")

    persona = _load_hr(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] == out_b["fingerprint"]
    assert out_a["fingerprint"].startswith("hr_director:")


def test_hr_fingerprint_changes_when_attrition_changes(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    for i in range(5):
        _seed_person(g, person_id=f"PERSON-A-{i}", department="Dept A")

    persona = _load_hr(monkeypatch, g)
    out_a = persona.summarise({"last_insight": None})

    for i in range(3):
        _seed_person(
            g, person_id=f"PERSON-A-lev-{i}",
            department="Dept A", employed_to=date(2025, 1, 1),
        )
    out_b = persona.summarise({"last_insight": None})

    assert out_a["fingerprint"] != out_b["fingerprint"], (
        out_a["fingerprint"], out_b["fingerprint"],
    )
