from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from api.server.main import app
from api.server.state import app_state

client = TestClient(app)


def test_list_domains_returns_live_memory_partitions(monkeypatch):
    monkeypatch.setattr(
        app_state,
        "domain_memories",
        {"network-incident": MagicMock(), "proactive-customer-care": MagicMock()},
    )

    response = client.get("/api/memory/v2/domains")

    assert response.status_code == 200
    assert response.json() == {
        "domains": ["network-incident", "proactive-customer-care"]
    }


def test_recall_returns_memories_from_domain_store(monkeypatch):
    class FakeDM:
        domain = "hiring"

        def recall(self, query, *, top_k=5):
            return [
                {"id": "m1", "memory": "sparse CVs should still advance", "score": 0.91},
            ]

    monkeypatch.setattr(app_state, "domain_memories", {"hiring": FakeDM()})
    r = client.post(
        "/api/memory/v2/recall",
        json={"domain": "hiring", "query": "how to handle sparse CVs", "top_k": 3},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["memories"]) == 1
    assert body["memories"][0]["score"] == 0.91


def test_recall_rejects_empty_query():
    r = client.post(
        "/api/memory/v2/recall",
        json={"domain": "hiring", "query": "", "top_k": 3},
    )
    assert r.status_code == 422


def test_recall_unknown_domain_returns_empty():
    r = client.post(
        "/api/memory/v2/recall",
        json={"domain": "nonexistent", "query": "test", "top_k": 3},
    )
    assert r.status_code == 200
    assert r.json()["memories"] == []


def test_list_memories_returns_all_for_domain(monkeypatch):
    class FakeDM:
        domain = "hiring"

        def list_all(self, *, limit=200):
            return [
                {"id": "m1", "memory": "insight one"},
                {"id": "m2", "memory": "insight two"},
            ]

    monkeypatch.setattr(app_state, "domain_memories", {"hiring": FakeDM()})
    r = client.get("/api/memory/v2/memories?domain=hiring")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert len(body["memories"]) == 2


def test_trigger_dream_returns_result(monkeypatch):
    """POST /api/memory/v2/dream triggers consolidation."""

    class FakeDM:
        domain = "hiring"
        _mem = MagicMock()
        _user_id = "domain:hiring"

        def list_all(self, *, limit=500):
            return [{"id": "m1", "memory": "test insight"}]

        def delete(self, mid):
            pass

        def add_distilled(self, text, metadata=None):
            return [{"id": "m2", "memory": text, "metadata": metadata or {}}]

    monkeypatch.setattr(app_state, "domain_memories", {"hiring": FakeDM()})

    import api.server.routes.memory_v2 as mv2

    async def _fake_consolidate(texts):
        return ["consolidated: " + "; ".join(texts)]

    monkeypatch.setattr(mv2, "_build_llm_consolidator", lambda domain: _fake_consolidate)

    r = client.post("/api/memory/v2/dream", json={"domain": "hiring"})
    assert r.status_code == 200
    body = r.json()
    assert body["domain"] == "hiring"
    assert body["input_count"] == 1
    assert body["output_count"] == 1


def test_trigger_dream_unknown_domain():
    r = client.post("/api/memory/v2/dream", json={"domain": "nonexistent"})
    assert r.status_code == 200
    assert "error" in r.json()
