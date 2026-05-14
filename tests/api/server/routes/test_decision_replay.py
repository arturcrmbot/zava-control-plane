"""POST /api/decisions/replay/{id} — pitch-i7 decision-replay endpoint."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.server.services.entity_graph import EntityGraph
from api.server.services.persona_responder import (
    PERSONA_DEFINITIONS,
    PersonaDefinition,
)
from api.server.state import app_state
from api.shared.types import Workflow


@pytest.fixture
def graph(tmp_path: Path, monkeypatch):
    g = EntityGraph(tmp_path / "g.kuzu")
    monkeypatch.setattr(app_state, "entities", g)
    try:
        yield g
    finally:
        g.close()


@pytest.fixture
def stub_persona(monkeypatch):
    """Register a deterministic test persona whose decide() echoes
    whatever ``context['_replay_verdict']`` says (defaulting to
    ``approve``). This lets a test flip the verdict on the fly without
    touching SKILL.md.
    """
    role = "i7-test-persona"

    def _decide(context):
        verdict = context.get("_replay_verdict") or "approve"
        return {"decision": verdict, "reason": f"stub:{verdict}"}

    PERSONA_DEFINITIONS[role] = PersonaDefinition(
        role=role,
        description="i7 test persona",
        workflow_label="i7-test",
        external_event="i7_decided",
        decide=_decide,
        skill_path=Path("/dev/null"),
    )
    try:
        yield role
    finally:
        PERSONA_DEFINITIONS.pop(role, None)


@pytest.fixture
def client():
    from api.server.main import app
    return TestClient(app)


def _seed_decision(graph, *, persona_role: str, verdict: str = "approve",
                   reason: str = "seeded", workflow_id: str = "WF-i7-1",
                   phase: str = "Approval", attributes: dict | None = None) -> str:
    return graph.record_decision(
        workflow_id=workflow_id,
        phase=phase,
        persona_role=persona_role,
        verdict=verdict,
        reason=reason,
        decided_at=dt.datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc),
        source_event="i7_decided",
        attributes=attributes or {"context": {"amount_usd": 100.0}},
    )


def test_replay_404_on_missing_decision(graph, client):
    resp = client.post("/api/decisions/replay/DOES-NOT-EXIST")
    assert resp.status_code == 404


def test_replay_same_verdict_changed_mind_false(graph, stub_persona, client):
    decision_id = _seed_decision(
        graph, persona_role=stub_persona, verdict="approve",
    )
    resp = client.post(f"/api/decisions/replay/{decision_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision_id"] == decision_id
    assert body["original"]["verdict"] == "approve"
    assert body["replay"]["verdict"] == "approve"
    assert body["changed_mind"] is False
    assert body["explanation_hints"] == []


def test_replay_flipped_verdict_changed_mind_true_with_hints(
    graph, stub_persona, client, monkeypatch,
):
    # Original verdict was "approve". Stash a workflow whose CURRENT
    # payload nudges the persona's decide() to return "escalate" — this
    # simulates "the org has changed its mind" via a state change.
    workflow_id = "WF-i7-flip"
    workflow = Workflow(
        id=workflow_id,
        type="expense-claim",
        created_at=0.0,
        sla_due_at=0.0,
        jurisdiction="US",
        agency="zava",
        payload={"_replay_verdict": "escalate"},
    )
    app_state.store.upsert_workflow(workflow)
    try:
        decision_id = _seed_decision(
            graph,
            persona_role=stub_persona,
            verdict="approve",
            workflow_id=workflow_id,
        )
        # Force at least one hint by marking the persona OOO today.
        monkeypatch.setattr(
            "api.shared.authority.is_ooo", lambda role: role == stub_persona,
        )
        resp = client.post(f"/api/decisions/replay/{decision_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["original"]["verdict"] == "approve"
        assert body["replay"]["verdict"] == "escalate"
        assert body["changed_mind"] is True
        assert body["explanation_hints"], "expected at least one hint"
        assert any("OOO" in h or "ooo" in h for h in body["explanation_hints"])
    finally:
        app_state.store._workflows.pop(workflow_id, None)  # type: ignore[attr-defined]


def test_replay_does_not_mutate_original_decision(graph, stub_persona, client):
    workflow_id = "WF-i7-immutable"
    workflow = Workflow(
        id=workflow_id, type="expense-claim",
        created_at=0.0, sla_due_at=0.0,
        jurisdiction="US", agency="zava",
        payload={"_replay_verdict": "reject"},
    )
    app_state.store.upsert_workflow(workflow)
    try:
        decision_id = _seed_decision(
            graph, persona_role=stub_persona, verdict="approve",
            workflow_id=workflow_id,
        )
        before = graph.get(decision_id)
        assert before is not None

        resp = client.post(f"/api/decisions/replay/{decision_id}")
        assert resp.status_code == 200
        assert resp.json()["changed_mind"] is True

        after = graph.get(decision_id)
        assert after is not None
        # Persisted attributes are unchanged.
        for key in ("verdict", "reason", "phase", "persona_role",
                    "workflow_id", "source_event", "attributes"):
            assert before.get(key) == after.get(key), (
                f"replay mutated Decision.{key}"
            )
    finally:
        app_state.store._workflows.pop(workflow_id, None)  # type: ignore[attr-defined]
