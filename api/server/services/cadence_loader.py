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

from dataclasses import dataclass
from pathlib import Path

import yaml
from croniter import croniter


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
