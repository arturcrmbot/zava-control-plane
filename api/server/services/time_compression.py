"""Time-compression helpers for the simulator (pitch-c5).

Some workflows naturally span months (contract renewals) or quarters
(perf-review cycles). Wall-clock cadence makes them indistinguishable
from a 2-minute expense claim during a demo. This module exposes a
"business time" clock that ticks faster than wall-clock so a 30-minute
demo can plausibly cover a quarter or fiscal year.

The compression factor is read from the ``SIMULATOR_TIME_COMPRESSION``
env var and represents *business seconds per wall-clock second*. The
default of ``60`` keeps the historical "1 wall-second = 1 business
minute" demo cadence; ``86400`` advances business time by one day per
real second (useful for "fast-forward" mode behind the j4 time-scrub UI).
"""
from __future__ import annotations

from datetime import datetime, timedelta
import os


def time_compression_factor() -> float:
    """Business-seconds per wall-clock second. Defaults to 60."""
    try:
        return float(os.environ.get("SIMULATOR_TIME_COMPRESSION", "60"))
    except ValueError:
        return 60.0


def business_now(
    real_now: datetime | None = None,
    *,
    base: datetime | None = None,
) -> datetime:
    """Return 'business time' for the given real-clock instant.

    ``base`` is the wall-clock instant when the simulator started
    (defaults to module import time). The returned datetime is
    ``base + (real_now - base) * compression_factor``.
    """
    real_now = real_now or datetime.utcnow()
    base = base or _BASE
    elapsed_real = (real_now - base).total_seconds()
    return base + timedelta(seconds=elapsed_real * time_compression_factor())


_BASE = datetime.utcnow()


def reset_base(at: datetime | None = None) -> None:
    """Test hook: reset the simulator's wall-clock base to ``at``.

    Defaults to ``datetime.utcnow()``. Tests use this to make
    ``business_now()`` deterministic.
    """
    global _BASE
    _BASE = at or datetime.utcnow()
