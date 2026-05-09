"""Sqlite-backed per-function KPI snapshot store — Phase 4 IP2 (TASK-008).

One table ``kpi_snapshot`` carrying ``(function, metric, period, value,
schema_version, captured_at)``. Composite index on
``(function, metric, period)`` keeps the per-function FM panel query
fast. Schema versioning per row (DEC-OQ3) — readers tolerate the union
of versions and project missing keys as null at the aggregation layer.

Mirrors :class:`api.server.services.magic_link.MagicLinkStore` in style.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS kpi_snapshot (
    function TEXT NOT NULL,
    metric TEXT NOT NULL,
    period TEXT NOT NULL,
    value REAL NOT NULL,
    schema_version INTEGER NOT NULL,
    captured_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kpi_snapshot_fn_metric_period
    ON kpi_snapshot(function, metric, period);
"""


class KpiStore:
    """Append-only KPI snapshot ledger.

    ``publish`` writes one row per ``(function, metric, period)``
    capture; multiple captures for the same key accumulate (the latest
    is selected by ``captured_at`` at read time when callers want a
    point-in-time view).
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def publish(
        self,
        function: str,
        metric: str,
        value: float,
        period: str,
        schema_version: int = 1,
    ) -> None:
        """Append one snapshot row."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO kpi_snapshot "
                "(function, metric, period, value, schema_version, captured_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (function, metric, period, float(value), int(schema_version), time.time()),
            )
            conn.commit()

    def query(
        self,
        function: str | None = None,
        metric: str | None = None,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return matching rows. ``since`` filters by ``period >= since``
        (ISO-comparable strings — daily ``YYYY-MM-DD``, monthly
        ``YYYY-MM``, quarterly ``YYYY-Qn``)."""
        clauses: list[str] = []
        params: list[Any] = []
        if function is not None:
            clauses.append("function = ?")
            params.append(function)
        if metric is not None:
            clauses.append("metric = ?")
            params.append(metric)
        if since is not None:
            clauses.append("period >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            "SELECT function, metric, period, value, schema_version, captured_at "
            f"FROM kpi_snapshot {where} "
            "ORDER BY captured_at ASC"
        )
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
