"""Sqlite-backed eval store. One row per Foundry-scored eval; one row per
batch corpus run. Single-process; FastAPI uses one worker locally so no
concurrency story beyond `check_same_thread=False`.

The store is the system of record for online evals (Foundry portal does
NOT have per-row entries for online — see spec §4.1).
"""
from __future__ import annotations
import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from api.shared.vertical_pack import VerticalRuntime


def default_db_path(runtime: "VerticalRuntime | None" = None) -> Path:
    if runtime is None:
        from api.shared.vertical_loader import active_runtime

        runtime = active_runtime()
    return runtime.data_dir / "eval" / "store.sqlite"


@dataclass
class EvalRow:
    id: str
    kind: str  # "online" | "batch"
    agent_label: str
    workflow_id: str | None
    agent_run_id: str | None
    ts: float
    scores_json: dict[str, Any] | None = None
    foundry_run_url: str | None = None
    status: str = "pending"
    error_text: str | None = None
    prompt: str = ""
    response_text: str = ""
    context: str = ""
    tool_calls: list[dict] = field(default_factory=list)


class EvalStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        resolved_path = Path(db_path) if db_path is not None else default_db_path()
        self._db_path = str(resolved_path)
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS evals (
                    id              TEXT PRIMARY KEY,
                    kind            TEXT NOT NULL,
                    agent_label     TEXT NOT NULL,
                    workflow_id     TEXT,
                    agent_run_id    TEXT,
                    ts              REAL NOT NULL,
                    scores_json     TEXT,
                    foundry_run_url TEXT,
                    status          TEXT NOT NULL,
                    error_text      TEXT,
                    prompt          TEXT,
                    response_text   TEXT,
                    context         TEXT,
                    tool_calls_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_evals_ts ON evals(ts DESC);
                CREATE INDEX IF NOT EXISTS idx_evals_workflow ON evals(workflow_id);
                CREATE INDEX IF NOT EXISTS idx_evals_agent ON evals(agent_label);

                CREATE TABLE IF NOT EXISTS batch_runs (
                    run_id    TEXT PRIMARY KEY,
                    ts        REAL NOT NULL,
                    report_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_batch_runs_ts ON batch_runs(ts DESC);
            """)

    # ---- write -----------------------------------------------------------

    def put_pending(self, row: EvalRow) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT OR REPLACE INTO evals
                   (id, kind, agent_label, workflow_id, agent_run_id, ts,
                    scores_json, foundry_run_url, status, error_text,
                    prompt, response_text, context, tool_calls_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row.id, row.kind, row.agent_label, row.workflow_id,
                    row.agent_run_id, row.ts,
                    json.dumps(row.scores_json) if row.scores_json else None,
                    row.foundry_run_url,
                    row.status, row.error_text,
                    row.prompt, row.response_text, row.context,
                    json.dumps(row.tool_calls or []),
                ),
            )

    def complete(self, row_id: str, *, scores: dict[str, Any], foundry_run_url: str | None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """UPDATE evals SET status='completed',
                   scores_json=?, foundry_run_url=?
                   WHERE id=?""",
                (json.dumps(scores), foundry_run_url, row_id),
            )

    def error(self, row_id: str, *, error_text: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE evals SET status='error', error_text=? WHERE id=?",
                (error_text, row_id),
            )

    def drop_oldest_pending(self) -> str | None:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT id FROM evals WHERE status='pending' ORDER BY ts ASC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            self._conn.execute("DELETE FROM evals WHERE id=?", (row["id"],))
            return row["id"]

    def put_batch(self, run_id: str, report: dict[str, Any]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO batch_runs (run_id, ts, report_json) VALUES (?, ?, ?)",
                (run_id, time.time(), json.dumps(report)),
            )

    # ---- read ------------------------------------------------------------

    def by_id(self, row_id: str) -> EvalRow | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM evals WHERE id=?", (row_id,)).fetchone()
        return _row_to_evalrow(r) if r else None

    def recent(self, n: int, agent_label: str | None = None) -> list[EvalRow]:
        sql = "SELECT * FROM evals"
        params: list[Any] = []
        if agent_label:
            sql += " WHERE agent_label=?"
            params.append(agent_label)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(n)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_evalrow(r) for r in rows]

    def by_workflow(self, workflow_id: str) -> list[EvalRow]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM evals WHERE workflow_id=? ORDER BY ts ASC",
                (workflow_id,),
            ).fetchall()
        return [_row_to_evalrow(r) for r in rows]

    def summary(self, window_minutes: int = 60) -> dict[str, Any]:
        cutoff = time.time() - window_minutes * 60
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM evals WHERE ts >= ? ORDER BY ts DESC",
                (cutoff,),
            ).fetchall()

        completed = [r for r in rows if r["status"] == "completed"]
        errored = [r for r in rows if r["status"] == "error"]

        per_agent: dict[str, dict[str, Any]] = {}
        for r in completed:
            label = r["agent_label"]
            scores = json.loads(r["scores_json"] or "{}")
            agent_bucket = per_agent.setdefault(label, {"n": 0, "_sums": {}, "scores": {}})
            agent_bucket["n"] += 1
            for name, value in scores.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    sums = agent_bucket["_sums"]
                    sums[name] = sums.get(name, 0.0) + float(value)

        for label, bucket in per_agent.items():
            n = bucket["n"]
            for name, total in bucket["_sums"].items():
                bucket["scores"][name] = total / n if n else 0.0
            del bucket["_sums"]

        return {
            "window_minutes": window_minutes,
            "n_completed": len(completed),
            "n_errored": len(errored),
            "per_agent": per_agent,
        }

    def last_batch_run(self) -> dict[str, Any] | None:
        with self._lock:
            r = self._conn.execute(
                "SELECT report_json FROM batch_runs ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        return json.loads(r["report_json"]) if r else None

    def health(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT status, COUNT(*) AS c FROM evals GROUP BY status"
            ).fetchall()
        out = {"pending": 0, "completed": 0, "error": 0}
        for r in rows:
            out[r["status"]] = r["c"]
        return out


def _row_to_evalrow(r: sqlite3.Row) -> EvalRow:
    return EvalRow(
        id=r["id"],
        kind=r["kind"],
        agent_label=r["agent_label"],
        workflow_id=r["workflow_id"],
        agent_run_id=r["agent_run_id"],
        ts=r["ts"],
        scores_json=json.loads(r["scores_json"]) if r["scores_json"] else None,
        foundry_run_url=r["foundry_run_url"],
        status=r["status"],
        error_text=r["error_text"],
        prompt=r["prompt"] or "",
        response_text=r["response_text"] or "",
        context=r["context"] or "",
        tool_calls=json.loads(r["tool_calls_json"] or "[]"),
    )


_default: EvalStore | None = None


def default_store() -> EvalStore:
    global _default
    if _default is None:
        _default = EvalStore()
    return _default
