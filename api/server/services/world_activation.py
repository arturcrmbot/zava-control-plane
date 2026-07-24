"""Eligibility policy for the live actor-world service."""
from __future__ import annotations

from api.shared.vertical_pack import VerticalRuntime


def should_start_actor_world(
    runtime: VerticalRuntime,
    *,
    world_name: str | None,
    actor_world_enabled: bool,
) -> bool:
    """Start only the effective registered world when enabled."""
    return (
        actor_world_enabled
        and world_name is not None
        and world_name in runtime.pack.worlds
    )
