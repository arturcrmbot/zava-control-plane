"""Tests for the substrate-realism additions to api/shared/domains.py."""
import pytest

from api.shared.domains import DOMAINS, Domain, live_domains


def test_live_domains_excludes_stubs() -> None:
    live = live_domains()
    assert all(not d.stub for d in live)
    # 36 live domains as of 2026-05-11 (Wave 4b promoted 5 stubs via
    # pitch-c1 0873322c, added 7 cross-domain meta-workflows via
    # pitch-c2 043f6655, and added 10 agency-specific domains via
    # pitch-c3 87429420). Was 14 originally.
    assert len(live) == 36


def test_every_live_domain_has_spawn_fn() -> None:
    for d in live_domains():
        assert d.spawn_fn is not None, f"{d.workflow_type} missing spawn_fn"
        assert "." in d.spawn_fn, (
            f"{d.workflow_type}.spawn_fn={d.spawn_fn!r} should be a dotted path"
        )


def test_stub_domains_have_no_spawn_fn() -> None:
    for d in DOMAINS.values():
        if d.stub:
            assert d.spawn_fn is None, (
                f"stub domain {d.workflow_type} should not declare spawn_fn"
            )


def test_resolve_spawner_imports_callable() -> None:
    # Picks any live domain and verifies the resolver returns a callable.
    from api.server.services.simulator_orchestrator import _resolve_spawner
    sample = next(iter(live_domains()))
    fn = _resolve_spawner(sample)
    assert callable(fn), f"resolved {sample.spawn_fn!r} did not return a callable"


def test_resolve_spawner_caches() -> None:
    from api.server.services.simulator_orchestrator import _resolve_spawner
    sample = next(iter(live_domains()))
    fn_a = _resolve_spawner(sample)
    fn_b = _resolve_spawner(sample)
    assert fn_a is fn_b, "_resolve_spawner should cache resolved callables"


def test_hitl_gate_has_wait_probability_field() -> None:
    from api.shared.domains import HitlGate
    g = HitlGate(gate_phase="x", external_event="x.evt", persona="x")
    assert g.wait_probability == 0.0  # default
    g2 = HitlGate(gate_phase="x", external_event="x.evt", persona="x",
                  wait_probability=0.5)
    assert g2.wait_probability == 0.5


def test_high_risk_gates_have_nonzero_wait_probability() -> None:
    """Spot-check that the calibration table actually populated values."""
    from api.shared.domains import DOMAINS
    expected = {
        ("privacy-dpia", "approver_signoff"): 0.40,
        ("contract-review", "approver_signoff"): 0.30,
        ("treasury-fx", "approver_signoff"): 0.30,
        ("perf-review", "hr_calibration"): 0.25,
        ("expense-claim", "Arbitrate"): 0.30,
    }
    for (wf_type, gate), expected_p in expected.items():
        domain = DOMAINS[wf_type]
        gate_obj = next(g for g in domain.hitl_gates if g.gate_phase == gate)
        assert gate_obj.wait_probability == pytest.approx(expected_p), (
            f"{wf_type}/{gate} expected {expected_p}, "
            f"got {gate_obj.wait_probability}"
        )


def test_every_live_domain_has_realistic_interval() -> None:
    for d in live_domains():
        assert d.realistic_interval_seconds is not None, (
            f"{d.workflow_type} missing realistic_interval_seconds"
        )
        assert d.realistic_interval_seconds > 0


def test_high_volume_domains_have_short_intervals() -> None:
    from api.shared.domains import DOMAINS
    assert DOMAINS["ap-invoice"].realistic_interval_seconds <= 3600
    assert DOMAINS["expense-claim"].realistic_interval_seconds <= 3600
    assert DOMAINS["perf-review"].realistic_interval_seconds >= 86400 * 30


def test_effective_cadence_with_time_warp(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_TIME_WARP_FACTOR", "60")
    from api.server.services.simulator_orchestrator import _effective_interval
    from api.shared.domains import DOMAINS
    ap = DOMAINS["ap-invoice"]
    assert _effective_interval(ap) == pytest.approx(30.0)  # 1800 / 60
    pr = DOMAINS["perf-review"]
    # pitch-c5 (commit b4d9c4f3) flagged perf-review as slow_burn=True so
    # its effective interval is multiplied by 5: 5184000 / 60 * 5 = 432000.
    assert _effective_interval(pr) == pytest.approx(432000.0)


def test_effective_cadence_falls_back_to_legacy_env(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_TIME_WARP_FACTOR", "60")
    monkeypatch.setenv("SIMULATOR_RAMP_AVG_INTERVAL_SECONDS", "120")
    from api.server.services.simulator_orchestrator import _effective_interval
    from api.shared.domains import Domain
    # A hand-crafted domain with no realistic_interval_seconds → fallback.
    d = Domain(
        workflow_type="x", display_name="x", workflow_id_prefix="X",
        orchestrator_name="x", operator_surface="x",
        phases=(), hitl_gates=(), skills=(),
    )
    assert _effective_interval(d) == 120.0
