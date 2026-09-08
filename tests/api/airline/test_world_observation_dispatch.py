from api.server.world.runtime import SimulationRuntime
from verticals.airline.aog_constants import AOG_SCENARIO_ID, AOG_SENSOR_ID
from verticals.airline.schedule_constants import SCHED_SCENARIO_ID, SCHED_SENSOR_ID
from verticals.airline.worlds.scenario import AirlineWorld


def _world() -> AirlineWorld:
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    return world


def _sensor(world: AirlineWorld, actor_id: str):
    return next(
        event
        for event in world.runtime.journal
        if event.type == "sensor.tripped" and event.actor_id == actor_id
    )


def test_build_observation_dispatches_aog_sensor() -> None:
    world = _world()
    world.activate_scenario(AOG_SCENARIO_ID)
    sensor = _sensor(world, AOG_SENSOR_ID)

    observation = world.build_observation(sensor.to_dict())

    assert observation["workflow_type"] == "aog-engineering-recovery"
    assert observation["sensor_event_id"] == sensor.event_id


def test_build_observation_dispatches_schedule_sensor() -> None:
    world = _world()
    world.activate_scenario(SCHED_SCENARIO_ID)
    sensor = _sensor(world, SCHED_SENSOR_ID)

    observation = world.build_observation(sensor.to_dict())

    assert observation["workflow_type"] == "preemptive-schedule-resilience"
    assert observation["sensor_event_id"] == sensor.event_id
