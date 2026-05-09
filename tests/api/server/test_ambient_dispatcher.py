"""TASK-018 — AmbientDispatcher bus + cypher + kill switch + cadence."""
from __future__ import annotations

import asyncio
import os
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")

import pytest

from api.server.services.ambient_agents import (
    AmbientAgent, BusTrigger, CadenceTrigger, CypherTrigger,
)
from api.server.services.ambient_dispatcher import AmbientDispatcher
from api.server.services.event_bus import EventBus
from api.server.services.governance.kill_switch import kill_switch_store
from api.shared.events import FleetEvent


@pytest.fixture(autouse=True)
def _clean_kill_switch():
    kill_switch_store.clear_for_tests()
    yield
    kill_switch_store.clear_for_tests()


class _FakeAudit:
    def __init__(self):
        self.entries = []

    def log(self, action, details):
        self.entries.append({"action": action, "details": details})


class _FakeGraph:
    def __init__(self, rows=None, raises=None):
        self._rows = rows or []
        self._raises = raises
        self.calls = 0

    def query(self, pattern, params=None):
        self.calls += 1
        if self._raises is not None:
            exc = self._raises
            # Raise once then succeed.
            self._raises = None
            raise exc
        return list(self._rows)


def _make_spawner():
    calls = []

    async def spawner(wt, payload):
        calls.append((wt, payload))
        return f"WF-{wt}-{len(calls)}"

    return spawner, calls


# ----- BusTrigger paths -----------------------------------------------------


def test_bus_trigger_no_filter_spawns_once():
    bus = EventBus()
    audit = _FakeAudit()
    spawner, calls = _make_spawner()
    agent = AmbientAgent(
        name="t1", function="finance",
        triggers=(BusTrigger(event_type="workflow.resolved"),),
        spawnable_workflow_types=("variance-investigation",),
    )
    disp = AmbientDispatcher(
        bus=bus, graph=_FakeGraph(), audit=audit,
        spawn_workflow=spawner, agents={"t1": agent},
    )
    disp.start()
    bus.emit(FleetEvent(type="workflow.resolved", workflow_id="WF-X"))
    assert len(calls) == 1
    decided = [e for e in audit.entries if e["action"] == "ambient.decided"]
    assert len(decided) == 1
    assert decided[0]["details"]["spawn_outcome"]["spawned"] is True


def test_bus_trigger_filter_narrows_spawns():
    bus = EventBus()
    audit = _FakeAudit()
    spawner, calls = _make_spawner()
    agent = AmbientAgent(
        name="t2", function="finance",
        triggers=(BusTrigger(event_type="workflow.resolved",
                             filter="amount > 1000"),),
        spawnable_workflow_types=("variance-investigation",),
    )
    disp = AmbientDispatcher(
        bus=bus, graph=_FakeGraph(), audit=audit,
        spawn_workflow=spawner, agents={"t2": agent},
    )
    disp.start()
    bus.emit(FleetEvent(type="workflow.resolved", workflow_id="WF-A", amount=500))
    assert calls == []
    bus.emit(FleetEvent(type="workflow.resolved", workflow_id="WF-B", amount=1500))
    assert len(calls) == 1


def test_bus_kill_switch_short_circuits():
    bus = EventBus()
    audit = _FakeAudit()
    spawner, calls = _make_spawner()
    agent = AmbientAgent(
        name="t3", function="finance",
        triggers=(BusTrigger(event_type="workflow.resolved"),),
        spawnable_workflow_types=("x",),
    )
    disp = AmbientDispatcher(
        bus=bus, graph=_FakeGraph(), audit=audit,
        spawn_workflow=spawner, agents={"t3": agent},
    )
    disp.start()
    kill_switch_store.add(actor="ambient.t3", tool="spawn_workflow",
                          ttl_seconds=60, reason="test")
    bus.emit(FleetEvent(type="workflow.resolved"))
    assert calls == []
    decided = [e for e in audit.entries if e["action"] == "ambient.decided"]
    assert decided[-1]["details"]["spawn_outcome"]["skipped_reason"] == "kill-switch"


# ----- CypherTrigger paths --------------------------------------------------


@pytest.mark.asyncio
async def test_cypher_two_rows_two_spawns():
    audit = _FakeAudit()
    graph = _FakeGraph(rows=[{"id": "A"}, {"id": "B"}])
    spawner, calls = _make_spawner()
    agent = AmbientAgent(
        name="cyp1", function="finance",
        triggers=(CypherTrigger(pattern="MATCH (m) RETURN m", sweep_seconds=0),),
        spawnable_workflow_types=("variance-investigation",),
    )
    disp = AmbientDispatcher(
        bus=EventBus(), graph=graph, audit=audit,
        spawn_workflow=spawner, agents={"cyp1": agent},
    )
    disp.start()
    # Yield control several times to let the sweep loop run.
    for _ in range(10):
        await asyncio.sleep(0)
    await disp.aclose()

    assert len(calls) >= 2
    decided = [e for e in audit.entries if e["action"] == "ambient.decided"]
    assert len([d for d in decided if d["details"]["spawn_outcome"]["spawned"]]) >= 2


@pytest.mark.asyncio
async def test_cypher_error_isolated():
    audit = _FakeAudit()
    graph = _FakeGraph(rows=[{"id": "Z"}], raises=RuntimeError("boom"))
    spawner, calls = _make_spawner()
    agent = AmbientAgent(
        name="cyp2", function="finance",
        triggers=(CypherTrigger(pattern="MATCH (m) RETURN m", sweep_seconds=0),),
        spawnable_workflow_types=("x",),
    )
    disp = AmbientDispatcher(
        bus=EventBus(), graph=graph, audit=audit,
        spawn_workflow=spawner, agents={"cyp2": agent},
    )
    disp.start()
    for _ in range(20):
        await asyncio.sleep(0)
    await disp.aclose()
    # First sweep raised; subsequent sweep returned the row → at least 1 spawn happened.
    assert len(calls) >= 1


@pytest.mark.asyncio
async def test_cypher_kill_switch_short_circuits():
    audit = _FakeAudit()
    graph = _FakeGraph(rows=[{"id": "X"}])
    spawner, calls = _make_spawner()
    agent = AmbientAgent(
        name="cyp3", function="finance",
        triggers=(CypherTrigger(pattern="MATCH (m) RETURN m", sweep_seconds=0),),
        spawnable_workflow_types=("x",),
    )
    disp = AmbientDispatcher(
        bus=EventBus(), graph=graph, audit=audit,
        spawn_workflow=spawner, agents={"cyp3": agent},
    )
    kill_switch_store.add(actor="ambient.cyp3", tool="spawn_workflow",
                          ttl_seconds=60, reason="halt")
    disp.start()
    for _ in range(10):
        await asyncio.sleep(0)
    await disp.aclose()
    assert calls == []


# ----- CadenceTrigger -------------------------------------------------------


def test_cadence_trigger_does_not_spawn_async_task():
    bus = EventBus()
    audit = _FakeAudit()
    spawner, calls = _make_spawner()
    agent = AmbientAgent(
        name="cad1", function="finance",
        triggers=(CadenceTrigger(cron="0 9 * * *"),),
        spawnable_workflow_types=("x",),
    )
    disp = AmbientDispatcher(
        bus=bus, graph=_FakeGraph(), audit=audit,
        spawn_workflow=spawner, agents={"cad1": agent},
    )
    disp.start()
    # No bus subscription, no asyncio task created.
    assert disp._cypher_tasks == []
    assert disp._bus_offs == []
    # Cadence registered for introspection.
    assert any("registered_cadence" in d for d in disp._ring["cad1"])
    assert calls == []
