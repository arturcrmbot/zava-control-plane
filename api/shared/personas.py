"""api/shared/personas.py — compatibility adapter over the active vertical pack.

Sister to :mod:`api.shared.domains`. This module is a thin adapter, not a
registry. It:

- re-exports the ``Persona``/``Archetype``/``ScopeFunction`` contract
  types from :mod:`api.shared.persona_contracts`
- exposes ``PERSONAS`` as the *active pack's* persona mapping only —
  sourced from ``active_runtime().pack.personas``
- exposes the existing lookup helpers (``get``, ``by_archetype``,
  ``by_function``, ``all_archetypes``, ``all_functions``,
  ``authority_users``)

Why this exists
---------------
Before this registry, persona metadata lived only in the YAML
frontmatter of ``api/server/personae/<role>/SKILL.md``. Consumers
(``persona_responder``, ``blueprint_inventory``, ``fleet_manager_service``)
either re-parsed those files or hardcoded literals. Adding a persona
or shifting an archetype meant tracking down every consumer.

The registry is now the authoritative source. The ``decision_policy``
block stays in the SKILL.md (it's the persona's *behaviour*, not
its *structure*); everything else lives here.

Canonical persona declarations live in ``verticals/agency/personas.py``
and ``verticals/telco/personas.py`` (shared roles such as
``delivery_lead`` are declared once in each pack that legitimately uses
them). This module contains no persona declarations, no all-vertical
registry, and does not parse the environment itself — vertical selection
happens once, while ``active_runtime()`` builds the selected pack.

Consumers:
- api.server.services.persona_responder       — validates against registry at attach()
- api.server.services.blueprint_inventory     — renders persona library on the microsite
- api.server.services.fleet_manager_service   — composes "personae under supervision" text
- api.server.routes.personas (Phase 7)        — operator-facing persona library page

Engagement-POC swap: real engagements replace the registry data with a
customer-supplied org chart slice; the consumers don't change.
"""
from __future__ import annotations

from api.shared.persona_contracts import Archetype, Persona, ScopeFunction
from api.shared.vertical_loader import active_runtime


__all__ = [
    "Archetype",
    "ScopeFunction",
    "Persona",
    "PERSONAS",
    "get",
    "by_archetype",
    "by_function",
    "all_archetypes",
    "all_functions",
    "authority_users",
]

PERSONAS: dict[str, Persona] = dict(active_runtime().pack.personas)


# --------------------------------------------------------------------------
# Lookup helpers — keep call sites readable.
# --------------------------------------------------------------------------


def get(role: str) -> Persona | None:
    """Return the registered Persona for a role, or None."""
    return PERSONAS.get(role)


def by_archetype(archetype: Archetype) -> list[Persona]:
    """Return every Persona whose archetype matches."""
    return [p for p in PERSONAS.values() if p.archetype == archetype]


def by_function(function: ScopeFunction) -> list[Persona]:
    """Return every Persona whose scope_function matches."""
    return [p for p in PERSONAS.values() if p.scope_function == function]


def all_archetypes() -> set[str]:
    """Set of every archetype represented in the registry."""
    return {p.archetype for p in PERSONAS.values()}


def all_functions() -> set[str]:
    """Set of every scope_function represented in the registry."""
    return {p.scope_function for p in PERSONAS.values()}


def authority_users() -> list[Persona]:
    """Personae whose decision_policy reads context.authority instead of inlining thresholds."""
    return [p for p in PERSONAS.values() if p.uses_authority_mcp]
