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
