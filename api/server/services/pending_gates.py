"""api/server/services/pending_gates.py — per-workflow HITL gate cache.

When a Durable orchestrator suspends for HITL, it stamps `phase` and
`external_event` on the suspended payload. The internal_durable_event
route caches that pair here, keyed by workflow_id. The exceptions resolve
route reads it back to know which event name to raise on the orchestration
when the operator clicks Approve / Reject.

Cleared on `resumed` and `workflow.completed`. Cold-start fallback is the
domain registry's `resolve_external_event`.

Scope: in-process singleton. Multi-worker uvicorn would need a Redis or
SQL backing — same posture as the workflow_type cache in
internal_durable_event.py (and same caveat noted in
docs/ARCHITECTURE.md §Known limitations).
"""
from __future__ import annotations

# (workflow_id) -> {"phase": <str>, "external_event": <str>}
_pending: dict[str, dict[str, str]] = {}


def record(workflow_id: str, phase: str | None, external_event: str | None) -> None:
    """Remember the active gate for a workflow. Silently drops when either
    field is missing (legacy POC1 paths that don't stamp external_event)."""
    if not workflow_id or not phase or not external_event:
        return
    _pending[workflow_id] = {"phase": phase, "external_event": external_event}


def get(workflow_id: str) -> dict[str, str] | None:
    """Return the cached gate for a workflow, or None."""
    return _pending.get(workflow_id)


def clear(workflow_id: str) -> None:
    """Drop a workflow's gate cache entry — call on resumed / completed /
    rejected so the cache doesn't leak."""
    _pending.pop(workflow_id, None)


def reset() -> None:
    """Test helper."""
    _pending.clear()
