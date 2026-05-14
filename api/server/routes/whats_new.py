"""What's-new feed (pitch-j6).

Aggregates substrate self-modifications into a single ring-buffered
feed so the cosmic-lens HUD's "what's new" panel can render learning
events without each browser polling four endpoints.

Sources (one bus event type per Track-I task):

* ``policy.installed``     — I2 vendor auto-block rule installed
* ``classifier.cache_hit`` — I3 exception classifier cache hit
* ``routing.rebalanced``   — I4 routing optimiser flipped its preferred role
* ``trend.fired``          — I5 KPI-trend cadence trigger

The buffer is module-singleton + bounded; the lifespan attaches it
to the bus once and detaches on teardown. Tests can construct a
private buffer + emit events manually.
"""
from __future__ import annotations

import logging
import threading
import time as _time
from collections import deque
from typing import Any, Callable, Deque

from fastapi import APIRouter, Query

from api.shared.events import FleetEvent

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whats-new")

_MAX_ITEMS = 500


_TYPE_TO_TRACK: dict[str, str] = {
    "policy.installed":     "I2",
    "classifier.cache_hit": "I3",
    "routing.rebalanced":   "I4",
    "trend.fired":          "I5",
}


def _summarise(event_type: str, details: dict[str, Any]) -> str:
    """Short human-friendly one-liner for an event.

    Defensive — every detail lookup tolerates missing keys so a malformed
    event still lands in the feed with a generic summary instead of
    crashing the subscriber.
    """
    if event_type == "policy.installed":
        vendor = details.get("vendor_id") or "unknown vendor"
        n = details.get("rejection_count")
        if isinstance(n, int):
            return f"Auto-block rule installed for {vendor} after {n} rejections"
        return f"Auto-block rule installed for {vendor}"
    if event_type == "classifier.cache_hit":
        sig = details.get("signature") or details.get("sig") or ""
        if sig:
            return f"Exception classifier cache hit ({sig})"
        return "Exception classifier cache hit"
    if event_type == "routing.rebalanced":
        domain = details.get("domain") or "?"
        gate = details.get("gate") or "?"
        prev = details.get("previous_role") or "—"
        new = details.get("preferred_role") or "?"
        return f"Routing rebalanced: {domain}/{gate}: {prev} → {new}"
    if event_type == "trend.fired":
        kpi = details.get("kpi_id") or "?"
        wt = details.get("workflow_type") or "?"
        direction = details.get("direction") or ""
        return f"Trend fired ({direction} {kpi}) → {wt}"
    return event_type


class WhatsNewBuffer:
    """Bounded ring buffer of substrate self-modification events."""

    def __init__(self, *, maxlen: int = _MAX_ITEMS) -> None:
        self._items: Deque[dict] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._unsubscribers: list[Callable[[], None]] = []

    # ------------------------------------------------------------------
    # bus wiring
    # ------------------------------------------------------------------

    def attach(self, bus) -> Callable[[], None]:
        """Subscribe to the four learning-loop event types on ``bus``.

        Returns a teardown callable that detaches every subscription.
        Idempotent — calling :meth:`attach` twice piles new subscriptions
        onto the same buffer; the lifespan owns the single attach call.
        """
        offs: list[Callable[[], None]] = []
        for event_type in _TYPE_TO_TRACK:
            offs.append(bus.on(event_type, self._on_event))
        with self._lock:
            self._unsubscribers.extend(offs)

        def _detach() -> None:
            for off in offs:
                try:
                    off()
                except Exception:
                    log.exception("whats_new: unsubscribe failed")
            with self._lock:
                for off in offs:
                    try:
                        self._unsubscribers.remove(off)
                    except ValueError:
                        pass

        return _detach

    def _on_event(self, event: FleetEvent) -> None:
        try:
            payload = event.model_dump()
        except Exception:
            log.exception("whats_new: model_dump failed for %r", event)
            return
        event_type = payload.pop("type", None)
        if not isinstance(event_type, str) or event_type not in _TYPE_TO_TRACK:
            return
        ts = payload.pop("timestamp", None) if "timestamp" in payload else None
        try:
            ts_f = float(ts) if ts is not None else _time.time()
        except (TypeError, ValueError):
            ts_f = _time.time()
        details = {k: v for k, v in payload.items() if v is not None}
        item = {
            "ts": ts_f,
            "type": event_type,
            "summary": _summarise(event_type, details),
            "details": details,
            "source_track": _TYPE_TO_TRACK[event_type],
        }
        with self._lock:
            self._items.append(item)

    # ------------------------------------------------------------------
    # readers
    # ------------------------------------------------------------------

    def items_since(
        self, *, since: float | None = None, limit: int = 20
    ) -> list[dict]:
        """Return items strictly newer than ``since`` (reverse-chrono)."""
        with self._lock:
            snap = list(self._items)
        if since is not None:
            snap = [i for i in snap if i["ts"] > since]
        snap.sort(key=lambda i: i["ts"], reverse=True)
        return snap[: max(0, int(limit))]

    def reset(self) -> None:
        """Test-only: clear the buffer."""
        with self._lock:
            self._items.clear()


# Module-level singleton wired by api.server.main lifespan.
_BUFFER = WhatsNewBuffer()


def attach_to_bus(bus) -> Callable[[], None]:
    """Wire the singleton buffer to ``bus``. Returns a teardown callable."""
    return _BUFFER.attach(bus)


def reset_for_tests() -> None:
    _BUFFER.reset()


def buffer() -> WhatsNewBuffer:
    """Expose the singleton — primarily so tests can drive it directly."""
    return _BUFFER


@router.get("")
def whats_new(
    since: float | None = Query(None, description="Unix-ts cursor; only items strictly newer are returned"),
    limit: int = Query(20, ge=1, le=200),
) -> dict:
    """Return the most recent substrate-self-modification events.

    Reverse-chronological. ``since`` is the cursor returned by the
    previous call (typically the ``ts`` of the newest item observed)
    so the panel only fetches new rows.
    """
    items = _BUFFER.items_since(since=since, limit=limit)
    return {"items": items}
