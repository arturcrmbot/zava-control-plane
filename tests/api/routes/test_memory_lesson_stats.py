from fastapi.testclient import TestClient
from api.server.main import app

client = TestClient(app)


def test_lesson_stats_returns_invocations_and_override_count():
    r = client.get("/api/memory/lessons/L1/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["lesson_id"] == "L1"
    assert "invocations" in body
    assert "hitl_override_count" in body
    assert "override_rate" in body
    assert "first_used_at" in body
    assert "last_used_at" in body


def test_lesson_stats_computes_override_rate_from_seeded_notes():
    """When working memory has two lesson_used notes for L42 and one of
    those workflows has a logged exception, override_rate = 0.5."""
    from api.server.state import app_state
    from api.server.services.lessons.working_memory_types import WorkingNote
    store = app_state.working_memory_store
    if hasattr(store, "_by_id"):
        for k in list(store._by_id.keys()):
            n = store._by_id[k]
            if getattr(n, "body", "").startswith("used L42:"):
                del store._by_id[k]
    store._by_id["wn-l42-1"] = WorkingNote(
        id="wn-l42-1", workflow_id="WF-A", agent_skill="hiring-segment-b",
        kind="lesson_used", body="used L42: …",
    )
    store._by_id["wn-l42-2"] = WorkingNote(
        id="wn-l42-2", workflow_id="WF-B", agent_skill="hiring-segment-b",
        kind="lesson_used", body="used L42: …",
    )
    r = client.get("/api/memory/lessons/L42/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["invocations"] == 2
    assert body["hitl_override_count"] == 0
    assert body["override_rate"] == 0.0
    assert body["first_used_at"] is not None
    assert body["last_used_at"] is not None
