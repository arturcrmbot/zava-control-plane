from fastapi.testclient import TestClient

from api.server.main import app

client = TestClient(app)


def test_working_notes_returns_list():
    r = client.get("/api/memory/working-notes", params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and isinstance(body["items"], list)


def test_active_lessons_returns_list():
    r = client.get("/api/memory/lessons/active", params={"domain": "hiring"})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["items"], list)
    # Domain filter must apply to every returned item.
    for it in body["items"]:
        assert it["domain"] == "hiring"


def test_active_lessons_without_domain_returns_all():
    r = client.get("/api/memory/lessons/active")
    assert r.status_code == 200
    assert isinstance(r.json()["items"], list)


def test_dream_passes_recent_returns_list():
    r = client.get("/api/memory/dream-passes/recent", params={"limit": 10})
    assert r.status_code == 200
    items = r.json()["items"]
    assert isinstance(items, list)
    for it in items:
        assert "id" in it and "domain" in it and "started_at" in it


def test_experiments_recent_returns_list():
    r = client.get("/api/memory/experiments/recent", params={"limit": 10})
    assert r.status_code == 200
    items = r.json()["items"]
    assert isinstance(items, list)
    for it in items:
        assert "id" in it
        assert "delta" in it


def test_experiments_recent_filterable_by_dream_pass():
    r = client.get(
        "/api/memory/experiments/recent",
        params={"dream_pass_id": "no-such-pass", "limit": 5},
    )
    assert r.status_code == 200
    # No experiments belong to this synthetic id.
    assert r.json()["items"] == []
