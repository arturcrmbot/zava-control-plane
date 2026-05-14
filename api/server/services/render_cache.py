"""Sqlite cache for Azure Speech avatar render outputs, keyed on
(sha256(script + voice), avatar_id).

Cache hit = the same script for the same avatar has already been rendered and
uploaded to Blob — return the cached SAS URL instead of re-billing Azure
Speech for an identical render.

See docs/superpowers/plans/2026-04-30-avatar-real-plan.md Task 1.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path
from typing import Any


class RenderCache:
    """Single-table sqlite cache for avatar renders.

    Schema: (content_hash, avatar_id, blob_name, blob_url, rendered_at)
    Primary key: (content_hash, avatar_id) — `put` is upsert (INSERT OR REPLACE).
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS render_cache (
                    content_hash TEXT NOT NULL,
                    avatar_id    TEXT NOT NULL,
                    blob_name    TEXT NOT NULL,
                    blob_url     TEXT NOT NULL,
                    rendered_at  TEXT NOT NULL,
                    PRIMARY KEY (content_hash, avatar_id)
                )
                """
            )

    def lookup(self, *, content_hash: str, avatar_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT content_hash, avatar_id, blob_name, blob_url, rendered_at "
                "FROM render_cache WHERE content_hash = ? AND avatar_id = ?",
                (content_hash, avatar_id),
            ).fetchone()
        return dict(row) if row else None

    def put(
        self,
        *,
        content_hash: str,
        avatar_id: str,
        blob_name: str,
        blob_url: str,
    ) -> None:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO render_cache "
                "(content_hash, avatar_id, blob_name, blob_url, rendered_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (content_hash, avatar_id, blob_name, blob_url, now),
            )
            conn.commit()
