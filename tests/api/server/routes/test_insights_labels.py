"""Test for /api/personas/labels/preview endpoint (spec §9 polish item g)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_labels_preview_returns_known_keys():
    from api.server.main import app
    client = TestClient(app)
    r = client.get(
        "/api/personas/labels/preview",
        headers={"x-actor-role": "executive"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "verdicts" in body
    assert "scopes" in body
    assert "personas" in body
    assert isinstance(body["verdicts"], dict)
    assert isinstance(body["scopes"], dict)
    assert isinstance(body["personas"], dict)
    assert body["verdicts"]["freeze"] == "Freeze"
    assert body["scopes"]["po"] == "purchase orders"
    assert body["personas"]["cfo"] == "CFO"
