from __future__ import annotations

import os
from dataclasses import dataclass

from api.shared.domains import DOMAINS, live_domains


@dataclass(frozen=True, slots=True)
class VerticalProfile:
    name: str
    world: str
    workflow_types: tuple[str, ...]
    ramp_workflow_types: tuple[str, ...]


_TELCO = VerticalProfile(
    name="telco",
    world="telco",
    workflow_types=(
        "network-incident",
        "proactive-customer-care",
        "order-to-activate",
    ),
    ramp_workflow_types=(),
)

_PROFILES: dict[str, VerticalProfile] = {
    _TELCO.name: _TELCO,
}


def active_vertical() -> VerticalProfile | None:
    raw = os.getenv("ZAVA_VERTICAL")
    if raw is None:
        return None
    name = raw.strip().lower()
    if not name:
        return None
    try:
        return _PROFILES[name]
    except KeyError as ex:
        raise ValueError(f"Unknown ZAVA_VERTICAL={raw!r}") from ex


def registered_workflow_types() -> tuple[str, ...]:
    profile = active_vertical()
    if profile is None:
        return tuple(DOMAINS.keys())
    live_workflow_types = {domain.workflow_type for domain in live_domains()}
    return tuple(
        workflow_type
        for workflow_type in profile.workflow_types
        if workflow_type in live_workflow_types
    )
