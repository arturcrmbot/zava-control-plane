from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from api.server.services.entity_graph import EntityGraph, EntityWrite
from api.server.state import app_state


def _signed(body: dict, secret: str = "test-durable-secret"):
    raw = json.dumps(body, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return raw, {"X-Durable-Event-Signature": signature, "Content-Type": "application/json"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DURABLE_EVENT_SECRET", "test-durable-secret")
    graph = EntityGraph(tmp_path / "aurora.kuzu")
    monkeypatch.setattr(app_state, "entities", graph)
    graph.upsert(EntityWrite(
        kind="Brand",
        id="BRAND-aurora",
        attrs={
            "name": "Aurora",
            "annual_budget_gbp": 100_000.0,
            "budget_remaining_gbp": 60_000.0,
            "attributes": "{}",
        },
        source_workflows=(),
    ))
    graph.upsert(EntityWrite(
        kind="Account",
        id="ACC-6010",
        attrs={"code": "6010", "name": "Marketing", "type": "expense", "currency": "GBP"},
        source_workflows=(),
    ))
    graph.upsert(EntityWrite(
        kind="Period",
        id="PERIOD-Q1-2026",
        attrs={
            "kind": "quarter",
            "starts": datetime(2026, 1, 1),
            "ends": datetime(2026, 3, 31),
            "label": "Q1 2026",
        },
        source_workflows=(),
    ))
    graph.upsert(EntityWrite(
        kind="Money",
        id="MONEY-AURORA-SEED",
        attrs={"kind": "po", "amount": 40_000.0, "currency": "GBP", "attributes": "{}"},
        source_workflows=(),
    ))
    graph.link("MONEY-AURORA-SEED", "COSTED_TO_BRAND", "BRAND-aurora")
    from api.server.main import app
    try:
        yield TestClient(app), graph
    finally:
        graph.close()


def test_signed_operation_observes_budget_and_applies_cfo_po_policy(client):
    http, graph = client
    observe_body = {
        "operation": "observe_budget",
        "workflow_id": "AUR-OPS-1",
        "brand_id": "BRAND-aurora",
        "target_pct": 1.0,
    }
    raw, headers = _signed(observe_body)
    observed = http.post(
        "/internal/agency/aurora-budget-operation",
        content=raw,
        headers=headers,
    )
    assert observed.status_code == 200, observed.text
    assert observed.json()["after_pct"] >= 1.0
    assert observed.json()["signal_id"]
    observed_again = http.post(
        "/internal/agency/aurora-budget-operation",
        content=raw,
        headers=headers,
    )
    assert observed_again.status_code == 200
    assert observed_again.json() == observed.json()

    apply_body = {
        "operation": "apply_policy",
        "workflow_id": "AUR-OPS-1",
        "brand_id": "BRAND-aurora",
        "approval": {
            "decision": "approve",
            "decision_id": "EXC-AUR-OPS-1",
            "resolved_by": "cfo@example.test",
            "actor_role": "cfo",
        },
        "proposed_action": {
            "id": "freeze-brand-aurora",
            "kind": "policy_set",
            "verdict": "freeze",
            "decided_on": ["BRAND-aurora"],
            "attributes": {"scope": "po", "expiry_days": 14},
            "reason": "Aurora exceeded budget.",
        },
    }
    raw, headers = _signed(apply_body)
    applied = http.post(
        "/internal/agency/aurora-budget-operation",
        content=raw,
        headers=headers,
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["outcome"] == "applied"
    assert applied.json()["governing_rule_id"] == "POL-CFO-001"

    duplicate = http.post(
        "/internal/agency/aurora-budget-operation",
        content=raw,
        headers=headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["decision_id"] == applied.json()["decision_id"]
    conflicting_body = {
        **apply_body,
        "approval": {
            **apply_body["approval"],
            "decision_id": "EXC-AUR-OPS-CONFLICT",
        },
    }
    conflicting_raw, conflicting_headers = _signed(conflicting_body)
    conflicting = http.post(
        "/internal/agency/aurora-budget-operation",
        content=conflicting_raw,
        headers=conflicting_headers,
    )
    assert conflicting.status_code == 409
    rows = graph.query(
        "MATCH (d:Decision) WHERE d.workflow_id = 'AUR-OPS-1' "
        "AND d.phase = 'policy_set' RETURN d.id AS id, d.verdict AS verdict"
    )
    assert rows == [{"id": applied.json()["decision_id"], "verdict": "freeze"}]


def test_signed_policy_operation_rejects_wrong_action_category(client):
    http, _graph = client
    body = {
        "operation": "apply_policy",
        "workflow_id": "AUR-OPS-DENIED",
        "brand_id": "BRAND-aurora",
        "approval": {
            "decision": "approve",
            "decision_id": "EXC-AUR-DENIED",
            "resolved_by": "executive@example.test",
            "actor_role": "cfo",
        },
        "proposed_action": {
            "id": "freeze-brand-aurora",
            "kind": "policy_set",
            "verdict": "freeze",
            "decided_on": ["BRAND-aurora"],
            "attributes": {"scope": "brand", "expiry_days": 14},
        },
    }
    raw, headers = _signed(body)

    response = http.post(
        "/internal/agency/aurora-budget-operation",
        content=raw,
        headers=headers,
    )

    assert response.status_code == 403
