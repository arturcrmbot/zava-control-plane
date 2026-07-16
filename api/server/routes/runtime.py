from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from api.shared.vertical_pack import VerticalRuntime


router = APIRouter()


def runtime_payload(
    runtime: VerticalRuntime,
    readiness: Any | None = None,
) -> dict[str, Any]:
    capabilities = set(runtime.pack.ui.capabilities)
    if runtime.world_name is not None:
        capabilities.add("world")
    readiness_payload = (
        {
            "functions": getattr(readiness, "status", "unavailable"),
            "scheduling_enabled": bool(
                getattr(readiness, "scheduling_enabled", False)
            ),
        }
        if readiness is not None
        else {
            "functions": "unavailable",
            "scheduling_enabled": False,
        }
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
        },
        "readiness": readiness_payload,
    }


@router.get("/api/runtime")
async def get_runtime_manifest() -> dict[str, Any]:
    from api.server.state import app_state
    from api.server.runtime_context import current_runtime

    return runtime_payload(
        current_runtime(),
        getattr(app_state, "functions_readiness", None),
    )
