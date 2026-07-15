from api.server.services.event_bus import EventBus
from api.server.world.model import SimulationCommand
from api.server.world.service import ActorWorldService


def _world():
    return ActorWorldService.telco(seed=42, bus=EventBus(), minutes_per_second=1000)


def _impact(world):
    world.inject_site_failure("SITE-01")
    world.runtime.run_until(2)
    return next(
        event
        for event in world.runtime.journal
        if event.type == "sensor.tripped"
        and event.actor_id == "sensor:customer_impact"
    )


def _remediation(impact, actions, command_id="care-1"):
    return SimulationCommand(
        command_id=command_id,
        trace_id=impact.trace_id,
        issued_by="customer_care",
        type="apply_customer_remediation",
        payload={"actions": actions},
    )


def test_install_creates_referentially_aligned_commercial_state():
    world = _world()
    scenario = world.scenario

    assert len(scenario.accounts) == len(scenario.subscribers) == 2_000
    assert len(scenario.subscriptions) == 2_000
    for subscriber in scenario.subscribers.values():
        account = scenario.accounts[subscriber.account_id]
        subscription = scenario.subscriptions[subscriber.subscription_id]
        assert account.subscriber_id == subscriber.id
        assert subscription.account_id == account.id
        assert subscription.subscriber_id == subscriber.id
        assert subscription.site_id == subscriber.home_site_id


def test_deterministic_hero_records_have_stable_ids():
    world = _world()
    scenario = world.scenario

    assert scenario.accounts["ACC-00001"].segment == "priority_business"
    assert scenario.accounts["ACC-00002"].vulnerable is True
    assert scenario.accounts["ACC-00003"].approval_required is True
    assert scenario.orders["ORD-00001"].status == "infeasible"


def test_customer_impact_sensor_uses_root_trace_and_real_accounts():
    world = _world()
    impact = _impact(world)
    failed = next(event for event in world.runtime.journal if event.type == "site.failed")

    assert impact.trace_id == failed.trace_id
    assert impact.payload["measurements"]["affected_account_count"] > 0
    assert impact.payload["account_ids"]
    assert all(account_id in world.scenario.accounts for account_id in impact.payload["account_ids"])
    observation = world.build_observation(impact.to_dict())
    assert observation["impacted_accounts"]
    assert observation["trace_id"] == failed.trace_id


def test_customer_remediation_is_atomic_and_idempotent():
    world = _world()
    impact = _impact(world)
    account_id = impact.payload["account_ids"][0]
    account = world.scenario.accounts[account_id]
    expected_credit = (
        50.0
        if account.approval_required
        else 20.0
        if account.vulnerable
        else 10.0
        if account.segment == "priority_business"
        else 5.0
    )
    action = {
        "account_id": account_id,
        "channel": "sms",
        "message": "We restored your service.",
        "credit_amount": expected_credit,
        "authority_approved": True,
    }
    command = _remediation(impact, [action])

    first = world.apply_command(command)
    journal_count = len(world.runtime.journal)
    second = world.apply_command(command)

    assert first.type == "command.accepted"
    assert second.event_id == first.event_id
    assert len(world.runtime.journal) == journal_count
    account = world.scenario.accounts[account_id]
    assert account.total_credits == expected_credit
    assert any(item.account_id == account_id for item in world.scenario.notifications.values())
    assert any(item.account_id == account_id for item in world.scenario.credits.values())
    assert any(
        event.type == "care.completed" and event.trace_id == impact.trace_id
        for event in world.runtime.journal
    )


def test_invalid_customer_remediation_mutates_nothing():
    world = _world()
    impact = _impact(world)
    valid_account = impact.payload["account_ids"][0]
    before = world.scenario.accounts[valid_account].total_credits
    command = _remediation(
        impact,
        [
            {
                "account_id": valid_account,
                "channel": "sms",
                "message": "Valid first action",
                "credit_amount": 5.0,
                "authority_approved": True,
            },
            {
                "account_id": "ACC-99999",
                "channel": "sms",
                "message": "Invalid second action",
                "credit_amount": 5.0,
                "authority_approved": True,
            },
        ],
    )

    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert world.scenario.accounts[valid_account].total_credits == before
    assert world.scenario.notifications == {}
    assert world.scenario.credits == {}


def test_customer_remediation_rejects_credit_above_server_policy():
    world = _world()
    impact = _impact(world)
    account_id = impact.payload["account_ids"][0]
    command = _remediation(
        impact,
        [{
            "account_id": account_id,
            "channel": "sms",
            "message": "Service restored.",
            "credit_amount": 5000.0,
            "authority_approved": True,
        }],
    )

    result = world.apply_command(command)

    assert result.type == "command.rejected"
    assert "policy entitlement" in result.payload["reason"]


def test_snapshot_exposes_commercial_actors_and_impact_projection():
    world = _world()
    _impact(world)
    snapshot = world.snapshot()

    assert len(snapshot["accounts"]) == 2_000
    assert len(snapshot["subscriptions"]) == 2_000
    assert snapshot["orders"]
    assert snapshot["customer_impact"]["affected_account_count"] > 0
