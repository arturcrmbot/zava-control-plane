"""
Fleet Manager service — long-running GHCP SDK session that consumes triage-filtered
events, debounces them, and reasons over batches via send_and_wait, calling tools as needed.

API surface uses the Phase 0.2 spike's findings; see spike/MAF-DURABLE-NOTES.md §2.
"""
from __future__ import annotations
import asyncio
import subprocess
import time
from pathlib import Path
from typing import Callable

from copilot import CopilotClient
from copilot.client import SubprocessConfig
from copilot.session import PermissionHandler
from copilot.generated.session_events import SessionEventType
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.audit_logger import AuditLogger
from api.server.services.fleet_manager_queue import FleetManagerQueue, QueueEntry
from api.server.services.triage import Triage
from api.server.mcp_tools import build_fleet_manager_tools
from api.shared.events import FleetEvent


def _gh_token() -> str:
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


_tracer = trace.get_tracer("zava.fleet_manager")


def _domain_catalogue_section() -> str:
    """Render the registered-domains section appended to the FM skill text.

    Reads api.shared.domains.DOMAINS at session-start time so a new
    compose-domain graduation lands in the FM's prompt without editing
    SKILL.md by hand.
    """
    from api.shared import domains as _registry
    lines = ["## Domains under supervision (auto-templated from registry)\n"]
    for d in _registry.DOMAINS.values():
        gates = ", ".join(g.external_event for g in d.hitl_gates) or "(none)"
        wakes = ", ".join(w.event for w in d.wake_hints) or "(none)"
        lines.append(
            f"- **{d.workflow_type}** — {d.display_name} · "
            f"operator surface: {d.operator_surface} · "
            f"HITL events: {gates} · wake hints: {wakes}"
        )
    lines.append(
        "\nWhen reasoning about an event, identify the domain via the "
        "`workflow_type` field on the bus and use the matching display "
        "name + operator surface in any compose-exception copy."
    )
    return "\n".join(lines)


def _function_identity_section(function_name: str) -> str:
    """Render the per-function identity block prepended to the FM skill text.

    Reads ``api.shared.functions.FUNCTIONS[function_name]`` at session-start
    time and renders five markdown blocks: header (``## You are the
    <Display> Function FM``), KPIs you own, domains you cover, persona
    hierarchy (indented bullet tree), and ambient watchers active for you.

    Plan: plan/feature-agentic-org-phase-3-function-fms.md TASK-026.
    """
    from api.shared.functions import FUNCTIONS, PersonaTree

    if function_name not in FUNCTIONS:
        raise ValueError(f"unknown function: {function_name!r}")
    fn = FUNCTIONS[function_name]

    def _render_tree(node: "PersonaTree", depth: int) -> list[str]:
        out = ["  " * depth + f"- {node.role}"]
        for child in node.manages:
            out.extend(_render_tree(child, depth + 1))
        return out

    kpis = ", ".join(fn.kpis) if fn.kpis else "(none)"
    domains = ", ".join(fn.owns_domains) if fn.owns_domains else "(none)"
    watchers = ", ".join(fn.ambient_agents) if fn.ambient_agents else "(none)"

    lines = [
        f"## You are the {fn.display} Function FM",
        "",
        f"You operate as the function-scoped Fleet Manager for **{fn.display}** "
        f"(operator surface: `{fn.operator_surface}`). Your tools, decisions, "
        "and KPIs are constrained to the domains your function owns.",
        "",
        "## KPIs you own",
        "",
        f"{kpis}",
        "",
        "## Domains you cover",
        "",
        f"{domains}",
        "",
        "## Persona hierarchy",
        "",
    ]
    lines.extend(_render_tree(fn.persona_hierarchy, 0))
    lines.extend(
        [
            "",
            "## Ambient watchers active for you",
            "",
            f"{watchers}",
        ]
    )
    return "\n".join(lines)


class FleetManagerService:
    def __init__(self, *, bus: EventBus | None = None, store: StateStore,
                 audit: AuditLogger,
                 model: str = "gpt-4.1", on_live: Callable[[dict], None] | None = None,
                 function: str | None = None,
                 tools: list | None = None,
                 hub=None):
        self._bus = bus
        self._store = store
        self._audit = audit
        self._model = model
        self._on_live = on_live or (lambda e: None)
        # Phase 3 (TASK-025) — per-function identity. ``None`` keeps the
        # existing fleet-wide singleton behaviour unchanged.
        self._function = function
        # Per-function FMs ship their own pre-built tool list via the
        # build_function_fm_tools factory; the fleet-wide singleton
        # leaves this None and lets start() build the default surface.
        self._tools_override = tools
        # Optional SSEHub reference — held for symmetry with TASK-028's
        # AppState wiring (per-function FMs can broadcast over their own
        # ``fleet-manager.<name>`` topic). Not required by start().
        self._hub = hub

        self._client: CopilotClient | None = None
        self._session = None
        self._unsub_session_events: Callable[[], None] | None = None
        self._unsub_bus: Callable[[], None] | None = None
        # Tool spans opened by TOOL_EXECUTION_START, closed by TOOL_EXECUTION_COMPLETE;
        # parented to the current reasoning span opened in _process_batch.
        self._open_tool_spans: dict[str, object] = {}
        self._reasoning_parent_ctx = None
        self._triage = Triage()
        self._queue = FleetManagerQueue(self._process_batch, debounce_ms=2000)
        self._tick_task: asyncio.Task | None = None
        self._started = False

    def _build_skill_text(self) -> str:
        """Compose the SKILL prompt for this FM session.

        - Fleet-wide (``self._function is None``): SKILL.md + the
          domain-catalogue auto-template (existing behaviour).
        - Function-scoped: the per-function identity block is prepended
          to the same fleet-wide skill body so the function FM still
          inherits all triage / batching / autonomy guidance.

        Extracted as a method so tests can introspect the templated
        prompt without driving the full ``start()`` pathway (which
        requires a live Copilot subprocess).
        """
        skill_path = Path(__file__).resolve().parents[1] / "skills" / "fleet-manager" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")
        skill_text += "\n\n" + _domain_catalogue_section()
        if self._function is not None:
            skill_text = _function_identity_section(self._function) + "\n\n" + skill_text
        return skill_text

    async def start(self) -> None:
        if self._started:
            return
        try:
            token = _gh_token()
        except Exception as ex:
            print(f"[fleet-manager] gh auth token failed: {ex}; not starting")
            return

        # The CopilotClient owns a node subprocess. If anything between
        # `client.start()` and `_started = True` raises, we must tear that
        # subprocess down here \u2014 otherwise the lifespan's `try: stop() except`
        # finds nothing to stop and the orphan keeps running across reloads.
        config = SubprocessConfig(github_token=token, log_level="warning")
        self._client = CopilotClient(config)
        try:
            await self._client.start()  # explicit start (alternative to async-with for long-lived)

            skill_text = self._build_skill_text()
            tools = self._tools_override if self._tools_override is not None else build_fleet_manager_tools(self._store, self._audit)

            self._session = await self._client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                model=self._model,
                tools=tools,
                system_message={"mode": "append", "content": skill_text},
            )

            # Subscribe to session events (single catch-all; filter inside)
            self._unsub_session_events = self._session.on(self._on_session_event)

            # Subscribe to the bus \u2014 every event flows through triage
            self._unsub_bus = self._bus.on_any(self._observe)

            # Periodic 30s tick
            self._tick_task = asyncio.create_task(self._tick_loop())
        except Exception as ex:
            print(f"[fleet-manager] start failed mid-init: {ex}; cleaning up")
            await self._safe_partial_teardown()
            raise

        self._started = True
        print("[fleet-manager] started")
        self._on_live({"kind": "idle", "timestamp": time.time()})

    async def _safe_partial_teardown(self) -> None:
        """Tear down whatever was constructed before start() raised.

        Mirrors stop() but every step is best-effort and the order matches
        construction-reverse: tick task, bus sub, session sub, session,
        client. Leaves attributes nulled so a retried start() begins fresh.
        """
        if self._tick_task is not None:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except (asyncio.CancelledError, Exception):
                pass
            self._tick_task = None
        if self._unsub_bus is not None:
            try:
                self._unsub_bus()
            except Exception:
                pass
            self._unsub_bus = None
        if self._unsub_session_events is not None:
            try:
                self._unsub_session_events()
            except Exception:
                pass
            self._unsub_session_events = None
        if self._session is not None:
            try:
                await self._session.disconnect()
            except Exception:
                pass
            self._session = None
        if self._client is not None:
            try:
                await self._client.stop()
            except Exception:
                pass
            self._client = None

    def _on_session_event(self, event) -> None:
        if event.type == SessionEventType.TOOL_EXECUTION_START:
            data = event.data
            name = getattr(data, "tool_name", None)
            call_id = getattr(data, "tool_call_id", None)
            # Open a child span under the current reasoning span (if any)
            parent_ctx = self._reasoning_parent_ctx
            try:
                span = _tracer.start_span(
                    f"tool.{name or 'unknown'}",
                    context=parent_ctx,
                )
                if name is not None:
                    span.set_attribute("zava.tool.name", str(name))
                if call_id is not None:
                    span.set_attribute("zava.tool.call_id", str(call_id))
                    self._open_tool_spans[call_id] = span
                else:
                    # Without a call_id we cannot correlate the complete event; end immediately.
                    span.end()
            except Exception:
                pass
            self._on_live({
                "kind": "tool_call",
                "timestamp": time.time(),
                "data": {
                    "stage": "start",
                    "name": name,
                    "args": getattr(data, "arguments", None),
                    "tool_call_id": call_id,
                }
            })
        elif event.type == SessionEventType.TOOL_EXECUTION_COMPLETE:
            data = event.data
            result_obj = getattr(data, "result", None)
            call_id = getattr(data, "tool_call_id", None)
            success = getattr(data, "success", None)
            try:
                span = self._open_tool_spans.pop(call_id, None) if call_id else None
                if span is not None:
                    if success is False:
                        span.set_status(Status(StatusCode.ERROR, "tool reported failure"))
                    span.end()
            except Exception:
                pass
            self._on_live({
                "kind": "tool_call",
                "timestamp": time.time(),
                "data": {
                    "stage": "complete",
                    "tool_call_id": call_id,
                    "success": success,
                    "result": getattr(result_obj, "content", None) if result_obj else None,
                }
            })

    def _observe(self, event: FleetEvent) -> None:
        # Update triage state, possibly emit derived anomaly event
        self._triage.observe(event)
        anomaly = self._triage.detect_anomaly()
        if anomaly:
            self._bus.emit(FleetEvent(
                type="fleet.anomaly.detected",
                pattern=anomaly["pattern"],
                workflow_ids=anomaly["workflow_ids"],
            ))
        # If wake-worthy, enqueue. Workflow-less wakes (fleet.tick,
        # fleet.anomaly.detected) are first-class — the queue handles them
        # via per-reason sentinel keys so the rail still pulses on idle demos.
        if self._triage.should_wake(event):
            self._queue.enqueue(QueueEntry(workflow_id=event.workflow_id, reason=event.type))
            self._on_live({
                "kind": "wakeup",
                "timestamp": time.time(),
                "data": {"workflow_id": event.workflow_id, "reason": event.type},
            })

    async def _tick_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(30)
                self._bus.emit(FleetEvent(type="fleet.tick", timestamp=time.time()))
            except asyncio.CancelledError:
                break

    async def _process_batch(self, batch: list[QueueEntry]) -> None:
        if self._queue.depth() > 20:
            self._bus.emit(FleetEvent(type="fleet.overload", queue_depth=self._queue.depth()))

        self._on_live({
            "kind": "reasoning_start",
            "timestamp": time.time(),
            "data": {
                "batch_size": len(batch),
                "workflow_ids": [b.workflow_id for b in batch],
            }
        })

        prompt_lines = [
            (f"- workflow={b.workflow_id} reason={b.reason}"
             if b.workflow_id else f"- reason={b.reason}")
            for b in batch
        ]
        prompt = (
            "Triggering events:\n"
            + "\n".join(prompt_lines)
            + "\n\nFollow the SKILL instructions. Call tools as needed. Prefer bulk grouping."
        )

        with _tracer.start_as_current_span("gen_ai.agent.run") as span:
            span.set_attribute("gen_ai.agent.name", "fleet-manager-agent")
            span.set_attribute("zava.fleet_manager.batch_size", len(batch))
            span.set_attribute(
                "zava.fleet_manager.workflow_ids",
                [b.workflow_id for b in batch if b.workflow_id],
            )
            # Capture context so session-event tool spans attach as children.
            self._reasoning_parent_ctx = trace.set_span_in_context(span)
            try:
                event = await self._session.send_and_wait(prompt, timeout=120.0)
                preview = ""
                if event and getattr(event, "data", None):
                    preview = (getattr(event.data, "content", "") or "")[:200]
                self._on_live({
                    "kind": "reasoning_done",
                    "timestamp": time.time(),
                    "data": {"preview": preview, "batch_size": len(batch)},
                })
            except Exception as ex:
                span.record_exception(ex)
                span.set_status(Status(StatusCode.ERROR, str(ex)))
                self._on_live({
                    "kind": "error",
                    "timestamp": time.time(),
                    "data": {"message": str(ex)},
                })
            finally:
                self._reasoning_parent_ctx = None

    async def stop(self) -> None:
        if self._tick_task:
            self._tick_task.cancel()
        if self._unsub_session_events:
            self._unsub_session_events()
        if self._unsub_bus:
            self._unsub_bus()
        if self._session:
            await self._session.disconnect()
        if self._client:
            await self._client.stop()
        self._started = False

    # ----------------------------------------------------------------------
    # Phase 4 IP2 (TASK-011) — KPI publish API
    # ----------------------------------------------------------------------
    def publish_kpi(self, metric: str, value: float, period: str) -> None:
        """Publish one KPI snapshot for this FM's function.

        Writes via :class:`api.server.services.kpi_store.KpiStore` and
        emits an SSE event on the FM's per-function topic. No-op for the
        fleet-wide singleton (``self._function is None``) since fleet-
        wide KPIs aren't a thing in the schema.
        """
        if self._function is None:
            return
        from api.server.state import app_state
        from api.shared.functions import FUNCTIONS

        schema_version = FUNCTIONS[self._function].kpi_schema_version
        app_state.kpi_store.publish(
            self._function, metric, value, period, schema_version,
        )
        try:
            self._on_live({
                "type": "kpi.published",
                "function": self._function,
                "metric": metric,
                "value": value,
                "period": period,
                "schema_version": schema_version,
            })
        except Exception:  # pragma: no cover — SSE broadcast is best-effort
            pass
        # C3: mirror to the bus so observatory listeners (cosmic lens,
        # blueprint relay) see KPI publications without subscribing to
        # the SSE callback.
        try:
            from api.shared.events import FleetEvent
            self._bus.emit(FleetEvent(
                type="kpi.published",
                function=self._function,
                metric=metric,
                value=value,
                period=period,
            ))
        except Exception:  # pragma: no cover
            pass


# Phase 3 blueprint primitive name (TASK-025). The ``Function`` Fleet
# Manager is implementation-identical to ``FleetManagerService`` — only
# the constructor's ``function=`` flag differs at call sites.
FunctionFleetManager = FleetManagerService
