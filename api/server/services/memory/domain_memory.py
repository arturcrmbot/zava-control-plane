"""Per-domain Mem0 memory store.

Each domain (hiring, vendor_kyc, etc.) gets its own logical partition
within a shared Mem0 backend, scoped by user_id="domain:{name}".

Agents write via add(infer=True) — Mem0's LLM extracts what's worth
remembering. Agents read via recall(query) — semantic search returns
the top-K relevant memories for the current decision context.

Dream passes consolidate by reading all memories, deduplicating,
pruning stale entries, and writing back a cleaned store.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class DomainMemory:
    """Thin wrapper over mem0.Memory scoped to one domain."""

    def __init__(self, *, domain: str, memory: Any) -> None:
        self.domain = domain
        self._mem = memory
        self._user_id = f"domain:{domain}"

    def add(
        self,
        text: str,
        *,
        agent_skill: str = "",
        workflow_id: str = "",
    ) -> list[dict]:
        """Write a memory with infer=True. Mem0's LLM decides what to
        extract and store. Returns the list of created/updated memories."""
        result = self._mem.add(
            messages=text,
            user_id=self._user_id,
            metadata={
                "domain": self.domain,
                "agent_skill": agent_skill,
                "workflow_id": workflow_id,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            },
            infer=True,
        )
        return (result or {}).get("results", [])

    def recall(self, query: str, *, top_k: int = 5) -> list[dict]:
        """Semantic search for top-K relevant memories."""
        results = self._mem.search(
            query=query,
            user_id=self._user_id,
            limit=top_k,
        )
        return [
            {"id": r["id"], "memory": r.get("memory", ""), "score": r.get("score", 0.0)}
            for r in (results or {}).get("results", [])
        ]

    def list_all(self, *, limit: int = 200) -> list[dict]:
        """List all memories in this domain (for UI + dream input)."""
        results = self._mem.get_all(user_id=self._user_id, limit=limit)
        return (results or {}).get("results", [])

    def count(self) -> int:
        """Count of memories in this domain."""
        return len(self.list_all(limit=10000))

    def delete(self, memory_id: str) -> None:
        """Delete a single memory (used by dream consolidator)."""
        self._mem.delete(memory_id=memory_id)

    def update(self, memory_id: str, data: str) -> None:
        """Update a memory's content (used by dream consolidator)."""
        self._mem.update(memory_id, data)

    def delete_all(self) -> None:
        """Wipe all memories for this domain."""
        self._mem.delete_all(user_id=self._user_id)


def build_domain_memories(
    *,
    domains: list[str],
    memory: Any,
) -> dict[str, DomainMemory]:
    """Build one DomainMemory per domain sharing a single Mem0 backend."""
    return {d: DomainMemory(domain=d, memory=memory) for d in domains}
