"""Pre-canned narrative arcs for the cosmic-lens HUD (Pitch D5).

The cosmic lens normally surfaces personae by *role id*
(e.g. ``cfo``, ``ap_clerk``). For pitch storytelling we want named
humans with photos and short bios so the demo operator can point at a
city and say "that's Aisha — she's been over-promoted; watch the
risk-averse calls" instead of "that's the finance_bp city".

This module is intentionally a static, hand-curated registry. It is
*not* derived from the synthetic employee generator at runtime — the
arcs are part of the pitch script, so they're checked into git.

The ``employee_id`` values follow the same pattern as
``api.server.data_fabric.employee_gen`` outputs
(``PERSON-EMP-0001``..``PERSON-EMP-0100``) so a future engagement-time
swap can join arcs back to the synthetic org chart on a single key.

The ``role`` values must exist in ``api.shared.personas.PERSONAS``;
the test suite asserts this.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaArc:
    """One named individual surfaced in the demo HUD."""

    employee_id: str
    name: str
    role: str
    photo_url: str
    one_liner: str
    arc: str
    function: str


ARCS: tuple[PersonaArc, ...] = (
    PersonaArc(
        employee_id="PERSON-EMP-0003",
        name="Aisha Khan",
        role="finance_bp",
        photo_url="/assets/personae/aisha.png",
        one_liner="Finance BP, over-promoted into a regional role",
        arc=(
            "After two strong cycles she is one bad quarter from a downgrade. "
            "Watch for risk-averse calls on borderline expense and vendor gates."
        ),
        function="finance",
    ),
    PersonaArc(
        employee_id="PERSON-EMP-0011",
        name="Marcus Holt",
        role="cfo",
        photo_url="/assets/personae/marcus.png",
        one_liner="New CFO mid-restructure, aggressive on cost",
        arc=(
            "Six weeks in, mandate to cut 12% from run-rate. "
            "Pushes thresholds down and escalates anything that smells like sprawl."
        ),
        function="finance",
    ),
    PersonaArc(
        employee_id="PERSON-EMP-0024",
        name="Priya Raman",
        role="ap_clerk",
        photo_url="/assets/personae/priya.png",
        one_liner="Senior AP clerk, the team's institutional memory",
        arc=(
            "Has seen every vendor trick. Slow but almost never wrong. "
            "Her reject rate spikes whenever a new category manager onboards."
        ),
        function="finance",
    ),
    PersonaArc(
        employee_id="PERSON-EMP-0037",
        name="Daniel Owusu",
        role="controller",
        photo_url="/assets/personae/daniel.png",
        one_liner="Group controller, audit-anxious, conservative",
        arc=(
            "PCAOB inspection landed last quarter. Treats every override as a "
            "future audit finding and asks for a paper trail before signing."
        ),
        function="finance",
    ),
    PersonaArc(
        employee_id="PERSON-EMP-0052",
        name="Lena Brandt",
        role="hr_bp",
        photo_url="/assets/personae/lena.png",
        one_liner="HR BP for commercial, juggling two reorgs at once",
        arc=(
            "Backlog of 14 open reqs and a redeployment shortlist. "
            "Decisions skew toward speed; she'll wave through borderline hires."
        ),
        function="hr",
    ),
    PersonaArc(
        employee_id="PERSON-EMP-0068",
        name="Sven Eriksen",
        role="recruiter",
        photo_url="/assets/personae/sven.png",
        one_liner="Senior recruiter, quota-led, optimistic on candidate fit",
        arc=(
            "Compensation tied to time-to-hire. Pushes interview loops to close "
            "fast — pairs well with Lena, friction with the hiring managers."
        ),
        function="hr",
    ),
    PersonaArc(
        employee_id="PERSON-EMP-0081",
        name="Naomi Carver",
        role="gc",
        photo_url="/assets/personae/naomi.png",
        one_liner="General counsel, new to the role, building the bench",
        arc=(
            "Inherited a thin legal team. Risk-averse on contract redlines and "
            "wants every privacy gate reviewed in person until DPO is hired."
        ),
        function="legal",
    ),
    PersonaArc(
        employee_id="PERSON-EMP-0094",
        name="Rafael Costa",
        role="cpo",
        photo_url="/assets/personae/rafael.png",
        one_liner="Chief procurement officer, savings-driven, vendor-skeptic",
        arc=(
            "Targeting 7% category savings this year. Slow-walks single-source "
            "deals and asks for a competitive bid even on small renewals."
        ),
        function="procurement",
    ),
)


def by_role(role: str) -> tuple[PersonaArc, ...]:
    """Return all arcs whose persona role matches ``role``."""
    return tuple(a for a in ARCS if a.role == role)


def by_function(function: str) -> tuple[PersonaArc, ...]:
    """Return all arcs whose corporate function matches ``function``."""
    return tuple(a for a in ARCS if a.function == function)
