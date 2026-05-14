"""Vendor auto-block rule emergence (pitch-i2).

Counts ``decision.recorded`` rejections per vendor (KYC personas only).
At the third rejection, installs a permanent "auto-block rule" Decision
node so future ``ap-invoice`` projections can short-circuit before even
spawning a vendor_block_watcher pause loop.

Idempotent on every axis:

* The in-memory ``_VENDOR_REJECT_HISTORY`` dedupes by ``decision_id`` so
  a replayed event never inflates the count.
* ``_INSTALLED`` ensures one ``policy.installed`` FleetEvent per vendor.
* The Decision write uses a stable workflow_id of
  ``f"AUTO-BLOCK-{vendor_id}"`` so the underlying ``record_decision``
  PAT-001 dedupe (``workflow_id, phase, persona_role``) collapses
  duplicate installs into a single row.
"""
from __future__ import annotations

import datetime as _dt
import logging
from typing import Any

from api.shared.events import FleetEvent

log = logging.getLogger(__name__)

_KYC_PERSONAS: frozenset[str] = frozenset({"vendor_kyc_finance_bp", "cfo"})
_REJECTION_THRESHOLD: int = 3
_AUTO_BLOCK_PHASE: str = "auto-block-rule"
_AUTO_BLOCK_PERSONA: str = "auto_block_rule_learner"

# Module-level state — survives re-imports inside one process so cumulative
# rejection counts are not lost when uvicorn --reload swaps the lifespan.
_VENDOR_REJECT_HISTORY: dict[str, list[str]] = {}
_INSTALLED: set[str] = set()


class AutoBlockRuleLearner:
    """Bus subscriber implementing the auto-block rule learner."""

    def __init__(self) -> None:
        self._bus = None
        self._graph = None
        self._unsub = None

    @property
    def installed_vendors(self) -> set[str]:
        return set(_INSTALLED)

    def history_for(self, vendor_id: str) -> list[str]:
        return list(_VENDOR_REJECT_HISTORY.get(vendor_id, ()))

    def start(self, bus, graph) -> None:
        self.stop()
        self._bus = bus
        self._graph = graph
        self._unsub = bus.on("decision.recorded", self._on_decision)

    def stop(self) -> None:
        if self._unsub is not None:
            try:
                self._unsub()
            except Exception:
                log.exception("auto_block_rule_learner: unsubscribe failed")
            self._unsub = None

    # ------------------------------------------------------------------
    # event handler
    # ------------------------------------------------------------------

    def _on_decision(self, event: FleetEvent) -> None:
        try:
            data: dict[str, Any] = event.model_dump()
            persona = data.get("persona_role")
            verdict = data.get("verdict")
            if persona not in _KYC_PERSONAS:
                return
            if verdict != "reject":
                return
            vendor_id = self._extract_vendor_id(data)
            if not vendor_id:
                return
            decision_id = data.get("decision_id")
            history = _VENDOR_REJECT_HISTORY.setdefault(vendor_id, [])
            if decision_id and decision_id in history:
                return
            history.append(decision_id or f"unknown-{len(history)}")
            if len(history) >= _REJECTION_THRESHOLD:
                self._install_rule(vendor_id, history)
        except Exception:
            log.exception(
                "auto_block_rule_learner: handler crashed (swallowed)"
            )

    # ------------------------------------------------------------------
    # vendor-id resolution (mirrors vendor_block_watcher's contract)
    # ------------------------------------------------------------------

    def _extract_vendor_id(self, data: dict[str, Any]) -> str | None:
        vid = data.get("vendor_id")
        if isinstance(vid, str) and vid:
            return vid
        decided_on = data.get("decided_on") or ()
        if isinstance(decided_on, (list, tuple)):
            for did in decided_on:
                if isinstance(did, str) and did.startswith("ORG-"):
                    return did
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
                log.exception(
                    "auto_block_rule_learner: decided_on lookup failed"
                )
        return None

    # ------------------------------------------------------------------
    # rule installation
    # ------------------------------------------------------------------

    def _install_rule(self, vendor_id: str, history: list[str]) -> None:
        if vendor_id in _INSTALLED:
            return
        _INSTALLED.add(vendor_id)
        installed_at = _dt.datetime.now(_dt.timezone.utc)
        rule_workflow_id = f"AUTO-BLOCK-{vendor_id}"
        decision_id: str | None = None
        if self._graph is not None and hasattr(self._graph, "record_decision"):
            try:
                decision_id = self._graph.record_decision(
                    workflow_id=rule_workflow_id,
                    phase=_AUTO_BLOCK_PHASE,
                    persona_role=_AUTO_BLOCK_PERSONA,
                    verdict="block",
                    reason="3 historical rejections",
                    decided_at=installed_at,
                    source_event="decision.recorded",
                    attributes={
                        "vendor_id": vendor_id,
                        "installed_at": installed_at.isoformat(),
                        "rejection_decisions": list(history),
                    },
                    decided_on=(vendor_id,),
                )
            except Exception:
                log.exception(
                    "auto_block_rule_learner: record_decision failed for %s",
                    vendor_id,
                )
        if self._bus is not None:
            try:
                self._bus.emit(
                    FleetEvent(
                        type="policy.installed",
                        workflow_id=rule_workflow_id,
                        decision_id=decision_id,
                        policy="auto-block-rule",
                        vendor_id=vendor_id,
                        installed_at=installed_at.isoformat(),
                        rejection_count=len(history),
                        installed_by=_AUTO_BLOCK_PERSONA,
                        reason="3 historical rejections",
                    )
                )
            except Exception:
                log.exception(
                    "auto_block_rule_learner: policy.installed emit failed "
                    "for %s",
                    vendor_id,
                )


# Module-level singleton wired by api.server.main lifespan.
_LEARNER = AutoBlockRuleLearner()


def start(bus, graph) -> None:
    """Wire the singleton learner to ``bus`` + ``graph``."""
    _LEARNER.start(bus, graph)


def stop() -> None:
    """Tear down the singleton learner's bus subscription."""
    _LEARNER.stop()


def is_vendor_auto_blocked(vendor_id: str) -> bool:
    """Return True if a permanent auto-block rule exists for ``vendor_id``.

    Scans :class:`Decision` nodes for the ``auto-block-rule`` phase. Falls
    back to the in-memory ``_INSTALLED`` ledger when the entity graph is
    unavailable (e.g. the Functions worker process where the entity plane
    is disabled).
    """
    graph = _LEARNER._graph
    if graph is None:
        try:
            from api.server.state import app_state  # late import — avoids cycle
            graph = getattr(app_state, "entities", None)
        except Exception:
            graph = None
    if graph is None:
        return vendor_id in _INSTALLED
    try:
        row = graph.query_one(
            "MATCH (d:Decision) WHERE d.phase = $ph "
            "AND d.workflow_id = $wf RETURN d.id AS id LIMIT 1",
            {"ph": _AUTO_BLOCK_PHASE, "wf": f"AUTO-BLOCK-{vendor_id}"},
        )
        if row is not None:
            return True
    except Exception:
        log.exception(
            "auto_block_rule_learner: is_vendor_auto_blocked query failed "
            "for %s",
            vendor_id,
        )
    return vendor_id in _INSTALLED


def _reset_for_tests() -> None:
    """Test-only: clear the in-memory ledger between cases."""
    _VENDOR_REJECT_HISTORY.clear()
    _INSTALLED.clear()


# Keep a JSON-friendly view of the rejection history available for the
# learning-loop dashboard so it can graph emergence in real time.
def history_snapshot() -> dict[str, list[str]]:
    return {k: list(v) for k, v in _VENDOR_REJECT_HISTORY.items()}


# ---------------------------------------------------------------------------
# Snapshot protocol (pitch-j7) — module-level dump/restore so the
# zava-snapshot bundle can preserve learned state across restarts.
# ---------------------------------------------------------------------------


def dump_state() -> dict:
    return {
        "_VENDOR_REJECT_HISTORY": {k: list(v) for k, v in _VENDOR_REJECT_HISTORY.items()},
        "_INSTALLED": sorted(_INSTALLED),
    }


def load_state(state: dict) -> None:
    global _VENDOR_REJECT_HISTORY, _INSTALLED
    hist = state.get("_VENDOR_REJECT_HISTORY", {}) or {}
    _VENDOR_REJECT_HISTORY = {str(k): list(v or []) for k, v in hist.items()}
    _INSTALLED = set(state.get("_INSTALLED", []) or [])
