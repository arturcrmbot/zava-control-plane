"""Simulator: ExpenseClaimOrchestrator spawn behaviour.

Verifies the simulator's expense-claim path schedules the right
function_name with an expense-shaped payload (claim, not vendor/invoice)
and an EXP-prefixed workflow id.
"""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.server.services import simulator_orchestrator


@pytest.fixture(autouse=True)
def _reset_seq():
    simulator_orchestrator._exp_seq = 0
    simulator_orchestrator._seq = 0
    yield


@pytest.mark.asyncio
async def test_spawn_expense_workflow_schedules_expense_claim_orchestrator():
    captured: dict = {}

    async def fake_schedule(payload, function_name="ExpenseClaimOrchestrator"):
        captured["payload"] = payload
        captured["function_name"] = function_name
        return {"id": "iid-test"}

    with patch(
        "api.server.services.simulator_orchestrator.schedule_new_orchestration",
        AsyncMock(side_effect=fake_schedule),
    ):
        wid = await simulator_orchestrator.spawn_expense_workflow()

    assert wid.startswith("EXP-")
    assert captured["function_name"] == "ExpenseClaimOrchestrator"

    payload = captured["payload"]
    assert payload["workflow_id"] == wid
    assert payload["type"] == "expense-claim"
    # Claim shape, not invoice shape
    assert "claim" in payload and payload["claim"] is not None
    assert "vendor" not in payload
    assert "invoice" not in payload
    assert payload["claim_id"]
    assert payload["claim_id"] == payload["claim"]["claim_id"]


@pytest.mark.asyncio
async def test_spawn_expense_workflow_with_explicit_claim_id_uses_that_seed():
    captured: dict = {}

    async def fake_schedule(payload, function_name="ExpenseClaimOrchestrator"):
        captured["payload"] = payload
        return {"id": "iid-x"}

    with patch(
        "api.server.services.simulator_orchestrator.schedule_new_orchestration",
        AsyncMock(side_effect=fake_schedule),
    ):
        wid = await simulator_orchestrator.spawn_expense_workflow(claim_id="CLM-0007")

    assert wid.startswith("EXP-")
    assert captured["payload"]["claim_id"] == "CLM-0007"


@pytest.mark.asyncio
async def test_spawn_expense_workflow_threads_scenario_tag():
    captured: dict = {}

    async def fake_schedule(payload, function_name="ExpenseClaimOrchestrator"):
        captured["payload"] = payload
        return {"id": "iid-y"}

    with patch(
        "api.server.services.simulator_orchestrator.schedule_new_orchestration",
        AsyncMock(side_effect=fake_schedule),
    ):
        await simulator_orchestrator.spawn_expense_workflow(scenario="receipt-mismatch-amount")

    assert captured["payload"]["scenario"] == "receipt-mismatch-amount"


@pytest.mark.asyncio
async def test_spawn_workflow_id_increments():
    async def fake_schedule(payload, function_name="ExpenseClaimOrchestrator"):
        return {"id": "iid"}

    with patch(
        "api.server.services.simulator_orchestrator.schedule_new_orchestration",
        AsyncMock(side_effect=fake_schedule),
    ):
        a = await simulator_orchestrator.spawn_expense_workflow()
        b = await simulator_orchestrator.spawn_expense_workflow()

    assert a == "EXP-0001"
    assert b == "EXP-0002"
