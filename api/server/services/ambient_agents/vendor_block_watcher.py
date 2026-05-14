"""Vendor KYC → AP invoice entanglement (pitch-h1).

When a ``vendor-kyc`` workflow records a ``reject`` / ``escalate`` decision
through one of the KYC personas, every in-flight ``ap-invoice`` workflow
that touches the same vendor pauses with reason ``vendor blocked``. When
a later KYC re-verifies as ``approve``, the block clears.

This module is a passive bus subscriber — it does NOT pause Durable
orchestrators directly. It emits ``workflow.paused`` FleetEvents so the
cosmic lens can render the cross-domain entanglement, and flips the
vendor's ``is_blocked`` attribute on the Organisation node so downstream
readers (and the next AP invoice projection) can see the block.

Defensive: every event handler is wrapped in try/except + log so a
malformed event can never crash the bus.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from api.server.services.entity_graph import EntityWrite
from api.shared.events import FleetEvent

log = logging.getLogger(__name__)

_BLOCKING_VERDICTS: frozenset[str] = frozenset({"reject", "escalate"})
_CLEARING_VERDICTS: frozenset[str] = frozenset({"approve"})
_KYC_PERSONAS: frozenset[str] = frozenset({"vendor_kyc_finance_bp", "cfo"})

# Module-level set so re-imports inside one process keep a single block view.
_BLOCKED_VENDORS: set[str] = set()


class VendorBlockWatcher:
    """Bus subscriber implementing the Vendor KYC → AP invoice gate."""

    def __init__(self) -> None:
        self._bus = None
        self._graph = None
        self._unsub = None

    @property
    def blocked_vendors(self) -> set[str]:
        return set(_BLOCKED_VENDORS)

    def start(self, bus, graph) -> None:
        # Idempotent — re-start cleanly drops the previous subscription so
        # uvicorn --reload cycles don't accumulate handlers.
        self.stop()
        self._bus = bus
        self._graph = graph
        self._unsub = bus.on("decision.recorded", self._on_decision)

    def stop(self) -> None:
        if self._unsub is not None:
            try:
                self._unsub()
            except Exception:
                log.exception("vendor_block_watcher: unsubscribe failed")
            self._unsub = None

    # ------------------------------------------------------------------
    # event handler
    # ------------------------------------------------------------------

    def _on_decision(self, event: FleetEvent) -> None:
        try:
            data: dict[str, Any] = event.model_dump()
            persona = data.get("persona_role")
            verdict = data.get("verdict")
            workflow_id = data.get("workflow_id")
            if persona not in _KYC_PERSONAS:
                return
            if not self._is_vendor_kyc(workflow_id, data):
                return
            vendor_id = self._extract_vendor_id(data)
            if not vendor_id:
                return
            if verdict in _BLOCKING_VERDICTS:
                self._block(vendor_id, workflow_id)
            elif verdict in _CLEARING_VERDICTS:
                self._clear(vendor_id, workflow_id)
        except Exception:
            log.exception("vendor_block_watcher: handler crashed (swallowed)")

    # ------------------------------------------------------------------
    # workflow-type + vendor-id resolution
    # ------------------------------------------------------------------

    def _is_vendor_kyc(self, workflow_id: str | None, data: dict[str, Any]) -> bool:
        wf_type = data.get("workflow_type")
        if wf_type == "vendor-kyc":
            return True
        if wf_type:
            return False
        # The simulator mints vendor-kyc workflow ids with a VKY- prefix
        # (see spawn_fleet_vendor_kyc_workflow). Cheap pre-check before
        # the graph round-trip.
        if isinstance(workflow_id, str) and workflow_id.startswith("VKY-"):
            return True
        if not workflow_id or self._graph is None:
            return False
        try:
            row = self._graph.query_one(
                "MATCH (w:Workflow) WHERE w.id = $id RETURN w.workflow_type AS t",
                {"id": workflow_id},
            )
            return bool(row and row.get("t") == "vendor-kyc")
        except Exception:
            log.exception("vendor_block_watcher: workflow_type lookup failed")
            return False

    def _extract_vendor_id(self, data: dict[str, Any]) -> str | None:
        vid = data.get("vendor_id")
        if isinstance(vid, str) and vid:
            return vid
        # Inline hint shipped by some callers via FleetEvent's extras.
        decided_on = data.get("decided_on") or ()
        if isinstance(decided_on, (list, tuple)):
            for did in decided_on:
                if isinstance(did, str) and did.startswith("ORG-"):
                    return did
        # Fallback: walk DECIDED_ORG off the Decision node.
        decision_id = data.get("decision_id")
        if decision_id and self._graph is not None:
            try:
                row = self._graph.query_one(
                    "MATCH (d:Decision)-[:DECIDED_ORG]->(o:Organisation) "
                    "WHERE d.id = $id AND o.kind = 'vendor' "
                    "RETURN o.id AS id LIMIT 1",
                    {"id": decision_id},
                )
                if row:
                    return row.get("id")
            except Exception:
                log.exception("vendor_block_watcher: decided_on lookup failed")
        return None

    # ------------------------------------------------------------------
    # block / clear
    # ------------------------------------------------------------------

    def _block(self, vendor_id: str, workflow_id: str | None) -> None:
        if vendor_id in _BLOCKED_VENDORS:
            return  # Idempotent — second red is a no-op (no double emit).
        _BLOCKED_VENDORS.add(vendor_id)
        self._mark_vendor(vendor_id, True, workflow_id)
        self._pause_in_flight_invoices(vendor_id)

    def _clear(self, vendor_id: str, workflow_id: str | None) -> None:
        if vendor_id not in _BLOCKED_VENDORS:
            return
        _BLOCKED_VENDORS.discard(vendor_id)
        self._mark_vendor(vendor_id, False, workflow_id)

    def _mark_vendor(
        self, vendor_id: str, blocked: bool, workflow_id: str | None
    ) -> None:
        # Organisation has no first-class is_blocked column on the schema,
        # so we merge the flag into its JSON ``attributes`` field. This
        # keeps the writer schema-additive-only and survives existing graph
        # files in the demo data dir.
        if self._graph is None:
            return
        try:
            row = self._graph.query_one(
                "MATCH (o:Organisation) WHERE o.id = $id RETURN o.attributes AS a",
                {"id": vendor_id},
            )
        except Exception:
            log.exception(
                "vendor_block_watcher: vendor attributes read failed for %s", vendor_id
            )
            row = None
        attrs_json = (row or {}).get("a") if row else None
        try:
            attrs = json.loads(attrs_json) if attrs_json else {}
        except Exception:
            attrs = {}
        attrs["is_blocked"] = bool(blocked)
        try:
            self._graph.upsert(
                EntityWrite(
                    kind="Organisation",
                    id=vendor_id,
                    attrs={"attributes": json.dumps(attrs)},
                    source_workflows=(workflow_id,) if workflow_id else (),
                )
            )
        except Exception:
            log.exception(
                "vendor_block_watcher: vendor upsert failed for %s", vendor_id
            )

    def _pause_in_flight_invoices(self, vendor_id: str) -> None:
        if self._graph is None or self._bus is None:
            return
        try:
            # Kuzu 0.6.1: inline LIMIT, $-bound params; CONTAINS is the
            # cheapest way to find Money rows whose JSON attributes mention
            # the vendor without a dedicated rel table.
            rows = self._graph.query(
                "MATCH (m:Money) WHERE m.kind = 'invoice' "
                "AND m.attributes CONTAINS $vid "
                "RETURN m.id AS id, m.source_workflows AS sw "
                "LIMIT 500",
                {"vid": vendor_id},
            )
        except Exception:
            log.exception(
                "vendor_block_watcher: in-flight invoice query failed for %s",
                vendor_id,
            )
            return
        for row in rows or []:
            invoice_id = row.get("id")
            sw = row.get("sw") or []
            paused_workflow_id = sw[0] if sw else None
            try:
                self._bus.emit(
                    FleetEvent(
                        type="workflow.paused",
                        workflow_id=paused_workflow_id,
                        invoice_id=invoice_id,
                        vendor_id=vendor_id,
                        paused_by="vendor_block_watcher",
                        reason="vendor blocked",
                    )
                )
            except Exception:
                log.exception(
                    "vendor_block_watcher: workflow.paused emit failed for %s",
                    invoice_id,
                )


# Module-level singleton wired by api.server.main lifespan.
_WATCHER = VendorBlockWatcher()


def start(bus, graph) -> None:
    """Wire the singleton watcher to ``bus`` + ``graph``."""
    _WATCHER.start(bus, graph)


def stop() -> None:
    """Tear down the singleton watcher's bus subscription."""
    _WATCHER.stop()


def _reset_for_tests() -> None:
    """Test-only: clear the in-memory block ledger between cases."""
    _BLOCKED_VENDORS.clear()


# ---------------------------------------------------------------------------
# Snapshot protocol (pitch-j7).
# ---------------------------------------------------------------------------


def dump_state() -> dict:
    return {"_BLOCKED_VENDORS": sorted(_BLOCKED_VENDORS)}


def load_state(state: dict) -> None:
    global _BLOCKED_VENDORS
    _BLOCKED_VENDORS = set(state.get("_BLOCKED_VENDORS", []) or [])
