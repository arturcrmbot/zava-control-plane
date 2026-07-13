from api.server.world.packs.support import DemandSurge, SupportConfig, run_support


def _small_config() -> SupportConfig:
    return SupportConfig(
        customer_count=120,
        worker_count=9,
        arrival_rate_per_hour=45,
        simulation_minutes=180,
        sla_minutes=30,
        sensor_backlog_threshold=10_000,
        sensor_recovery_threshold=5_000,
    )


def test_support_world_contains_real_customers_workers_and_tickets():
    scenario = run_support(seed=11, config=_small_config())
    assert len(scenario.customers) == 120
    assert len(scenario.workers) == 9
    assert len(scenario.tickets) > 0
    assert {e.type for e in scenario.runtime.journal} >= {
        "customer.created", "worker.created", "ticket.arrived", "ticket.queued"
    }


def test_assigned_tickets_match_worker_skills_and_workers_do_not_double_serve():
    scenario = run_support(seed=12, config=_small_config())
    active: dict[str, str] = {}
    for event in scenario.runtime.journal:
        if event.type == "ticket.service_started":
            worker_id = event.payload["worker_id"]
            ticket = scenario.tickets[event.actor_id]
            worker = scenario.workers[worker_id]
            assert ticket.required_skill in worker.skills
            assert worker_id not in active
            active[worker_id] = ticket.id
        elif event.type in {"ticket.resolved", "ticket.abandoned"}:
            worker_id = event.payload.get("worker_id")
            if worker_id:
                active.pop(worker_id, None)


def test_ticket_terminal_states_are_mutually_exclusive():
    scenario = run_support(seed=13, config=_small_config())
    terminal_events: dict[str, list[str]] = {}
    for event in scenario.runtime.journal:
        if event.type in {"ticket.resolved", "ticket.abandoned"}:
            terminal_events.setdefault(event.actor_id, []).append(event.type)
    assert terminal_events
    assert all(len(types) == 1 for types in terminal_events.values())


def test_scheduled_surge_is_a_real_journalled_input():
    surge = DemandSurge(at_minute=30, multiplier=6, duration_minutes=45)
    scenario = run_support(seed=14, config=_small_config(), surges=(surge,))
    events = scenario.runtime.journal
    started = next(e for e in events if e.type == "perturbation.started")
    ended = next(e for e in events if e.type == "perturbation.ended")
    assert started.payload["multiplier"] == 6
    assert ended.cause_event_id == started.event_id
    assert any(
        e.type == "ticket.arrived" and e.payload["arrival_multiplier"] == 6
        for e in events
    )


def test_every_causal_reference_points_to_an_earlier_event():
    scenario = run_support(seed=15, config=_small_config())
    positions = {event.event_id: event.seq for event in scenario.runtime.journal}
    for event in scenario.runtime.journal:
        if event.cause_event_id:
            assert positions[event.cause_event_id] < event.seq


def test_sla_observation_does_not_hijack_lifecycle_cause():
    scenario = run_support(seed=13, config=_small_config())
    by_id = {event.event_id: event for event in scenario.runtime.journal}
    lifecycle_types = {"ticket.assigned", "ticket.resolved", "ticket.abandoned"}
    for event in scenario.runtime.journal:
        if event.type in lifecycle_types and event.cause_event_id:
            assert by_id[event.cause_event_id].type != "ticket.sla_breached"
