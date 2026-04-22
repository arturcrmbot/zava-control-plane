# src/functions/graphs/executors/agents/_wrapper.py
"""
Helper for invoking a finance-agent skill via the GHCP SDK directly.

Pattern: each agent executor function calls run_agent_skill(skill_name, prompt) which:
1. Loads the named SKILL.md as the system message
2. Creates an ephemeral CopilotSession per invocation
3. Subscribes session.on(...) → OTEL bridge so tool calls appear as child spans
4. Sends the prompt via send_and_wait
5. Parses the first JSON object from the response text
6. Returns the parsed dict (or {"raw": text, "parse_error": True} on failure)

The agent identity is "finance-agent" universally — single agent across all 9 skills,
matching the spec's "specialisation via skills, not via separate agents" pattern.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

from copilot import CopilotClient
from copilot.client import SubprocessConfig
from copilot.session import PermissionHandler
from copilot.generated.session_events import SessionEventType
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


_SKILLS_DIR = Path(__file__).resolve().parents[4] / "server" / "skills"
_tracer = trace.get_tracer("wpp.agents.finance")

# 4KB cap on response-text span-event payload (OTEL event attr size safety).
_MAX_RESPONSE_EVENT_BYTES = 4096


def _load_skill(name: str) -> str:
    return (_SKILLS_DIR / f"{name}.skill.md").read_text(encoding="utf-8")


def _gh_token() -> str:
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


def _install_session_otel_bridge(session) -> callable:
    """Bridge GHCP session events → OTEL child spans. Returns unsubscribe callable.

    TOOL_EXECUTION_START opens a span `tool.{name}` keyed by tool_call_id; the matching
    TOOL_EXECUTION_COMPLETE closes it with status derived from `.success`.
    """
    open_spans: dict[str, object] = {}
    parent_ctx = trace.set_span_in_context(trace.get_current_span())

    def on_event(event) -> None:
        try:
            if event.type == SessionEventType.TOOL_EXECUTION_START:
                data = event.data
                name = getattr(data, "tool_name", "unknown")
                call_id = getattr(data, "tool_call_id", None)
                span = _tracer.start_span(f"tool.{name}", context=parent_ctx)
                span.set_attribute("wpp.tool.name", str(name))
                if call_id:
                    span.set_attribute("wpp.tool.call_id", str(call_id))
                    open_spans[call_id] = span
            elif event.type == SessionEventType.TOOL_EXECUTION_COMPLETE:
                data = event.data
                call_id = getattr(data, "tool_call_id", None)
                span = open_spans.pop(call_id, None) if call_id else None
                if span is not None:
                    success = getattr(data, "success", None)
                    if success is False:
                        span.set_status(Status(StatusCode.ERROR, "tool reported failure"))
                    span.end()
        except Exception:
            # Observability must never crash the caller.
            pass

    return session.on(on_event)


async def run_agent_skill(skill_name: str, prompt: str, model: str = "gpt-4.1") -> dict:
    """Run a finance-agent ephemeral session loading the named skill, return parsed JSON output."""
    skill_text = _load_skill(skill_name)

    with _tracer.start_as_current_span("gen_ai.generate_content") as span:
        span.set_attribute("gen_ai.system", "github_copilot")
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.agent.name", "finance-agent")
        span.set_attribute("wpp.skill", skill_name)

        config = SubprocessConfig(github_token=_gh_token(), log_level="warning")
        client = CopilotClient(config)
        async with client:
            session = await client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                model=model,
                system_message={"mode": "append", "content": skill_text},
            )
            unsub = _install_session_otel_bridge(session)
            try:
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

        # Response text as span event (truncated)
        event_text = text[:_MAX_RESPONSE_EVENT_BYTES]
        span.add_event("gen_ai.response", {"gen_ai.response.text": event_text})

        # Token usage, if exposed by the SDK
        data = getattr(response_event, "data", None) if response_event else None
        usage = getattr(data, "usage", None) if data is not None else None
        if usage is not None:
            in_tok = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None)
            out_tok = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None)
            if in_tok is not None:
                span.set_attribute("gen_ai.usage.input_tokens", int(in_tok))
            if out_tok is not None:
                span.set_attribute("gen_ai.usage.output_tokens", int(out_tok))

    # Extract the first JSON object/array from the response text
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
