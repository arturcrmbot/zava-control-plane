from api.server.world.model import SimulationCommand
from api.server.world.packs.support import SupportConfig, SupportScenario
from api.server.world.runtime import SimulationRuntime


def scenario_with_reserve() -> SupportScenario:
    runtime = SimulationRuntime(seed=31)
    scenario = SupportScenario(
        runtime,
        SupportConfig(
            customer_count=50,
            worker_count=12,
            reserve_worker_count=3,
            arrival_rate_per_hour=0.1,
            simulation_minutes=180,
            sensor_backlog_threshold=10_000,
            sensor_recovery_threshold=5_000,
        ),
    )
    scenario.install()
    runtime.run_until(0)
    return scenario


def command(worker_ids=("WRK-0010", "WRK-0011"), command_id="cmd-1"):
    return SimulationCommand(
        command_id=command_id,
        trace_id="trace-1",
        issued_by="surge_staffing",
        type="reallocate_workers",
        payload={
            "worker_ids": list(worker_ids),
            "from_team_id": "TEAM-RESERVE",
            "to_team_id": "TEAM-SUPPORT",
            "duration_minutes": 30,
        },
    )


def test_valid_command_moves_actual_workers_and_journals_each_move():
    scenario = scenario_with_reserve()
    result = scenario.apply_command(command())
    assert result.type == "command.accepted"
    assert scenario.workers["WRK-0010"].team_id == "TEAM-SUPPORT"
    assert scenario.workers["WRK-0010"].status == "idle"
    moved = [e.actor_id for e in scenario.runtime.journal if e.type == "worker.reallocated"]
    assert moved == ["WRK-0010", "WRK-0011"]


def test_invalid_command_is_all_or_nothing():
    scenario = scenario_with_reserve()
    result = scenario.apply_command(command(("WRK-0010", "MISSING")))
    assert result.type == "command.rejected"
    assert scenario.workers["WRK-0010"].team_id == "TEAM-RESERVE"
    assert not any(e.type == "worker.reallocated" for e in scenario.runtime.journal)


def test_duplicate_command_is_idempotent():
    scenario = scenario_with_reserve()
    first = scenario.apply_command(command())
    count = len(scenario.runtime.journal)
    second = scenario.apply_command(command())
    assert second.event_id == first.event_id
    assert len(scenario.runtime.journal) == count


def test_workers_return_to_reserve_after_duration():
    scenario = scenario_with_reserve()
    accepted = scenario.apply_command(command(("WRK-0010",)))
    scenario.runtime.run_until(31)
    worker = scenario.workers["WRK-0010"]
    assert worker.team_id == "TEAM-RESERVE"
    assert worker.status == "reserve"
    returned = next(e for e in scenario.runtime.journal if e.type == "worker.returned")
    assert returned.cause_event_id in {
        e.event_id for e in scenario.runtime.journal if e.type == "worker.reallocated"
    }
    assert accepted.trace_id == returned.trace_id
