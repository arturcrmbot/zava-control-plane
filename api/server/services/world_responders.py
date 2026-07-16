from __future__ import annotations

from api.shared.vertical_pack import VerticalRuntime
from api.shared.world_contracts import ResponderRegistration


def resolve_responder(
    runtime: VerticalRuntime,
    objective_type: str,
) -> ResponderRegistration:
    responders = {
        responder_type: responder
        for world in runtime.pack.worlds.values()
        for responder_type, responder in world.responders.items()
    }
    try:
        return responders[objective_type]
    except KeyError:
        raise ValueError(
            f"no responder for objective type {objective_type!r} "
            f"in vertical {runtime.pack.name!r}; "
            f"known types: {sorted(responders)}"
        ) from None
