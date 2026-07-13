"""Neutral support-queue toy world — the engine's permanent industry guard.

Baseline arrival (30/h) < service capacity (20 agents * 2/h = 40/h) so the
backlog stays drained. A manual `demand_surge` (+60/h for 3 ticks) pushes
arrival to 90/h; backlog climbs, `sla_breach_pct` crosses 0.5, the sensor
emits `ops.surge_staffing.requested`. A responder completing
`surge-staffing.completed` with `hired` feeds the actuator, raising capacity
until the backlog drains again.
"""
from api.server.world.contract import (
    Stock, Flow, Signal, Resource, Perturbation, Sensor, Actuator, WorldPack,
)

PACK = WorldPack(
    name="toy",
    stocks=(Stock("support_backlog", initial=0.0, min=0.0, max=None),),
    resources=(Resource("agents", capacity=20.0),),
    inputs={"ticket_arrival_rate": 30.0},
    constants={"HANDLE": 2.0},
    flows=(
        Flow(into="support_backlog", rate=lambda w: w["ticket_arrival_rate"]),
        Flow(into="support_backlog", rate=lambda w: -(w["agents"] * w["HANDLE"])),
    ),
    signals=(
        Signal("sla_breach_pct",
               lambda w: w["support_backlog"] / max(w["support_backlog"] + w["agents"] * w["HANDLE"], 1)),
    ),
    perturbations=(
        Perturbation("demand_surge", target="ticket_arrival_rate", magnitude=60.0, duration_ticks=3),
    ),
    sensors=(
        Sensor("backlog_high", when=lambda w: w["sla_breach_pct"] > 0.5,
               emit="ops.surge_staffing.requested"),
    ),
    actuators=(
        Actuator("hire", on="surge-staffing.completed", target="agents",
                 effect=lambda ev: ev.get("hired", 0)),
    ),
)
