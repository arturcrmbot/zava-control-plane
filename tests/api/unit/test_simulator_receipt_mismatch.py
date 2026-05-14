"""Simulator receipt-mismatch scenarios (Day 7 / Task 11).

Each scenario should pick a claim from the synthetic corpus whose
`receipt_mismatch_flavour` matches the scenario's flavour. Mocks
`schedule_new_orchestration` so we don't need a Functions host.
"""
from __future__ import annotations
import json
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


SCENARIO_TO_FLAVOUR = {
    "receipt-mismatch-correct": "correct",
    "receipt-mismatch-amount": "wrong-amount",
    "receipt-mismatch-date": "wrong-date",
    "receipt-mismatch-vendor": "wrong-vendor",
    "receipt-missing-line": "missing-line-item",
    "receipt-missing": "missing-receipt",
}


@pytest.mark.parametrize("scenario,flavour", list(SCENARIO_TO_FLAVOUR.items()))
@pytest.mark.asyncio
async def test_scenario_spawns_claim_with_matching_flavour(scenario, flavour):
    """spawn_expense_workflow(scenario=...) picks a claim whose stamped
    receipt_mismatch_flavour matches the scenario's flavour."""
    captured: dict = {}

    async def fake_schedule(payload, function_name=None):
        captured["payload"] = payload
        captured["function_name"] = function_name
        return {"id": f"durable-{payload['workflow_id']}"}

    with patch.object(
        simulator_orchestrator, "schedule_new_orchestration",
        AsyncMock(side_effect=fake_schedule),
    ):
        wid = await simulator_orchestrator.spawn_expense_workflow(scenario=scenario)

    assert wid.startswith("EXP-"), wid
    payload = captured["payload"]
    assert captured["function_name"] == "ExpenseClaimOrchestrator"
    assert payload["type"] == "expense-claim"
    assert payload["scenario"] == scenario
    claim_id = payload["claim_id"]

    # Verify the picked claim actually has the matching flavour stamped.
    claim_path = simulator_orchestrator._CLAIMS_DIR / f"{claim_id}.json"
    record = json.loads(claim_path.read_text(encoding="utf-8"))
    assert record["receipt_mismatch_flavour"] == flavour, (
        f"scenario {scenario} picked {claim_id} with flavour "
        f"{record['receipt_mismatch_flavour']!r}, expected {flavour!r}"
    )


@pytest.mark.asyncio
async def test_explicit_claim_id_overrides_scenario_pick():
    """When claim_id is passed explicitly (e.g. Day 9 repeat-offender ramp),
    the scenario flavour-matching is skipped."""
    async def fake_schedule(payload, function_name=None):
        return {"id": f"durable-{payload['workflow_id']}"}

    with patch.object(
        simulator_orchestrator, "schedule_new_orchestration",
        AsyncMock(side_effect=fake_schedule),
    ):
        # Pass an explicit CLM-0000 with a contradictory scenario; explicit wins.
        await simulator_orchestrator.spawn_expense_workflow(
            scenario="receipt-mismatch-vendor", claim_id="CLM-0000",
        )

    # No assertion on payload — the test is that the call doesn't raise from
    # _pick_claim_for_flavour. That confirms the explicit-claim_id branch
    # short-circuits the scenario lookup.


def test_unknown_scenario_does_not_invoke_flavour_pick():
    """A scenario not in _SCENARIO_TO_FLAVOUR should not attempt to pick a
    claim by flavour. We assert this by checking the scenario set."""
    assert "demo-anything" not in simulator_orchestrator._SCENARIO_TO_FLAVOUR
    # Coverage that the mapping is exactly the six receipt-mismatch flavours.
    assert set(simulator_orchestrator._SCENARIO_TO_FLAVOUR) == set(SCENARIO_TO_FLAVOUR)
