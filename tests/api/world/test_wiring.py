import asyncio
import contextlib
import pytest
from api.server.services.event_bus import EventBus
from api.server.world import active_world_name, load_pack, maybe_start_world


def test_active_world_name_reads_env(monkeypatch):
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    assert active_world_name() is None
    monkeypatch.setenv("ZAVA_WORLD", "toy")
    assert active_world_name() == "toy"


def test_load_toy_pack():
    pack = load_pack("toy")
    assert pack.name == "toy"
    assert any(s.name == "support_backlog" for s in pack.stocks)
    assert any(sen.emit == "ops.surge_staffing.requested" for sen in pack.sensors)


def test_load_unknown_pack_raises():
    with pytest.raises(Exception):
        load_pack("does_not_exist")


@pytest.mark.asyncio
async def test_maybe_start_world_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    assert maybe_start_world(EventBus()) is None


@pytest.mark.asyncio
async def test_maybe_start_world_starts_and_ticks(monkeypatch):
    monkeypatch.setenv("ZAVA_WORLD", "toy")
    bus = EventBus()
    ticks = []
    bus.on("world.tick", lambda e: ticks.append(e))
    task = maybe_start_world(bus, tick_seconds=0.0)
    assert task is not None
    await asyncio.sleep(0.02)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert len(ticks) >= 1
