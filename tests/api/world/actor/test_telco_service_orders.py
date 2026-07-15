from api.server.services.event_bus import EventBus
from api.server.world.model import SimulationCommand
from api.server.world.service import ActorWorldService


def _world():
    return ActorWorldService.telco(
        seed=42, bus=EventBus(), minutes_per_second=1000
    )


def test_submit_service_order_emits_routable_sensor_observation():
    world = _world()

    order_id = world.submit_service_order(
        account_id="ACC-00001",
        product="fiber-1gb",
        requested_site_id="SITE-02",
    )

    sensor = world.runtime.journal[-1]
    assert sensor.type == "sensor.tripped"
    assert sensor.actor_id == "sensor:service_order"
    observation = world.build_observation(sensor.to_dict())
    assert observation["order"]["id"] == order_id
    assert observation["account"]["id"] == "ACC-00001"
    assert observation["requested_site"]["id"] == "SITE-02"


def test_activation_command_updates_order_and_creates_subscription():
    world = _world()
    order_id = world.submit_service_order(
        account_id="ACC-00001",
        product="fiber-1gb",
        requested_site_id="SITE-02",
    )
    sensor = world.runtime.journal[-1]
    route = next(
        route
        for route in world.registration.objective_routes
        if route.sensor_id == "sensor:service_order"
    )
    objective = world.open_objective(
        sensor.to_dict(), route, owner_function="service_fulfillment"
    )
    world.transition_objective(
        objective.id, "claimed", claimed_by="service_fulfillment"
    )
    world.transition_objective(objective.id, "acting")
    command = SimulationCommand(
        command_id=f"activate-{order_id}",
        trace_id=sensor.trace_id,
        issued_by="service_fulfillment",
        type="activate_service_order",
        payload={"order_id": order_id, "capacity_approved": False},
    )

    result = world.apply_typed_command(objective, command)

    assert result.type == "command.accepted"
    assert world.scenario.orders[order_id].status == "activated"
    assert any(
        subscription.account_id == "ACC-00001"
        and subscription.product == "fiber-1gb"
        for subscription in world.scenario.subscriptions.values()
    )
    assert any(
        event.type == "order.activated" and event.trace_id == sensor.trace_id
        for event in world.runtime.journal
    )
