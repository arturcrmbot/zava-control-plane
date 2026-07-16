from __future__ import annotations

from types import MappingProxyType

from api.shared.all_personas import Archetype, Persona, ScopeFunction
from api.shared.all_personas import PERSONAS as ALL_PERSONAS
from api.shared.vertical_loader import active_runtime


_ROOTS = active_runtime().pack.personae_roots
PERSONAS = MappingProxyType(
    {
        role: persona
        for role, persona in ALL_PERSONAS.items()
        if any((root / role / "SKILL.md").is_file() for root in _ROOTS)
    }
)


def get(role: str) -> Persona | None:
    return PERSONAS.get(role)


def by_archetype(archetype: Archetype) -> list[Persona]:
    return [
        persona
        for persona in PERSONAS.values()
        if persona.archetype == archetype
    ]


def by_function(function: ScopeFunction) -> list[Persona]:
    return [
        persona
        for persona in PERSONAS.values()
        if persona.scope_function == function
    ]


def all_archetypes() -> set[str]:
    return {persona.archetype for persona in PERSONAS.values()}


def all_functions() -> set[str]:
    return {persona.scope_function for persona in PERSONAS.values()}


def authority_users() -> list[Persona]:
    return [
        persona
        for persona in PERSONAS.values()
        if persona.uses_authority_mcp
    ]
