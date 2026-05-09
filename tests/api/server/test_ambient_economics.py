"""Phase 4 IP8 TASK-040 — ambient_reasoning ledger row lands when
``AmbientAgent.reasoning_skill`` is set (DEC-OQ4)."""
from __future__ import annotations

import pytest

from api.server.services import economics
from api.server.services.ambient_agents import AmbientAgent, CadenceTrigger
from api.server.services.ambient_dispatcher import AmbientDispatcher


class _Bus:
    def on(self, *a, **k):
        return lambda: None

    def emit(self, *a, **k):
        pass


class _Audit:
    def __init__(self):
        self.entries = []

    def log(self, action, details):
        self.entries.append((action, details))


@pytest.mark.asyncio
async def test_ambient_reasoning_records_economics_row():
    economics.reset_ambient_ledger()
    agent = AmbientAgent(
        name="test-reasoner",
        function="ceo",
        triggers=(CadenceTrigger(cron="0 0 * * *"),),
        reasoning_skill="okr-quarterly-review",
        spawnable_workflow_types=(),
    )
    dispatcher = AmbientDispatcher(
        bus=_Bus(), graph=None, audit=_Audit(),
        spawn_workflow=lambda wt, payload: None,
        agents={agent.name: agent},
    )
    await dispatcher.dispatch(agent.name, {"kind": "cadence", "cadence_name": "x"})

    rows = economics.list_ambient_costs("test-reasoner")
    assert len(rows) == 1
    row = rows[0]
    assert row["cost_kind"] == "ambient_reasoning"
    assert row["actor"] == "ambient.test-reasoner"
    assert row["agent_name"] == "test-reasoner"
    assert row["extra"]["reasoning_skill"] == "okr-quarterly-review"


@pytest.mark.asyncio
async def test_no_economics_row_when_reasoning_skill_absent():
    economics.reset_ambient_ledger()
    agent = AmbientAgent(
        name="test-no-reasoner",
        function="finance",
        triggers=(CadenceTrigger(cron="0 0 * * *"),),
        reasoning_skill=None,
        spawnable_workflow_types=("ap-invoice",),
    )
    dispatcher = AmbientDispatcher(
        bus=_Bus(), graph=None, audit=_Audit(),
        spawn_workflow=lambda wt, payload: None,
        agents={agent.name: agent},
    )
    await dispatcher.dispatch(agent.name, {"kind": "cadence", "cadence_name": "x"})
    assert economics.list_ambient_costs("test-no-reasoner") == []
