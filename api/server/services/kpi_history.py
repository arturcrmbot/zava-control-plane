"""Durable KPI history series (pitch-j1).

A SQLite-backed rolling time-series store for agency KPIs and per-persona
load metrics. Replaces the persistence backing of
``api.server.services.kpi_trend_buffer`` (which remains the in-memory
fast-path for slope computations).

Schema is intentionally minimal: one row per ``(timestamp, kpi, value, dim)``
sample. ``dim`` is a free-form namespace (empty string for un-dimensioned
KPIs, role name for ``persona_*`` series, workflow_type for the
decision-latency series, etc).

24h retention. ``cleanup_old()`` is invoked opportunistically from
``record()`` so the recorder does not need a separate sweep loop.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Default lives under repo-root ``data/`` (gitignored). Override for tests.
_DEFAULT_DB_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "kpi_history.sqlite"
)
_DB_PATH: Path = Path(os.environ.get("KPI_HISTORY_DB", _DEFAULT_DB_PATH))

_RETENTION = 60 * 60 * 24  # 24 hours

_lock = threading.Lock()
_initialised = False
# How often to opportunistically GC. Guarded so we don't DELETE on every record.
_LAST_CLEANUP_TS = 0.0
_CLEANUP_INTERVAL = 300.0  # 5 minutes


def set_db_path(path: str | Path) -> None:
    """Repoint the backing SQLite file. Used by tests to isolate state."""
    global _DB_PATH, _initialised, _LAST_CLEANUP_TS
    with _lock:
        _DB_PATH = Path(path)
        _initialised = False
        _LAST_CLEANUP_TS = 0.0


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    """Create the ``kpi_history`` table + indexes if missing.

    Idempotent. Safe to call from multiple threads."""
    global _initialised
    with _lock:
        if _initialised and _DB_PATH.exists():
            return
        with _connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kpi_history (
                    ts REAL NOT NULL,
                    kpi TEXT NOT NULL,
                    value REAL NOT NULL,
                    dim TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_kpi_history_kpi_dim_ts "
                "ON kpi_history (kpi, dim, ts)"
            )
        _initialised = True


def record(kpi: str, value: float, *, dim: str = "") -> None:
    """Append a fresh ``(now, value)`` sample.

    ``value`` is coerced to ``float`` (non-numeric raises ``TypeError``).
    Opportunistically GCs rows older than the retention window.
    """
    init()
    v = float(value)
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO kpi_history (ts, kpi, value, dim) VALUES (?, ?, ?, ?)",
            (now, str(kpi), v, str(dim or "")),
        )
    _maybe_cleanup(now)


def _maybe_cleanup(now: float) -> None:
    global _LAST_CLEANUP_TS
    if now - _LAST_CLEANUP_TS < _CLEANUP_INTERVAL:
        return
    _LAST_CLEANUP_TS = now
    try:
        cleanup_old()
    except Exception:  # pragma: no cover — defensive
        pass


def series(
    kpi: str, *, since_seconds: int = 3600, dim: str = ""
) -> list[tuple[float, float]]:
    """Return ``[(ts, value), ...]`` for ``kpi`` (and ``dim``) within window."""
    init()
    cutoff = time.time() - float(since_seconds)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ts, value FROM kpi_history "
            "WHERE kpi = ? AND dim = ? AND ts >= ? ORDER BY ts ASC",
            (str(kpi), str(dim or ""), cutoff),
        ).fetchall()
    return [(float(t), float(v)) for t, v in rows]


def latest(kpi: str, *, dim: str = "") -> tuple[float, float] | None:
    """Return ``(ts, value)`` of the most recent sample, or ``None``."""
    init()
    with _connect() as conn:
        row = conn.execute(
            "SELECT ts, value FROM kpi_history "
            "WHERE kpi = ? AND dim = ? ORDER BY ts DESC LIMIT 1",
            (str(kpi), str(dim or "")),
        ).fetchone()
    if row is None:
        return None
    return (float(row[0]), float(row[1]))


def cleanup_old() -> None:
    """Delete rows older than ``_RETENTION`` seconds."""
    init()
    cutoff = time.time() - _RETENTION
    with _connect() as conn:
        conn.execute("DELETE FROM kpi_history WHERE ts < ?", (cutoff,))


def _reset_for_tests() -> None:
    """Test-only: drop all rows from the current DB (keeping schema)."""
    global _LAST_CLEANUP_TS
    init()
    with _connect() as conn:
        conn.execute("DELETE FROM kpi_history")
    _LAST_CLEANUP_TS = 0.0
