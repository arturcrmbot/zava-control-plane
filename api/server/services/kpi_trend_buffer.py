"""KPI trend ring buffer (pitch-i5 / pitch-j1).

Lightweight rolling per-KPI history of ``(timestamp, value)`` samples
plus a simple linear-regression slope helper. Used by the
trend-cadence ambient agent to spot 7-period slopes in agency KPIs and
spawn the matching workflow.

J1 update: ``record()`` now also forwards each sample into the durable
``kpi_history`` SQLite store. The in-memory deque is kept as a
fast-path cache for the slope helper (no SQLite round-trips on the
per-minute tick) so the public surface
(``record`` / ``slope`` / ``latest``) stays backward-compatible.
"""
from __future__ import annotations

from collections import deque
from time import time
from typing import Deque

# Per-KPI rolling ring of ``(timestamp_seconds, value)``.
_BUF: dict[str, Deque[tuple[float, float]]] = {}

# 24h at 1-minute resolution. Plenty of headroom for the 7-minute
# (== 7 business-day, time-compressed) demo window without unbounded
# memory growth.
_MAX = 60 * 24


def record(kpi: str, value: float) -> None:
    """Append a fresh ``(now, value)`` sample for ``kpi``.

    Silently coerces ``value`` to ``float``; non-numeric inputs raise.
    Eviction at the deque's left edge is automatic via ``maxlen``.
    Also forwards the sample into the durable ``kpi_history`` store
    (best-effort; an SQLite hiccup never breaks the in-memory ring).
    """
    buf = _BUF.setdefault(kpi, deque(maxlen=_MAX))
    buf.append((time(), float(value)))
    try:
        from api.server.services import kpi_history
        kpi_history.record(kpi, float(value))
    except Exception:  # pragma: no cover — defensive
        pass


def latest(kpi: str) -> tuple[float, float] | None:
    """Return ``(timestamp, value)`` of the most recent sample, or ``None``."""
    buf = _BUF.get(kpi)
    if not buf:
        return None
    return buf[-1]


def slope(kpi: str, window_seconds: int) -> float | None:
    """Linear-regression slope of (value vs time) over the window.

    Returns ``None`` when the buffer holds fewer than 3 samples within
    the window, or when every in-window sample shares an identical
    timestamp (would divide by zero). Units: ``value-units / second``.
    """
    buf = _BUF.get(kpi)
    if not buf:
        return None
    cutoff = time() - float(window_seconds)
    pts = [(t, v) for (t, v) in buf if t >= cutoff]
    n = len(pts)
    if n < 3:
        return None
    mean_t = sum(t for t, _ in pts) / n
    mean_v = sum(v for _, v in pts) / n
    num = sum((t - mean_t) * (v - mean_v) for t, v in pts)
    den = sum((t - mean_t) ** 2 for t, _ in pts)
    if den == 0:
        return None
    return num / den


def _reset_for_tests() -> None:
    """Test-only: clear all per-KPI buffers."""
    _BUF.clear()
