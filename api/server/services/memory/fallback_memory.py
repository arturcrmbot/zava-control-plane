"""Fallback in-memory backend for `DomainMemory` when Mem0 isn't wired.

Mirrors the slice of the Mem0 surface that `DomainMemory` actually
calls: `add`, `search`, `get_all`, `delete`, `update`, `delete_all`.
Stores entries in a per-`user_id` list with ULID-style ids and a naive
keyword scoring fn for `search`.

This exists so the dream-pass demo works on a laptop without any Azure
OpenAI / Chroma credentials. Production deploys still get real Mem0 via
``build_default_memory``; this is the fallback when that raises.
"""
from __future__ import annotations

import re
import threading
import uuid
from collections import defaultdict
from typing import Any


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if t}


class FallbackMemory:
    """Process-local stand-in for `mem0.Memory` with the methods we use.

    Thread-safe via a single lock. Entries are dicts:
      {"id": str, "memory": str, "metadata": dict, "user_id": str}
    """

    def __init__(self) -> None:
        self._by_user: dict[str, list[dict]] = defaultdict(list)
        self._lock = threading.Lock()

    def add(
        self,
        *,
        messages: str,
        user_id: str,
        metadata: dict | None = None,
        infer: bool = False,  # noqa: ARG002 — accepted for parity, ignored
    ) -> dict[str, Any]:
        text = (messages or "").strip()
        if not text:
            return {"results": []}
        entry = {
            "id": uuid.uuid4().hex,
            "memory": text,
            "metadata": dict(metadata or {}),
            "user_id": user_id,
        }
        with self._lock:
            self._by_user[user_id].append(entry)
        return {"results": [entry]}

    def get_all(self, *, user_id: str, limit: int = 200) -> dict[str, Any]:
        with self._lock:
            items = list(self._by_user.get(user_id, []))[-limit:]
        return {"results": items}

    def search(
        self,
        *,
        query: str,
        user_id: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        qtoks = _tokens(query)
        if not qtoks:
            return {"results": []}
        scored: list[tuple[float, dict]] = []
        with self._lock:
            items = list(self._by_user.get(user_id, []))
        for it in items:
            mtoks = _tokens(it["memory"])
            if not mtoks:
                continue
            overlap = len(qtoks & mtoks)
            if overlap == 0:
                continue
            score = overlap / max(1, len(qtoks | mtoks))
            scored.append((score, it))
        scored.sort(key=lambda p: p[0], reverse=True)
        out = [
            {"id": it["id"], "memory": it["memory"], "score": score}
            for score, it in scored[:limit]
        ]
        return {"results": out}

    def delete(self, *, memory_id: str) -> None:
        with self._lock:
            for uid, items in self._by_user.items():
                self._by_user[uid] = [i for i in items if i["id"] != memory_id]

    def update(self, memory_id: str, data: str) -> None:
        with self._lock:
            for items in self._by_user.values():
                for it in items:
                    if it["id"] == memory_id:
                        it["memory"] = data
                        return

    def delete_all(self, *, user_id: str) -> None:
        with self._lock:
            self._by_user[user_id] = []


_singleton: FallbackMemory | None = None


def get_fallback_memory() -> FallbackMemory:
    """Process-wide singleton so all DomainMemory instances share state."""
    global _singleton
    if _singleton is None:
        _singleton = FallbackMemory()
    return _singleton
