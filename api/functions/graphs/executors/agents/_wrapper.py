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

The agent identity is "finance-agent" universally; specialisation comes from
the loaded skill, matching the spec's "specialisation via skills, not via
separate agents" pattern.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

from copilot import CopilotClient
from copilot.client import SubprocessConfig
from copilot.session import PermissionHandler
from copilot.generated.session_events import SessionEventType
from copilot.tools import Tool
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


_SKILLS_DIR = Path(__file__).resolve().parents[4] / "server" / "skills"

# Public alias — agents reference this rather than recomputing parents[4]
# magic with their own path arithmetic.
SKILLS_DIR = _SKILLS_DIR
_tracer = trace.get_tracer("wpp.agents.finance")


def _load_skill(skill_dir: Path) -> str:
    """Read the SKILL.md body for a skill (skill_dir is the skill's own
    directory, e.g. .../skills/rag-classifier/)."""
    return (skill_dir / "SKILL.md").read_text(encoding="utf-8")

# 4KB cap on response-text span-event payload (OTEL event attr size safety).
_MAX_RESPONSE_EVENT_BYTES = 4096


def _gh_token() -> str:
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


def _install_session_otel_bridge(session) -> callable:
    """Bridge GHCP session events -> OTEL child spans. Returns unsubscribe callable.

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


def _extract_json(text: str) -> dict:
    """Extract the first JSON object/array from the response text."""
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
) -> dict:
    """Run a finance-agent ephemeral session and return the parsed JSON response.

    Args:
        prompt: The user prompt — per-call context.
        tools: SDK-native tools (each created via `@define_tool`) registered on
            the session via `tools=[...]`. The model invokes them autonomously.
        skill_dir: Path to the skill's directory (containing SKILL.md). The
            SKILL.md body is read and appended to the session's system message
            so the model strongly follows the role + output schema. The
            directory is also passed to the SDK's `skill_directories` so the
            skill is discoverable.
        skill_label: Optional OTEL span tag.
        model: Model id (default `gpt-4.1`).
        attachments: Optional multimodal attachments for `send_and_wait`.
    """
    tools = tools or []
    skill_text = _load_skill(skill_dir) if skill_dir else None

    with _tracer.start_as_current_span("gen_ai.generate_content") as span:
        span.set_attribute("gen_ai.system", "github_copilot")
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.agent.name", "finance-agent")
        if skill_label:
            span.set_attribute("wpp.skill", skill_label)
        span.set_attribute("wpp.tools.count", len(tools))
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
            unsub = _install_session_otel_bridge(session)
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

    return _extract_json(text)


# Backwards-compatible alias for legacy agents that pass a skill_name string.
# Resolves the name (e.g. "rag_classifier" or "rag-classifier") to the
# corresponding skill directory under api/server/skills/. New code should call
# run_agent_session(skill_dir=..., tools=[...]) directly.
async def run_agent_skill(
    skill_name: str,
    prompt: str,
    model: str = "gpt-4.1",
    attachments: list[dict] | None = None,
) -> dict:
    """Deprecated alias — prefer `run_agent_session(skill_dir=..., tools=[...])`.

    Resolves a skill name to a directory under api/server/skills/, allowing
    underscore→hyphen normalisation (so legacy callers using
    "anomaly_flagger" still find the "anomaly-flagger/" directory).
    """
    candidate = _SKILLS_DIR / skill_name
    if not candidate.is_dir():
        candidate = _SKILLS_DIR / skill_name.replace("_", "-")
    return await run_agent_session(
        prompt=prompt,
        skill_dir=candidate if candidate.is_dir() else None,
        skill_label=skill_name,
        model=model,
        attachments=attachments,
    )
