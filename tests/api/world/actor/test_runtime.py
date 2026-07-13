import json

from api.server.world.runtime import SimulationRuntime


def _install_clock(runtime: SimulationRuntime) -> None:
    def clock():
        first = runtime.emit("clock.started", actor_id="clock-1", payload={"n": 1})
        yield runtime.env.timeout(5)
        runtime.emit(
            "clock.rang",
            actor_id="clock-1",
            cause_event_id=first.event_id,
            trace_id=first.trace_id,
            payload={"n": 2},
        )

    runtime.process(clock())


def test_step_advances_to_next_event_and_returns_new_journal_entries():
    runtime = SimulationRuntime(seed=7)
    _install_clock(runtime)
    events = runtime.step()
    assert runtime.now == 0.0
    assert [e.type for e in events] == ["clock.started"]
    assert runtime.status == "paused"


def test_run_until_processes_events_in_logical_time_order():
    runtime = SimulationRuntime(seed=7)
    _install_clock(runtime)
    runtime.run_until(5)
    assert [e.type for e in runtime.journal] == ["clock.started", "clock.rang"]
    assert runtime.journal[1].cause_event_id == runtime.journal[0].event_id
    assert runtime.journal[1].sim_time == 5.0


def test_event_ids_and_default_trace_ids_are_deterministic():
    left = SimulationRuntime(seed=1)
    right = SimulationRuntime(seed=1)
    for runtime in (left, right):
        runtime.emit("a")
        runtime.emit("b")
    assert left.canonical_journal() == right.canonical_journal()
    assert left.journal[0].event_id == "evt-00000001"
    assert left.journal[0].trace_id == "evt-00000001"


def test_export_ndjson_round_trips(tmp_path):
    runtime = SimulationRuntime(seed=3)
    runtime.emit("simulation.started", payload={"seed": 3})
    path = runtime.export_ndjson(tmp_path / "journal.ndjson")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows == runtime.canonical_journal()
