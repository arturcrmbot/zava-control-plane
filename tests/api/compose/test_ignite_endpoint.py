import pytest
from api.server.services.compose import registry
from api.server.services.compose.session import ComposeSession
from api.server.routes import compose as compose_routes


@pytest.mark.asyncio
async def test_ignite_spawns_supervisor(monkeypatch):
    registry.reset()
    registry.register(ComposeSession("cid"))
    calls = {}
    def fake_popen(args, **kw):
        calls["args"] = args
        class P: pass
        return P()
    monkeypatch.setattr(compose_routes.subprocess, "Popen", fake_popen)
    res = await compose_routes.ignite("cid")
    assert res["ok"] is True
    assert "compose-ignite.sh" in " ".join(calls["args"])
