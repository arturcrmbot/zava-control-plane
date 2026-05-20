from fastapi.testclient import TestClient
from api.server.main import app

client = TestClient(app)


def test_pause_then_unpause_round_trip():
    # Start clean
    client.delete("/api/dream-pass/pause", params={"domain": "hiring"})

    r1 = client.post("/api/dream-pass/pause", params={"domain": "hiring"})
    assert r1.status_code == 200
    assert r1.json() == {"ok": True, "paused": ["hiring"]}

    r2 = client.get("/api/dream-pass/pause")
    assert r2.status_code == 200
    assert "hiring" in r2.json()["paused"]

    r3 = client.delete("/api/dream-pass/pause", params={"domain": "hiring"})
    assert r3.status_code == 200
    assert "hiring" not in r3.json()["paused"]


def test_run_endpoint_refuses_when_paused():
    client.post("/api/dream-pass/pause", params={"domain": "hiring"})
    try:
        r = client.post("/api/dream-pass/run", params={"domain": "hiring"})
        assert r.status_code == 423
        assert "paused" in r.json()["detail"].lower()
    finally:
        client.delete("/api/dream-pass/pause", params={"domain": "hiring"})
