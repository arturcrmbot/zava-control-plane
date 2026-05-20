from fastapi.testclient import TestClient

from api.server.main import app

client = TestClient(app)


def test_dream_storm_runs_n_passes_per_domain():
    r = client.post(
        "/api/simulator/dream-storm",
        params={"domains": "hiring", "runs": 2, "sample": 5},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["count"] == 2
    assert len(body["passes"]) == 2
    assert all(p["domain"] == "hiring" for p in body["passes"])
    assert all("dream_pass_id" in p for p in body["passes"])


def test_dream_storm_handles_unknown_domain_gracefully():
    r = client.post(
        "/api/simulator/dream-storm",
        params={"domains": "does-not-exist", "runs": 1},
    )
    assert r.status_code == 200
    body = r.json()
    # Unknown domain produces an error row, not a 500.
    assert any("error" in p for p in body["passes"])


def test_dream_storm_multi_domain_csv():
    r = client.post(
        "/api/simulator/dream-storm",
        params={"domains": "hiring,does-not-exist", "runs": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert any(p.get("domain") == "hiring" and "dream_pass_id" in p for p in body["passes"])
    assert any(p.get("domain") == "does-not-exist" and "error" in p for p in body["passes"])
