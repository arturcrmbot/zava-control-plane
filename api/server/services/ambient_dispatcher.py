"""Ambient agent dispatch loop — Phase 3 of plan/feature-agentic-org-phase-3-function-fms.md.

``AmbientDispatcher`` subscribes every declared ``AmbientAgent``'s
triggers to the right substrate primitive:

- ``BusTrigger``  → ``bus.on(event_type, handler)`` (sync handler from
  ``bus.emit``)
- ``CypherTrigger`` → ``asyncio.Task`` running ``_cypher_sweep_loop``
  (periodic ``graph.query``)
- ``CadenceTrigger`` → registered but NOT fired in Phase 3. Phase 4's
  cadence loop calls ``await dispatcher.dispatch(agent_name, ctx)``.

Each spawn path is gated by the kill switch
(``ambient.<agent.name>`` × ``spawn_workflow``). Successful + skipped
decisions both emit an ``ambient.decided`` audit entry.

Async/sync boundary:

- ``_handle_bus_trigger`` is **sync** because ``EventBus.emit`` calls
  handlers synchronously. It schedules spawns on a fire-and-forget
  ``asyncio.create_task`` if a running loop is available; otherwise it
  invokes the spawner with ``asyncio.run``.
- ``_cypher_sweep_loop`` and ``dispatch`` are **async** — driven by
  the dispatcher's own asyncio tasks / Phase 4's cadence loop.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from functools import partial
from typing import Any, Awaitable, Callable

from api.server.services.ambient_agents import (
    AMBIENT_AGENTS,
    AmbientAgent,
    BusTrigger,
    CadenceTrigger,
    CypherTrigger,
    Trigger,
)
from api.server.services.governance.kill_switch import kill_switch_store
from api.server.services.persona_responder import _DECISION_BUILTINS as _AMBIENT_BUILTINS
from api.shared.events import FleetEvent

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Safe-eval helper (TASK-015 / TASK-017)
# --------------------------------------------------------------------------


def _eval_filter(expr: str, ctx: dict[str, Any]) -> bool:
    """Safe-eval a BusTrigger filter expression against an event context.

    Uses the same whitelist (``_DECISION_BUILTINS``) as the persona
    responder, so callers cannot reach ``__import__`` / ``eval`` /
    ``exec`` / etc. Compile errors and runtime exceptions are caught
    and treated as "filter returned False" (no spawn).
    """
    if not expr:
        return True
    try:
        code = compile(expr, "<bus_filter>", "eval")
        result = eval(code, {"__builtins__": _AMBIENT_BUILTINS}, dict(ctx))
        return bool(result)
    except Exception as ex:
        log.warning("ambient_dispatcher: filter eval failed (%r): %s", expr, ex)
        return False


# --------------------------------------------------------------------------
# AmbientDispatcher
# --------------------------------------------------------------------------


SpawnFn = Callable[[str, dict[str, Any]], Awaitable[Any]]


class AmbientDispatcher:
    """Wires every declared AmbientAgent into the right substrate path.

    Constructor injects the four substrate dependencies (bus, graph,
    audit, spawner). Tests pass mocks for each. The dispatcher owns
    the bus-unsubscribe handles and the cypher sweep tasks; ``aclose``
    tears both down.
    """

    def __init__(
        self,
        *,
        bus: Any,
        graph: Any,
        audit: Any,
        spawn_workflow: SpawnFn,
        agents: dict[str, AmbientAgent] | None = None,
    ) -> None:
        self._bus = bus
        self._graph = graph
        self._audit = audit
        self._spawn_workflow = spawn_workflow
        # Snapshot the registry at construction so monkeypatching
        # ``AMBIENT_AGENTS`` in tests is honoured if done before
        # instantiation. Callers can override via ``agents=`` kwarg.
        self._agents: dict[str, AmbientAgent] = dict(agents if agents is not None else AMBIENT_AGENTS)
        self._bus_offs: list[Callable[[], None]] = []
        self._cypher_tasks: list[asyncio.Task] = []
        self._ring: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
        self._started = False

    # -- lifecycle --------------------------------------------------

    def start(self) -> None:
        """Subscribe bus triggers + spawn cypher sweep tasks. Cadence
        triggers are registered (counted) but not fired."""
        if self._started:
            return
        self._started = True
        for agent in self._agents.values():
            for trigger in agent.triggers:
                if isinstance(trigger, BusTrigger):
                    handler = partial(self._handle_bus_trigger, agent, trigger)
                    off = self._bus.on(trigger.event_type, handler)
                    self._bus_offs.append(off)
                elif isinstance(trigger, CypherTrigger):
                    task = asyncio.create_task(self._cypher_sweep_loop(agent, trigger))
                    self._cypher_tasks.append(task)
                elif isinstance(trigger, CadenceTrigger):
                    # Registered for introspection only — Phase 4 cadence
                    # loop drives via dispatch().
                    self._ring[agent.name].append({"registered_cadence": trigger.cron})
                else:  # pragma: no cover — exhaustive union
                    log.warning("ambient_dispatcher: unknown trigger %r", trigger)

    async def aclose(self) -> None:
        """Unsubscribe bus handlers + cancel cypher sweep tasks."""
        for off in self._bus_offs:
            try:
                off()
            except Exception:  # pragma: no cover
                pass
        self._bus_offs.clear()
        for task in self._cypher_tasks:
            task.cancel()
        for task in self._cypher_tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._cypher_tasks.clear()
        self._started = False

    def get_state(self, agent_name: str) -> dict[str, Any]:
        """Return the recent decision ring for an agent (Phase 4 surface)."""
        return {
            "agent": agent_name,
            "recent": list(self._ring.get(agent_name, ())),
        }

    # -- public dispatch entrypoint (TASK-018b) ---------------------

    async def dispatch(self, agent_name: str, trigger_ctx: dict[str, Any]) -> None:
        """Public entrypoint used by Phase 4's cadence loop.

        Runs the same kill-switch + filter + spawn pipeline as the bus
        handler, but parameterised by an externally-supplied
        ``trigger_ctx`` (whose ``kind`` is typically ``"cadence"``).
        Raises ``KeyError`` if ``agent_name`` is unknown.
        """
        if agent_name not in self._agents:
            raise KeyError(f"unknown ambient agent: {agent_name!r}")
        agent = self._agents[agent_name]
        kind = trigger_ctx.get("kind", "unknown")

        if self._is_killed(agent):
            self._audit_decided(agent, kind, trigger_ctx, spawn_outcome={
                "spawned": False, "skipped_reason": "kill-switch",
            })
            return

        # External callers may pass a "filter" key + "event" payload to
        # opt into safe-eval; otherwise we just spawn unconditionally.
        filter_expr = trigger_ctx.get("filter", "")
        eval_ctx = trigger_ctx.get("event", {}) or {}
        if filter_expr and not _eval_filter(filter_expr, eval_ctx):
            self._audit_decided(agent, kind, trigger_ctx, spawn_outcome={
                "spawned": False, "skipped_reason": "filter-false",
            })
            return

        spawned = await self._spawn_for_agent(agent, base_payload={
            "trigger": kind, "ctx": trigger_ctx,
        })
        self._audit_decided(agent, kind, trigger_ctx, spawn_outcome={
            "spawned": True, "workflow_ids": spawned,
        })

    # -- bus path (TASK-016) ----------------------------------------

    def _handle_bus_trigger(
        self, agent: AmbientAgent, trigger: BusTrigger, event: FleetEvent,
    ) -> None:
        """Sync handler invoked from ``EventBus.emit``."""
        if self._is_killed(agent):
            self._audit_decided(agent, "bus", {
                "event_type": trigger.event_type, "event": _safe_dump(event),
            }, spawn_outcome={"spawned": False, "skipped_reason": "kill-switch"})
            return

        event_dict = _safe_dump(event)
        if trigger.filter and not _eval_filter(trigger.filter, event_dict):
            self._audit_decided(agent, "bus", {
                "event_type": trigger.event_type, "event": event_dict,
            }, spawn_outcome={"spawned": False, "skipped_reason": "filter-false"})
            return

        # We're in a sync context (bus.emit). Run the async spawn
        # synchronously — tests drive ``bus.emit`` from inside an
        # async test, so we cannot ``asyncio.run``. Use the running
        # loop via ``run_until_complete`` if one exists, else create
        # a fresh loop. Easiest path: schedule on the current loop
        # when one is running.
        spawned = _run_sync(self._spawn_for_agent(agent, base_payload={
            "trigger": "bus", "event": event_dict,
        }))
        self._audit_decided(agent, "bus", {
            "event_type": trigger.event_type, "event": event_dict,
        }, spawn_outcome={"spawned": True, "workflow_ids": spawned})

    # -- cypher path (TASK-017) -------------------------------------

    async def _cypher_sweep_loop(
        self, agent: AmbientAgent, trigger: CypherTrigger,
    ) -> None:
        """Per-CypherTrigger periodic sweep. Per-iteration exception
        isolation so a single Cypher error does not kill the loop."""
        while True:
            try:
                await asyncio.sleep(trigger.sweep_seconds)
            except asyncio.CancelledError:
                break
            try:
                if self._is_killed(agent):
                    self._audit_decided(agent, "cypher", {
                        "pattern": trigger.pattern,
                    }, spawn_outcome={"spawned": False, "skipped_reason": "kill-switch"})
                    continue
                rows = self._graph.query(trigger.pattern)
                for row in rows or []:
                    spawned = await self._spawn_for_agent(agent, base_payload={
                        "trigger": "cypher", "match": row,
                    })
                    self._audit_decided(agent, "cypher", {
                        "pattern": trigger.pattern, "match": row,
                    }, spawn_outcome={"spawned": True, "workflow_ids": spawned})
            except asyncio.CancelledError:
                break
            except Exception as ex:
                log.warning(
                    "ambient_dispatcher: cypher sweep failed for %s: %s",
                    agent.name, ex,
                )
                continue

    # -- shared spawn helper ----------------------------------------

    async def _spawn_for_agent(
        self, agent: AmbientAgent, *, base_payload: dict[str, Any],
    ) -> list[Any]:
        """Spawn every workflow_type in agent.spawnable_workflow_types.

        Returns the list of spawn results (workflow ids or ``None`` for
        not-yet-graduated meta-workflows; see TASK-013 in the OVERALL
        plan).
        """
        out: list[Any] = []
        for wt in agent.spawnable_workflow_types:
            try:
                result = self._spawn_workflow(wt, dict(base_payload))
                if asyncio.iscoroutine(result):
                    result = await result
            except Exception as ex:
                log.warning(
                    "ambient_dispatcher: spawn %s by %s failed: %s",
                    wt, agent.name, ex,
                )
                result = None
            out.append(result)
        return out

    # -- governance + audit -----------------------------------------

    def _is_killed(self, agent: AmbientAgent) -> bool:
        return kill_switch_store.is_killed(
            f"ambient.{agent.name}", "spawn_workflow",
        ) is not None

    def _audit_decided(
        self,
        agent: AmbientAgent,
        trigger_kind: str,
        trigger_payload: dict[str, Any],
        *,
        spawn_outcome: dict[str, Any],
    ) -> None:
        details = {
            "ambient_agent": agent.name,
            "function": agent.function,
            "trigger_kind": trigger_kind,
            "trigger_payload": trigger_payload,
            "spawn_outcome": spawn_outcome,
        }
        try:
            self._audit.log("ambient.decided", details)
        except Exception as ex:  # pragma: no cover
            log.warning("ambient_dispatcher: audit append failed: %s", ex)
        self._ring[agent.name].append(details)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _safe_dump(event: Any) -> dict[str, Any]:
    """Coerce a FleetEvent (or dict) into a plain dict for filter eval + audit."""
    if hasattr(event, "model_dump"):
        try:
            return event.model_dump()
        except Exception:
            pass
    if isinstance(event, dict):
        return dict(event)
    return {"value": repr(event)}


def _run_sync(coro_or_value: Any) -> Any:
    """Drive an async result to completion from a sync context.

    The injected spawner is typed as async but tests may pass a sync
    Mock; handle both. If we're already inside a running event loop,
    schedule the coroutine without blocking (returns the Task).
    Otherwise run it to completion via ``asyncio.run``.
    """
    if not asyncio.iscoroutine(coro_or_value):
        return coro_or_value
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is None:
        return asyncio.run(coro_or_value)
    task = loop.create_task(coro_or_value)
    return task
