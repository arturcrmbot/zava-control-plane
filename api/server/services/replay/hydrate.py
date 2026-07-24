from __future__ import annotations

from typing import Any

from api.server.services.replay.mutation_bus import get_active_bus, set_active_bus
from api.server.services.replay.tape_loader import TapeLoader
from api.server.state import app_state
from api.shared.types import Exception_, McpCall, OtelSpan, Phase


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
        _hydrate_audit_entries(snapshot.get("audit_entries.json"))
        _hydrate_dream_history(snapshot.get("dream_history.json"))
        _hydrate_spans(app_state.store, snapshot.get("spans.json") or {})
        _hydrate_mcp_calls(app_state.store, snapshot.get("mcp_calls.json") or {})
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
    # NB: store._policies is intentionally NOT cleared. Policies are
    # seeded from api/shared/policies.yaml at api/server/routes/policy.py
    # import time and are not part of the tape's mutable state. Clearing
    # them here left /api/policy empty after every replay hydrate cycle,
    # which broke the Policy & Autonomy page (no policies → no
    # WhatIfPanel → user sees just "Select a policy" forever).
    store._amplifications.clear()
    store._mcp_calls.clear()
    store._agent_output_recorded_at.clear()
    store._candidates.clear()
    store._role_index.clear()


def _hydrate_workflows(store: Any, dicts: list[dict[str, Any]]) -> None:
    for item in dicts:
        store.upsert_workflow_replay_patch(item)


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


def _hydrate_spans(store: Any, by_workflow_id: dict[str, list[dict[str, Any]]]) -> None:
    """Restore per-workflow OTel spans so /economics + workflow Timeline
    tab show real cost / token counts in replay. The snapshot is keyed
    by workflow_id; we wholesale-replace store._spans for each id."""
    if not isinstance(by_workflow_id, dict):
        return
    for wid, spans in by_workflow_id.items():
        if not isinstance(spans, list):
            continue
        store._spans[wid] = [OtelSpan.model_validate(s) for s in spans]


def _hydrate_mcp_calls(store: Any, by_workflow_id: dict[str, list[dict[str, Any]]]) -> None:
    """Restore per-workflow MCP/tool call records. Same rationale as
    :func:`_hydrate_spans` — without this /economics shows ``toolCalls=0``
    on every workflow in replay."""
    if not isinstance(by_workflow_id, dict):
        return
    for wid, calls in by_workflow_id.items():
        if not isinstance(calls, list):
            continue
        store._mcp_calls[wid] = [McpCall.model_validate(c) for c in calls]


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


def _hydrate_audit_entries(payload: Any) -> None:
    """Replace ``app_state.audit._entries`` with the snapshotted chain
    AND replay each ``decision.recorded`` entry's ``decision_id`` back
    into the governance kernel's in-process registry.

    Without the kernel re-registration the EvidencePanel paints every
    AGT-emitted row red after a pod restart (the chain + signatures
    stay green because those don't depend on the registry — only the
    ``decisions_resolvable`` chip does).
    """
    if not isinstance(payload, dict):
        return
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return

    audit = getattr(app_state, "audit", None)
    if audit is not None and hasattr(audit, "_entries"):
        audit._entries = [e for e in entries if isinstance(e, dict)]

    _replay_decisions_into_kernel(entries)


def _replay_decisions_into_kernel(entries: list[dict[str, Any]]) -> None:
    """Walk the rehydrated audit chain and re-register every decision
    referenced in an entry's ``details`` (under ``governance`` or as a
    top-level ``decision_id``). Failures are swallowed — registry
    misses degrade to "AGT row red" rather than breaking boot."""
    try:
        from api.server.services.audit_logger import _extract_decision_refs
        from api.server.services.governance import kernel as _gov_kernel
        from api.server.services.governance.kernel import Decision
    except Exception:
        return

    try:
        k = _gov_kernel()
    except Exception:
        return

    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for decision_id, recorded_pv in _extract_decision_refs(entry.get("details")):
            if decision_id in seen:
                continue
            seen.add(decision_id)
            try:
                decision = Decision(
                    allowed=True,
                    decision_id=decision_id,
                    policy_version=recorded_pv or "phase1-noop",
                    reason="rehydrated from audit chain",
                )
                k._register_decision(decision)
            except Exception:
                continue


def _hydrate_dream_history(payload: Any) -> None:
    """Repopulate ``memory_v2._dream_history`` from the tape so the
    Memory page's Dream Passes / Experiments tabs render after replay
    boot."""
    if not isinstance(payload, dict):
        return
    items = payload.get("items")
    if not isinstance(items, list):
        return
    try:
        from api.server.routes.memory_v2 import _dream_history
    except Exception:
        return
    _dream_history.clear()
    # Recorded order is newest-first (deque.appendleft); restore in
    # reverse so re-appendleft yields the same order.
    for r in reversed(items):
        if isinstance(r, dict):
            _dream_history.appendleft(r)
