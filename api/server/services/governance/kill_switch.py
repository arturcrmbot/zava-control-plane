"""Operator kill switch — Phase 7 TASK-051..052 of plan/feature-agent-governance-toolkit-1.md.

A KillSwitch pauses an agent or blocks a tool fleet-wide for a TTL
without redeploying. Sub-second to flip; consulted on every
:meth:`GovernanceKernel.evaluate_tool_call` (TASK-052).

Wildcard semantics:
  - ``("*", "concur.submit_decision")``  → blocks the tool fleet-wide
  - ``("finance-agent", "*")``           → pauses the agent everywhere
  - ``("finance-agent", "concur.submit_decision")`` → narrow precision

Lifetime: every kill carries an ``expires_at`` timestamp. Reads do
lazy expiry — no background thread; if you read a stale kill it's
cleaned up on the spot.

Operator-auth lives one layer up at the route level
(api/server/routes/governance.py) — this store is a pure in-memory
table with no auth opinions of its own. Nothing here is persisted;
restarting the FastAPI process clears every kill (intentional —
"emergency stop" not "permanent ban").
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


WILDCARD = "*"


class KillSwitch(BaseModel):
    """One operator kill. ``actor='*'`` matches any actor; ``tool='*'``
    matches any tool. The (actor, tool) pair is the lookup key but
    multiple kills can share components — the kernel ORs the matches."""

    kill_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    actor: str
    tool: str
    created_at: float = Field(default_factory=time.time)
    expires_at: float
    reason: str
    created_by: str = "operator"

    def matches(self, actor: str, tool: str) -> bool:
        actor_ok = self.actor == WILDCARD or self.actor == actor
        tool_ok = self.tool == WILDCARD or self.tool == tool
        return actor_ok and tool_ok

    def is_expired(self, now: float | None = None) -> bool:
        return (now or time.time()) >= self.expires_at

    def remaining_seconds(self, now: float | None = None) -> float:
        return max(0.0, self.expires_at - (now or time.time()))


class KillSwitchStore:
    """In-process kill-switch table. Thread-safe; lazy expiry on read.

    Singleton via :data:`kill_switch_store` below; the FastAPI app
    state holds a reference.
    """

    def __init__(self) -> None:
        self._kills: dict[str, KillSwitch] = {}
        self._lock = threading.Lock()

    def add(
        self,
        actor: str,
        tool: str,
        ttl_seconds: float,
        reason: str,
        created_by: str = "operator",
    ) -> KillSwitch:
        if not actor or not tool:
            raise ValueError("kill switch: actor and tool are required (use '*' for wildcard)")
        if ttl_seconds <= 0:
            raise ValueError(f"kill switch: ttl_seconds must be > 0; got {ttl_seconds}")
        kill = KillSwitch(
            actor=actor,
            tool=tool,
            expires_at=time.time() + ttl_seconds,
            reason=reason,
            created_by=created_by,
        )
        with self._lock:
            self._kills[kill.kill_id] = kill
        return kill

    def remove(self, kill_id: str) -> bool:
        """Remove by id. Returns True if a kill was removed."""
        with self._lock:
            return self._kills.pop(kill_id, None) is not None

    def list_active(self) -> list[KillSwitch]:
        """All non-expired kills, freshest first. Lazy-cleans expired."""
        now = time.time()
        with self._lock:
            expired = [k for k in self._kills.values() if k.is_expired(now)]
            for k in expired:
                self._kills.pop(k.kill_id, None)
            active = list(self._kills.values())
        active.sort(key=lambda k: k.created_at, reverse=True)
        return active

    def is_killed(self, actor: str, tool: str) -> KillSwitch | None:
        """Return the matching active kill (most-specific wins) or
        ``None``. "Most-specific" means: an exact (actor, tool) match
        beats an actor-wildcard which beats a tool-wildcard which beats
        a both-wildcard. Ties broken by recency."""
        now = time.time()
        with self._lock:
            expired = [k for k in self._kills.values() if k.is_expired(now)]
            for k in expired:
                self._kills.pop(k.kill_id, None)
            candidates = [k for k in self._kills.values() if k.matches(actor, tool)]
        if not candidates:
            return None

        def _specificity(k: KillSwitch) -> tuple[int, float]:
            # Higher specificity = denser match. (3,t) beats (2,t)
            # beats (1,t). t = recency.
            score = (0 if k.actor == WILDCARD else 2) + (0 if k.tool == WILDCARD else 1)
            return (score, k.created_at)

        return max(candidates, key=_specificity)

    def clear_for_tests(self) -> None:
        with self._lock:
            self._kills.clear()


# Module-level singleton — the kernel + the route both consult this
# instance. AppState hands its reference out; tests reset it via
# ``clear_for_tests()``.
kill_switch_store = KillSwitchStore()
