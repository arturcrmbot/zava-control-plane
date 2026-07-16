from __future__ import annotations

from pathlib import Path

from api.shared.vertical_pack import (
    DurableFunctionRegistration,
    LifecycleRegistration,
    RecordingSources,
    SeedRegistration,
    VerticalPack,
    VerticalUiManifest,
)
from api.shared.world_contracts import WorldPackRegistration, WorldScaleProfile


async def _start(_state):
    return ()


def make_test_pack(name: str, root: Path) -> VerticalPack:
    world_name = "support" if name == "agency" else "telco"
    world = WorldPackRegistration(
        name=world_name,
        scales={
            "demo": WorldScaleProfile(
                name="demo",
                build_scenario=lambda _runtime: None,
                default_minutes_per_second=10.0,
            ),
        },
        default_scale="demo",
        objective_routes=(),
        responders={},
    )
    return VerticalPack(
        root=root / name,
        name=name,
        display_name=name.title(),
        manifest_version="1",
        domains={},
        organisation_functions={},
        agents={},
        authority={},
        policy_sources=(),
        durable_functions=DurableFunctionRegistration(
            register=lambda _app: None,
            orchestrators=frozenset(),
            activities=frozenset(),
        ),
        personae_roots=(),
        skill_roots=(),
        mcp_modules=(),
        external_capabilities=frozenset(),
        worlds={world_name: world},
        default_world=None if name == "agency" else world_name,
        seed=SeedRegistration(bootstrap=lambda _state: None),
        projections={},
        memory_workflow_types=(),
        lifecycle=LifecycleRegistration(start=_start),
        recordings=RecordingSources(curated_dirs=()),
        ui=VerticalUiManifest(
            capabilities=frozenset(),
            lenses=(),
            theme={},
            phase_aliases={},
        ),
        ramp_workflow_types=(),
    )
