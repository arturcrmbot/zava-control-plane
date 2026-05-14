"""TASK-018b — public AmbientDispatcher.dispatch entrypoint."""
from __future__ import annotations

import os
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")

import pytest

from api.server.services.ambient_agents import AmbientAgent, CadenceTrigger
from api.server.services.ambient_dispatcher import AmbientDispatcher
from api.server.services.event_bus import EventBus
from api.server.services.governance.kill_switch import kill_switch_store


@pytest.fixture(autouse=True)
def _clean():
    kill_switch_store.clear_for_tests()
    yield
    kill_switch_store.clear_for_tests()


class _FakeAudit:
    def __init__(self):
        self.entries = []

    def log(self, action, details):
        self.entries.append({"action": action, "details": details})


def _agent(name="budget-variance-watcher"):
    return AmbientAgent(
        name=name, function="finance",
        triggers=(CadenceTrigger(cron="0 9 * * *"),),
        spawnable_workflow_types=("variance-investigation",),
    )


@pytest.mark.asyncio
async def test_dispatch_cadence_spawns_and_audits():
    audit = _FakeAudit()
    spawned = []

    async def spawner(wt, payload):
        spawned.append((wt, payload))
        return f"WF-{wt}"

    agent = _agent()
    disp = AmbientDispatcher(
        bus=EventBus(), graph=None, audit=audit,
        spawn_workflow=spawner, agents={agent.name: agent},
    )
    await disp.dispatch(agent.name, {"kind": "cadence", "cadence_name": "morning-sweep"})
    assert len(spawned) == 1
    decided = [e for e in audit.entries if e["action"] == "ambient.decided"]
    assert len(decided) == 1
    assert decided[0]["details"]["trigger_kind"] == "cadence"
    assert decided[0]["details"]["spawn_outcome"]["spawned"] is True


@pytest.mark.asyncio
async def test_dispatch_unknown_agent_raises_keyerror():
    disp = AmbientDispatcher(
        bus=EventBus(), graph=None, audit=_FakeAudit(),
        spawn_workflow=lambda *a, **kw: None, agents={},
    )
    with pytest.raises(KeyError):
        await disp.dispatch("nope", {"kind": "cadence"})


@pytest.mark.asyncio
async def test_dispatch_kill_switch_short_circuits():
    audit = _FakeAudit()
    spawned = []

    async def spawner(wt, payload):
        spawned.append((wt, payload))
        return None

    agent = _agent("cad-kill")
    disp = AmbientDispatcher(
        bus=EventBus(), graph=None, audit=audit,
        spawn_workflow=spawner, agents={agent.name: agent},
    )
    kill_switch_store.add(actor="ambient.cad-kill", tool="spawn_workflow",
                          ttl_seconds=60, reason="test")
    await disp.dispatch(agent.name, {"kind": "cadence"})
    assert spawned == []
    decided = [e for e in audit.entries if e["action"] == "ambient.decided"]
    assert decided[-1]["details"]["spawn_outcome"]["skipped_reason"] == "kill-switch"
