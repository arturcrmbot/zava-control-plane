"""Online cache for the ``exception-classifier`` skill (pitch-i3).

The classifier LLM is deterministic enough that we can short-circuit
repeat invocations on the same ``(kind, vendor, amount_band, scenario)``
signature. First call: classify, then ``remember(sig, resolution)``.
Second call with an equivalent payload: ``lookup(sig)`` hits the cache
and we skip the LLM round-trip entirely.

Module-level dict — survives within a single process. No persistence
across restarts (intentional for the POC: the cache warms quickly under
fleet load and stale entries cannot poison cross-deploy behaviour).
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

log = logging.getLogger(__name__)

_CACHE: dict[str, dict] = {}
_HITS: int = 0
_MISSES: int = 0


def _amount_band(amount: Any) -> str:
    """Coarse log-scale bucketing so semantically equivalent amounts
    collapse onto the same signature."""
    try:
        a = float(amount)
    except (TypeError, ValueError):
        return "unknown"
    if a < 0:
        return "negative"
    for cap in (100, 1_000, 10_000, 100_000, 1_000_000):
        if a < cap:
            return f"<{cap}"
    return ">=1000000"


def signature_for(payload: dict) -> str:
    """Stable signature for the (kind, vendor, amount_band, scenario) tuple.

    ``payload`` may be either the full ``execute(input)`` dict (with an
    ``unmatched_item`` sub-dict) or the inner item directly. Missing
    fields collapse to empty strings — cache hits across slightly
    different shapes are intentional.
    """
    item = payload.get("unmatched_item") if isinstance(payload, dict) else None
    if not isinstance(item, dict):
        item = payload if isinstance(payload, dict) else {}
    kind = (
        payload.get("kind") if isinstance(payload, dict) else None
    ) or item.get("kind") or "exception_classifier"
    vendor = (
        item.get("vendor_id")
        or item.get("vendor")
        or item.get("counterparty")
        or ""
    )
    amount = (
        item.get("amount") if "amount" in item else item.get("value")
    )
    scenario = (
        item.get("scenario") or item.get("type") or item.get("category") or ""
    )
    raw = json.dumps(
        {
            "k": str(kind),
            "v": str(vendor),
            "a": _amount_band(amount),
            "s": str(scenario),
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def lookup(signature: str) -> dict | None:
    """Return the cached resolution for ``signature`` or ``None``.

    Updates the hit / miss counters as a side effect so the
    ``/api/learning/classifier-cache-stats`` endpoint can report cache
    effectiveness without re-instrumenting the call site.
    """
    global _HITS, _MISSES
    hit = _CACHE.get(signature)
    if hit is None:
        _MISSES += 1
        return None
    _HITS += 1
    _emit_cache_hit(signature)
    # Defensive copy — callers must never mutate the cached row in place.
    return dict(hit)


def _emit_cache_hit(signature: str) -> None:
    """Best-effort ``classifier.cache_hit`` emit so the J6 what's-new
    panel sees every short-circuit. Late-imported to avoid a hard
    dependency on app_state at module-import time (tests load this
    module without constructing the full state)."""
    try:
        from api.server.state import app_state
        from api.shared.events import FleetEvent
    except Exception:
        return
    bus = getattr(app_state, "bus", None)
    if bus is None:
        return
    try:
        bus.emit(FleetEvent(type="classifier.cache_hit", signature=signature))
    except Exception:
        log.debug("classifier_cache: cache_hit emit failed", exc_info=True)


def remember(signature: str, resolution: dict) -> None:
    """Cache ``resolution`` against ``signature``."""
    if not isinstance(resolution, dict):
        log.debug("classifier_cache: refusing to remember non-dict resolution")
        return
    _CACHE[signature] = dict(resolution)


def stats() -> dict:
    """Return cache size + hit / miss counters for the learning panel."""
    total = _HITS + _MISSES
    hit_rate = (_HITS / total) if total else 0.0
    return {
        "size": len(_CACHE),
        "hits": _HITS,
        "misses": _MISSES,
        "hit_rate": hit_rate,
    }


def _reset_for_tests() -> None:
    """Test-only: clear cache + counters between cases."""
    global _HITS, _MISSES
    _CACHE.clear()
    _HITS = 0
    _MISSES = 0


# ---------------------------------------------------------------------------
# Snapshot protocol (pitch-j7) — preserves the warm online cache across
# restarts so the post-rehydrate first hit on a known signature still
# avoids the LLM round-trip.
# ---------------------------------------------------------------------------


def dump_state() -> dict:
    return {
        "_CACHE": {str(k): dict(v) for k, v in _CACHE.items()},
        "_HITS": int(_HITS),
        "_MISSES": int(_MISSES),
    }


def load_state(state: dict) -> None:
    global _HITS, _MISSES
    _CACHE.clear()
    for k, v in (state.get("_CACHE", {}) or {}).items():
        _CACHE[str(k)] = dict(v or {})
    _HITS = int(state.get("_HITS", 0) or 0)
    _MISSES = int(state.get("_MISSES", 0) or 0)
