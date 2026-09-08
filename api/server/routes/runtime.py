from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from api.shared.vertical_pack import VerticalRuntime


router = APIRouter()


def _runnable_workflow_types() -> frozenset[str]:
    """Workflow types the active world can actually start on demand.

    Published per domain so the /world "Run scenario" row only renders buttons
    the backend will accept. Without it a pack whose scenario doesn't declare
    ``reference_process_types`` (or declares a partial set) renders buttons
    that fail with "unknown reference process" when clicked.
    """
    try:
        from api.server.routes.world import runnable_reference_processes
        from api.server.state import app_state

        service = getattr(app_state, "world_service", None)
        if service is None:
            return frozenset()
        return runnable_reference_processes(service)
    except Exception:  # noqa: BLE001 -- manifest must never fail to render
        return frozenset()


def runtime_payload(
    runtime: VerticalRuntime,
) -> dict[str, Any]:
    capabilities = set(runtime.pack.ui.capabilities)
    has_world_scene = False
    if runtime.world_name is not None:
        capabilities.add("world")
        has_world_scene = runtime.pack.worlds[runtime.world_name].scene is not None

    ui: dict[str, Any] = {
        "lenses": list(runtime.pack.ui.lenses),
        "theme": dict(runtime.pack.ui.theme),
        "world_scene": has_world_scene,
    }
    if runtime.pack.ui.world_scene is not None:
        ui["world_scene"] = runtime.pack.ui.world_scene.to_metadata()

    domains = [
        {
            "workflow_type": domain.workflow_type,
            "display_name": domain.display_name,
            "runnable": domain.workflow_type in _runnable_workflow_types(),
        }
        for _, domain in sorted(runtime.pack.domains.items())
    ]

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
        "domains": domains,
        "ui": ui,
    }


@router.get("/api/runtime")
async def get_runtime_manifest() -> dict[str, Any]:
    from api.server.runtime_context import current_runtime

    return runtime_payload(current_runtime())
