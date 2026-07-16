"""Ambient agents primitive — Phase 3 of plan/feature-agentic-org-phase-3-function-fms.md.

This module exposes:

- ``BusTrigger`` / ``CypherTrigger`` / ``CadenceTrigger`` — frozen
  dataclasses forming the ``Trigger`` discriminated union (each carries
  a ``kind`` Literal discriminator).
- ``AmbientAgent`` — the per-agent declaration shape (name, function,
  triggers tuple, optional reasoning skill, spawnable workflow types).
- ``AMBIENT_AGENTS`` — module-level dict keyed by ``AmbientAgent.name``,
  populated at import time by ``_discover_ambient_agents()`` walking
  every ``*.py`` sibling module. Phase 6 (TASK-035..-037) plants the
  three concrete agent declarations; until then the dict is empty.

Cross-validation: every discovered agent must have ``agent.function in
FUNCTIONS`` AND ``agent.name in FUNCTIONS[agent.function].ambient_agents``
(loud failure on mismatch — same discipline as the active pack's function
ownership wiring in ``verticals._helpers.wire_domain_functions``).
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass
from typing import Literal

from api.shared.functions import FUNCTIONS

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Trigger union
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BusTrigger:
    """Fires when a matching FleetEvent is emitted on the EventBus."""
    event_type: str
    filter: str = ""  # optional safe-eval expression evaluated against event.model_dump()
    kind: Literal["bus"] = "bus"


@dataclass(frozen=True)
class CypherTrigger:
    """Periodic Cypher sweep against the Phase 1 EntityGraph."""
    pattern: str
    sweep_seconds: int = 3600
    kind: Literal["cypher"] = "cypher"


@dataclass(frozen=True)
class CadenceTrigger:
    """Cron-shaped cadence; fired by Phase 4's cadence loop via
    ``AmbientDispatcher.dispatch()``. The dispatcher does NOT spin up
    an asyncio task for cadence triggers in Phase 3."""
    cron: str
    kind: Literal["cadence"] = "cadence"


Trigger = BusTrigger | CypherTrigger | CadenceTrigger


# --------------------------------------------------------------------------
# AmbientAgent
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AmbientAgent:
    name: str
    function: str
    triggers: tuple[Trigger, ...]
    reasoning_skill: str | None = None
    spawnable_workflow_types: tuple[str, ...] = ()


# --------------------------------------------------------------------------
# Discovery + registry
# --------------------------------------------------------------------------


def _discover_ambient_agents() -> dict[str, AmbientAgent]:
    """Walk every sibling ``*.py`` module, scan its globals for
    ``AmbientAgent`` instances, and aggregate into a name-keyed dict.

    Cross-validates each discovered agent against ``FUNCTIONS``. Each
    module import is wrapped in try/except — file-level syntax errors
    degrade gracefully (logged, no agents from that module) so a single
    broken per-function file does not crash boot.
    """
    discovered: dict[str, AmbientAgent] = {}
    pkg_name = __name__
    pkg = importlib.import_module(pkg_name)
    for mod_info in pkgutil.iter_modules(pkg.__path__):
        if mod_info.name.startswith("_"):
            continue
        full_name = f"{pkg_name}.{mod_info.name}"
        try:
            mod = importlib.import_module(full_name)
        except Exception as ex:  # pragma: no cover — graceful degrade
            log.warning("ambient_agents: import of %s failed: %s", full_name, ex)
            continue
        for value in vars(mod).values():
            if not isinstance(value, AmbientAgent):
                continue
            if value.function not in FUNCTIONS:
                raise ValueError(
                    f"AmbientAgent '{value.name}' (in {full_name}) declares "
                    f"function='{value.function}' which is not in FUNCTIONS"
                )
            allowed = FUNCTIONS[value.function].ambient_agents
            if value.name not in allowed:
                raise ValueError(
                    f"AmbientAgent '{value.name}' (in {full_name}) is not listed "
                    f"in FUNCTIONS['{value.function}'].ambient_agents={allowed!r}"
                )
            if value.name in discovered:
                raise ValueError(
                    f"AmbientAgent '{value.name}' declared more than once "
                    f"(second declaration in {full_name})"
                )
            discovered[value.name] = value
    return discovered


AMBIENT_AGENTS: dict[str, AmbientAgent] = _discover_ambient_agents()


# --------------------------------------------------------------------------
# Helpers (TASK-009)
# --------------------------------------------------------------------------


def agents_for_function(function: str) -> tuple[AmbientAgent, ...]:
    """All ambient agents declared for ``function``."""
    return tuple(a for a in AMBIENT_AGENTS.values() if a.function == function)


def agents_by_trigger_kind(
    kind: Literal["bus", "cypher", "cadence"],
) -> tuple[AmbientAgent, ...]:
    """All ambient agents that carry at least one trigger of ``kind``.

    Phase 4's cadence loop uses ``kind="cadence"`` to find which agents
    to fire on each cron tick.
    """
    return tuple(
        a for a in AMBIENT_AGENTS.values()
        if any(t.kind == kind for t in a.triggers)
    )
