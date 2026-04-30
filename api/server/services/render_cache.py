"""Sqlite cache for HeyGen render outputs, keyed on (sha256(script), avatar_id).

Skeleton — implemented by Stream 3 HeyGen-real subagent (see
docs/superpowers/plans/2026-04-30-heygen-real-plan.md Task 1).
"""
from __future__ import annotations
from pathlib import Path
from typing import Any


class RenderCache:
    """Skeleton — see plan Task 1 for the implementation contract.

    Methods to implement:
        lookup(*, content_hash, avatar_id) -> dict[str, Any] | None
        put(*, content_hash, avatar_id, blob_name, blob_url) -> None
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)

    def lookup(self, *, content_hash: str, avatar_id: str) -> dict[str, Any] | None:
        raise NotImplementedError("Stream 3 subagent: implement per plan Task 1")

    def put(self, *, content_hash: str, avatar_id: str, blob_name: str, blob_url: str) -> None:
        raise NotImplementedError("Stream 3 subagent: implement per plan Task 1")
