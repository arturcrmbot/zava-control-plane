from __future__ import annotations

from api.shared.vertical_pack import VerticalRuntime
from api.shared.world_contracts import ObjectiveRoute, WorldPackRegistration


def resolve_world_pack(
    runtime: VerticalRuntime,
    name: str,
) -> WorldPackRegistration:
    try:
        return runtime.pack.worlds[name]
    except KeyError:
        raise ValueError(
            f"world {name!r} is not owned by vertical "
            f"{runtime.pack.name!r}; known worlds: "
            f"{sorted(runtime.pack.worlds)}"
        ) from None


def resolve_objective_route(
    registration: WorldPackRegistration,
    sensor_id: str,
) -> ObjectiveRoute:
    for route in registration.objective_routes:
        if route.sensor_id == sensor_id:
            return route
    raise ValueError(
        f"no objective route for sensor {sensor_id!r} "
        f"in world {registration.name!r}"
    )
