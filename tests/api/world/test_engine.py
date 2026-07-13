from api.server.services.event_bus import EventBus
from api.server.world.contract import (
    Stock, Flow, Signal, Resource, Perturbation, Sensor, WorldPack,
)
from api.server.world.engine import WorldState, WorldEngine


def _pack():
    return WorldPack(
        name="t",
        stocks=(Stock("backlog", initial=0.0, min=0.0, max=None),),
        resources=(Resource("agents", capacity=20.0),),
        inputs={"arrival": 30.0},
        constants={"HANDLE": 2.0},
        flows=(
            Flow(into="backlog", rate=lambda w: w["arrival"]),
            Flow(into="backlog", rate=lambda w: -(w["agents"] * w["HANDLE"])),
        ),
        signals=(
            Signal("breach", lambda w: w["backlog"] / max(w["backlog"] + w["agents"] * w["HANDLE"], 1)),
        ),
        perturbations=(
            Perturbation("surge", target="arrival", magnitude=60.0, duration_ticks=2),
        ),
        sensors=(
            Sensor("hot", when=lambda w: w["breach"] > 0.5, emit="ops.hot"),
        ),
    )


def test_state_accessor_reads_across_categories_and_clamps_add():
    s = WorldState(_pack())
    assert s["backlog"] == 0.0 and s["agents"] == 20.0
    assert s["arrival"] == 30.0 and s["HANDLE"] == 2.0
    s.add("backlog", -100.0)
    assert s.stocks["backlog"] == 0.0        # clamped at min
    s.add("agents", 40.0)
    assert s.resources["agents"] == 60.0     # resources unbounded


def test_tick_integrates_flows_and_recomputes_signals():
    engine = WorldEngine(_pack(), EventBus())
    engine.tick()
    # inflow 30, outflow 40 -> net -10 -> clamped at 0
    assert engine.state.stocks["backlog"] == 0.0
    assert engine.state.signals["breach"] == 0.0


def test_tick_publishes_world_tick():
    bus = EventBus()
    seen = []
    bus.on("world.tick", lambda e: seen.append(e))
    WorldEngine(_pack(), bus).tick()
    assert len(seen) == 1
    assert seen[0].world == "t" and "breach" in seen[0].signals


def test_manual_perturbation_offsets_input_for_its_duration():
    engine = WorldEngine(_pack(), EventBus())
    engine.inject("surge")
    engine.tick()   # arrival 90, out 40 -> backlog 50
    assert engine.state.stocks["backlog"] == 50.0
    engine.tick()   # surge tick 2: arrival 90, out 40 -> +50 -> 100
    assert engine.state.stocks["backlog"] == 100.0
    engine.tick()   # surge expired: arrival 30, out 40 -> -10 -> 90
    assert engine.state.stocks["backlog"] == 90.0


def test_sensor_fires_once_on_rising_edge():
    bus = EventBus()
    fired = []
    bus.on("ops.hot", lambda e: fired.append(e))
    engine = WorldEngine(_pack(), bus)
    engine.tick()                 # backlog 0, breach 0 -> quiet
    assert fired == []
    engine.inject("surge")
    engine.tick()                 # backlog 50 -> breach 50/90 > 0.5 -> fire
    engine.tick()                 # still hot -> latched, no refire
    assert len(fired) == 1 and fired[0].sensor == "hot"


import asyncio
import contextlib
import pytest
from api.shared.events import FleetEvent
from api.server.world.contract import Actuator, WorldPack, Stock, Resource


def _feedback_pack():
    return WorldPack(
        name="fb",
        resources=(Resource("agents", capacity=20.0),),
        actuators=(
            Actuator("hire", on="surge-staffing.completed", target="agents",
                     effect=lambda ev: ev.get("hired", 0)),
        ),
    )


def test_actuator_applies_delta_from_completion_event():
    engine = WorldEngine(_feedback_pack(), EventBus())
    engine.attach()
    engine.bus.emit(FleetEvent(type="surge-staffing.completed", hired=15))
    assert engine.state.resources["agents"] == 35.0


def test_actuator_ignores_unrelated_and_malformed_events():
    engine = WorldEngine(_feedback_pack(), EventBus())
    engine.attach()
    engine.bus.emit(FleetEvent(type="something.else", hired=15))     # not subscribed
    engine.bus.emit(FleetEvent(type="surge-staffing.completed"))     # no 'hired' -> 0
    assert engine.state.resources["agents"] == 20.0


@pytest.mark.asyncio
async def test_run_loop_ticks_until_stopped():
    engine = WorldEngine(_pack(), EventBus())
    ticks = []
    engine.bus.on("world.tick", lambda e: ticks.append(e))
    task = asyncio.create_task(engine.run(tick_seconds=0.0))
    await asyncio.sleep(0.02)
    engine.stop()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1.0)
    assert len(ticks) >= 1


def test_closed_loop_surge_triggers_hiring_then_recovers():
    # Toy-shaped pack with the full loop: surge -> sensor -> (stub responder) -> actuator -> drain.
    pack = WorldPack(
        name="loop",
        stocks=(Stock("backlog", initial=0.0, min=0.0, max=None),),
        resources=(Resource("agents", capacity=20.0),),
        inputs={"arrival": 30.0},
        constants={"HANDLE": 2.0},
        flows=(
            Flow(into="backlog", rate=lambda w: w["arrival"]),
            Flow(into="backlog", rate=lambda w: -(w["agents"] * w["HANDLE"])),
        ),
        signals=(Signal("breach", lambda w: w["backlog"] / max(w["backlog"] + w["agents"] * w["HANDLE"], 1)),),
        perturbations=(Perturbation("surge", target="arrival", magnitude=60.0, duration_ticks=3),),
        sensors=(Sensor("hot", when=lambda w: w["breach"] > 0.5, emit="ops.surge_staffing.requested"),),
        actuators=(Actuator("hire", on="surge-staffing.completed", target="agents",
                            effect=lambda ev: ev.get("hired", 0)),),
    )
    bus = EventBus()
    fired = []
    bus.on("ops.surge_staffing.requested", lambda e: fired.append(e))
    # Stub responder: a surge request "hires" 60 agent-capacity.
    bus.on("ops.surge_staffing.requested",
           lambda e: bus.emit(FleetEvent(type="surge-staffing.completed", hired=60)))

    engine = WorldEngine(pack, bus)
    engine.attach()
    for _ in range(3):
        engine.tick()
    assert engine.state.stocks["backlog"] == 0.0 and fired == []

    engine.inject("surge")
    for _ in range(4):
        engine.tick()
    assert len(fired) >= 1
    assert engine.state.resources["agents"] >= 80.0     # 20 + 60 hired

    for _ in range(10):
        engine.tick()
    assert engine.state.stocks["backlog"] == 0.0        # extra capacity drained it
