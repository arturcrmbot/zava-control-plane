"""Phase 4 Task 4.4: /api/entities/{id}/precedents."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from tests.api.server.routes._entities_fixtures import client, graph  # noqa: F401


def test_precedents_empty_when_no_chain(graph, client):
    from api.server.services.entity_graph import EntityWrite
    graph.upsert(EntityWrite(kind="Money", id="MONEY-X", attrs={"kind": "invoice", "amount": 1.0}))
    graph.record_decision(
        workflow_id="W-1", phase="signoff", persona_role="ap_clerk",
        verdict="approve", reason="ok", decided_at=datetime(2026, 5, 12, 10, 0, 0),
        source_event="e", attributes={}, decided_on=("MONEY-X",),
    )
    rows = graph.query("MATCH (d:Decision) RETURN d.id AS id LIMIT 1")
    decision_id = rows[0]["id"]
    r = client.get(f"/api/entities/{decision_id}/precedents")
    assert r.status_code == 200
    assert r.json()["precedents"] == []


def test_precedents_returns_chain(graph, client):
    from api.server.services.entity_graph import EntityWrite
    graph.upsert(EntityWrite(kind="Money", id="MONEY-Y", attrs={"kind": "invoice", "amount": 1.0}))
    graph.record_decision(
        workflow_id="W-prior", phase="signoff", persona_role="cfo",
        verdict="approve", reason="prior precedent", decided_at=datetime(2026, 5, 1, 10, 0, 0),
        source_event="e", attributes={}, decided_on=("MONEY-Y",),
    )
    graph.record_decision(
        workflow_id="W-now", phase="signoff", persona_role="cfo",
        verdict="approve", reason="cited prior", decided_at=datetime(2026, 5, 12, 10, 0, 0),
        source_event="e", attributes={}, decided_on=("MONEY-Y",),
    )
    rows = graph.query("MATCH (d:Decision) RETURN d.id AS id, d.workflow_id AS wf")
    by_wf = {r["wf"]: r["id"] for r in rows}
    # Wire PRECEDENT_OF: now -> prior
    graph.link(by_wf["W-now"], "PRECEDENT_OF", by_wf["W-prior"])
    r = client.get(f"/api/entities/{by_wf['W-now']}/precedents")
    assert r.status_code == 200
    body = r.json()
    assert len(body["precedents"]) == 1
    assert body["precedents"][0]["workflow_id"] == "W-prior"
