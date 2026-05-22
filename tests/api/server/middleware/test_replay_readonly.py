import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.middleware.replay_readonly import ReplayReadOnlyMiddleware


@pytest.fixture
def app_with_middleware():
    app = FastAPI()
    app.add_middleware(ReplayReadOnlyMiddleware)

    @app.get("/probe")
    def get_probe():
        return {"ok": True}

    @app.post("/probe")
    def post_probe():
        return {"ok": True}

    @app.put("/probe")
    def put_probe():
        return {"ok": True}

    @app.patch("/probe")
    def patch_probe():
        return {"ok": True}

    @app.delete("/probe")
    def delete_probe():
        return {"ok": True}

    return app


@pytest.fixture
def client(app_with_middleware):
    return TestClient(app_with_middleware)


def test_get_passes_through_in_replay_mode(monkeypatch, client):
    monkeypatch.setenv("ZAVA_MODE", "replay")
    assert client.get("/probe").status_code == 200


def test_post_blocked_in_replay_mode(monkeypatch, client):
    monkeypatch.setenv("ZAVA_MODE", "replay")
    r = client.post("/probe")
    assert r.status_code == 403
    body = r.json()
    assert body["error"] == "replay"
    assert "actions are observed" in body["message"]


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_all_write_methods_blocked_in_replay_mode(monkeypatch, client, method):
    monkeypatch.setenv("ZAVA_MODE", "replay")
    r = client.request(method, "/probe")
    assert r.status_code == 403


def test_post_allowed_in_live_mode(monkeypatch, client):
    monkeypatch.delenv("ZAVA_MODE", raising=False)
    assert client.post("/probe").status_code == 200


def test_post_allowed_when_zava_mode_is_live(monkeypatch, client):
    monkeypatch.setenv("ZAVA_MODE", "live")
    assert client.post("/probe").status_code == 200
