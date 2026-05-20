"""Pure-logic dream-pass trigger.

The cadence loop snapshots inputs and asks `should_trigger`. No I/O,
no state. Two signals OR'd together:
  - backlog: there are at least N unconsumed working notes for the
    domain → there's fresh evidence to learn from.
  - heartbeat: it's been at least M seconds since the last pass →
    safety net so paused-but-quiet systems still tick (subject to
    kill switch).

The caller is responsible for actually firing the pass and updating
`last_pass_at` on success.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class TriggerInputs:
    domain: str
    unconsumed_backlog: int
    last_pass_at: datetime | None
    backlog_threshold: int
    heartbeat_seconds: int
    now: datetime


def should_trigger(inp: TriggerInputs) -> tuple[bool, str]:
    if inp.unconsumed_backlog >= inp.backlog_threshold:
        return True, f"backlog={inp.unconsumed_backlog}>={inp.backlog_threshold}"
    if inp.last_pass_at is None:
        return True, "heartbeat:first-pass"
    elapsed = inp.now - inp.last_pass_at
    if elapsed >= timedelta(seconds=inp.heartbeat_seconds):
        return True, f"heartbeat:elapsed={int(elapsed.total_seconds())}s>={inp.heartbeat_seconds}s"
    return False, (
        f"skip: backlog={inp.unconsumed_backlog}<{inp.backlog_threshold} "
        f"elapsed={int(elapsed.total_seconds())}s<{inp.heartbeat_seconds}s"
    )
