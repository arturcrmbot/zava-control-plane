"""Subsidiary capacity watcher (pitch-h4).

Cross-domain entanglement: when a new ``media-pitch-to-win`` workflow
starts and the target subsidiary is already running >= 90% billable
utilisation (in-flight workflow count / headcount), emit a
``workflow.exception.detected`` carrying ``kind='no_capacity'`` so the
cosmic-lens consumers can render saturated subsidiary cities with
warning halos.

Idempotent on ``(subsidiary_id, hour_of_day)`` so a single saturation
window does not flood the bus — the next hour's first start that still
sees saturation re-emits.

This module is a passive bus subscriber — it does NOT pause Durable
orchestrators directly. It only emits the exception event + logs.
Defensive: every event handler is wrapped in try/except + log so a
malformed event can never crash the bus.
"""
from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Callable

from api.shared.events import FleetEvent

log = logging.getLogger(__name__)


# Per-subsidiary headcount, mirroring ``_SUBSIDIARY_META`` in
# ``api.server.data_fabric.pack``. Duplicated here so the watcher does
# not pay the cost of importing the data-fabric pack on boot. The
# holding (``ORG-zava-group``) is intentionally absent — utilisation is
# tracked per operating subsidiary, not the parent. Override via the
# ``headcounts`` constructor kwarg in tests.
DEFAULT_SUBSIDIARY_HEADCOUNTS: dict[str, int] = {
    "ORG-zava-creative":   20,
    "ORG-zava-media":      20,
    "ORG-zava-production": 20,
    "ORG-zava-data":       20,
}

# Threshold above which a new pitch trips the no_capacity exception.
# 90% per the H4 spec.
DEFAULT_THRESHOLD_PCT: float = 90.0

# Workflow statuses considered "in flight" for the utilisation count.
# Anything else is treated as terminal / not-yet-billable and excluded.
_IN_FLIGHT_STATUSES: frozenset[str] = frozenset({
    "in_progress", "awaiting_hitl",
})


class SubsidiaryCapacityWatcher:
    """Bus subscriber implementing the H4 capacity gate."""

    def __init__(
        self,
        *,
        headcounts: dict[str, int] | None = None,
        threshold_pct: float = DEFAULT_THRESHOLD_PCT,
        hour_provider: Callable[[], int] | None = None,
    ) -> None:
        self._bus = None
        self._store = None
        self._unsub = None
        self.headcounts = dict(headcounts or DEFAULT_SUBSIDIARY_HEADCOUNTS)
        self.threshold_pct = threshold_pct
        self._hour_provider = hour_provider or _default_hour_provider
        # Idempotency ledger: (subsidiary_id, hour_of_day) → already emitted.
        self._seen: set[tuple[str, int]] = set()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def start(self, bus, store) -> None:
        """Subscribe to ``workflow.started`` on ``bus``; read in-flight from
        ``store``. Idempotent — re-start drops the previous subscription
        so uvicorn --reload cycles don't accumulate handlers."""
        self.stop()
        self._bus = bus
        self._store = store
        self._unsub = bus.on("workflow.started", self._on_started)

    def stop(self) -> None:
        if self._unsub is not None:
            try:
                self._unsub()
            except Exception:
                log.exception("subsidiary_capacity_watcher: unsubscribe failed")
            self._unsub = None

    # ------------------------------------------------------------------
    # event handler
    # ------------------------------------------------------------------

    def _on_started(self, event: FleetEvent) -> None:
        try:
            self._handle(event)
        except Exception:
            log.exception("subsidiary_capacity_watcher: handler failed")

    def _handle(self, event: FleetEvent) -> None:
        data: dict[str, Any] = event.model_dump()
        if (data.get("workflow_type") or (data.get("payload") or {}).get("workflow_type")
                ) != "media-pitch-to-win":
            return

        subsidiary_id = self._resolve_subsidiary_id(data)
        if not subsidiary_id:
            log.debug("subsidiary_capacity_watcher: no subsidiary resolvable; skipping")
            return

        headcount = self.headcounts.get(subsidiary_id) or 0
        if headcount <= 0:
            log.debug(
                "subsidiary_capacity_watcher: %s has no headcount on file; skipping",
                subsidiary_id,
            )
            return

        in_flight = self._count_in_flight(subsidiary_id)
        utilisation_pct = 100.0 * in_flight / headcount
        if utilisation_pct < self.threshold_pct:
            log.debug(
                "subsidiary_capacity_watcher: %s healthy (%.1f%% < %.1f%%)",
                subsidiary_id, utilisation_pct, self.threshold_pct,
            )
            return

        key = (subsidiary_id, self._hour_provider())
        if key in self._seen:
            log.debug(
                "subsidiary_capacity_watcher: %s already flagged this hour; "
                "suppressing re-emit", subsidiary_id,
            )
            return
        self._seen.add(key)

        log.info(
            "subsidiary_capacity_watcher: %s saturated at %.1f%% "
            "(%d in-flight / %d headcount); emitting no_capacity",
            subsidiary_id, utilisation_pct, in_flight, headcount,
        )
        if self._bus is None:
            return
        self._bus.emit(FleetEvent(
            type="workflow.exception.detected",
            workflow_id=data.get("workflow_id"),
            kind="no_capacity",
            subsidiary_id=subsidiary_id,
            utilisation_pct=utilisation_pct,
            in_flight=in_flight,
            headcount=headcount,
        ))

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _resolve_subsidiary_id(self, data: dict[str, Any]) -> str | None:
        """Extract the subsidiary the new pitch is targeting.

        Resolution order:
          1. top-level ``subsidiary_id`` on the event
          2. ``payload.subsidiary_id``
          3. fall back to the first known subsidiary in
             ``self.headcounts`` (per the H4 spec — the holding's first
             operating subsidiary is the demo default).
        """
        sid = data.get("subsidiary_id")
        if sid:
            return sid
        payload = data.get("payload") or {}
        sid = payload.get("subsidiary_id")
        if sid:
            return sid
        if self.headcounts:
            return next(iter(self.headcounts))
        return None

    def _count_in_flight(self, subsidiary_id: str) -> int:
        """Count distinct in-flight workflows touching this subsidiary.

        Proxy used (per the H4 spec): workflows whose ``payload``
        carries the same ``subsidiary_id`` and whose status is still in
        ``_IN_FLIGHT_STATUSES``. Returns 0 on any store error so a
        flaky store can never raise on the bus path.
        """
        if self._store is None:
            return 0
        try:
            workflows = self._store.list_workflows()
        except Exception:
            log.exception("subsidiary_capacity_watcher: list_workflows failed")
            return 0
        seen_ids: set[str] = set()
        for w in workflows:
            status = getattr(w, "status", None)
            if status not in _IN_FLIGHT_STATUSES:
                continue
            payload = getattr(w, "payload", None) or {}
            if payload.get("subsidiary_id") != subsidiary_id:
                continue
            wid = getattr(w, "id", None)
            if wid:
                seen_ids.add(wid)
        return len(seen_ids)


def _default_hour_provider() -> int:
    return _dt.datetime.now(tz=_dt.timezone.utc).hour


# Module-level singleton wired by api.server.main lifespan.
_WATCHER = SubsidiaryCapacityWatcher()


def start(bus, store) -> None:
    """Wire the singleton watcher to ``bus`` + ``store``."""
    _WATCHER.start(bus, store)


def stop() -> None:
    """Tear down the singleton watcher's bus subscription."""
    _WATCHER.stop()


def _reset_for_tests() -> None:
    """Test-only: clear the idempotency ledger between cases."""
    _WATCHER._seen.clear()


# ---------------------------------------------------------------------------
# Snapshot protocol (pitch-j7) — exposes the per-singleton _seen ledger
# under the `_FIRED_THIS_HOUR` key for parity with the J7 plan.
# ---------------------------------------------------------------------------


def dump_state() -> dict:
    return {
        "_FIRED_THIS_HOUR": [
            [str(sub_id), int(hour)] for (sub_id, hour) in _WATCHER._seen
        ],
    }


def load_state(state: dict) -> None:
    raw = state.get("_FIRED_THIS_HOUR", []) or []
    _WATCHER._seen = {
        (str(item[0]), int(item[1])) for item in raw if len(item) == 2
    }
