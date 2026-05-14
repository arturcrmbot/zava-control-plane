"""Cadenced rituals registry — pitch-e5.

Several agency rituals are inherently scheduled, not on-demand: weekly
pitch reviews on Monday morning, monthly client P&L on the 1st, etc.
The Poisson-ramp simulator (``simulator_orchestrator``) spawns the rest
of the live domains at random, but these need to fire on a wall-clock
cadence to feel like a real agency.

This module is the single source of truth for those scheduled rituals.
Each :class:`CadencedRitual` references a ``workflow_type`` that must
exist in :mod:`api.shared.domains`; the cadence loop in
:mod:`api.server.services.cadence_loader` drives the actual spawning.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CadencedRitual:
    """A workflow that fires on a crontab-style schedule, not on Poisson ramp."""

    name: str
    workflow_type: str
    cron_like: str
    description: str


CADENCED_RITUALS: tuple[CadencedRitual, ...] = (
    CadencedRitual(
        "weekly-pitch-review",
        "weekly-pitch-review",
        "0 9 * * 1",
        "Monday 09:00 — pitch board reviews active opportunities",
    ),
    CadencedRitual(
        "monthly-client-pnl",
        "monthly-client-pnl",
        "0 9 1 * *",
        "1st of month 09:00 — client P&L close",
    ),
    CadencedRitual(
        "quarterly-creative-awards",
        "quarterly-creative-awards",
        "0 9 1 1,4,7,10 *",
        "1st of quarter 09:00 — creative awards review",
    ),
    CadencedRitual(
        "annual-budget-setting",
        "annual-budget-setting",
        "0 9 1 11 *",
        "1 Nov 09:00 — annual budget cycle starts",
    ),
    CadencedRitual(
        "new-business-pipeline-scrub",
        "new-business-pipeline-scrub",
        "0 14 * * 5",
        "Friday 14:00 — pipeline scrub",
    ),
)
