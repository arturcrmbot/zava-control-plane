from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from api.shared.vertical_pack import VerticalRuntime


router = APIRouter()


def runtime_payload(
    runtime: VerticalRuntime,
) -> dict[str, Any]:
    capabilities = set(runtime.pack.ui.capabilities)
    has_world_scene = False
    if runtime.world_name is not None:
        capabilities.add("world")
        has_world_scene = (
            runtime.pack.worlds[runtime.world_name].scene is not None
        )
    return {
        "vertical": {
            "name": runtime.pack.name,
            "display_name": runtime.pack.display_name,
            "manifest_version": runtime.pack.manifest_version,
            "fingerprint": runtime.fingerprint,
        },
        "world": runtime.world_name,
        "world_scale": runtime.world_scale_name,
        "capabilities": sorted(capabilities),
        "ui": {
            "lenses": list(runtime.pack.ui.lenses),
            "theme": dict(runtime.pack.ui.theme),
            "world_scene": has_world_scene,
        },
    }


@router.get("/api/runtime")
async def get_runtime_manifest() -> dict[str, Any]:
    from api.server.runtime_context import current_runtime

    return runtime_payload(current_runtime())
