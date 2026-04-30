"""Bus subscriber for agent.completed events.

Pattern: lifespan-register iff Foundry is configured. on_bus_event filters
to agent.completed, applies sampling, builds an EvalRow, persists it as
pending, and pushes onto an asyncio.Queue. A background drain worker pops
rows, calls each evaluator's `__call__`, and writes results into the store.

Online evals call evaluator `__call__` directly (one row at a time).
`evaluate()` is the *batch* helper — see batch_runner.py and spec §4.1.
"""
from __future__ import annotations
import asyncio
import logging
import os
import random
import time
import uuid
from typing import Any

from api.server.eval import foundry_client
from api.server.eval.store import EvalRow, default_store
from api.shared.events import FleetEvent

log = logging.getLogger(__name__)

_DEFAULT_QUEUE_MAX = "1000"
_RETRY_BACKOFF_S = 2.0

_store = default_store()
_queue: asyncio.Queue[EvalRow] = asyncio.Queue(maxsize=int(os.environ.get("EVAL_QUEUE_MAX", _DEFAULT_QUEUE_MAX)))
_metrics: dict[str, int] = {"dropped": 0, "in_flight": 0}
_unsub = None
_worker_task: asyncio.Task | None = None


_DECLARED_TOOLS: dict[str, list[str]] = {
    # Mirror each agent executor's `tools=[...]` registration. ToolCallValidity
    # scores 1.0 when the tool name was declared; 0.0 if the model hallucinated
    # a tool the skill never gets. Empty list scores 1.0 trivially (no calls
    # are technically valid).
    "rag-classifier":     ["policy_search", "claim_get_structured"],
    "arbitration":        ["policy_search", "precedents_search"],
    "escalation":         ["employee_history"],
    "escalation-advisor": ["employee_history"],
    "notification":       ["claim_summary", "policy_cite"],
    "notification-composer": ["claim_summary", "policy_cite"],
    "receipt-validator":  ["claim_get_structured", "ocr_extract"],
    "audit-summariser":   ["claim_summary", "audit_query"],
    # Extractors typically don't get registered tools — empty list ⇒ 1.0.
    "field_extractor":    [],
    "line_item_extractor": [],
    "anomaly_flagger":    [],
    "exception_classifier": [],
    "resolution_recommender": [],
    "root_cause_explainer": [],
}


def _declared_tools_for(label: str) -> list[str]:
    return _DECLARED_TOOLS.get(label, [])


def on_bus_event(event: FleetEvent) -> None:
    """Bus on_any callback. Filters to agent.completed and enqueues."""
    if event.type != "agent.completed":
        return
    rate = float(os.environ.get("EVAL_SAMPLE_RATE", "1.0"))
    if random.random() >= rate:
        return
    row = _build_row(event)
    _store.put_pending(row)
    try:
        _enqueue_for_drain(row)
    except asyncio.QueueFull:
        # Pop the oldest from the queue to free a slot; drop the matching store row.
        try:
            old_row = _queue.get_nowait()
        except asyncio.QueueEmpty:
            old_row = None
        dropped_id = _store.drop_oldest_pending()
        if dropped_id:
            _metrics["dropped"] = _metrics.get("dropped", 0) + 1
            log.warning("eval queue full; dropped oldest pending row %s", dropped_id)
        try:
            _enqueue_for_drain(row)
        except asyncio.QueueFull:
            _store.drop_oldest_pending()
            _metrics["dropped"] = _metrics.get("dropped", 0) + 1


def _enqueue_for_drain(row: EvalRow) -> None:
    """Indirection so tests can replace this with a list-appender."""
    _queue.put_nowait(row)


def _build_row(event: FleetEvent) -> EvalRow:
    extra = event.model_dump()
    return EvalRow(
        id=f"ev-{uuid.uuid4().hex[:12]}",
        kind="online",
        agent_label=extra.get("agent_label", "unknown"),
        workflow_id=extra.get("workflow_id"),
        agent_run_id=extra.get("agent_run_id"),
        ts=time.time(),
        status="pending",
        prompt=extra.get("prompt", ""),
        response_text=extra.get("response_text", ""),
        context=extra.get("context", ""),
        tool_calls=extra.get("tool_calls", []) or [],
    )


async def _drain_loop() -> None:
    while True:
        row = await _queue.get()
        _metrics["in_flight"] = _metrics.get("in_flight", 0) + 1
        try:
            await _score_row(row)
        finally:
            _metrics["in_flight"] = max(0, _metrics.get("in_flight", 1) - 1)


async def _score_row(row: EvalRow, *, attempt: int = 0) -> None:
    """Run all evaluators for the row in parallel and merge scores.

    Per-evaluator failures are isolated: one evaluator throwing no longer
    fails the whole row. Only when EVERY evaluator throws do we mark the
    row as errored. This is important because LLM-judge calls are flaky
    on real Foundry — single transient 429s shouldn't void four other
    successful scores.
    """
    from api.server.eval.evaluator_set import evaluators_for

    async def _call_one(name: str, ev) -> tuple[str, dict | None, str | None]:
        try:
            result = await asyncio.to_thread(
                ev,
                query=row.prompt,
                response=row.response_text,
                context=row.context,
                tool_calls=row.tool_calls,
                declared_tools=_declared_tools_for(row.agent_label),
            )
            return (name, result if isinstance(result, dict) else None, None)
        except Exception as ex:
            return (name, None, str(ex)[:200])

    try:
        evaluators = evaluators_for(row.agent_label)
    except Exception as ex:
        _store.error(row.id, error_text=f"evaluator_set: {ex}"[:500])
        return

    results = await asyncio.gather(*(_call_one(n, e) for n, e in evaluators.items()))
    merged_scores: dict[str, Any] = {}
    errors: list[str] = []
    succeeded = 0
    for name, result, err in results:
        if err is not None:
            errors.append(f"{name}: {err}")
        elif result:
            merged_scores.update(result)
            succeeded += 1
        # `result == {}` (e.g. safety evaluator silently empty) counts as
        # neither error nor success — just no signal.

    if succeeded == 0 and errors:
        if attempt == 0:
            await asyncio.sleep(_RETRY_BACKOFF_S)
            return await _score_row(row, attempt=1)
        _store.error(row.id, error_text=" | ".join(errors)[:500])
        return

    _store.complete(row.id, scores=merged_scores, foundry_run_url=None)


def _reset_queue_for_test(maxsize: int) -> None:
    """Test-only: replace the module-level queue with one of a different size."""
    global _queue
    _queue = asyncio.Queue(maxsize=maxsize)


async def lifespan_register(app) -> None:
    """Called from the FastAPI lifespan startup. No-ops if Foundry is not configured."""
    global _unsub, _worker_task
    if not foundry_client.is_configured():
        log.warning("Foundry not configured; online eval subscriber inactive")
        return
    from api.server.state import app_state
    _unsub = app_state.bus.on_any(on_bus_event)
    _worker_task = asyncio.create_task(_drain_loop())

    # Recovery: any rows still marked 'pending' in the store are orphans
    # from a previous process — the in-memory asyncio.Queue is wiped on
    # restart but sqlite persists. Re-enqueue them so the new drain worker
    # picks them up. Bounded by EVAL_QUEUE_MAX so a corrupted store can't
    # blow us up.
    try:
        recent_pending = [r for r in _store.recent(int(_DEFAULT_QUEUE_MAX)) if r.status == "pending"]
        for row in recent_pending:
            try:
                _enqueue_for_drain(row)
            except asyncio.QueueFull:
                break
        if recent_pending:
            log.info("eval startup: re-enqueued %d orphaned pending rows", len(recent_pending))
    except Exception as ex:
        log.warning("eval startup: pending-row recovery failed: %s", ex)


async def lifespan_shutdown(app) -> None:
    global _unsub, _worker_task
    if _unsub is not None:
        try:
            _unsub()
        except Exception:
            pass
        _unsub = None
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except (asyncio.CancelledError, Exception):
            pass
        _worker_task = None
