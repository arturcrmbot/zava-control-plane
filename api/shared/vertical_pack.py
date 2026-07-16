from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.shared.agent_contracts import AgentRegistryEntry
from api.shared.authority_contracts import AuthorityRow
from api.shared.domain_contracts import Domain
from api.shared.function_contracts import Function
from api.shared.projection_contracts import ProjectionFn
from api.shared.world_contracts import WorldPackRegistration


StopAction = Callable[[], Any]


@dataclass(frozen=True, slots=True)
class DurableFunctionRegistration:
    load_module: Callable[[], Any]
    orchestrators: frozenset[str]
    activities: frozenset[str]


@dataclass(frozen=True, slots=True)
class RecordingSources:
    curated_dirs: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class VerticalUiManifest:
    capabilities: frozenset[str]
    lenses: tuple[str, ...]
    theme: Mapping[str, str]
    phase_aliases: Mapping[str, Mapping[str, str]]
    aspirational_domains: tuple[str, ...] = ()
    include_meta_skills: bool = False


@dataclass(frozen=True, slots=True)
class SeedRegistration:
    bootstrap: Callable[[Any], None]


@dataclass(frozen=True, slots=True)
class LifecycleRegistration:
    start: Callable[[Any], Awaitable[Sequence[StopAction]]]


@dataclass(frozen=True, slots=True)
class VerticalPack:
    root: Path
    name: str
    display_name: str
    manifest_version: str
    domains: Mapping[str, Domain]
    organisation_functions: Mapping[str, Function]
    agents: Mapping[str, AgentRegistryEntry]
    authority: Mapping[str, AuthorityRow]
    policy_sources: tuple[Path, ...]
    durable_functions: DurableFunctionRegistration
    personae_roots: tuple[Path, ...]
    skill_roots: tuple[Path, ...]
    mcp_modules: tuple[str, ...]
    external_capabilities: frozenset[str]
    worlds: Mapping[str, WorldPackRegistration]
    default_world: str | None
    seed: SeedRegistration
    projections: Mapping[str, ProjectionFn]
    memory_workflow_types: tuple[str, ...]
    lifecycle: LifecycleRegistration
    recordings: RecordingSources
    ui: VerticalUiManifest
    ramp_workflow_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VerticalRuntime:
    pack: VerticalPack
    world_name: str | None
    world_scale_name: str | None
    data_dir: Path
    fingerprint: str
