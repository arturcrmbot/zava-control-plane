"""Cadence YAML loader — Phase 4 IP1 (TASK-002).

Walks a directory of ``<name>.yaml`` cadence files, validates each, and
returns a list of :class:`Cadence` records. Validation rules:

* filename stem must equal ``name``;
* ``schedule`` must parse via :mod:`croniter`;
* ``fires_ambient_agent`` must be a non-empty string.

Any failure raises :class:`CadenceConfigError`. Plan reference:
``plan/feature-agentic-org-phase-4-ceo-fm.md`` TASK-002.
"""
from __future__ import annotations

import datetime as _dt
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

import yaml
from croniter import croniter

from api.server.data_fabric.cadenced_rituals import (
    CADENCED_RITUALS,
    CadencedRitual,
)


class CadenceConfigError(ValueError):
    """Raised on any cadence YAML validation failure."""


@dataclass(frozen=True)
class Cadence:
    name: str
    schedule: str
    fires_ambient_agent: str


def load_cadences(dir: Path) -> list[Cadence]:
    """Load every ``*.yaml`` under ``dir`` as a :class:`Cadence`."""
    if not dir.exists():
        return []
    out: list[Cadence] = []
    for path in sorted(dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as ex:
            raise CadenceConfigError(f"{path}: invalid YAML: {ex}") from ex
        name = data.get("name")
        schedule = data.get("schedule")
        fires = data.get("fires_ambient_agent")
        if name != path.stem:
            raise CadenceConfigError(
                f"{path}: filename stem {path.stem!r} != name {name!r}")
        if not isinstance(fires, str) or not fires.strip():
            raise CadenceConfigError(
                f"{path}: fires_ambient_agent must be a non-empty string")
        if not isinstance(schedule, str) or not croniter.is_valid(schedule):
            raise CadenceConfigError(
                f"{path}: schedule {schedule!r} is not a valid cron expression")
        out.append(Cadence(name=name, schedule=schedule, fires_ambient_agent=fires))
    return out


# ── pitch-e5 — cadenced rituals ────────────────────────────────────
# A registry-driven scheduler that fires whole workflows (not ambient
# agents) on wall-clock cadences. The YAML loader above is a separate
# substrate from Phase 4-IP1; this section reuses ``croniter`` and the
# same module home so all cadence-style scheduling lives together.
#
# Spawning is decoupled via a ``spawn_fn`` callable so the module stays
# import-safe (no eager pull of simulator_orchestrator) and unit tests
# can pass a synchronous fake. Last-fire times are kept in a process-
# local dict — persistence across restart is out of scope (J7 will land
# that later).

_LAST_RITUAL_FIRE: dict[str, _dt.datetime] = {}

_log = logging.getLogger(__name__)

SpawnFn = Callable[[str], object]


def burst_cadenced_rituals_enabled() -> bool:
    """Return True if SIMULATOR_CADENCE_BURST is set to a truthy value.

    When set, one tick fires every cadenced ritual exactly once
    (subsequent ticks honour the cron schedule normally). Default off so
    production-shaped runs only fire rituals when their cron is due.
    """
    raw = os.environ.get("SIMULATOR_CADENCE_BURST", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def reset_cadenced_rituals_state() -> None:
    """Clear the in-memory last-fire ledger. Test helper."""
    _LAST_RITUAL_FIRE.clear()


def _is_due(ritual: CadencedRitual, now: _dt.datetime) -> bool:
    last = _LAST_RITUAL_FIRE.get(ritual.name)
    base = last if last is not None else now - _dt.timedelta(minutes=1)
    if base >= now:
        return False
    try:
        nxt = croniter(ritual.cron_like, base).get_next(_dt.datetime)
    except Exception as ex:  # pragma: no cover — registry validates at import
        _log.warning("ritual %s: invalid cron %r: %s",
                     ritual.name, ritual.cron_like, ex)
        return False
    return nxt <= now


def tick_cadenced_rituals(
    *,
    spawn_fn: SpawnFn,
    now: _dt.datetime | None = None,
    burst: bool | None = None,
    rituals: tuple[CadencedRitual, ...] = CADENCED_RITUALS,
) -> list[str]:
    """Run one scheduling tick. Returns list of ritual names that fired.

    When ``burst`` is True (or unset and ``SIMULATOR_CADENCE_BURST=1``),
    every ritual that has not yet fired in this process fires now —
    used so the demo doesn't have to wait for Monday 09:00.

    Otherwise each ritual fires only when its cron is due since the
    previous fire (or since one minute before ``now`` for first run).
    """
    if now is None:
        now = _dt.datetime.now()
    if burst is None:
        burst = burst_cadenced_rituals_enabled()

    fired: list[str] = []
    for ritual in rituals:
        if burst and ritual.name not in _LAST_RITUAL_FIRE:
            should_fire = True
        else:
            should_fire = _is_due(ritual, now)
        if not should_fire:
            continue
        try:
            spawn_fn(ritual.workflow_type)
        except Exception as ex:
            _log.warning("ritual %s: spawn_fn raised: %s", ritual.name, ex)
            continue
        _LAST_RITUAL_FIRE[ritual.name] = now
        fired.append(ritual.name)
    return fired


async def _default_spawn_workflow(workflow_type: str) -> str | None:
    """Resolve and invoke the domain's ``spawn_fn`` for a cadenced ritual.

    Imported lazily so this module stays cheap to import in tests.
    """
    from api.shared.domains import DOMAINS
    from api.server.services.simulator_orchestrator import _resolve_spawner

    domain = DOMAINS.get(workflow_type)
    if domain is None:
        _log.warning("cadenced ritual: unknown workflow_type %r", workflow_type)
        return None
    spawn = _resolve_spawner(domain)
    return await spawn()


async def run_cadenced_rituals_loop(
    *,
    interval_seconds: float = 60.0,
    spawn_fn: Callable[[str], Awaitable[object]] | None = None,
) -> None:
    """Forever loop: tick every ``interval_seconds`` and spawn due rituals.

    Wire-up helper for the FastAPI lifespan to schedule as a background
    task. Kept thin so the testable surface lives in
    :func:`tick_cadenced_rituals`.
    """
    import asyncio

    spawn_async = spawn_fn or _default_spawn_workflow

    pending: list[asyncio.Task] = []

    def _schedule(workflow_type: str) -> None:
        pending.append(asyncio.create_task(spawn_async(workflow_type)))

    while True:
        try:
            tick_cadenced_rituals(spawn_fn=_schedule)
        except Exception as ex:  # pragma: no cover — defensive
            _log.warning("cadenced rituals tick failed: %s", ex)
        # Drain finished tasks so they don't accumulate.
        pending[:] = [t for t in pending if not t.done()]
        await asyncio.sleep(interval_seconds)
