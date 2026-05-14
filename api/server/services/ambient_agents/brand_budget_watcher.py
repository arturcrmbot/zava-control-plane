"""Brand budget gates campaign + media spend (pitch-h2).

Every ``Money`` row tagged to a Brand decrements the brand's
``budget_remaining_gbp``. When remaining drops below zero we emit a
single ``workflow.exception.detected`` FleetEvent (kind=budget_variance)
per (brand, fiscal-period) pair so we don't spawn fifty exceptions for
one overspent quarter.

Defensive: per-event try/except + log; no event can crash the bus.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from api.server.services.entity_graph import EntityWrite
from api.shared.events import FleetEvent

log = logging.getLogger(__name__)

# (brand_id, period_id) keys that have already fired an exception.
_BUDGET_EXCEPTIONS_FIRED: set[tuple[str, str]] = set()


class BrandBudgetWatcher:
    """Bus subscriber implementing the Brand-budget gate."""

    def __init__(self) -> None:
        self._bus = None
        self._graph = None
        self._unsub = None

    @property
    def fired_exceptions(self) -> set[tuple[str, str]]:
        return set(_BUDGET_EXCEPTIONS_FIRED)

    def start(self, bus, graph) -> None:
        self.stop()
        self._bus = bus
        self._graph = graph
        self._unsub = bus.on("entity.upserted", self._on_upsert)

    def stop(self) -> None:
        if self._unsub is not None:
            try:
                self._unsub()
            except Exception:
                log.exception("brand_budget_watcher: unsubscribe failed")
            self._unsub = None

    # ------------------------------------------------------------------
    # event handler
    # ------------------------------------------------------------------

    def _on_upsert(self, event: FleetEvent) -> None:
        try:
            data: dict[str, Any] = event.model_dump()
            if data.get("kind") != "Money":
                return
            money_id = data.get("entity_id")
            if not money_id:
                return
            self._process_money(money_id, data.get("workflow_id"))
        except Exception:
            log.exception("brand_budget_watcher: handler crashed (swallowed)")

    def _process_money(self, money_id: str, workflow_id: str | None) -> None:
        if self._graph is None:
            return
        try:
            row = self._graph.query_one(
                "MATCH (m:Money) WHERE m.id = $id "
                "RETURN m.attributes AS a, m.amount AS amt, m.period AS p",
                {"id": money_id},
            )
        except Exception:
            log.exception(
                "brand_budget_watcher: money lookup failed for %s", money_id
            )
            return
        if not row:
            return
        attrs_json = row.get("a")
        try:
            attrs = json.loads(attrs_json) if attrs_json else {}
        except Exception:
            attrs = {}
        brand_id = attrs.get("brand_id")
        if not brand_id:
            return
        # Prefer the explicit GBP figure when shipped; fall back to the
        # raw amount column. Either way coerce to float defensively.
        raw = attrs.get("amount_gbp")
        if raw is None:
            raw = attrs.get("amount")
        if raw is None:
            raw = row.get("amt")
        try:
            amount = float(raw or 0)
        except (TypeError, ValueError):
            log.warning(
                "brand_budget_watcher: non-numeric amount on %s: %r", money_id, raw
            )
            return
        period_id = row.get("p") or attrs.get("period_id") or ""
        self._decrement(brand_id, amount, str(period_id), workflow_id)

    # ------------------------------------------------------------------
    # decrement + exception spawn
    # ------------------------------------------------------------------

    def _decrement(
        self,
        brand_id: str,
        amount: float,
        period_id: str,
        workflow_id: str | None,
    ) -> None:
        if self._graph is None:
            return
        try:
            row = self._graph.query_one(
                "MATCH (b:Brand) WHERE b.id = $id "
                "RETURN b.budget_remaining_gbp AS rem, "
                "b.annual_budget_gbp AS ann",
                {"id": brand_id},
            )
        except Exception:
            log.exception(
                "brand_budget_watcher: brand lookup failed for %s", brand_id
            )
            return
        if not row:
            return
        rem = row.get("rem")
        if rem is None:
            rem = row.get("ann") or 0.0
        try:
            new_value = float(rem) - amount
        except (TypeError, ValueError):
            log.warning(
                "brand_budget_watcher: non-numeric budget on brand %s "
                "(rem=%r amount=%r)",
                brand_id, rem, amount,
            )
            return
        try:
            self._graph.upsert(
                EntityWrite(
                    kind="Brand",
                    id=brand_id,
                    attrs={"budget_remaining_gbp": new_value},
                    source_workflows=(workflow_id,) if workflow_id else (),
                )
            )
        except Exception:
            log.exception(
                "brand_budget_watcher: budget write failed for %s", brand_id
            )
            return
        if new_value < 0:
            self._maybe_emit_exception(brand_id, period_id, new_value, workflow_id)

    def _maybe_emit_exception(
        self,
        brand_id: str,
        period_id: str,
        new_value: float,
        workflow_id: str | None,
    ) -> None:
        key = (brand_id, period_id)
        if key in _BUDGET_EXCEPTIONS_FIRED:
            return
        _BUDGET_EXCEPTIONS_FIRED.add(key)
        if self._bus is None:
            return
        try:
            self._bus.emit(
                FleetEvent(
                    type="workflow.exception.detected",
                    workflow_id=workflow_id,
                    kind="budget_variance",
                    brand_id=brand_id,
                    period_id=period_id,
                    overspend_gbp=abs(new_value),
                )
            )
        except Exception:
            log.exception(
                "brand_budget_watcher: exception emit failed for %s/%s",
                brand_id, period_id,
            )


_WATCHER = BrandBudgetWatcher()


def start(bus, graph) -> None:
    """Wire the singleton watcher to ``bus`` + ``graph``."""
    _WATCHER.start(bus, graph)


def stop() -> None:
    """Tear down the singleton watcher's bus subscription."""
    _WATCHER.stop()


def _reset_for_tests() -> None:
    """Test-only: clear the per-(brand, period) dedupe ledger."""
    _BUDGET_EXCEPTIONS_FIRED.clear()


# ---------------------------------------------------------------------------
# Snapshot protocol (pitch-j7).
# ---------------------------------------------------------------------------


def dump_state() -> dict:
    return {
        "_BUDGET_EXCEPTIONS_FIRED": [list(t) for t in _BUDGET_EXCEPTIONS_FIRED],
    }


def load_state(state: dict) -> None:
    global _BUDGET_EXCEPTIONS_FIRED
    raw = state.get("_BUDGET_EXCEPTIONS_FIRED", []) or []
    _BUDGET_EXCEPTIONS_FIRED = {tuple(item) for item in raw if len(item) == 2}
