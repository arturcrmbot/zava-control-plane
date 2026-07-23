from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

import pytest

from api.server.state import app_state


@pytest.mark.asyncio
async def test_scene_route_returns_the_active_pack_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = import_module("api.server.routes.world")
    handler = getattr(routes, "world_scene", None)
    assert callable(handler)
    scene = {
        "schema_version": 1,
        "title": "Demo",
        "locations": [{"id": "LOC-1"}],
        "layers": [{"state_key": "people"}],
        "event_mappings": [{"event_type": "person.moved"}],
    }
    service = SimpleNamespace(
        registration=SimpleNamespace(scene=scene),
    )
    monkeypatch.setattr(app_state, "world_service", service, raising=False)

    assert await handler() == {"enabled": True, **scene}


@pytest.mark.asyncio
async def test_reset_route_reinstalls_seeded_world(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = import_module("api.server.routes.world")
    handler = getattr(routes, "reset_world", None)
    request_type = getattr(routes, "WorldResetRequest", None)
    assert callable(handler)
    assert request_type is not None
    lifecycle: list[str] = []
    service = SimpleNamespace(
        seed=42,
        runtime=SimpleNamespace(now=0),
        reset=lambda seed: lifecycle.append(f"reset:{seed}"),
    )
    bridge = SimpleNamespace(
        stop=lambda: lifecycle.append("bridge:stop"),
        start=lambda: lifecycle.append("bridge:start"),
    )
    monkeypatch.setattr(app_state, "world_service", service, raising=False)
    monkeypatch.setattr(app_state, "world_bridge", bridge, raising=False)

    result = await handler(request_type(seed=7))

    assert lifecycle == ["bridge:stop", "reset:7", "bridge:start"]
    assert result == {"ok": True, "seed": 7, "sim_time": 0}
