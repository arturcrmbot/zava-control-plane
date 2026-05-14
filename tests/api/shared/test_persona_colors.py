"""Phase F1 of autonomous-domain-insights v1.1: per-persona display_color.

Covers the dataclass plumbing and the registry-level invariant that
every assigned colour is a 7-char hex string.
"""
from __future__ import annotations

import re

from api.shared.personas import PERSONAS, Persona


_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def test_persona_dataclass_accepts_display_color():
    p = Persona(
        role="probe",
        archetype="approver",
        scope_function="finance",
        workflow_label="probe",
        display_color="#abc123",
    )
    assert p.display_color == "#abc123"


def test_persona_dataclass_defaults_to_none():
    p = Persona(
        role="probe",
        archetype="approver",
        scope_function="finance",
        workflow_label="probe",
    )
    assert p.display_color is None


def test_known_personas_have_color_or_none():
    for role, p in PERSONAS.items():
        c = p.display_color
        assert c is None or _HEX_RE.match(c), (
            f"persona '{role}' has invalid display_color: {c!r}"
        )


def test_at_least_15_personas_have_colors():
    coloured = [r for r, p in PERSONAS.items() if p.display_color is not None]
    assert len(coloured) >= 15, (
        f"expected >=15 personas with display_color, got {len(coloured)}: "
        f"{sorted(coloured)}"
    )
