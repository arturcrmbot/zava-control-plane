import pytest
from api.server.services.compose import registry
from api.server.services.compose.session import ComposeSession
from api.server.routes import compose as compose_routes


class _Req:
    """Minimal Request stand-in for the loopback guard."""
    def __init__(self, xff=None, host="127.0.0.1"):
        self.headers = {"x-forwarded-for": xff} if xff else {}
        self.client = type("C", (), {"host": host})()


@pytest.mark.asyncio
async def test_ignite_spawns_supervisor_from_loopback(monkeypatch):
    registry.reset()
    registry.register(ComposeSession("cid"))
    monkeypatch.setattr(compose_routes, "_guard", lambda r: True)
    calls = {}
    def fake_popen(args, **kw):
        calls["args"] = args
        class P: pass
        return P()
    monkeypatch.setattr(compose_routes.subprocess, "Popen", fake_popen)
    res = await compose_routes.ignite("cid", _Req())
    assert res["ok"] is True
    assert "compose-ignite.sh" in " ".join(calls["args"])


@pytest.mark.asyncio
async def test_ignite_refuses_non_loopback(monkeypatch):
    registry.reset()
    registry.register(ComposeSession("cid"))
    called = {"popen": False}
    def fake_popen(args, **kw):
        called["popen"] = True
        class P: pass
        return P()
    monkeypatch.setattr(compose_routes.subprocess, "Popen", fake_popen)
    # A forwarded-for header means a proxy/public caller -> refuse, don't spawn.
    res = await compose_routes.ignite("cid", _Req(xff="203.0.113.5"))
    assert getattr(res, "status_code", None) == 403
    assert called["popen"] is False
