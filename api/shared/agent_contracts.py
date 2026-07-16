from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentRegistryEntry:
    agent_id: str
    allowed_tools: tuple[str, ...] = field(default_factory=tuple)
    max_value_gbp: float | None = None
    reversible_only: bool = True
    scope_function: str = "shared"
    description: str = ""
