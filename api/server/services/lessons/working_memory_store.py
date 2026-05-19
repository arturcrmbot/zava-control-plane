"""Working memory tier.

Per-workflow_id scratchpad written by agents during a run; consumed by
the dream pass between runs. Mem0-backed for production, in-memory for
tests. Like LessonStore, this is storage only — governance and ledger
writes live in WorkingMemoryGovernor (Task 13).
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any, Protocol

from api.server.services.lessons.working_memory_types import WorkingNote


def _user_id_for(workflow_id: str) -> str:
    return f"working-memory:{workflow_id}"


class WorkingMemoryStore(Protocol):
    def add(self, note: WorkingNote) -> None: ...
    def list_for_workflow(self, *, workflow_id: str) -> list[WorkingNote]: ...
    def list_recent_unconsumed(
        self, *, domain_agents: tuple[str, ...], limit: int = 200
    ) -> list[WorkingNote]: ...
    def mark_consumed(self, *, note_id: str, dream_pass_id: str) -> None: ...


class InMemoryWorkingMemoryStore:
    def __init__(self) -> None:
        self._by_id: dict[str, WorkingNote] = {}

    def add(self, note: WorkingNote) -> None:
        self._by_id[note.id] = note

    def list_for_workflow(self, *, workflow_id: str) -> list[WorkingNote]:
        return [
            n for n in self._by_id.values()
            if n.workflow_id == workflow_id and n.consumed_by_dream_pass is None
        ]

    def list_recent_unconsumed(
        self, *, domain_agents: tuple[str, ...], limit: int = 200
    ) -> list[WorkingNote]:
        out = [
            n for n in self._by_id.values()
            if n.consumed_by_dream_pass is None and n.agent_skill in domain_agents
        ]
        out.sort(key=lambda n: n.captured_at, reverse=True)
        return out[:limit]

    def mark_consumed(self, *, note_id: str, dream_pass_id: str) -> None:
        existing = self._by_id.get(note_id)
        if existing is None:
            return
        self._by_id[note_id] = existing.mark_consumed(dream_pass_id=dream_pass_id)


class _MemoryLike(Protocol):
    def add(
        self,
        messages: str,
        *,
        user_id: str,
        metadata: dict[str, Any],
        infer: bool = ...,
    ) -> Any: ...
    def get_all(
        self,
        *,
        user_id: str | None = ...,
        filters: dict[str, Any] | None = ...,
        limit: int = ...,
    ) -> Any: ...
    def delete(self, *, memory_id: str) -> Any: ...


class Mem0WorkingMemoryStore:
    """Mem0-backed working memory.

    Working memory is ephemeral by design: once the dream pass has
    consumed a note, we delete it rather than just flagging it. That
    keeps the qdrant collection from growing unboundedly and avoids
    the limitation that mem0.Memory.update() only accepts new body
    text, not metadata.
    """

    def __init__(self, *, memory: _MemoryLike | None = None) -> None:
        if memory is None:
            from mem0 import Memory
            memory = Memory()
        self._memory = memory

    def add(self, note: WorkingNote) -> None:
        self._memory.add(
            messages=note.body,
            user_id=_user_id_for(note.workflow_id),
            metadata=_serialise_note(note),
            infer=False,
        )

    def list_for_workflow(self, *, workflow_id: str) -> list[WorkingNote]:
        results = self._memory.get_all(
            user_id=_user_id_for(workflow_id),
            limit=200,
        )
        return [
            n for n in self._iter_notes(results)
            if n.consumed_by_dream_pass is None
        ]

    def list_recent_unconsumed(
        self, *, domain_agents: tuple[str, ...], limit: int = 200
    ) -> list[WorkingNote]:
        # mem0 doesn't natively cross user_ids in one call. We rely on
        # the metadata filter — every note carries `agent_skill` — and
        # let the caller pass the agents it cares about. The InMemory
        # impl above demonstrates the intended semantics.
        results = self._memory.get_all(
            filters={"agent_skill": list(domain_agents)},
            limit=limit,
        )
        notes = [n for n in self._iter_notes(results) if n.consumed_by_dream_pass is None]
        notes.sort(key=lambda n: n.captured_at, reverse=True)
        return notes[:limit]

    def mark_consumed(self, *, note_id: str, dream_pass_id: str) -> None:
        del dream_pass_id
        self._memory.delete(memory_id=note_id)

    def _iter_notes(self, results: Any):
        # mem0.get_all returns either {"results": [...]} or [...]
        if isinstance(results, dict):
            results = results.get("results", [])
        for r in results or []:
            metadata = r.get("metadata") or {}
            note = _deserialise_note(metadata)
            if note is not None:
                yield note


def _serialise_note(note: WorkingNote) -> dict[str, Any]:
    payload = asdict(note)
    payload["captured_at"] = note.captured_at.isoformat()
    return {
        "note_id": note.id,
        "workflow_id": note.workflow_id,
        "agent_skill": note.agent_skill,
        "kind": note.kind,
        "captured_at": payload["captured_at"],
        "consumed_by_dream_pass": note.consumed_by_dream_pass or "",
        "note_json": json.dumps(payload),
    }


def _deserialise_note(metadata: dict[str, Any]) -> WorkingNote | None:
    raw_json = metadata.get("note_json")
    if not raw_json:
        return None
    try:
        raw = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    return WorkingNote(
        id=raw["id"],
        workflow_id=raw["workflow_id"],
        agent_skill=raw["agent_skill"],
        kind=raw["kind"],
        body=raw["body"],
        captured_at=datetime.fromisoformat(raw["captured_at"]),
        consumed_by_dream_pass=(raw.get("consumed_by_dream_pass") or None),
    )
