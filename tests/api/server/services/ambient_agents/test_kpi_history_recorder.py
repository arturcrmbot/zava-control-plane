"""Pitch-j1/j2: kpi_history_recorder per-minute snapshotter.

Drives the recorder with stub providers so the tick is deterministic
without touching app_state. Verifies:

  * agency KPIs land in the durable store under the right kpi id (J1)
  * per-persona queue + decisions land namespaced by role via dim (J2)
  * a raising provider doesn't crash the tick (defensive)
  * the default persona-load provider reads workflows from app_state
    (HITL queue + decisions stamp parsing)
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from api.server.services import kpi_history
from api.server.services.ambient_agents import kpi_history_recorder


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path: Path):
    original = kpi_history._DB_PATH
    db = tmp_path / "kh.sqlite"
    kpi_history.set_db_path(db)
    kpi_history.init()
    yield db
    kpi_history.set_db_path(original)


async def test_tick_records_agency_kpis():
    rec = kpi_history_recorder.KpiHistoryRecorder(
        agency_kpi_provider=lambda: {"win_rate_pct": 42.0, "pitch_cost": 12500.0},
        persona_load_provider=lambda: ({}, {}),
    )
    counts = await rec.tick()
    assert counts["agency"] == 2
    assert kpi_history.latest("win_rate_pct")[1] == 42.0
    assert kpi_history.latest("pitch_cost")[1] == 12500.0


async def test_tick_records_persona_queue_depth_per_role():
    rec = kpi_history_recorder.KpiHistoryRecorder(
        agency_kpi_provider=lambda: {},
        persona_load_provider=lambda: (
            {"hr_director": 3.0, "cfo": 1.0},
            {},
        ),
    )
    counts = await rec.tick()
    assert counts["persona_queue"] == 2
    assert kpi_history.latest("persona_queue_depth", dim="hr_director")[1] == 3.0
    assert kpi_history.latest("persona_queue_depth", dim="cfo")[1] == 1.0


async def test_tick_records_persona_decisions_per_min_per_role():
    rec = kpi_history_recorder.KpiHistoryRecorder(
        agency_kpi_provider=lambda: {},
        persona_load_provider=lambda: ({}, {"cfo": 5.0}),
    )
    counts = await rec.tick()
    assert counts["persona_decisions"] == 1
    assert (
        kpi_history.latest("persona_decisions_per_min", dim="cfo")[1] == 5.0
    )


async def test_tick_swallows_agency_provider_exception():
    def _boom() -> dict[str, float]:
        raise RuntimeError("kpi blow-up")

    rec = kpi_history_recorder.KpiHistoryRecorder(
        agency_kpi_provider=_boom,
        persona_load_provider=lambda: ({"hr": 1.0}, {}),
    )
    counts = await rec.tick()
    assert counts["agency"] == 0
    assert counts["persona_queue"] == 1


async def test_tick_swallows_persona_provider_exception():
    def _boom():
        raise RuntimeError("persona blow-up")

    rec = kpi_history_recorder.KpiHistoryRecorder(
        agency_kpi_provider=lambda: {"win_rate_pct": 1.0},
        persona_load_provider=_boom,
    )
    counts = await rec.tick()
    assert counts["agency"] == 1
    assert counts["persona_queue"] == 0
    assert counts["persona_decisions"] == 0


async def test_default_persona_load_provider_counts_hitl_and_recent_decisions(
    monkeypatch,
):
    """The default provider walks app_state.store.list_workflows().

    Stub the store so we exercise the role-attribution + 60s decision
    window logic without spinning up the full app."""
    import datetime as _dt
    from types import SimpleNamespace

    now = time.time()

    pending = SimpleNamespace(
        id="W1",
        type="expense-claim",
        status="awaiting_hitl",
        current_phase="ManagerApproval",
        payload={"hitl_context": {"persona": "cfo"}, "decisions": []},
    )
    fresh_iso = _dt.datetime.fromtimestamp(now - 5).isoformat()
    stale_iso = _dt.datetime.fromtimestamp(now - 600).isoformat()
    decided = SimpleNamespace(
        id="W2",
        type="expense-claim",
        status="completed",
        current_phase="Done",
        payload={
            "decisions": [
                {"persona_role": "hr_director", "decided_at": fresh_iso},
                {"persona_role": "hr_director", "decided_at": fresh_iso},
                {"persona_role": "hr_director", "decided_at": stale_iso},
                {"persona_role": "cfo", "decided_at": fresh_iso},
            ]
        },
    )

    fake_store = SimpleNamespace(list_workflows=lambda: [pending, decided])
    fake_app_state = SimpleNamespace(store=fake_store)

    import api.server.state as _state
    monkeypatch.setattr(_state, "app_state", fake_app_state)

    queue, decisions = kpi_history_recorder._default_persona_load_provider()
    assert queue == {"cfo": 1.0}
    # Stale decision (>60s old) is filtered out; fresh ones counted.
    assert decisions == {"hr_director": 2.0, "cfo": 1.0}
