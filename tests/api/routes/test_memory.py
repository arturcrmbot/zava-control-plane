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


def test_active_lessons_route_uses_lesson_store_search_not_private_by_id(monkeypatch):
    """Regression: the route MUST go through LessonStore.search so it
    works against Mem0 (which has no _by_id dict). InMemoryLessonStore
    happens to expose _by_id but reaching into it makes the route
    incompatible with Mem0."""
    from api.server.state import app_state

    captured: list[dict] = []
    real_search = app_state.lesson_store.search

    def spy_search(query="", *, scope, top_k=100):
        captured.append({"query": query, "scope": scope, "top_k": top_k})
        return real_search(query=query, scope=scope, top_k=top_k)

    monkeypatch.setattr(app_state.lesson_store, "search", spy_search)
    r = client.get("/api/memory/lessons/active", params={"domain": "hiring"})
    assert r.status_code == 200
    assert captured, "route did not call lesson_store.search — it must be the public read API"
    assert captured[0]["scope"].domain == "hiring"


def test_active_lessons_no_domain_discovers_dream_pass_dirs(tmp_path, monkeypatch):
    """No-domain mode fans out over api/server/skills/dream-passes/. The
    fix landed in this task: previously parents[2] resolved to api/ and
    the directory never existed, silently masking discovery."""
    from pathlib import Path as _Path
    route_file = _Path("api/server/routes/memory.py").resolve()
    dream_passes_dir = route_file.parents[1] / "skills" / "dream-passes"
    assert dream_passes_dir.exists(), f"expected {dream_passes_dir} to exist on disk"
    r = client.get("/api/memory/lessons/active")
    assert r.status_code == 200
    assert "items" in r.json()
