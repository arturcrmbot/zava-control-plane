from fastapi.testclient import TestClient

from api.server.main import app

client = TestClient(app)


def test_run_endpoint_returns_pass_summary():
    r = client.post("/api/dream-pass/run", params={"domain": "hiring", "sample": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["domain"] == "hiring"
    assert "dream_pass_id" in body
    assert body["experiments_run"] >= 0
    assert set(body["verdict_counts"].keys()) == {"promoted", "rejected", "flagged"}
    # `flagged` key is kept at 0 for one cycle of back-compat after the
    # flagged→reject collapse (see dream_pass orchestrator change-log).
    assert body["verdict_counts"]["flagged"] == 0
    assert body["flagged_lesson_ids"] == []
    assert isinstance(body["promoted_lesson_ids"], list)
    assert isinstance(body["rejected_lesson_ids"], list)
    assert isinstance(body["experiments"], list)


def test_run_endpoint_rejects_unknown_domain():
    r = client.post("/api/dream-pass/run", params={"domain": "does-not-exist"})
    assert r.status_code == 422
