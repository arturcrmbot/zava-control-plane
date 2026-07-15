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

from api.server.services.replay.mutation_bus import emit_mutation

_DEFAULT_MEMORY_DOMAINS = ("hiring",)
_TELCO_MEMORY_DOMAINS = (
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
)


def configured_memory_domains(
    *,
    raw: str | None,
    vertical_name: str | None,
    registered_workflow_types: tuple[str, ...],
) -> list[str]:
    """Resolve memory partitions without changing default-off behavior."""
    if raw is not None:
        return [item.strip() for item in raw.split(",") if item.strip()]
    if vertical_name == "telco":
        registered = set(registered_workflow_types)
        return [name for name in _TELCO_MEMORY_DOMAINS if name in registered]
    return list(_DEFAULT_MEMORY_DOMAINS)


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
        kind: str = "working",
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[dict]:
        """Write a memory directly (infer=False). The raw agent output
        is stored as-is; the dream consolidation pass is responsible for
        deduplication, pruning, and crystallisation.

        We use infer=False because Mem0's built-in inference rejects raw
        agent log lines as 'no facts found'. Our dream pass handles the
        intelligence layer instead.

        ``kind`` defaults to ``"working"`` so the UI / consolidator can
        distinguish raw working notes from already-distilled lessons.
        """
        metadata = {
            "domain": self.domain,
            "agent_skill": agent_skill,
            "workflow_id": workflow_id,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
        }
        if extra_metadata:
            metadata.update(extra_metadata)
        result = self._mem.add(
            messages=text,
            user_id=self._user_id,
            metadata=metadata,
            infer=False,
        )
        results = (result or {}).get("results", [])
        mutation_kind = "lesson" if kind == "lesson" else "memory"
        for entry in results:
            emit_mutation(
                op="upsert",
                kind=mutation_kind,
                id=entry["id"],
                patch={
                    "domain": self.domain,
                    "text": text,
                    "metadata": metadata,
                    "kind": kind,
                    "agent_skill": agent_skill,
                    "workflow_id": workflow_id,
                },
            )
        return results

    def add_distilled(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[dict]:
        """Write a pre-distilled memory with infer=False."""
        merged = {
            **(metadata or {}),
            "domain": self.domain,
            "kind": "lesson",
        }
        result = self._mem.add(
            messages=text,
            user_id=self._user_id,
            metadata=merged,
            infer=False,
        )
        results = (result or {}).get("results", [])
        for entry in results:
            emit_mutation(
                op="upsert",
                kind="lesson",
                id=entry["id"],
                patch={
                    "domain": self.domain,
                    "text": text,
                    "metadata": merged,
                    "kind": "lesson",
                },
            )
        return results

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

    def list_by_kind(self, kind: str, *, limit: int = 200) -> list[dict]:
        """Filter by metadata.kind — 'working' vs 'lesson'."""
        out: list[dict] = []
        for r in self.list_all(limit=limit):
            md = r.get("metadata") or {}
            if md.get("kind") == kind:
                out.append(r)
        return out

    def count(self) -> int:
        """Count of memories in this domain."""
        return len(self.list_all(limit=10000))

    def count_working(self) -> int:
        """Count of un-distilled working memories — the cadence-loop signal."""
        return len(self.list_by_kind("working", limit=10000))

    def delete(self, memory_id: str) -> None:
        """Delete a single memory (used by dream consolidator)."""
        self._mem.delete(memory_id=memory_id)
        emit_mutation(
            op="delete",
            kind="memory",
            id=memory_id,
            patch={"domain": self.domain},
        )

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
