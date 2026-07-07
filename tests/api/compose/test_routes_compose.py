import sys
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.server.routes.compose import router, set_copilot_cmd_for_tests


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def test_create_session_and_stream(monkeypatch):
    monkeypatch.setenv("FAKE_ACP_TRACE", "tests/api/compose/fixtures/basic_trace.jsonl")
    set_copilot_cmd_for_tests([sys.executable, "tests/api/compose/fake_acp_agent.py"])
    client = TestClient(_app())

    r = client.post("/api/compose/session", data={"text": "A capex approval process."})
    assert r.status_code == 200
    cid = r.json()["compose_id"]
    assert cid

    # Consume the SSE stream to the terminal 'ready' stage.
    events = []
    with client.stream("GET", f"/api/compose/{cid}/stream") as s:
        for line in s.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            ev = json.loads(line[len("data: "):])
            events.append(ev)
            if ev.get("type") == "stage" and ev.get("stage") == "ready":
                break

    types = {e["type"] for e in events}
    assert {"thought", "tool", "narration"} <= types


def test_stream_unknown_session_404():
    client = TestClient(_app())
    assert client.get("/api/compose/nope/stream").status_code == 404


def test_non_loopback_forbidden(monkeypatch):
    set_copilot_cmd_for_tests([sys.executable, "tests/api/compose/fake_acp_agent.py"])
    client = TestClient(_app())
    r = client.post("/api/compose/session", data={"text": "x"},
                    headers={"x-forwarded-for": "8.8.8.8"})
    assert r.status_code == 403
