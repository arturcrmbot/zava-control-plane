from __future__ import annotations

from typing import Any

from api.server.services.replay.mutation_bus import get_active_bus, set_active_bus
from api.server.services.replay.tape_loader import TapeLoader
from api.server.state import app_state
from api.shared.types import Exception_, Phase, Workflow


def hydrate_from_snapshot(loader: TapeLoader) -> None:
    """Replace in-process state with the loader's snapshot contents."""
    prev_bus = get_active_bus()
    set_active_bus(None)
    try:
        snapshot = loader.snapshot
        _clear_state_store(app_state.store)
        _hydrate_workflows(app_state.store, _snapshot_items(snapshot.get("workflows.json")))
        _hydrate_phases(app_state.store, snapshot.get("phases.json") or {})
        _hydrate_exceptions(app_state.store, _snapshot_items(snapshot.get("exceptions.json")))
        _hydrate_memories(
            app_state.domain_memories,
            _snapshot_items(snapshot.get("memories.json")),
            _snapshot_items(snapshot.get("lessons.json")),
        )
        # KPI/entity graph/personae/functions payloads are intentionally skipped:
        # those stores are external or code-baked and not part of Task 3.2 hydration.
    finally:
        set_active_bus(prev_bus)


def _snapshot_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return items
    return []


def _clear_state_store(store: Any) -> None:
    store._workflows.clear()
    store._phases.clear()
    store._spans.clear()
    store._exceptions.clear()
    store._policies.clear()
    store._amplifications.clear()
    store._mcp_calls.clear()
    store._candidates.clear()
    store._role_index.clear()


def _hydrate_workflows(store: Any, dicts: list[dict[str, Any]]) -> None:
    for item in dicts:
        store.upsert_workflow(Workflow.model_validate(item))


def _hydrate_phases(store: Any, by_workflow_id: dict[str, list[dict[str, Any]]]) -> None:
    """Restore per-workflow phase lists from the snapshot."""
    if not isinstance(by_workflow_id, dict):
        return
    for wid, phases in by_workflow_id.items():
        if not isinstance(phases, list):
            continue
        store._phases[wid] = [Phase.model_validate(p) for p in phases]


def _hydrate_exceptions(store: Any, dicts: list[dict[str, Any]]) -> None:
    for item in dicts:
        store.upsert_exception(Exception_.model_validate(item))


def _hydrate_memories(
    domain_memories: dict[str, Any],
    memories: list[dict[str, Any]],
    lessons: list[dict[str, Any]],
) -> None:
    for domain, memory_store in domain_memories.items():
        memory_store.delete_all()

        for item in memories:
            metadata = dict(item.get("metadata") or {})
            if (item.get("domain") or metadata.get("domain")) != domain:
                continue
            text = (item.get("memory") or "").strip()
            if not text:
                continue
            agent_skill = item.get("agent_skill") or metadata.get("agent_skill") or ""
            workflow_id = item.get("workflow_id") or metadata.get("workflow_id") or ""
            kind = item.get("kind") or metadata.get("kind") or "working"
            extra_metadata = dict(metadata)
            for key in ("domain", "kind", "agent_skill", "workflow_id"):
                extra_metadata.pop(key, None)
            memory_store.add(
                text,
                kind=kind,
                agent_skill=agent_skill,
                workflow_id=workflow_id,
                extra_metadata=extra_metadata or None,
            )

        for item in lessons:
            metadata = dict(item.get("metadata") or {})
            if (item.get("domain") or metadata.get("domain")) != domain:
                continue
            text = (item.get("memory") or "").strip()
            if not text:
                continue
            if "source" not in metadata and item.get("source"):
                metadata["source"] = item["source"]
            if "consolidated_at" not in metadata and item.get("consolidated_at"):
                metadata["consolidated_at"] = item["consolidated_at"]
            memory_store.add_distilled(text, metadata=metadata or None)
