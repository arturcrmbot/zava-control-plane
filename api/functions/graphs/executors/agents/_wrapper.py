# src/functions/graphs/executors/agents/_wrapper.py
"""
Helper for invoking a finance-agent skill via the GHCP SDK natively.

Pattern (post-2026-04-28 retrofit):
1. Create an ephemeral CopilotSession with `skill_directories=[skills_dir]`
   and `tools=[Tool, ...]`. The SDK auto-discovers `*.skill.md` files and
   registers the tools natively. The model invokes the tools per the skill's
   `allowed-tools` frontmatter — *no* prompt-stuffing of tool results.
2. Subscribe `session.on(...)` -> OTEL bridge so tool calls appear as child spans.
3. Send the user prompt via `send_and_wait` (with optional `attachments` for
   multimodal). Return the parsed JSON object from the response text.
4. Emit a FleetEvent("agent.completed", ...) so the eval subscriber can score
   the invocation. Wrapped in try/except — eval pipeline failures must never
   propagate up into the caller.

The agent identity is "finance-agent" universally; specialisation comes from
the loaded skill, matching the spec's "specialisation via skills, not via
separate agents" pattern.
"""
from __future__ import annotations
import asyncio
import json
import subprocess
import time
import uuid
from pathlib import Path

from copilot import CopilotClient
from copilot.client import SubprocessConfig
from copilot.session import PermissionHandler
from copilot.generated.session_events import SessionEventType
from copilot.tools import Tool
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from api.server.state import app_state
from api.shared.events import FleetEvent


_SKILLS_DIR = Path(__file__).resolve().parents[4] / "server" / "skills"
SKILLS_DIR = _SKILLS_DIR
_tracer = trace.get_tracer("zava.agents.finance")
_MAX_RESPONSE_EVENT_BYTES = 4096


_gh_token_cache: str | None = None


def _gh_token() -> str:
    """Return the gh CLI auth token, cached for the lifetime of the process."""
    global _gh_token_cache
    if _gh_token_cache is None:
        _gh_token_cache = subprocess.check_output(
            ["gh", "auth", "token"], text=True,
        ).strip()
    return _gh_token_cache


def _load_skill(skill_dir: Path) -> str:
    return (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def _install_session_otel_bridge(
    session,
    tool_calls_out: list[dict],
    *,
    workflow_id: str | None = None,
    skill_label: str | None = None,
) -> callable:
    """Bridge GHCP session events -> OTEL child spans + collect a flat list of
    completed tool calls into `tool_calls_out` for the eval payload + emit
    per-tool `tool.invoked` webhooks so the observatory orbit lights up the
    MCP nodes in near-real time.

    TOOL_EXECUTION_START opens a span keyed by tool_call_id, and fires a
    `tool.invoked` (stage=start) webhook so the page can flare the
    skill->tool edge immediately.
    TOOL_EXECUTION_COMPLETE closes the span, appends to `tool_calls_out`,
    and fires a `tool.invoked` (stage=complete) webhook.
    """
    open_spans: dict[str, object] = {}
    open_meta: dict[str, dict] = {}
    parent_ctx = trace.set_span_in_context(trace.get_current_span())
    # Capture the running loop so the synchronous SDK callback can schedule
    # async emits without blocking.
    try:
        _loop = asyncio.get_running_loop()
    except RuntimeError:
        _loop = None

    def _fire_tool_webhook(stage: str, tool_name: str, *, latency_ms: int = 0) -> None:
        if _loop is None or workflow_id is None:
            return
        from api.functions.webhook import emit as _webhook_emit

        async def _send():
            await _webhook_emit(
                workflow_id, workflow_id, "tool.invoked",
                {
                    "tool": tool_name,
                    "skill": skill_label,
                    "stage": stage,
                    "duration_ms": latency_ms,
                },
            )
        try:
            _loop.call_soon_threadsafe(
                lambda: _loop.create_task(_send()),
            )
        except Exception:
            pass

    def on_event(event) -> None:
        try:
            if event.type == SessionEventType.TOOL_EXECUTION_START:
                data = event.data
                name = getattr(data, "tool_name", "unknown")
                call_id = getattr(data, "tool_call_id", None)
                args = getattr(data, "tool_args", None) or getattr(data, "arguments", None) or ""
                if not isinstance(args, str):
                    try:
                        args = json.dumps(args)
                    except Exception:
                        args = str(args)
                span = _tracer.start_span(f"tool.{name}", context=parent_ctx)
                span.set_attribute("zava.tool.name", str(name))
                if call_id:
                    span.set_attribute("zava.tool.call_id", str(call_id))
                    open_spans[call_id] = span
                    open_meta[call_id] = {
                        "name": str(name), "args": args, "started_at": time.monotonic(),
                    }
                # Fire an observatory webhook so the page lights up the
                # skill -> tool edge in near-real-time.
                _fire_tool_webhook("start", str(name))
            elif event.type == SessionEventType.TOOL_EXECUTION_COMPLETE:
                data = event.data
                call_id = getattr(data, "tool_call_id", None)
                span = open_spans.pop(call_id, None) if call_id else None
                meta = open_meta.pop(call_id, None) if call_id else None
                if span is not None:
                    success = getattr(data, "success", None)
                    if success is False:
                        span.set_status(Status(StatusCode.ERROR, "tool reported failure"))
                    span.end()
                if meta is not None:
                    result_text = getattr(data, "result", None) or getattr(data, "output", None) or ""
                    if not isinstance(result_text, str):
                        try:
                            result_text = json.dumps(result_text)
                        except Exception:
                            result_text = str(result_text)
                    latency_ms = int((time.monotonic() - meta["started_at"]) * 1000)
                    tool_calls_out.append({
                        "name": meta["name"],
                        "args": meta["args"],
                        "result": result_text,
                        "success": getattr(data, "success", True) is not False,
                        "latency_ms": latency_ms,
                    })
                    _fire_tool_webhook("complete", meta["name"], latency_ms=latency_ms)
        except Exception:
            pass

    return session.on(on_event)


def _extract_json(text: str) -> dict:
    obj_start = text.find("{")
    obj_end = text.rfind("}")
    arr_start = text.find("[")
    arr_end = text.rfind("]")

    if obj_start >= 0 and obj_end > obj_start:
        try:
            return json.loads(text[obj_start:obj_end + 1])
        except json.JSONDecodeError:
            pass
    if arr_start >= 0 and arr_end > arr_start:
        try:
            result = json.loads(text[arr_start:arr_end + 1])
            return {"items": result} if isinstance(result, list) else result
        except json.JSONDecodeError:
            pass
    return {"raw": text, "parse_error": True}


async def run_agent_session(
    prompt: str,
    *,
    tools: list[Tool] | None = None,
    skill_dir: Path | None = None,
    skill_label: str | None = None,
    model: str = "gpt-4.1",
    attachments: list[dict] | None = None,
    workflow_id: str | None = None,
) -> dict:
    """Run a finance-agent ephemeral session and return the parsed JSON response.

    Args:
        prompt: The user prompt — per-call context.
        tools: SDK-native tools registered on the session via `tools=[...]`.
        skill_dir: Path to the skill's directory (containing SKILL.md).
        skill_label: Optional OTEL span tag. Also drives evaluator selection
            in the online subscriber.
        model: Model id (default `gpt-4.1`).
        attachments: Optional multimodal attachments for `send_and_wait`.
        workflow_id: Durable Functions instance_id, plumbed through from the
            executor's input dict, so eval rows can be joined to the workflow
            on the control plane.
    """
    tools = tools or []
    skill_text = _load_skill(skill_dir) if skill_dir else None
    tool_calls_collected: list[dict] = []
    started_at = time.monotonic()
    in_tok = out_tok = None

    with _tracer.start_as_current_span("gen_ai.generate_content") as span:
        span.set_attribute("gen_ai.system", "github_copilot")
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.agent.name", "finance-agent")
        if skill_label:
            span.set_attribute("zava.skill", skill_label)
        # 2026-05-05: workflow_id stamped so Foundry Tracing can filter
        # spans by workflow. Span attribute → App Insights customDimensions.
        if workflow_id:
            span.set_attribute("workflow.id", workflow_id)
            span.set_attribute("zava.workflow.id", workflow_id)
        span.set_attribute("zava.tools.count", len(tools))
        if attachments:
            span.set_attribute("gen_ai.attachments.count", len(attachments))

        config = SubprocessConfig(github_token=_gh_token(), log_level="warning")
        client = CopilotClient(config)
        async with client:
            session_kwargs: dict = {
                "on_permission_request": PermissionHandler.approve_all,
                "model": model,
                "tools": tools,
            }
            if skill_text:
                session_kwargs["system_message"] = {"mode": "append", "content": skill_text}
            if skill_dir:
                session_kwargs["skill_directories"] = [str(skill_dir)]
            session = await client.create_session(**session_kwargs)
            unsub = _install_session_otel_bridge(
                session,
                tool_calls_collected,
                workflow_id=workflow_id,
                skill_label=skill_label,
            )
            try:
                if attachments:
                    response_event = await session.send_and_wait(
                        prompt, attachments=attachments, timeout=120.0,
                    )
                else:
                    response_event = await session.send_and_wait(prompt, timeout=120.0)
            finally:
                try:
                    unsub()
                except Exception:
                    pass
                try:
                    await session.disconnect()
                except Exception:
                    pass

        text = ""
        if response_event and getattr(response_event, "data", None):
            text = getattr(response_event.data, "content", "") or ""

        event_text = text[:_MAX_RESPONSE_EVENT_BYTES]
        span.add_event("gen_ai.response", {"gen_ai.response.text": event_text})

        data = getattr(response_event, "data", None) if response_event else None
        usage = getattr(data, "usage", None) if data is not None else None
        if usage is not None:
            in_tok = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None)
            out_tok = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None)
            if in_tok is not None:
                span.set_attribute("gen_ai.usage.input_tokens", int(in_tok))
            if out_tok is not None:
                span.set_attribute("gen_ai.usage.output_tokens", int(out_tok))

    # Note: the OTEL span above is recorded in this (Functions host) process.
    # The FastAPI process — which serves /api/fleet/economics — receives the
    # token usage via the `agent.completed` webhook below and persists its own
    # gen_ai.generate_content span there. Don't `app_state.store.append_span`
    # here: it would write to the wrong process's store.
    elapsed_s = time.monotonic() - started_at
    parsed = _extract_json(text)
    elapsed_ms = int(elapsed_s * 1000)

    try:
        from api.server.eval.evaluator_set import extract_context
        context = extract_context(skill_label or "", tool_calls_collected)
    except Exception:
        context = ""

    # Cross-process emit: agent executors normally run in the Azure Functions
    # host process, while the online_subscriber lives in the FastAPI process.
    # Sending via the existing webhook bridge ensures the subscriber sees it.
    # `webhook.emit` is best-effort and swallows errors.
    #
    # Stamp realistic input-side context for the FastAPI-side token estimator:
    # - skill_chars: the SKILL.md system message (often 2-5k chars)
    # - attachment_count: each inline image counts ~1.1k input tokens for
    #   gpt-4.1 vision (low-detail). Without this, estimated_from_chars
    #   underreports multimodal calls by 10x.
    payload = {
        "agent_label": skill_label or "unknown",
        "agent_run_id": f"ar-{uuid.uuid4().hex[:8]}",
        "prompt": prompt,
        "response_text": text,
        "extracted_json": parsed,
        "tool_calls": tool_calls_collected,
        "context": context,
        "model": model,
        "skill_chars": len(skill_text) if skill_text else 0,
        "attachment_count": len(attachments) if attachments else 0,
        "usage": {
            "input_tokens": int(in_tok) if in_tok is not None else None,
            "output_tokens": int(out_tok) if out_tok is not None else None,
        },
        "latency_ms": elapsed_ms,
    }
    try:
        from api.functions.webhook import emit as _webhook_emit
        await _webhook_emit(workflow_id or "?", workflow_id, "agent.completed", payload)
    except Exception:
        pass

    return parsed


# Backwards-compatible alias for legacy agents that pass a skill_name string.
async def run_agent_skill(
    skill_name: str,
    prompt: str,
    model: str = "gpt-4.1",
    attachments: list[dict] | None = None,
    workflow_id: str | None = None,
) -> dict:
    """Deprecated alias — prefer `run_agent_session(skill_dir=..., tools=[...])`."""
    candidate = _SKILLS_DIR / skill_name
    if not candidate.is_dir():
        candidate = _SKILLS_DIR / skill_name.replace("_", "-")
    return await run_agent_session(
        prompt=prompt,
        skill_dir=candidate if candidate.is_dir() else None,
        skill_label=skill_name,
        model=model,
        attachments=attachments,
        workflow_id=workflow_id,
    )
