from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaTree:
    role: str
    manages: tuple["PersonaTree", ...] = ()


@dataclass(frozen=True)
class Function:
    name: str
    display: str
    operator_surface: str
    owns_domains: tuple[str, ...]
    ambient_agents: tuple[str, ...]
    kpis: tuple[str, ...]
    persona_hierarchy: PersonaTree
    kpi_schema_version: int = 1
