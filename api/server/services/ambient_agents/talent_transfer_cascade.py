"""TalentTransferCascade — pitch-h5 entanglement bridge.

Listens for ``workflow.completed`` bus events whose workflow type is
``intercompany-talent-transfer`` and produces the visible cross-domain
ripples that the projection alone cannot:

1. Emits four ``workflow.sub_spawned`` FleetEvents (one per cascaded
   child) so the MetaWorkflowReflector mirrors them as ``SUB_WORKFLOW_OF``
   edges in the entity graph and the cosmic lens animates a parent
   rocket spawning four sub-rockets.
2. Walks every Asset that the transferring Person ``OWNS``, rewrites its
   ``attributes.subsidiary_id`` to the destination subsidiary, and
   re-runs ``EntityGraph.link`` so each move re-emits an
   ``entity.linked`` bus event the lens picks up.

The cascade is idempotent: ``(person_id, transfer_id)`` is recorded on
first fire and any retry is a silent no-op — the underlying graph
operations are MERGE-based and safe to re-run regardless, but the
seen-set keeps the bus quiet.

Failures in any step never propagate back into ``EventBus.emit`` so a
buggy cascade cannot knock out other subscribers (mirrors the
MetaWorkflowReflector's defensive contract).
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any

from api.server.services.entity_projections.intercompany_talent_transfer import (
    CHILD_SPECS,
    WORKFLOW_TYPE,
    child_workflow_id,
)
from api.shared.events import FleetEvent

log = logging.getLogger(__name__)

_TRIGGER_EVENT_TYPE = "workflow.completed"


def _slug(value: str) -> str:
    import re
    s = re.sub(r"[^A-Za-z0-9]+", "-", value or "").strip("-").lower()
    return s or "unknown"


class TalentTransferCascade:
    """Bridges ``intercompany-talent-transfer`` completions into the
    four-child cascade + Asset OWNS reassignment."""

    def __init__(self, *, bus: Any, audit: Any | None, graph: Any | None) -> None:
        self._bus = bus
        self._audit = audit
        self._graph = graph
        self._off: Any = None
        self._started = False
        self._seen: set[tuple[str, str]] = set()
        self._seen_lock = threading.Lock()

    def start(self) -> None:
        if self._started:
            return
        self._off = self._bus.on(_TRIGGER_EVENT_TYPE, self._handle)
        self._started = True

    def aclose(self) -> None:
        if self._off is not None:
            try:
                self._off()
            except Exception:  # pragma: no cover
                pass
            self._off = None
        self._started = False

    # -- handler -------------------------------------------------------

    def _handle(self, event: FleetEvent) -> None:
        try:
            payload = event.model_dump() if hasattr(event, "model_dump") else dict(event)
        except Exception as ex:  # pragma: no cover
            log.warning("talent_transfer_cascade: bad event %r: %s", event, ex)
            return

        wf_type = (
            payload.get("workflow_type")
            or (payload.get("payload") or {}).get("workflow_type")
            or (payload.get("payload") or {}).get("type")
        )
        if wf_type != WORKFLOW_TYPE:
            return

        parent_id = payload.get("workflow_id") or payload.get("parent_workflow_id")
        if not parent_id:
            log.warning("talent_transfer_cascade: missing workflow_id in %r", payload)
            return
        parent_id = str(parent_id)

        inner = (
            (payload.get("payload") or {}).get("transfer")
            or payload.get("transfer")
            or {}
        )
        employee_id = str(
            inner.get("employee_id")
            or payload.get("employee_id")
            or parent_id
        )
        person_id = str(payload.get("person_id") or f"PERSON-{employee_id}")
        from_sub = str(inner.get("from_subsidiary") or payload.get("from_subsidiary") or "")
        to_sub = str(inner.get("to_subsidiary") or payload.get("to_subsidiary") or "")
        transfer_id = str(payload.get("transfer_id") or parent_id)

        key = (person_id, transfer_id)
        with self._seen_lock:
            if key in self._seen:
                return
            self._seen.add(key)

        self._spawn_children(parent_id)
        if to_sub and self._graph is not None:
            self._reassign_owns(person_id, to_sub)

    # -- effects -------------------------------------------------------

    def _spawn_children(self, parent_id: str) -> None:
        for child_type, suffix in CHILD_SPECS:
            child_id = child_workflow_id(child_type, suffix, parent_id)
            try:
                self._bus.emit(FleetEvent(
                    type="workflow.sub_spawned",
                    workflow_id=parent_id,
                    parent_workflow_id=parent_id,
                    parent_workflow_type=WORKFLOW_TYPE,
                    child_workflow_id=child_id,
                    child_workflow_type=child_type,
                    cascade_role=suffix,
                ))
            except Exception as ex:  # pragma: no cover
                log.warning(
                    "talent_transfer_cascade: failed to emit sub_spawned %s -> %s: %s",
                    parent_id, child_id, ex,
                )

    def _reassign_owns(self, person_id: str, to_sub: str) -> None:
        new_sub_id = f"ORG-subsidiary-{_slug(to_sub)}"
        try:
            rows = self._graph.query(
                "MATCH (p:Person)-[:OWNS]->(a:Asset) "
                "WHERE p.id = $pid RETURN a.id AS id, a.attributes AS attrs",
                {"pid": person_id},
            )
        except Exception as ex:
            log.warning("talent_transfer_cascade: OWNS query failed for %s: %s",
                        person_id, ex)
            return
        for row in rows:
            asset_id = row.get("id")
            if not asset_id:
                continue
            raw_attrs = row.get("attrs") or "{}"
            try:
                attrs = json.loads(raw_attrs) if isinstance(raw_attrs, str) else dict(raw_attrs)
            except Exception:
                attrs = {}
            attrs["subsidiary_id"] = new_sub_id
            # Re-link to re-emit entity.linked; MERGE keeps the rel stable.
            try:
                self._graph.link(person_id, "OWNS", asset_id)
            except Exception as ex:
                log.warning(
                    "talent_transfer_cascade: re-link %s -OWNS-> %s failed: %s",
                    person_id, asset_id, ex,
                )
                continue
            # Persist the new subsidiary_id on the Asset so subsequent
            # sweeps see the moved ownership in JSON-shape attributes.
            try:
                self._graph.query(
                    "MATCH (a:Asset) WHERE a.id = $aid SET a.attributes = $attrs",
                    {"aid": asset_id, "attrs": json.dumps(attrs)},
                )
            except Exception as ex:  # pragma: no cover
                log.warning(
                    "talent_transfer_cascade: attr update for %s failed: %s",
                    asset_id, ex,
                )
            if self._audit is not None:
                try:
                    self._audit.log("entity.linked", {
                        "subscriber": "talent_transfer_cascade",
                        "src_id": person_id,
                        "dst_id": asset_id,
                        "rel": "OWNS",
                        "subsidiary_id": new_sub_id,
                    })
                except Exception:  # pragma: no cover
                    pass
