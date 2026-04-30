"""Sqlite-backed magic-link token store.

Single-use semantics on offer-grade scopes; repeatable read on status-grade scopes.

See docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Task 1.
"""
from __future__ import annotations

import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any


class MagicLinkExpired(Exception):
    """Raised by consume() when the token's expires_at has passed."""


class MagicLinkAlreadyConsumed(Exception):
    """Raised by consume() when a single_use token is already spent."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    token TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    issued_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    single_use INTEGER NOT NULL,
    consumed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_active ON links(expires_at, consumed_at);
"""


class MagicLinkStore:
    """Sqlite-backed token store. Tokens are 32-char url-safe strings.

    Methods:
        issue(*, candidate_id, scope, ttl_seconds, single_use=True) -> str
        consume(token, *, scope) -> dict
            Validates expiry/scope; on single_use marks consumed_at; raises
            MagicLinkExpired or MagicLinkAlreadyConsumed or ValueError.
        peek(token, *, scope) -> dict | None
            Read without mutation; returns None if not found.
        list_active() -> list[dict]
            For the admin Candidates panel fallback.
    """

    def __init__(self, db_path: str | Path):
        self._path = str(db_path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._path, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def issue(
        self,
        *,
        candidate_id: str,
        scope: str,
        ttl_seconds: int,
        single_use: bool = True,
    ) -> str:
        token = secrets.token_urlsafe(24)[:32]
        now = time.time()
        with self._conn() as c:
            c.execute(
                "INSERT INTO links (token, candidate_id, scope, issued_at,"
                " expires_at, single_use) VALUES (?,?,?,?,?,?)",
                (token, candidate_id, scope, now, now + ttl_seconds, int(single_use)),
            )
        return token

    def consume(self, token: str, *, scope: str) -> dict[str, Any]:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM links WHERE token=?", (token,)
            ).fetchone()
            if row is None:
                raise ValueError("token not found")
            if row["scope"] != scope:
                raise ValueError(
                    f"scope mismatch: token={row['scope']} requested={scope}"
                )
            if time.time() > row["expires_at"]:
                raise MagicLinkExpired(token)
            if row["single_use"] and row["consumed_at"] is not None:
                raise MagicLinkAlreadyConsumed(token)
            if row["single_use"]:
                c.execute(
                    "UPDATE links SET consumed_at=? WHERE token=?",
                    (time.time(), token),
                )
            return {"candidate_id": row["candidate_id"], "scope": row["scope"]}

    def peek(self, token: str, *, scope: str) -> dict[str, Any] | None:
        """Read a token's payload without mutating consumed_at.

        Returns None when the token does not exist. Raises ValueError on scope
        mismatch and MagicLinkExpired when past expiry, mirroring consume's
        validation semantics minus the single-use bookkeeping.
        """
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM links WHERE token=?", (token,)
            ).fetchone()
            if row is None:
                return None
            if row["scope"] != scope:
                raise ValueError(
                    f"scope mismatch: token={row['scope']} requested={scope}"
                )
            if time.time() > row["expires_at"]:
                raise MagicLinkExpired(token)
            return {
                "candidate_id": row["candidate_id"],
                "scope": row["scope"],
                "single_use": bool(row["single_use"]),
                "consumed_at": row["consumed_at"],
                "expires_at": row["expires_at"],
                "issued_at": row["issued_at"],
            }

    def list_active(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            now = time.time()
            rows = c.execute(
                "SELECT token, candidate_id, scope, issued_at, expires_at"
                " FROM links WHERE expires_at > ? AND consumed_at IS NULL"
                " ORDER BY issued_at DESC",
                (now,),
            ).fetchall()
            return [dict(r) for r in rows]
