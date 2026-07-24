"""EntityReflector — bus → projection → graph dispatcher (TASK-010).

Sub-phase 2 of the agentic-org Phase 1 plan. Subscribes to the FleetEvent
bus, looks up the workflow that the event references, dispatches it
through the per-domain projection registered in
:mod:`api.server.services.entity_projections`, and applies the resulting
ops to :class:`EntityGraph` (upsert / link / record_decision).

Design notes
------------

* **Sync handler.** ``EventBus.emit`` runs handlers synchronously in the
  caller's thread (see ``api/server/services/event_bus.py``); the bus
  also wraps each call in ``try/except: pass`` so an exception inside
  ``_on_event`` cannot kill the bus. We still log exceptions to audit as
  ``reflector.error`` (projection-level failures) or
  ``entity.write.failed`` (per-op failures) so they're visible.
* **Per-op isolation.** Each projection op (EntityWrite / RelWrite /
  DecisionWrite) is dispatched inside its own try/except. One failing
  op (e.g. a schema-mismatched rel) does NOT abort the rest of the
  projection's writes — the loop always continues, audit-logging
  ``entity.write.failed`` for each casualty.
* **No new lock.** Every write goes through ``EntityGraph.upsert`` /
  ``link`` / ``record_decision``, all of which are already lock-protected.
  The reflector keeps only a bounded LRU of successful projection
  fingerprints in addition to the ``off`` callback stash.
* **None-permissive substrate.** ``governance`` and ``audit`` are
  optional ctor params; ``None`` skips the gate / log entirely (mirrors
  ``EntityGraph.attach``'s pattern).
* **Governance gate.** When ``governance`` is set, every event runs
  through ``governance.evaluate_tool_call(actor, tool, args)``. The
  returned :class:`Decision` carries ``allowed: bool``; on ``False`` we
  audit ``entity.write.killed`` and return without touching the graph.
  (The kernel itself folds in the operator kill-switch via
  ``kill_switch_store.is_killed`` — see kernel.py:342-360 — so the
  reflector does not need its own kill-switch check.)
* **Unknown workflow_type.** ``PROJECTIONS.get(workflow.type)`` returning
  ``None`` is a **silent** no-op: no audit, no exception. CON-001 /
  TASK-014.
"""
from __future__ import annotations

import hashlib
import json
import logging
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Callable

from api.server.services.entity_graph import (
    DecisionWrite,
    EntityGraph,
    EntityWrite,
    RelWrite,
)
from api.server.services.entity_projections import PROJECTIONS
from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.shared.events import FleetEvent

log = logging.getLogger(__name__)

_REFLECTOR_ACTOR = "reflector.entity_reflector"
_REFLECTOR_TOOL = "entity.write"
_PROJECTION_FINGERPRINT_CACHE_MAX = 10_000


def _describe_op(op: Any) -> tuple[str, str]:
    """Return ``(kind, id)`` for an op for audit logging — best-effort."""
    if isinstance(op, EntityWrite):
        return op.kind, op.id
    if isinstance(op, RelWrite):
        return f"rel:{op.rel}", f"{op.src_id}->{op.dst_id}"
    if isinstance(op, DecisionWrite):
        return "Decision", f"{op.workflow_id}:{op.phase}"
    return type(op).__name__, ""


def _projection_fingerprint(
    workflow_op: EntityWrite,
    ops: list[EntityWrite | RelWrite | DecisionWrite],
) -> str:
    """Return a stable digest of every graph write in one projection."""
    payload = [
        {
            "type": type(op).__name__,
            "op": asdict(op) if is_dataclass(op) else repr(op),
        }
        for op in (workflow_op, *ops)
    ]
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EntityReflector:
    """Bus subscriber that turns FleetEvents into entity-graph writes."""

    def __init__(
        self,
        bus: EventBus,
        store: StateStore,
        graph: EntityGraph,
        governance: Any | None = None,
        audit: Any | None = None,
        projections: Mapping[str, Any] | None = None,
    ) -> None:
        self._bus = bus
        self._store = store
        self._graph = graph
        self._governance = governance
        self._audit = audit
        self._projections = projections if projections is not None else PROJECTIONS
        self._off: Callable[[], None] | None = None
        self._projection_fingerprints: OrderedDict[str, str] = OrderedDict()
        self._projection_fingerprint_cache_max = _PROJECTION_FINGERPRINT_CACHE_MAX

    # -- lifecycle -------------------------------------------------------

    def start(self) -> None:
        """Subscribe to ``bus.on_any``; idempotent (a second start is a no-op)."""
        if self._off is not None:
            return
        self._off = self._bus.on_any(self._on_event)

    def aclose(self) -> None:
        """Unsubscribe from the bus (safe to call without a prior start)."""
        if self._off is not None:
            try:
                self._off()
            finally:
                self._off = None

    # -- dispatch --------------------------------------------------------

    def _on_event(self, event: FleetEvent) -> None:
        """Resolve workflow → projection → graph ops. See module docstring."""
        try:
            # Skip events the graph itself emits — otherwise stamping
            # workflow_id on EntityWrite.attrs (Phase 1.5 honesty fix)
            # would create a write→event→reflect→write loop. ``entity.*``
            # events are graph-emission feedback, not workflow lifecycle
            # signals.
            event_type = getattr(event, "type", "") or ""
            if event_type.startswith("entity."):
                return

            workflow_id = getattr(event, "workflow_id", None)
            if not workflow_id:
                return

            workflow = self._store.get_workflow(workflow_id)
            if workflow is None:
                return

            workflow_type = workflow.type
            projection = self._projections.get(workflow_type)
            if projection is None:
                # CON-001: unknown / unregistered workflow_type is a silent
                # no-op. No audit, no exception.
                return

            # Governance gate (None-permissive).
            if self._governance is not None:
                decision = self._governance.evaluate_tool_call(
                    actor=_REFLECTOR_ACTOR,
                    tool=_REFLECTOR_TOOL,
                    args={
                        "workflow_id": workflow_id,
                        "workflow_type": workflow_type,
                    },
                    workflow_id=workflow_id,
                )
                if not getattr(decision, "allowed", True):
                    self._audit_log(
                        "entity.write.killed",
                        {
                            "workflow_id": workflow_id,
                            "workflow_type": workflow_type,
                            "reason": getattr(decision, "reason", "kill-switch"),
                        },
                    )
                    return

            ops = projection(workflow)
        except Exception as exc:
            # Projection itself raised — nothing to dispatch. Make it visible.
            log.exception("entity_reflector: projection raised")
            self._audit_log(
                "reflector.error",
                {
                    "event_type": getattr(event, "type", None),
                    "workflow_id": getattr(event, "workflow_id", None),
                    "error": repr(exc),
                },
            )
            return

        # Stamp the spawning workflow_id onto every EntityWrite's attrs so
        # ``EntityGraph.upsert`` can thread it into the resulting
        # ``entity.upserted`` FleetEvent. ``EntityWrite`` is a frozen
        # dataclass but ``attrs`` is a plain dict, so in-place mutation
        # works without rebuilding the op. Without this, every entity
        # event reaches the cosmic-lens SSE bus with workflow_id=None and
        # the rocket-loop skips it (no rockets ever fly to entity cities).
        for op in ops:
            if isinstance(op, EntityWrite):
                op.attrs.setdefault("workflow_id", workflow_id)

        workflow_op = EntityWrite(
            kind="Workflow",
            id=str(workflow_id),
            attrs={
                "workflow_type": workflow_type or "unknown",
                "status": getattr(workflow, "status", "") or "",
            },
            source_workflows=(),
        )
        fingerprint = _projection_fingerprint(workflow_op, ops)
        workflow_key = str(workflow_id)
        if self._projection_fingerprints.get(workflow_key) == fingerprint:
            self._projection_fingerprints.move_to_end(workflow_key)
            return

        # Always materialise the dispatching workflow as a Workflow node
        # before applying the projection's ops. Without this, the SUB_WORKFLOW_OF
        # rel table can never accumulate rows (its endpoints would be unanchored)
        # and any future Workflow-targeted edge has nothing to point at. The
        # upsert is idempotent on id so re-dispatching the same workflow is safe.
        dispatch_succeeded = True
        try:
            self._graph.upsert(workflow_op)
        except Exception as exc:
            dispatch_succeeded = False
            log.warning(
                "entity_reflector: Workflow node upsert failed for %s: %s",
                workflow_id, exc,
            )

        # Per-op isolation: a single failing op (e.g. schema mismatch on one
        # entity kind) must NOT skip the rest of the projection's writes.
        # Each op gets its own try/except + audit; the loop always continues.
        for op_index, op in enumerate(ops):
            try:
                self._dispatch_op(op)
            except Exception as exc:
                dispatch_succeeded = False
                kind, ent_id = _describe_op(op)
                log.exception(
                    "entity_reflector: op %d (%s id=%s) failed",
                    op_index, kind, ent_id,
                )
                self._audit_log(
                    "entity.write.failed",
                    {
                        "subscriber": "entity_reflector",
                        "event_type": getattr(event, "type", None),
                        "kind": kind,
                        "id": ent_id,
                        "op_index": op_index,
                        "error_type": type(exc).__name__,
                        "error_msg": str(exc),
                        "error": f"{type(exc).__name__}: {exc}",
                        "workflow_id": getattr(event, "workflow_id", None),
                    },
                )

        if dispatch_succeeded:
            self._projection_fingerprints[workflow_key] = fingerprint
            self._projection_fingerprints.move_to_end(workflow_key)
            while (
                len(self._projection_fingerprints)
                > self._projection_fingerprint_cache_max
            ):
                self._projection_fingerprints.popitem(last=False)
        else:
            self._projection_fingerprints.pop(workflow_key, None)

    def _dispatch_op(self, op: EntityWrite | RelWrite | DecisionWrite) -> None:
        if isinstance(op, EntityWrite):
            self._graph.upsert(op)
        elif isinstance(op, RelWrite):
            self._graph.link(op.src_id, op.rel, op.dst_id, **op.attrs)
        elif isinstance(op, DecisionWrite):
            decided_at = op.decided_at
            if isinstance(decided_at, str):
                decided_at = datetime.fromisoformat(decided_at)
            self._graph.record_decision(
                op.workflow_id,
                op.phase,
                op.persona_role,
                op.verdict,
                op.reason,
                decided_at,
                op.source_event,
                op.attributes,
                op.decided_on,
            )
        else:  # pragma: no cover — guard against future op kinds
            raise TypeError(f"unknown projection op: {type(op).__name__}")

    # -- helpers ---------------------------------------------------------

    def _audit_log(self, action: str, details: dict[str, Any]) -> None:
        if self._audit is None:
            return
        try:
            self._audit.log(action, details)
        except Exception:
            log.exception("entity_reflector: audit emission failed")
