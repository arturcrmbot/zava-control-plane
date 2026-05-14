"""Phase F1 of autonomous-domain-insights v1.1: GET /api/personas/colors."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from api.shared.personas import PERSONAS


_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@pytest.fixture(scope="module")
def client():
    from api.server.main import app
    return TestClient(app)


def test_colors_endpoint_returns_dict_for_all_personas(client: TestClient):
    r = client.get("/api/personas/colors")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, dict)
    assert set(body.keys()) == set(PERSONAS.keys())
    non_null = [v for v in body.values() if v is not None]
    assert len(non_null) >= 15, f"expected >=15 coloured personas, got {len(non_null)}"
    for v in non_null:
        assert _HEX_RE.match(v), f"invalid hex colour in response: {v!r}"
