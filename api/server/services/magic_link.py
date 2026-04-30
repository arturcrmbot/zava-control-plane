"""Sqlite-backed magic-link token store. Skeleton — implemented by Stream 1
candidate-portal subagent (see docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Task 1).

Single-use semantics on offer-grade scopes; repeatable read on status-grade scopes.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any


class MagicLinkExpired(Exception):
    """Raised by consume() when the token's expires_at has passed."""


class MagicLinkAlreadyConsumed(Exception):
    """Raised by consume() when a single_use token is already spent."""


class MagicLinkStore:
    """Skeleton — see plan Task 1 for the implementation contract.

    Methods to implement:
        issue(*, candidate_id, scope, ttl_seconds, single_use=True) -> str
        consume(token, *, scope) -> dict[str, Any]
        peek(token, *, scope) -> dict[str, Any] | None    # read without consuming
        list_active() -> list[dict[str, Any]]
    """

    def __init__(self, db_path: str | Path):
        self._path = str(db_path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)

    def issue(self, *, candidate_id: str, scope: str, ttl_seconds: int, single_use: bool = True) -> str:
        raise NotImplementedError("Stream 1 subagent: implement per plan Task 1")

    def consume(self, token: str, *, scope: str) -> dict[str, Any]:
        raise NotImplementedError("Stream 1 subagent: implement per plan Task 1")

    def peek(self, token: str, *, scope: str) -> dict[str, Any] | None:
        raise NotImplementedError("Stream 1 subagent: implement per plan Task 1")

    def list_active(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Stream 1 subagent: implement per plan Task 1")
