"""Day 9 repeat-offender ramp simulator scenario."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.server.services import simulator_orchestrator


@pytest.fixture(autouse=True)
def _isolate_app_state_store():
    """Reset app_state.store after each test so order-dependent failures
    don't appear once parallel test runners read the global store."""
    store = simulator_orchestrator.app_state.store
    pre_existing = {w.id for w in store.list_workflows()}
    yield
    for w in list(store.list_workflows()):
        if w.id not in pre_existing:
            store._workflows.pop(w.id, None)


@pytest.mark.asyncio
async def test_ramp_spawns_n_claims_from_same_employee():
    captured_payloads: list[dict] = []

    async def fake_schedule(payload, function_name=None):
        captured_payloads.append(payload)
        return {"id": f"durable-{payload['workflow_id']}"}

    with patch.object(
        simulator_orchestrator, "schedule_new_orchestration",
        AsyncMock(side_effect=fake_schedule),
    ):
        ids = await simulator_orchestrator.spawn_repeat_offender_ramp(
            employee_id="EMP-0001", count=3, delay_seconds=0.0,
        )

    assert len(ids) == 3
    assert all(wid.startswith("EXP-") for wid in ids)
    # All three claims must be from the same employee.
    employee_ids = {p["claim"]["employee_id"] for p in captured_payloads}
    assert employee_ids == {"EMP-0001"}
    # Each spawn carries the repeat-offender scenario tag.
    assert all(p["scenario"] == "repeat-offender" for p in captured_payloads)


@pytest.mark.asyncio
async def test_ramp_raises_when_corpus_too_small_for_unknown_employee():
    """An employee not in the corpus has 0 claims and should raise loudly."""
    with pytest.raises(ValueError, match="EMP-NOPE"):
        await simulator_orchestrator.spawn_repeat_offender_ramp(
            employee_id="EMP-NOPE", count=3, delay_seconds=0.0,
        )


@pytest.mark.asyncio
async def test_ramp_raises_when_count_exceeds_real_employee_corpus(monkeypatch):
    """Genuine 'too small' case: a real employee with N claims, asked for N+1."""
    real_count = len(simulator_orchestrator._claims_for_employee("EMP-0001"))
    assert real_count >= 1, "fixture changed; pick another employee"
    with pytest.raises(ValueError, match=f"need {real_count + 5}"):
        await simulator_orchestrator.spawn_repeat_offender_ramp(
            employee_id="EMP-0001", count=real_count + 5, delay_seconds=0.0,
        )


def test_claims_for_employee_returns_corpus_matches():
    """Helper used by the ramp — sorted, deterministic."""
    matches = simulator_orchestrator._claims_for_employee("EMP-0001")
    # EMP-0001 has multiple claims in the synthetic corpus by construction.
    assert len(matches) >= 3
    # Sorted (claim_id is also chronological by index).
    assert matches == sorted(matches)
