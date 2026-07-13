from api.server.world.packs.support import SupportConfig, run_support
from api.server.world.projection import project_support


def test_projection_is_derived_from_actor_state():
    scenario = run_support(
        seed=21,
        config=SupportConfig(
            customer_count=100,
            worker_count=6,
            arrival_rate_per_hour=80,
            simulation_minutes=120,
            sensor_backlog_threshold=10_000,
            sensor_recovery_threshold=5_000,
        ),
    )
    projection = project_support(scenario)
    assert projection.support_backlog == sum(
        ticket.status == "queued" for ticket in scenario.tickets.values()
    )
    assert projection.workers_busy == sum(
        worker.status == "busy" for worker in scenario.workers.values()
    )
    assert projection.tickets_opened == len(scenario.tickets)
    assert 0.0 <= projection.sla_breach_pct <= 1.0
    assert 0.0 <= projection.customer_sentiment <= 1.0


def test_overloaded_actor_world_trips_sensor_with_real_ticket_ids():
    scenario = run_support(
        seed=22,
        config=SupportConfig(
            customer_count=200,
            worker_count=3,
            arrival_rate_per_hour=180,
            simulation_minutes=90,
            sensor_backlog_threshold=8,
            sensor_recovery_threshold=3,
        ),
    )
    sensor = next(e for e in scenario.runtime.journal if e.type == "sensor.tripped")
    assert sensor.payload["measurements"]["support_backlog"] >= 8
    assert sensor.payload["actor_ids"]
    assert all(actor_id in scenario.tickets for actor_id in sensor.payload["actor_ids"])
    assert sensor.cause_event_id is not None


def test_live_queue_index_matches_authoritative_ticket_state():
    scenario = run_support(
        seed=23,
        config=SupportConfig(
            customer_count=150,
            worker_count=6,
            arrival_rate_per_hour=120,
            simulation_minutes=120,
            sensor_backlog_threshold=10_000,
            sensor_recovery_threshold=5_000,
        ),
    )
    expected = [
        ticket.id for ticket in scenario.tickets.values() if ticket.status == "queued"
    ]
    assert list(scenario.queued_ticket_ids) == expected


def test_sensor_does_not_full_project_until_an_edge(monkeypatch):
    import api.server.world.projection as projection_module

    calls = 0
    original = projection_module.project_support

    def counted(scenario):
        nonlocal calls
        calls += 1
        return original(scenario)

    monkeypatch.setattr(projection_module, "project_support", counted)
    run_support(
        seed=24,
        config=SupportConfig(
            customer_count=150,
            worker_count=9,
            arrival_rate_per_hour=45,
            simulation_minutes=180,
            sensor_backlog_threshold=10_000,
            sensor_recovery_threshold=5_000,
        ),
    )
    assert calls == 0
