from api.server.world.contract import (
    Stock, Flow, Signal, Resource, Perturbation, Sensor, Actuator, WorldPack,
)


def test_primitives_construct_with_expected_defaults():
    assert Stock("backlog").min == 0.0 and Stock("backlog").max is None
    assert Flow(into="backlog", rate=lambda w: 1.0).out_of is None
    assert Signal("sla", lambda w: 0.5).formula(None) == 0.5
    assert Resource("agents", capacity=20.0).capacity == 20.0
    assert Perturbation("surge", target="arrival", magnitude=60.0).duration_ticks == 1
    assert Sensor("hot", when=lambda w: True, emit="ops.x").emit == "ops.x"
    assert Actuator("hire", on="x.done", target="agents",
                    effect=lambda ev: ev["hired"]).effect({"hired": 3}) == 3


def test_worldpack_groups_declarations_with_empty_defaults():
    pack = WorldPack(
        name="t",
        stocks=(Stock("backlog"),),
        inputs={"arrival": 30.0},
        constants={"HANDLE": 2.0},
    )
    assert pack.name == "t"
    assert pack.stocks[0].name == "backlog"
    assert pack.inputs["arrival"] == 30.0
    assert pack.flows == () and pack.sensors == ()
