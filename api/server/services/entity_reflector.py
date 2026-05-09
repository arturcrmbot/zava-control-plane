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
  ``reflector.error`` so they're visible.
* **No new lock.** Every write goes through ``EntityGraph.upsert`` /
  ``link`` / ``record_decision``, all of which are already lock-protected.
  The reflector itself is stateless beyond the ``off`` callback stash.
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

import logging
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


class EntityReflector:
    """Bus subscriber that turns FleetEvents into entity-graph writes."""

    def __init__(
        self,
        bus: EventBus,
        store: StateStore,
        graph: EntityGraph,
        governance: Any | None = None,
        audit: Any | None = None,
    ) -> None:
        self._bus = bus
        self._store = store
        self._graph = graph
        self._governance = governance
        self._audit = audit
        self._off: Callable[[], None] | None = None

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
            workflow_id = getattr(event, "workflow_id", None)
            if not workflow_id:
                return

            workflow = self._store.get_workflow(workflow_id)
            if workflow is None:
                return

            workflow_type = workflow.type
            projection = PROJECTIONS.get(workflow_type)
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
            for op in ops:
                self._dispatch_op(op)
        except Exception as exc:
            # Bus already swallows, but make the failure visible.
            log.exception("entity_reflector: dispatch failed")
            self._audit_log(
                "reflector.error",
                {
                    "event_type": getattr(event, "type", None),
                    "workflow_id": getattr(event, "workflow_id", None),
                    "error": repr(exc),
                },
            )

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
