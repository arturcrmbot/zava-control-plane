"""Pitch I4 — routing optimiser.

Tracks per-(domain, gate, role) decision outcomes in an in-memory map.
``preferred_role`` returns the highest-approval-rate candidate, with a
minimum sample size and an "experience" tie-breaker (Pitch I6).

Used by ``persona_responder`` when picking a cascade target between two
plausible delegates (an explicit AUTHORITY ``delegate_to`` and the
function-hierarchy parent). Empty / under-sampled history → returns
``None`` so the responder keeps its existing default.
"""
from __future__ import annotations

import threading
from typing import Iterable


# Key: (domain, gate, role) → {"approves": int, "total": int}
_STATS: dict[tuple[str, str, str], dict[str, int]] = {}
_LOCK = threading.RLock()
# Last-seen preferred role per (domain, gate) — drives the J6
# ``routing.rebalanced`` emit. Updated lazily inside ``record`` after
# a cell mutation so a flip emits exactly once on the transition.
_LAST_PREFERRED: dict[tuple[str, str], str | None] = {}

# Minimum samples before a candidate is eligible for routing preference.
MIN_SAMPLES = 5


def reset() -> None:
    """Clear all stats — test helper. Not used in production."""
    with _LOCK:
        _STATS.clear()
        _LAST_PREFERRED.clear()


def record(domain: str | None, gate: str | None, role: str | None,
           *, approved: bool) -> None:
    """Record one decision outcome.

    Silently ignores rows missing any of (domain, gate, role) — the
    responder calls this best-effort and there's no value in raising
    for half-shaped events.
    """
    if not (domain and gate and role):
        return
    key = (str(domain), str(gate), str(role))
    with _LOCK:
        bucket = _STATS.setdefault(key, {"approves": 0, "total": 0})
        bucket["total"] += 1
        if approved:
            bucket["approves"] += 1
    _maybe_emit_rebalance(str(domain), str(gate))


def _maybe_emit_rebalance(domain: str, gate: str) -> None:
    """Re-evaluate ``preferred_role`` for ``(domain, gate)`` against every
    role seen so far. If it changed *from one non-None role to another*,
    emit a single ``routing.rebalanced`` FleetEvent so the J6 what's-new
    panel can render the flip. The first time a (domain, gate) becomes
    eligible (``None → role``) is initialisation, not a rebalance.
    """
    with _LOCK:
        candidates = [r for (d, g, r) in _STATS.keys() if d == domain and g == gate]
    if not candidates:
        return
    pick = preferred_role(domain, gate, candidates)
    cell = (domain, gate)
    with _LOCK:
        prev = _LAST_PREFERRED.get(cell)
        if prev == pick:
            return
        _LAST_PREFERRED[cell] = pick
    # Only treat a transition between two distinct, non-None roles as
    # a rebalance — initial pick (None → role) is just bootstrap.
    if prev is None or pick is None:
        return
    try:
        from api.server.state import app_state
        from api.shared.events import FleetEvent
    except Exception:
        return
    bus = getattr(app_state, "bus", None)
    if bus is None:
        return
    try:
        bus.emit(FleetEvent(
            type="routing.rebalanced",
            domain=domain,
            gate=gate,
            previous_role=prev,
            preferred_role=pick,
        ))
    except Exception:  # pragma: no cover — defensive only
        pass


def stats_for(domain: str, gate: str, role: str) -> dict[str, int]:
    """Return the raw counts for one (domain, gate, role) cell."""
    with _LOCK:
        return dict(_STATS.get((str(domain), str(gate), str(role)),
                               {"approves": 0, "total": 0}))


def approval_rate(domain: str, gate: str, role: str) -> float:
    """Approval ratio in [0,1]; 0.0 when the cell is empty."""
    s = stats_for(domain, gate, role)
    return (s["approves"] / s["total"]) if s["total"] else 0.0


def preferred_role(
    domain: str | None,
    gate: str | None,
    candidate_roles: Iterable[str],
) -> str | None:
    """Pick the candidate with the best approval rate at this (domain, gate).

    Rules:
    * Each candidate must have at least :data:`MIN_SAMPLES` recorded
      decisions at this cell — otherwise it is ineligible.
    * Highest approval rate wins.
    * Ties are broken by I6 ``experience_score`` (more experience first).
    * Further ties prefer the candidate listed FIRST in
      ``candidate_roles`` — the caller is expected to pass the more
      junior delegate first so the optimiser nudges work *down* the
      hierarchy by default (the I4 headline: delegates that consistently
      ratify their boss's verdicts get the work directly).
    * Returns ``None`` when no candidate is eligible — caller must
      fall back to its existing default.
    """
    if not (domain and gate):
        return None
    candidates = [str(r) for r in candidate_roles if r]
    if not candidates:
        return None

    eligible: list[tuple[str, float, int, int]] = []
    for idx, role in enumerate(candidates):
        s = stats_for(domain, gate, role)
        if s["total"] < MIN_SAMPLES:
            continue
        rate = s["approves"] / s["total"]
        eligible.append((role, rate, idx, s["total"]))
    if not eligible:
        return None

    # I6 hook — lazy import to avoid a circular at module-load time.
    try:
        from api.server.services.persona_experience import experience_score
    except Exception:
        def experience_score(_role: str, _domain: str | None) -> int:
            return 0

    def _sort_key(row: tuple[str, float, int, int]) -> tuple:
        role, rate, idx, _total = row
        # Sort by: -rate (highest first), -experience (most first), idx (first listed first)
        return (-rate, -experience_score(role, domain), idx)

    eligible.sort(key=_sort_key)
    return eligible[0][0]


def snapshot() -> dict[str, dict]:
    """Return the full stats matrix as a JSON-serialisable dict.

    Shape: ``{ "domain|gate|role": {"approves": n, "total": n,
    "approval_rate": float} }``. Used by the
    ``GET /api/learning/routing-stats`` endpoint.
    """
    with _LOCK:
        out: dict[str, dict] = {}
        for (domain, gate, role), bucket in _STATS.items():
            key = f"{domain}|{gate}|{role}"
            total = bucket["total"]
            approves = bucket["approves"]
            out[key] = {
                "domain": domain,
                "gate": gate,
                "role": role,
                "approves": approves,
                "total": total,
                "approval_rate": (approves / total) if total else 0.0,
            }
        return out


# ---------------------------------------------------------------------------
# Snapshot protocol (pitch-j7) — module-level dump/restore so the
# zava-snapshot bundle preserves learned routing weights across restarts.
# Tuple keys (domain, gate, role) are JSON-encoded as "domain|gate|role".
# ---------------------------------------------------------------------------


def dump_state() -> dict:
    with _LOCK:
        return {
            "_STATS": {
                f"{d}|{g}|{r}": dict(bucket)
                for (d, g, r), bucket in _STATS.items()
            }
        }


def load_state(state: dict) -> None:
    raw = state.get("_STATS", {}) or {}
    with _LOCK:
        _STATS.clear()
        for key, bucket in raw.items():
            parts = str(key).split("|", 2)
            if len(parts) != 3:
                continue
            _STATS[(parts[0], parts[1], parts[2])] = {
                "approves": int(bucket.get("approves", 0)),
                "total": int(bucket.get("total", 0)),
            }
