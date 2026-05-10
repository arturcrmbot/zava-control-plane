"""MetaWorkflowReflector — Phase 4 IP7 (TASK-033b).

A small audit/bus subscriber that mirrors ``workflow.sub_spawned`` events
into the entity graph. For each event it:

1. ``upsert``s a ``Workflow`` node for the parent (if absent).
2. ``upsert``s a ``Workflow`` node for the child.
3. ``link``s ``parent --[SUB_WORKFLOW_OF]--> child`` (idempotent MERGE).

The substrate's :class:`api.server.services.event_bus.EventBus` is the
canonical broadcast surface, so this reflector subscribes to the bus by
event type. The event itself is a :class:`api.shared.events.FleetEvent`
that carries (at least) ``parent_workflow_id``, ``child_workflow_id``
and ``child_workflow_type`` extras (see Phase 4 IP4 codegen).

No-op + WARN if the entity graph is unavailable. Failures NEVER propagate
back into the bus emit so a buggy projection does not knock out spawning.
"""
from __future__ import annotations

import logging
from typing import Any

from api.server.services.entity_graph import EntityGraph, EntityWrite
from api.shared.events import FleetEvent

log = logging.getLogger(__name__)

_EVENT_TYPE = "workflow.sub_spawned"


class MetaWorkflowReflector:
    """Mirrors ``workflow.sub_spawned`` events into the Workflow self-relation."""

    def __init__(self, *, bus: Any, audit: Any, graph: EntityGraph) -> None:
        self._bus = bus
        self._audit = audit
        self._graph = graph
        self._off: Any = None
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._off = self._bus.on(_EVENT_TYPE, self._handle)
        self._started = True

    def aclose(self) -> None:
        if self._off is not None:
            try:
                self._off()
            except Exception:  # pragma: no cover
                pass
            self._off = None
        self._started = False

    # -- handler ---------------------------------------------------

    def _handle(self, event: FleetEvent) -> None:
        try:
            payload = event.model_dump() if hasattr(event, "model_dump") else dict(event)
        except Exception as ex:  # pragma: no cover
            log.warning("meta_workflow_reflector: bad event %r: %s", event, ex)
            return

        parent_id = payload.get("parent_workflow_id") or payload.get("workflow_id")
        child_id = payload.get("child_workflow_id")
        child_type = payload.get("child_workflow_type") or "unknown"
        parent_type = payload.get("parent_workflow_type") or "unknown"
        spawned_at = payload.get("timestamp")

        if not parent_id or not child_id:
            log.warning(
                "meta_workflow_reflector: missing ids in %s event: %r",
                _EVENT_TYPE, payload,
            )
            return

        try:
            self._graph.upsert(EntityWrite(
                kind="Workflow", id=str(parent_id),
                attrs={"workflow_type": parent_type},
                source_workflows=(str(parent_id),),
            ))
            self._graph.upsert(EntityWrite(
                kind="Workflow", id=str(child_id),
                attrs={"workflow_type": child_type},
                source_workflows=(str(child_id),),
            ))
            kwargs: dict[str, Any] = {}
            if spawned_at is not None:
                kwargs["spawned_at"] = spawned_at
            self._graph.link(str(parent_id), "SUB_WORKFLOW_OF",
                             str(child_id), **kwargs)
        except Exception as ex:
            log.warning(
                "meta_workflow_reflector: graph write failed (%s -> %s): %s",
                parent_id, child_id, ex,
            )
            try:
                self._audit.log("entity.write.failed", {
                    "subscriber": "meta_workflow_reflector",
                    "event_type": _EVENT_TYPE,
                    "parent_workflow_id": parent_id,
                    "child_workflow_id": child_id,
                    "error": str(ex),
                })
            except Exception:  # pragma: no cover
                pass
