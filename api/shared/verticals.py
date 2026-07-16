from __future__ import annotations

from dataclasses import dataclass

from api.shared.vertical_loader import active_runtime


@dataclass(frozen=True, slots=True)
class VerticalProfile:
    name: str
    world: str | None
    workflow_types: tuple[str, ...]
    ramp_workflow_types: tuple[str, ...]


def active_vertical() -> VerticalProfile:
    runtime = active_runtime()
    return VerticalProfile(
        name=runtime.pack.name,
        world=runtime.world_name,
        workflow_types=tuple(runtime.pack.domains),
        ramp_workflow_types=runtime.pack.ramp_workflow_types,
    )


def registered_workflow_types() -> tuple[str, ...]:
    return tuple(active_runtime().pack.domains)
