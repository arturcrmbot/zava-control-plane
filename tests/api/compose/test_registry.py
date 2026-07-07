from api.server.services.compose import registry
from api.server.services.compose.session import ComposeSession


def test_register_sets_active_and_lookup():
    registry.reset()
    s = ComposeSession("cid1")
    registry.register(s)
    assert registry.get("cid1") is s
    assert registry.active() is s


def test_register_second_replaces_active():
    registry.reset()
    a, b = ComposeSession("a"), ComposeSession("b")
    registry.register(a)
    registry.register(b)
    assert registry.active() is b
    assert registry.get("a") is a
