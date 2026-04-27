"""Tests for /api/policy-md routes — get/save with cache invalidation."""
from __future__ import annotations
from pathlib import Path

from fastapi.testclient import TestClient

from api.server.main import app
from api.server.mcp_tools import policy_search

client = TestClient(app)

POLICY_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "policy.md"


def test_get_content_returns_policy_markdown():
    resp = client.get("/api/policy-md/content")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "content" in body
    assert "# WPP Group T&E Policy" in body["content"]


def test_save_writes_file_and_invalidates_cache(monkeypatch, tmp_path):
    # Redirect both the route and the search tool to a sandbox file so the
    # real policy.md is not mutated.
    sandbox = tmp_path / "policy.md"
    sandbox.write_text("# original\n", encoding="utf-8")

    from api.server.routes import policy_md as route
    monkeypatch.setattr(route, "_POLICY_PATH", sandbox)
    monkeypatch.setattr(policy_search, "_POLICY_PATH", sandbox)

    called = {"reset": 0}
    real_reset = policy_search.reset_cache

    def counted_reset():
        called["reset"] += 1
        real_reset()

    monkeypatch.setattr(policy_search, "reset_cache", counted_reset)
    monkeypatch.setattr(route, "policy_search", policy_search)

    new_text = "# edited\nMeal cap is now 50.\n"
    resp = client.post("/api/policy-md/save", json={"content": new_text})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True

    assert sandbox.read_text(encoding="utf-8") == new_text
    assert called["reset"] == 1


def test_get_content_404_when_file_missing(monkeypatch, tmp_path):
    from api.server.routes import policy_md as route
    monkeypatch.setattr(route, "_POLICY_PATH", tmp_path / "missing.md")
    resp = client.get("/api/policy-md/content")
    assert resp.status_code == 404
