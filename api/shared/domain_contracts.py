from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping


PhaseKind = Literal["deterministic", "agent", "hitl"]


@dataclass(frozen=True)
class Phase:
    name: str
    kind: PhaseKind


@dataclass(frozen=True)
class HitlGate:
    gate_phase: str
    external_event: str
    persona: str
    wait_probability: float = 0.0
    sick_probability: float = 0.0
    holiday_probability: float = 0.0
    timeout_probability: float = 0.0
    override_probability: float = 0.0


@dataclass(frozen=True)
class RegionOverlay:
    extra_phases: tuple[Phase, ...] = ()
    policy_threshold_overrides: Mapping[str, float] = field(default_factory=dict)
    extra_hitl_gates: tuple[HitlGate, ...] = ()


@dataclass(frozen=True)
class WakeHint:
    event: str
    reason: str


@dataclass(frozen=True)
class Domain:
    workflow_type: str
    display_name: str
    workflow_id_prefix: str
    orchestrator_name: str
    operator_surface: str
    phases: tuple[Phase, ...]
    hitl_gates: tuple[HitlGate, ...]
    skills: tuple[str, ...]
    wake_hints: tuple[WakeHint, ...] = ()
    function: str | None = None
    stub: bool = False
    spawn_fn: str | None = None
    realistic_interval_seconds: int | None = None
    region_overlays: Mapping[str, RegionOverlay] = field(default_factory=dict)
    slow_burn: bool = False

    def phases_for_region(self, region: str | None) -> tuple[Phase, ...]:
        if not region:
            return self.phases
        overlay = self.region_overlays.get(region)
        if overlay is None or not overlay.extra_phases:
            return self.phases
        return self.phases + tuple(overlay.extra_phases)
