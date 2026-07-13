import json

from api.server.world.packs.telco import NetworkConfig, SiteFailure, run_network


CONFIG = NetworkConfig(
    site_count=12,
    subscriber_count=2_000,
    session_count=2_200,
    site_capacity_mbps=600.0,
    simulation_minutes=240.0,
)
FAILURES = (SiteFailure(at_minute=30),)


def test_same_seed_and_inputs_produce_identical_journal():
    left = run_network(seed=42, config=CONFIG, failures=FAILURES)
    right = run_network(seed=42, config=CONFIG, failures=FAILURES)
    assert left.runtime.canonical_journal() == right.runtime.canonical_journal()


def test_different_seed_changes_the_world():
    left = run_network(seed=42, config=CONFIG, failures=FAILURES)
    right = run_network(seed=43, config=CONFIG, failures=FAILURES)
    assert left.runtime.canonical_journal() != right.runtime.canonical_journal()


def test_scale_run_contains_explicit_actors_and_bounded_journal():
    scenario = run_network(seed=42, config=CONFIG, failures=FAILURES)
    assert len(scenario.sites) == 12
    assert len(scenario.subscribers) == 2_000
    assert len(scenario.sessions) == 2_200
    assert len(scenario.runtime.journal) < 100_000
    assert any(e.type == "site.failed" for e in scenario.runtime.journal)
    assert any(e.type == "sensor.tripped" for e in scenario.runtime.journal)


def test_exported_journal_matches_canonical_run(tmp_path):
    scenario = run_network(seed=42, config=CONFIG, failures=FAILURES)
    path = scenario.runtime.export_ndjson(tmp_path / "telco.ndjson")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows == scenario.runtime.canonical_journal()
