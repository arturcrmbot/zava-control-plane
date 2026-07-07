import json
import sys
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _write_tape(tmp_path):
    d = tmp_path / "data" / "compose-recordings"
    d.mkdir(parents=True)
    p = d / "capex-approval-20260101T000000.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in [
        {"ts_offset_ms": 0, "event": {"type": "thought", "text": "hi"}},
        {"ts_offset_ms": 20, "event": {"type": "done", "workflow_type": "capex-approval", "display_name": "Capex"}},
    ]))
    return p.name


def test_list_and_replay(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAVA_REPO_ROOT", str(tmp_path))
    (tmp_path / ".poc-safety").write_text("POC_UNSAFE_FOR_PUBLIC_DEPLOY=1\n")
    name = _write_tape(tmp_path)
    
    # Clear cached imports to force fresh load
    for mod in list(sys.modules.keys()):
        if 'api.server.routes.compose' in mod:
            del sys.modules[mod]
    
    # Import router AFTER setting env vars and clearing cache
    from api.server.routes.compose import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    r = client.get("/api/compose/tapes")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    tapes = r.json()["tapes"]
    assert name in tapes

    r = client.post("/api/compose/replay", json={"tape": name, "speed": 1000})
    assert r.status_code == 200
    cid = r.json()["compose_id"]

    events = []
    with client.stream("GET", f"/api/compose/{cid}/stream") as s:
        for line in s.iter_lines():
            if line and line.startswith("data: "):
                ev = json.loads(line[6:])
                events.append(ev)
                if ev.get("type") == "stage" and ev.get("stage") == "ready":
                    break
    assert any(e["type"] == "thought" for e in events)
    assert any(e.get("type") == "done" for e in events)
