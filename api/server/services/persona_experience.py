"""Pitch I6 — persona experience attribute.

Each persona accumulates a per-domain decision count. ``experience_score``
is consumed by ``routing_stats.preferred_role`` as a tie-breaker so a
more-experienced delegate wins when two candidates have the same
approval rate at a given (domain, gate).

In-memory only for the POC1 demo (long-running observability is Track J's
durable history series — j1/j2). The map survives across requests within
one process; a restart resets it.
"""
from __future__ import annotations

import threading


# role → {domain → count}
_EXPERIENCE: dict[str, dict[str, int]] = {}
_LOCK = threading.RLock()


def reset() -> None:
    """Clear all experience — test helper."""
    with _LOCK:
        _EXPERIENCE.clear()


def record_decision(role: str | None, domain: str | None) -> None:
    """Increment ``role``'s decision count in ``domain``.

    No-op when either is missing — the persona_responder calls this best
    effort and there's no value in raising on a half-shaped event.
    """
    if not (role and domain):
        return
    with _LOCK:
        bucket = _EXPERIENCE.setdefault(str(role), {})
        bucket[str(domain)] = bucket.get(str(domain), 0) + 1


def experience_score(role: str | None, domain: str | None) -> int:
    """Return ``role``'s decision count in ``domain``; 0 when unknown."""
    if not (role and domain):
        return 0
    with _LOCK:
        return _EXPERIENCE.get(str(role), {}).get(str(domain), 0)


def snapshot() -> dict[str, dict[str, int]]:
    """Return the full experience matrix (role → domain → count).

    Used by ``GET /api/learning/persona-experience``.
    """
    with _LOCK:
        return {role: dict(domains) for role, domains in _EXPERIENCE.items()}


# ---------------------------------------------------------------------------
# Snapshot protocol (pitch-j7).
# ---------------------------------------------------------------------------


def dump_state() -> dict:
    with _LOCK:
        return {
            "_EXPERIENCE": {
                str(role): {str(d): int(c) for d, c in domains.items()}
                for role, domains in _EXPERIENCE.items()
            }
        }


def load_state(state: dict) -> None:
    raw = state.get("_EXPERIENCE", {}) or {}
    with _LOCK:
        _EXPERIENCE.clear()
        for role, domains in raw.items():
            _EXPERIENCE[str(role)] = {
                str(d): int(c) for d, c in (domains or {}).items()
            }
