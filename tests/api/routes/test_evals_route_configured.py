"""When configured, /api/evals/summary excludes errored rows from averages."""
from __future__ import annotations
import time

from fastapi.testclient import TestClient


def _client_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://e")
    monkeypatch.setenv("AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT", "gpt-4o")
    import sys
    sys.modules.pop("api.server.eval.foundry_client", None)
    sys.modules.pop("api.server.eval.store", None)
    sys.modules.pop("api.server.eval.online_subscriber", None)
    sys.modules.pop("api.server.routes.evals", None)
    from api.server.eval.store import EvalStore, EvalRow
    store = EvalStore(db_path=str(tmp_path / "s.sqlite"))
    monkeypatch.setattr("api.server.eval.store._default", store, raising=False)
    monkeypatch.setattr("api.server.routes.evals._store", store, raising=False)
    base_ts = time.time()
    r1 = EvalRow(id="ev-1", kind="online", agent_label="rag-classifier",
                 workflow_id="wf-1", agent_run_id="ar-1", ts=base_ts)
    r2 = EvalRow(id="ev-2", kind="online", agent_label="rag-classifier",
                 workflow_id="wf-2", agent_run_id="ar-2", ts=base_ts)
    r3 = EvalRow(id="ev-3", kind="online", agent_label="rag-classifier",
                 workflow_id="wf-3", agent_run_id="ar-3", ts=base_ts)
    store.put_pending(r1); store.put_pending(r2); store.put_pending(r3)
    store.complete("ev-1", scores={"groundedness": 0.9}, foundry_run_url=None)
    store.complete("ev-2", scores={"groundedness": 0.7}, foundry_run_url=None)
    store.error("ev-3", error_text="boom")

    from api.server.main import app
    return TestClient(app)


def test_summary_excludes_errored_from_averages(monkeypatch, tmp_path):
    c = _client_configured(monkeypatch, tmp_path)
    r = c.get("/api/evals/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is True
    assert body["n_completed"] == 2
    assert body["n_errored"] == 1
    rag = body["per_agent"]["rag-classifier"] if "per_agent" in body else None
    if rag is None:
        # The plan's response shape: by_agent list, not per_agent dict
        by_agent = {x["agent_label"]: x for x in body["by_agent"]}
        rag = by_agent["rag-classifier"]
    assert abs(rag["scores"]["groundedness"] - 0.8) < 1e-9
