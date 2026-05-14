"""Slow-burn time-compression integration with the simulator (pitch-c5).

A ``slow_burn=True`` Domain (e.g. client-renewal, contract-review,
m-and-a-integration) should:

1. Have its effective spawn interval stretched by 5x relative to the
   nominal ``realistic_interval_seconds / DEMO_TIME_WARP_FACTOR``.
2. Have its workflow's ``created_at`` stamped with **business time**
   (so the dashboard ages it as if the workflow had been running for
   weeks/months) rather than wall-clock now.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from api.server.services import simulator_orchestrator, time_compression
from api.server.state import app_state
from api.shared.domains import DOMAINS


SLOW_BURN_DOMAINS = (
    "contract-renewal",
    "contract-review",
    "perf-review",
    "m-and-a-integration",
    "client-renewal",
    "annual-budget-setting",
)


def test_six_expected_domains_marked_slow_burn():
    for wt in SLOW_BURN_DOMAINS:
        assert DOMAINS[wt].slow_burn is True, f"{wt} missing slow_burn=True"


def test_other_domains_default_to_fast():
    # Spot-check a handful of fast-cadence domains.
    for wt in ("expense-claim", "ap-invoice", "hiring", "vendor-kyc"):
        assert DOMAINS[wt].slow_burn is False


def test_effective_interval_multiplies_by_five_for_slow_burn(monkeypatch):
    monkeypatch.setenv("DEMO_TIME_WARP_FACTOR", "60")
    fast = DOMAINS["expense-claim"]
    slow = DOMAINS["client-renewal"]
    fast_interval = simulator_orchestrator._effective_interval(fast)
    slow_interval = simulator_orchestrator._effective_interval(slow)
    assert fast_interval == fast.realistic_interval_seconds / 60
    assert slow_interval == (slow.realistic_interval_seconds / 60) * 5


@pytest.mark.asyncio
async def test_slow_burn_spawn_stamps_business_time_created_at(monkeypatch):
    """Spawning client-renewal should set workflow.created_at to
    business_now() rather than wall-clock now."""
    # Pin business clock to a far-future "fast-forward" instant so
    # we can prove created_at is NOT just wall-clock now.
    base = datetime(2026, 1, 1, 0, 0, 0)
    time_compression.reset_base(base)
    monkeypatch.setenv("SIMULATOR_TIME_COMPRESSION", "86400")  # 1 sec wall = 1 day biz
    fixed_real = base + timedelta(seconds=30)  # 30 days of business time
    expected_business = base + timedelta(days=30)

    # Reset spawn sequence so we get a deterministic id.
    simulator_orchestrator._clr_seq = 0

    async def fake_schedule(payload, function_name="ClientRenewalOrchestrator"):
        return {"id": "iid-clr-1"}

    with patch(
        "api.server.services.simulator_orchestrator.schedule_new_orchestration",
        AsyncMock(side_effect=fake_schedule),
    ), patch(
        "api.server.services.simulator_orchestrator.business_now",
        return_value=expected_business,
    ):
        wid = await simulator_orchestrator.spawn_client_renewal_workflow()

    w = app_state.store.get_workflow(wid)
    assert w is not None
    # business_now returned `expected_business`; the spawner stamps
    # created_at = expected_business.timestamp(). Compare timestamps
    # directly to avoid naive-vs-UTC conversion mismatches.
    assert w.created_at == pytest.approx(expected_business.timestamp(), abs=2)


@pytest.mark.asyncio
async def test_fast_domain_spawn_keeps_wall_clock_created_at(monkeypatch):
    """A non-slow-burn agency spawn should NOT have its created_at
    rewritten by business_now()."""
    base = datetime(2026, 1, 1, 0, 0, 0)
    time_compression.reset_base(base)
    monkeypatch.setenv("SIMULATOR_TIME_COMPRESSION", "86400")

    simulator_orchestrator._fob_seq = 0  # freelancer-onboarding (not slow_burn)

    async def fake_schedule(payload, function_name=None):
        return {"id": "iid-fob-1"}

    with patch(
        "api.server.services.simulator_orchestrator.schedule_new_orchestration",
        AsyncMock(side_effect=fake_schedule),
    ):
        import time as _time
        before = _time.time()
        wid = await simulator_orchestrator.spawn_freelancer_onboarding_workflow()
        after = _time.time()

    w = app_state.store.get_workflow(wid)
    assert w is not None
    # Wall-clock created_at should be sandwiched between before/after.
    assert before - 1 <= w.created_at <= after + 1
