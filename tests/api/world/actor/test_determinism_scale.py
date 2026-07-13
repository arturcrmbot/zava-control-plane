import json

from api.server.world.packs.support import DemandSurge, SupportConfig, run_support


CONFIG = SupportConfig(
    customer_count=1_000,
    worker_count=40,
    arrival_rate_per_hour=90,
    simulation_minutes=480,
    sla_minutes=30,
    sensor_backlog_threshold=25,
    sensor_recovery_threshold=10,
)
SURGES = (DemandSurge(at_minute=120, multiplier=4, duration_minutes=90),)


def test_same_seed_and_inputs_produce_identical_journal():
    left = run_support(seed=42, config=CONFIG, surges=SURGES)
    right = run_support(seed=42, config=CONFIG, surges=SURGES)
    assert left.runtime.canonical_journal() == right.runtime.canonical_journal()


def test_different_seed_changes_the_world():
    left = run_support(seed=42, config=CONFIG, surges=SURGES)
    right = run_support(seed=43, config=CONFIG, surges=SURGES)
    assert left.runtime.canonical_journal() != right.runtime.canonical_journal()


def test_scale_run_contains_explicit_actors_and_bounded_journal():
    scenario = run_support(seed=42, config=CONFIG, surges=SURGES)
    assert len(scenario.customers) == 1_000
    assert len(scenario.workers) == 40
    assert len(scenario.tickets) >= 500
    assert len(scenario.runtime.journal) < 100_000
    assert any(e.type == "sensor.tripped" for e in scenario.runtime.journal)


def test_exported_journal_matches_canonical_run(tmp_path):
    scenario = run_support(seed=42, config=CONFIG, surges=SURGES)
    path = scenario.runtime.export_ndjson(tmp_path / "support.ndjson")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows == scenario.runtime.canonical_journal()
