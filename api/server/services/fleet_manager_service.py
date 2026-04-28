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


_tracer = trace.get_tracer("wpp.fleet_manager")


class FleetManagerService:
    def __init__(self, *, bus: EventBus, store: StateStore, audit: AuditLogger,
                 model: str = "gpt-4.1", on_live: Callable[[dict], None] | None = None):
        self._bus = bus
        self._store = store
        self._audit = audit
        self._model = model
        self._on_live = on_live or (lambda e: None)

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

    async def start(self) -> None:
        if self._started:
            return
        try:
            token = _gh_token()
        except Exception as ex:
            print(f"[fleet-manager] gh auth token failed: {ex}; not starting")
            return

        config = SubprocessConfig(github_token=token, log_level="warning")
        self._client = CopilotClient(config)
        await self._client.start()  # explicit start (alternative to async-with for long-lived)

        skill_path = Path(__file__).resolve().parents[1] / "skills" / "fleet-manager" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")
        tools = build_fleet_manager_tools(self._store, self._audit)

        self._session = await self._client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model=self._model,
            tools=tools,
            system_message={"mode": "append", "content": skill_text},
        )

        # Subscribe to session events (single catch-all; filter inside)
        self._unsub_session_events = self._session.on(self._on_session_event)

        # Subscribe to the bus — every event flows through triage
        self._unsub_bus = self._bus.on_any(self._observe)

        # Periodic 30s tick
        self._tick_task = asyncio.create_task(self._tick_loop())

        self._started = True
        print("[fleet-manager] started")
        self._on_live({"kind": "idle", "timestamp": time.time()})

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
                    span.set_attribute("wpp.tool.name", str(name))
                if call_id is not None:
                    span.set_attribute("wpp.tool.call_id", str(call_id))
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
        # If wake-worthy and has workflow_id, enqueue
        if self._triage.should_wake(event) and event.workflow_id:
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

        prompt_lines = [f"- workflow={b.workflow_id} reason={b.reason}" for b in batch]
        prompt = (
            "Triggering events:\n"
            + "\n".join(prompt_lines)
            + "\n\nFollow the SKILL instructions. Call tools as needed. Prefer bulk grouping."
        )

        with _tracer.start_as_current_span("gen_ai.agent.run") as span:
            span.set_attribute("gen_ai.agent.name", "fleet-manager-agent")
            span.set_attribute("wpp.fleet_manager.batch_size", len(batch))
            span.set_attribute(
                "wpp.fleet_manager.workflow_ids",
                [b.workflow_id for b in batch],
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
