"""GET /api/replay/meta — replay mode indicator endpoint."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.routes import replay as replay_routes
from api.server.services.replay import player as player_module


@pytest.fixture
def client():
    """Create a test client with only the replay router (no full app lifespan)."""
    app = FastAPI()
    app.include_router(replay_routes.router)
    return TestClient(app)


def test_meta_returns_live_when_not_in_replay_mode(monkeypatch, client):
    """In live mode, /api/replay/meta returns {mode: "live"}."""
    monkeypatch.delenv("ZAVA_MODE", raising=False)
    r = client.get("/api/replay/meta")
    assert r.status_code == 200
    assert r.json() == {"mode": "live"}


def test_meta_returns_replay_shape_when_player_active(monkeypatch, client):
    """In replay mode with active player, meta includes tape_id, recorded_at, duration_s, current_t."""
    monkeypatch.setenv("ZAVA_MODE", "replay")

    # Build a fake Player with a meta + current_t. Avoids spinning up the
    # full player asyncio loop just to read its meta.
    from types import SimpleNamespace

    fake_meta = SimpleNamespace(
        tape_id="tape_test",
        recorded_at="2026-05-22T11:00:00+00:00",
        duration_s=42.0,
        version=1,
        app_sha="abc1234",
    )
    fake_player = SimpleNamespace(meta=fake_meta, current_t=lambda: 7.5)

    player_module.set_active_player(fake_player)
    try:
        r = client.get("/api/replay/meta")
        assert r.status_code == 200
        body = r.json()
        assert body == {
            "mode": "replay",
            "tape_id": "tape_test",
            "recorded_at": "2026-05-22T11:00:00+00:00",
            "duration_s": 42.0,
            "current_t": 7.5,
        }
    finally:
        player_module.set_active_player(None)


def test_meta_returns_replay_without_player_fields_when_player_missing(monkeypatch, client):
    """In replay mode but no active player, returns {mode: "replay"} only."""
    monkeypatch.setenv("ZAVA_MODE", "replay")
    # Make sure no active player
    player_module.set_active_player(None)
    r = client.get("/api/replay/meta")
    assert r.status_code == 200
    assert r.json() == {"mode": "replay"}
