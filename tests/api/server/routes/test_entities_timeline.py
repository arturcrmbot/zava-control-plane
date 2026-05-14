"""GET /api/entities/{id}/timeline — chronological audit-ledger view."""
from __future__ import annotations

import time

from api.server.state import app_state

from tests.api.server.routes._entities_fixtures import client, graph  # noqa: F401


def _audit():
    return app_state.audit


def _seed(target_id: str, n: int = 3, action: str = "decision") -> list[float]:
    """Append ``n`` audit entries referencing ``target_id`` and return their
    monotonically increasing timestamps. Each entry uses a different
    detail key so the entries_for_id union is exercised end-to-end.
    """
    audit = _audit()
    audit._entries.clear()
    audit._tail_hashes.clear()
    keys = ("entity_id", "id", "decision_id")
    for i in range(n):
        audit.log(
            action,
            {
                "workflow_id": f"WF-{i}",
                keys[i % len(keys)]: target_id,
                "verdict": "approved" if i % 2 == 0 else "rejected",
                "persona_role": "cfo",
            },
        )
        time.sleep(0.001)
    return [e["timestamp"] for e in audit._entries]


def test_timeline_known_id_returns_rows(graph, client):
    _seed("ENT-1", n=3)
    r = client.get("/api/entities/ENT-1/timeline")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 3
    # Newest first.
    timestamps = [row["timestamp"] for row in body]
    assert timestamps == sorted(timestamps, reverse=True)
    row = body[0]
    assert row["action"] == "decision"
    assert isinstance(row["summary"], str) and row["summary"]
    assert row["raw_details"]["verdict"] in ("approved", "rejected")


def test_timeline_unknown_id_is_empty(graph, client):
    _seed("ENT-1", n=2)
    r = client.get("/api/entities/NO-SUCH-ID/timeline")
    assert r.status_code == 200
    assert r.json() == []


def test_timeline_respects_limit(graph, client):
    _seed("ENT-2", n=5)
    r = client.get("/api/entities/ENT-2/timeline", params={"limit": 2})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2


def test_timeline_respects_before_ts(graph, client):
    timestamps = _seed("ENT-3", n=4)
    cutoff = timestamps[2]  # entries at index 0,1 strictly before this
    r = client.get(
        "/api/entities/ENT-3/timeline",
        params={"before_ts": cutoff},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    for row in body:
        assert row["timestamp"] < cutoff


def test_timeline_workflow_id_match(graph, client):
    audit = _audit()
    audit._entries.clear()
    audit._tail_hashes.clear()
    audit.log("workflow.start", {"workflow_id": "WF-XYZ", "phase": "init"})
    r = client.get("/api/entities/WF-XYZ/timeline")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["raw_details"]["workflow_id"] == "WF-XYZ"
